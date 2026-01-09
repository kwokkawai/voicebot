import os
import json
import re
from dotenv import load_dotenv
from typing import Dict, Any, Optional

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool
from livekit.plugins import (
    openai,
    noise_cancellation,
)

from shopify_service import ShopifyService
from tools import ShopifyTools, SHOPIFY_TOOLS

load_dotenv(".env.local")

# 初始化 Shopify 服务
shopify_service = ShopifyService(
    store_name=os.getenv("SHOPIFY_STORE_NAME", ""),
    access_token=os.getenv("SHOPIFY_ACCESS_TOKEN", "")
)

shopify_tools = ShopifyTools(shopify_service)

class ShopifyAssistant(Agent):
    """Shopify 订单查询助手"""
    
    def __init__(self) -> None:
        instructions = """你是一个专业的 Shopify 订单查询助手，可以直接调用 Shopify API 查询订单信息。
你可以帮助用户查询订单信息，包括：
- 根据订单号查询订单详情（使用 get_order_by_number 函数）
- 根据客户邮箱搜索订单（使用 search_orders_by_email 函数）
- 查看最近的订单列表（使用 get_recent_orders 函数）

当用户询问订单信息时，你需要：
1. 理解用户的查询意图（订单号、邮箱或最近订单）
2. 自动调用相应的工具函数来查询 Shopify API
3. 用清晰、友好的中文向用户解释查询结果

重要提示：
- 如果用户提到订单号（如 "1001" 或 "#1001"），调用 get_order_by_number 函数
- 如果用户提到邮箱地址，调用 search_orders_by_email 函数
- 如果用户说"最近订单"或"最新订单"，调用 get_recent_orders 函数
- 查询结果会自动返回，你只需要用自然、友好的语言向用户解释

请用中文回复用户。"""
        
        super().__init__(instructions=instructions)
    
    @function_tool()
    async def get_order_by_number(self, order_number: str) -> str:
        """根据订单号查询订单信息。订单号可以是数字，如 '1001' 或 '#1001'"""
        print(f"[工具调用] get_order_by_number: {order_number}")
        try:
            result = shopify_tools.get_order_by_number(order_number)
            print(f"[工具调用] 结果: {result[:100]}...")  # 只打印前100个字符
            return result
        except Exception as e:
            error_msg = f"查询订单时出错: {str(e)}"
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
            return f"查询订单时出错: {str(e)}"
    
    @function_tool()
    async def search_orders_by_email(self, email: str, limit: int = 5) -> str:
        """根据客户邮箱地址搜索该客户的所有订单"""
        print(f"[工具调用] search_orders_by_email: {email}, limit={limit}")
        try:
            result = shopify_tools.search_orders_by_email(email, limit)
            return result
        except Exception as e:
            return f"查询订单时出错: {str(e)}"
    
    @function_tool()
    async def get_recent_orders(self, limit: int = 5) -> str:
        """获取最近的订单列表。limit 参数指定返回的订单数量"""
        print(f"[工具调用] get_recent_orders: limit={limit}")
        try:
            result = shopify_tools.get_recent_orders(limit)
            return result
        except Exception as e:
            return f"查询订单时出错: {str(e)}"
    
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
    print(f"[Agent] 工具函数: get_order_by_number, get_order_by_id, search_orders_by_email, get_recent_orders")
    
    # 生成欢迎语
    await session.generate_reply(
        instructions="用中文问候用户，介绍你是 Shopify 订单查询助手，可以帮用户查询订单信息。可以说：'你好，我是 Shopify 订单查询助手，我可以帮你查询订单信息。你可以通过订单号、客户邮箱或查看最近的订单来查询。请直接告诉我订单号、邮箱或说查看最近订单。'"
    )
    
    print("[Agent] 欢迎语已发送")

if __name__ == "__main__":
    agents.cli.run_app(server)
