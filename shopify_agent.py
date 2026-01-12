import os
import json
import re
import math
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from collections import Counter, defaultdict
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Iterable, List, Tuple

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool
from livekit.plugins import (
    openai,
    noise_cancellation,
)

from shopify_service import ShopifyService
from tools import ShopifyTools, SHOPIFY_TOOLS

load_dotenv(".env.local")

# -----------------------------
# RAG / Knowledge Base (local)
# -----------------------------

RAG_DIR = Path(__file__).resolve().parent / "RAG"

# Minimal bilingual keyword hints (ZH -> EN) to help retrieve English KB with Chinese queries.
ZH_EN_KEYWORDS: Dict[str, str] = {
    "退款": "refund",
    "退货": "return",
    "退换": "return exchange",
    "换货": "exchange",
    "政策": "policy",
    "保修": "warranty",
    "质保": "warranty",
    "运费": "shipping",
    "物流": "shipping",
    "配送": "shipping",
    "发货": "ship",
    "免运费": "free shipping",
    "国际": "international",
    "礼品卡": "gift card",
    "奖励": "rewards",
    "积分": "points rewards",
    "RMA": "RMA",
}


def _expand_query_for_kb(query: str) -> str:
    """
    Expand query with simple ZH->EN keyword hints so Chinese queries can retrieve English KB.
    """
    q = (query or "").strip()
    if not q:
        return q
    if re.search(r"[\u4e00-\u9fff]", q):
        extra: List[str] = []
        for zh, en in ZH_EN_KEYWORDS.items():
            if zh in q:
                extra.append(en)
        if extra:
            return q + " " + " ".join(extra)
    return q


def _tokenize(text: str) -> List[str]:
    """
    Dependency-free tokenizer that works for both English and CJK text.
    - English/number tokens: [a-zA-Z0-9_]+
    - CJK tokens: contiguous Han characters [\u4e00-\u9fff]+
    """
    if not text:
        return []
    text = text.lower()
    return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text)


def _extract_text_from_docx(docx_path: Path) -> str:
    """
    Extract plain text from a .docx using only stdlib (docx is a zip of XML).
    """
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            xml_bytes = zf.read("word/document.xml")
    except Exception as e:
        return f"[DOCX parse failed: {docx_path.name}] {e}"

    try:
        root = ET.fromstring(xml_bytes)
        # Prefer deriving the namespace URI from the document itself (fully local),
        # and only fall back to the common WordprocessingML namespace if missing.
        m = re.match(r"^\{([^}]+)\}", root.tag or "")
        w_ns_uri = m.group(1) if m else "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ns = {"w": w_ns_uri}
        paragraphs: List[str] = []
        for p in root.findall(".//w:p", ns):
            texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
            if texts:
                paragraphs.append("".join(texts).strip())
        return "\n".join([p for p in paragraphs if p])
    except Exception as e:
        return f"[DOCX XML parse failed: {docx_path.name}] {e}"


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[Read failed: {path.name}] {e}"


def _iter_rag_files(rag_dir: Path) -> Iterable[Path]:
    if not rag_dir.exists() or not rag_dir.is_dir():
        return []
    exts = {".txt", ".md", ".markdown", ".docx"}
    return [p for p in rag_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]


@dataclass(frozen=True)
class KBChunk:
    source: str
    chunk_id: int
    text: str


class LocalKnowledgeBase:
    """
    A tiny, dependency-free RAG knowledge base:
    - Loads documents from ./RAG
    - Splits into text chunks
    - Uses a simple TF-IDF scoring for retrieval
    """

    def __init__(self, rag_dir: Path, chunk_size: int = 900, chunk_overlap: int = 150) -> None:
        self.rag_dir = rag_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.chunks: List[KBChunk] = []
        self._chunk_tfs: List[Counter[str]] = []
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}

        self._build()

    def _load_doc(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".docx":
            return _extract_text_from_docx(path)
        return _read_text_file(path)

    def _chunk_text(self, text: str) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []
        # If the document looks like FAQ (Q:/A:), chunk by Q/A to improve retrieval precision.
        if re.search(r"(?mi)^\s*Q\s*[:：]", text):
            lines = text.splitlines()
            chunks: List[str] = []
            current_heading: str = ""
            cur: List[str] = []

            for raw in lines:
                s = raw.strip()
                if not s:
                    continue

                is_q = re.match(r"(?i)^Q\s*[:：]", s) is not None
                is_a = re.match(r"(?i)^A\s*[:：]", s) is not None

                if is_q:
                    if cur:
                        chunks.append("\n".join(cur).strip())
                        cur = []
                    if current_heading:
                        cur.append(current_heading)
                    cur.append(s)
                    continue

                if is_a:
                    if not cur and current_heading:
                        cur.append(current_heading)
                    cur.append(s)
                    continue

                # Non Q/A line: could be a section header ("Products", "Shipping and Returns")
                # or a continuation line within an answer.
                if cur:
                    cur.append(s)
                else:
                    current_heading = s

            if cur:
                chunks.append("\n".join(cur).strip())

            # If we got reasonable chunks, return them (no need to pack).
            if chunks:
                return chunks

        # Fallback: paragraph-ish segmentation, then pack to chunk_size.
        parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        packed: List[str] = []
        buf = ""
        for part in parts:
            if not buf:
                buf = part
                continue
            if len(buf) + 2 + len(part) <= self.chunk_size:
                buf = buf + "\n\n" + part
            else:
                packed.append(buf)
                # overlap: keep last N chars
                if self.chunk_overlap > 0 and len(buf) > self.chunk_overlap:
                    buf = buf[-self.chunk_overlap :] + "\n\n" + part
                else:
                    buf = part
        if buf:
            packed.append(buf)
        return packed

    def _build(self) -> None:
        files = list(_iter_rag_files(self.rag_dir))
        all_chunks: List[KBChunk] = []
        for f in files:
            raw = self._load_doc(f)
            for i, chunk_text in enumerate(self._chunk_text(raw)):
                all_chunks.append(KBChunk(source=f.name, chunk_id=i, text=chunk_text))

        self.chunks = all_chunks
        self._chunk_tfs = [Counter(_tokenize(c.text)) for c in self.chunks]

        # document frequency (by chunk)
        df: Dict[str, int] = defaultdict(int)
        for tf in self._chunk_tfs:
            for term in tf.keys():
                df[term] += 1
        self._df = dict(df)

        n = max(len(self.chunks), 1)
        self._idf = {t: (math.log((n + 1) / (df_t + 1)) + 1.0) for t, df_t in self._df.items()}

    def search(self, query: str, top_k: int = 3) -> List[Tuple[KBChunk, float]]:
        q_terms = _tokenize(query or "")
        if not q_terms or not self.chunks:
            return []

        q_tf = Counter(q_terms)
        q_weights = {t: (q_tf[t] * self._idf.get(t, 0.0)) for t in q_tf.keys()}

        scored: List[Tuple[int, float]] = []
        for idx, tf in enumerate(self._chunk_tfs):
            score = 0.0
            for t, qw in q_weights.items():
                if qw <= 0:
                    continue
                if t in tf:
                    score += qw * (tf[t] * self._idf.get(t, 0.0))
            if score > 0:
                scored.append((idx, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results: List[Tuple[KBChunk, float]] = []
        for idx, score in scored[: max(1, top_k)]:
            results.append((self.chunks[idx], score))
        return results


# Build KB at import time so tools can use it immediately.
knowledge_base = LocalKnowledgeBase(RAG_DIR)

# 初始化 Shopify 服务
shopify_service = ShopifyService(
    store_name=os.getenv("SHOPIFY_STORE_NAME", ""),
    access_token=os.getenv("SHOPIFY_ACCESS_TOKEN", "")
)

shopify_tools = ShopifyTools(shopify_service)

class ShopifyAssistant(Agent):
    """Shopify 订单查询助手"""
    
    def __init__(self) -> None:
        instructions = """You are a professional Shopify order assistant. You can call Shopify APIs to look up order information, and you also have a local document knowledge base (the `RAG/` folder) for company/product FAQs and policies.

You can help users with:
- Get order details by order number (use `get_order_by_number`)
- Search orders by customer email (use `search_orders_by_email`)
- List recent orders (use `get_recent_orders`)

When the user asks about orders, you must:
1) Identify the intent (order number vs email vs recent orders)
2) Call the appropriate tool to query Shopify
3) Explain the results clearly in English

When the user asks about product/company information (FAQ, policies, warranty, returns, shipping, etc.), you must:
1) **Call `search_knowledge` first** to retrieve relevant passages from `RAG/`
2) Answer based on the retrieved passages and **cite the source file name** in your answer

Important:
- If the user mentions an order number (e.g. "1001" or "#1001"), call `get_order_by_number`
- If the user mentions an email address, call `search_orders_by_email`
- If the user says "recent orders" / "latest orders", call `get_recent_orders`
- If the question is about product/company policy/FAQ/warranty/returns/shipping, **call `search_knowledge` first**

Always reply in English."""
        
        super().__init__(instructions=instructions)

    @function_tool()
    async def search_knowledge(self, query: str, top_k: int = 3) -> str:
        """Retrieve the most relevant passages from the local `RAG/` knowledge base."""
        print(f"[工具调用] search_knowledge: query={query!r}, top_k={top_k}")
        try:
            expanded_query = _expand_query_for_kb(query)
            results = knowledge_base.search(query=expanded_query, top_k=top_k)
            if not results:
                return "No relevant content found in the knowledge base. Try different keywords or clarify what you’re looking for."

            lines: List[str] = []
            for chunk, score in results:
                preview = chunk.text.strip()
                # keep output compact (tool return can be large otherwise)
                if len(preview) > 1200:
                    preview = preview[:1200] + "..."
                lines.append(
                    f"[来源: {chunk.source} | 片段: {chunk.chunk_id} | score={score:.3f}]\n{preview}"
                )
            return "\n\n---\n\n".join(lines)
        except Exception as e:
            return f"Knowledge base search error: {str(e)}"

    @function_tool()
    async def kb_status(self) -> str:
        """Return current KB load status (files, chunk count, preview) for debugging."""
        try:
            files = [p.name for p in _iter_rag_files(RAG_DIR)]
            chunk_count = len(knowledge_base.chunks)
            preview = ""
            if knowledge_base.chunks:
                c0 = knowledge_base.chunks[0]
                preview = c0.text[:300].replace("\n", " ")
            return (
                f"RAG_DIR: {str(RAG_DIR)}\n"
                f"Files: {files}\n"
                f"Chunks: {chunk_count}\n"
                f"FirstChunk: {knowledge_base.chunks[0].source if knowledge_base.chunks else None}\n"
                f"Preview: {preview}"
            )
        except Exception as e:
            return f"kb_status error: {str(e)}"
    
    @function_tool()
    async def get_order_by_number(self, order_number: str) -> str:
        """根据订单号查询订单信息。订单号可以是数字，如 '1001' 或 '#1001'"""
        print(f"[工具调用] get_order_by_number: {order_number}")
        try:
            result = shopify_tools.get_order_by_number(order_number)
            print(f"[工具调用] 结果: {result[:100]}...")  # 只打印前100个字符
            return result
        except Exception as e:
            error_msg = f"Error while looking up the order: {str(e)}"
            print(f"[工具调用] 错误: {error_msg}")
            return error_msg
    
    @function_tool()
    async def get_order_by_id(self, order_id: str) -> str:
        """根据订单 ID 查询订单信息。订单 ID 是 Shopify 系统的唯一标识符"""
        print(f"[工具调用] get_order_by_id: {order_id}")
        try:
            result = shopify_tools.get_order_by_id(order_id)
            return result
        except Exception as e:
            return f"Error while looking up the order: {str(e)}"
    
    @function_tool()
    async def search_orders_by_email(self, email: str, limit: int = 5) -> str:
        """根据客户邮箱地址搜索该客户的所有订单"""
        print(f"[工具调用] search_orders_by_email: {email}, limit={limit}")
        try:
            result = shopify_tools.search_orders_by_email(email, limit)
            return result
        except Exception as e:
            return f"Error while searching orders: {str(e)}"
    
    @function_tool()
    async def get_recent_orders(self, limit: int = 5) -> str:
        """获取最近的订单列表。limit 参数指定返回的订单数量"""
        print(f"[工具调用] get_recent_orders: limit={limit}")
        try:
            result = shopify_tools.get_recent_orders(limit)
            return result
        except Exception as e:
            return f"Error while fetching recent orders: {str(e)}"
    
    # 注意：使用 @function_tool 装饰器时，不需要手动实现 on_tool_call
    # 工具调用会自动处理

server = AgentServer()

@server.rtc_session()
async def shopify_agent(ctx: agents.JobContext):
    """Shopify 订单查询 Agent"""
    
    # 使用支持工具调用的 OpenAI 模型（GPT-4 或 GPT-3.5-turbo）
    # 注意：使用 Chat 模型需要配合 STT 和 TTS 来实现完整的语音交互
    
    # 配置 STT（语音转文本）
    # OpenAI STT 在 use_realtime=True 时支持流式转写（并内置 server_vad 进行断句）
    stt_adapter = openai.STT(
        language="en",
        use_realtime=True,
    )
    
    # 配置支持工具调用的 LLM（使用模型 ID 字符串）
    llm = "openai/gpt-4o"  # 使用 GPT-4o，支持工具调用
    # 也可以使用 "openai/gpt-4-turbo" 或 "openai/gpt-3.5-turbo-1106"
    
    # 配置 TTS（文本转语音）
    tts = openai.TTS(
        voice="alloy",  # 可选: alloy, echo, fable, onyx, nova, shimmer
    )
    
    # 创建支持工具调用的 session
    # Agent 类中使用 @function_tool 装饰器的方法会自动注册为工具
    session = AgentSession(
        stt=stt_adapter,  # 使用 StreamAdapter 包装的 STT
        llm=llm,
        tts=tts,
    )
    
    assistant = ShopifyAssistant()
    
    await session.start(
        room=ctx.room,
        agent=assistant,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony() 
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP 
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )
    
    # 工具调用会自动通过 @function_tool 装饰器处理
    # 不需要手动实现 on_tool_call 方法
    
    # 添加调试信息
    print("[Agent] Session 已启动")
    print(f"[Agent] 使用的模型: {llm}")
    print(f"[Agent] 工具函数: search_knowledge, get_order_by_number, get_order_by_id, search_orders_by_email, get_recent_orders")
    
    # 生成欢迎语
    await session.generate_reply(
        instructions="Greet the user in English. Introduce yourself as a Shopify order assistant that can look up orders (by order number, customer email, or recent orders) and also answer product/company FAQ and policy questions by referencing the local knowledge base in the `RAG/` folder."
    )
    
    print("[Agent] 欢迎语已发送")

if __name__ == "__main__":
    agents.cli.run_app(server)
