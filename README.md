# LiveKit Voice Agent

A LiveKit-based voice AI agent built with the LiveKit Agents framework and the OpenAI Realtime API.

## Features

- **Real-time voice conversations**: Low-latency speech-to-speech interactions via OpenAI Realtime
- **Noise cancellation**: Uses the noise-cancellation plugin
  - SIP participants: BVCTelephony
  - Others: BVC
- **Shopify order assistant**: Order lookups via Shopify API tools
- **Local RAG knowledge base**: Reads documents from the local `RAG/` folder to answer product/company FAQ & policy questions
- **English-first agent**: The assistant is configured to reply in English

## Requirements

- Python **>= 3.10**
- A LiveKit server (local or cloud)
- An OpenAI API key
- (For Shopify agent) Shopify Admin API access token with `read_orders`

## Install

This repo uses `pyproject.toml`. If you use `uv`:

```bash
uv sync
```

## Environment variables

Create a `.env.local` file:

```env
# LiveKit
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Shopify (required for shopify_agent.py)
SHOPIFY_STORE_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=your-shopify-access-token
```

## Run

Important: run with the project virtual environment so dependencies resolve correctly:

```bash
/root/Projects/livekit.io/livekit-voice-agent/.venv/bin/python agent.py dev
```

### Basic Agent

```bash
/root/Projects/livekit.io/livekit-voice-agent/.venv/bin/python agent.py dev
```

### Shopify Order + RAG Agent

```bash
/root/Projects/livekit.io/livekit-voice-agent/.venv/bin/python shopify_agent.py dev
```

## Local RAG Knowledge Base (`RAG/`)

The Shopify agent includes a lightweight, dependency-free local knowledge base:

- **Source**: files under the `RAG/` folder (supported: `.docx`, `.txt`, `.md`)
- **Retrieval**: the agent calls `search_knowledge` to retrieve relevant passages
- **Policy/FAQ answers**: for product/company policy questions (returns, shipping, warranty, etc.), the agent is instructed to **retrieve first**, then answer and **cite the source file name**

### Important: `RAG/` is not pushed to GitHub

`RAG/` is ignored via `.gitignore` and should be kept **locally** on your server/workstation.

If you deploy this project elsewhere, copy the `RAG/` folder as part of your deployment (do not rely on GitHub to contain those documents).

## Project structure

```text
livekit-voice-agent/
├── agent.py              # basic agent
├── shopify_agent.py      # Shopify order + local RAG agent
├── shopify_service.py    # Shopify API client wrapper
├── tools.py              # tool functions for order lookups
├── RAG/                  # local knowledge base (ignored by git)
├── pyproject.toml        # dependencies
└── .env.local            # environment variables (local only, ignored by git)
```

## Resources

- [LiveKit website](https://livekit.io/)
- [LiveKit docs](https://docs.livekit.io/intro/overview/)
- [LiveKit Agents examples](https://github.com/livekit/agents/blob/main/examples/voice_agents/basic_agent.py)
