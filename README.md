# LiveKit Voice Agent

基于 LiveKit 的语音 AI 助手基础实现。这是一个使用 LiveKit Agents 框架和 OpenAI Realtime API 构建的语音对话 agent。

## 功能特性

- 🎙️ **实时语音对话**：使用 OpenAI Realtime API 实现流畅的语音交互
- 🔊 **噪声消除**：集成噪声消除插件，提升音频质量
  - 对 SIP 参与者使用 BVCTelephony 降噪
  - 对其他参与者使用 BVC 降噪
- 🤖 **智能助手**：基于 OpenAI 的对话式 AI 助手
- 🚀 **易于扩展**：简洁的代码结构，便于自定义和扩展

## 前置要求

- Python >= 3.10
- LiveKit 服务器（本地或云端）
- OpenAI API 密钥

## 安装

1. 克隆或下载此项目

2. 安装依赖（推荐使用 uv）：
```bash
uv sync
```

或使用 pip：
```bash
pip install -r requirements.txt
```

3. 配置环境变量

创建 `.env.local` 文件并添加以下配置：

```env
# LiveKit 配置
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# OpenAI 配置
OPENAI_API_KEY=your-openai-api-key

# Shopify 配置（仅在使用 shopify_agent.py 时需要）
SHOPIFY_STORE_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=your-shopify-access-token
```

**获取 Shopify 访问令牌：**

1. 在 Shopify 管理后台，进入"应用程序" > "开发应用程序"
2. 创建新的开发应用或使用现有应用
3. 确保应用具有 `read_orders` 权限
4. 获取访问令牌（Access Token）

## 使用方法

### 基础 Agent

运行基础 agent：

```bash
python agent.py dev
```

或使用 LiveKit CLI：

```bash
livekit-cli agent start agent.py
```

### Shopify 订单查询 Agent

运行 Shopify 订单查询 agent：

```bash
python shopify_agent.py dev
```

或使用 LiveKit CLI：

```bash
livekit-cli agent start shopify_agent.py
```

**使用 Shopify agent 前，需要配置 Shopify 相关环境变量：**

在 `.env.local` 文件中添加：

```env
SHOPIFY_STORE_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=your-shopify-access-token
```

**Shopify Agent 功能：**

- 📦 根据订单号查询订单详情
- 📧 根据客户邮箱搜索订单
- 📋 查看最近的订单列表
- 🗣️ 支持中文语音交互

**使用示例：**

用户可以通过语音说：
- "查询订单号 1001"
- "帮我看看订单 #1002 的详情"
- "查找邮箱是 customer@example.com 的所有订单"
- "显示最近的 5 个订单"

## 项目结构

```
livekit-voice-agent/
├── agent.py              # 基础 agent 实现
├── shopify_agent.py      # Shopify 订单查询 agent
├── shopify_service.py    # Shopify API 服务封装
├── tools.py              # Shopify 查询工具函数
├── pyproject.toml        # 项目配置和依赖
├── README.md             # 项目文档
└── .env.local            # 环境变量配置（需自行创建）
```

## 代码说明

### Assistant 类

基础的 AI 助手类，继承自 `Agent`，定义了助手的基本行为。

### AgentServer

LiveKit Agent 服务器，处理 RTC 会话和房间连接。

### 主要功能

- **实时语音交互**：使用 OpenAI Realtime Model（语音：coral）
- **噪声消除**：根据参与者类型自动选择合适的降噪算法
- **自动问候**：连接后自动生成问候语并开始对话

## 自定义

### 修改助手指令

在 `Assistant` 类的 `__init__` 方法中修改 `instructions` 参数：

```python
super().__init__(instructions="你的自定义指令")
```

### 修改语音模型

在 `my_agent` 函数中修改 `voice` 参数：

```python
llm=openai.realtime.RealtimeModel(
    voice="alloy"  # 可选: alloy, echo, fable, onyx, nova, shimmer, coral
)
```

### 修改问候语

在 `session.generate_reply` 中修改 `instructions` 参数：

```python
await session.generate_reply(
    instructions="你的自定义问候语"
)
```

## 相关资源

- [LiveKit 官网](https://livekit.io/)
- [LiveKit 文档](https://docs.livekit.io/intro/overview/)
- [LiveKit Agents 示例](https://github.com/livekit/agents/blob/main/examples/voice_agents/basic_agent.py)

## 许可证

本项目基于 LiveKit Agents 框架构建。
