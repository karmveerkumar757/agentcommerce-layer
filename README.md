# ⚡ AgentCommerce Layer
### Autonomous Policy-Gated Agentic Commerce Infrastructure on Razorpay Payment Rails
**Razorpay Buildathon — Track 01: AI Growth & Agentic Commerce**

[![CI - Test Suite](https://github.com/karmveerkumar757/agentcommerce-layer/actions/workflows/ci.yml/badge.svg)](https://github.com/karmveerkumar757/agentcommerce-layer/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-orange.svg)
![Razorpay Test Rails](https://img.shields.io/badge/Razorpay-Test%20Rails-528FF0.svg)
![AP2 Gated](https://img.shields.io/badge/Security-HMAC--SHA256-green.svg)

---

## 🌟 Executive Summary

**AgentCommerce Layer** is an autonomous, policy-gated commerce infrastructure that sits in front of a Razorpay merchant's product catalog and checkout pipeline. It makes the merchant **agent-readable, cryptographically verifiable, and agent-transactable** — allowing both human consumers and external AI buying agents to discover products, evaluate specifications, manage carts, and execute payments via bounded tool execution and Razorpay test-mode payment rails.

Conforms to emerging open agentic commerce patterns (**Unified Agent Protocol / ACP / AP2**).

---

## 🏗️ Architecture: 7-Layer Tree Model

```
                    [ Leaves: Interfaces ]
     Buyer Chat Widget       Autonomous Buyer Simulator      Merchant Dashboard
  (Live ReAct Stream UI)    (HMAC-SHA256 Authenticated)      (dashboard/app.py)
              \                       |                       /
               -----------------------------------------------
                                      |
                     [ Layer 6: Interoperability Endpoint ]
                     - GET /.well-known/agent-commerce.json
                     - POST /interop/execute (HMAC-SHA256 Gated)
                                      |
                     [ Layer 5: Trust & Verification Gate ]
                     - Policy Engine (Max cart cap, velocity, item limits)
                     - Immutable Audit Logging (1-Click CSV/JSON Export)
                                      |
                     [ Layer 4: Checkout Orchestration ]
                     - Razorpay Test Mode Order API
                     - Idempotency-Key Deduplication
                                      |
                     [ Layer 3: Conversational ReAct Agent ]
                     - Gemini 3.6 Flash + LangGraph ReAct Loop
                     - Real-Time Server-Sent Events (SSE) Stream
                                      |
                     [ Layer 2: Typed Tool Schemas ]
                     - search_catalog, get_product_details, add_to_cart, checkout
                                      |
                     [ Layer 1: Catalog Embedding (Roots) ]
                     - ChromaDB vector store + all-MiniLM-L6-v2 embeddings
```

---

## 🚀 Quickstart Guide

### Option A: Standard Local Setup

#### 1. Environment Setup
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest httpx
```

#### 2. Configure Environment (`.env`)
Copy the example environment file and add your credentials:
```powershell
cp .env.example .env
```
```ini
GEMINI_API_KEY=your_gemini_api_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
DATABASE_URL=sqlite:///./agentcommerce.db
CHROMA_PERSIST_DIR=./chroma_data
AP2_HMAC_SECRET=agentcommerce_secret_2026
```

#### 3. Initialize Catalog & Vector Database
Seeds 10 diverse products and default trust policies into SQLite and ChromaDB:
```powershell
python scripts/init_db.py
```

#### 4. Run the Servers
In **Terminal 1** (FastAPI Backend & Live ReAct Chat Widget):
```powershell
python -m uvicorn app.main:app --port 8000 --reload
```
- Buyer Chat Widget: [http://localhost:8000](http://localhost:8000)
- Discovery Manifest: [http://localhost:8000/.well-known/agent-commerce.json](http://localhost:8000/.well-known/agent-commerce.json)
- Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

In **Terminal 2** (Merchant Evaluation & Audit Dashboard):
```powershell
streamlit run dashboard/app.py
```
- Dashboard UI: [http://localhost:8501](http://localhost:8501)

---

### Option B: Docker Compose (1-Command Launch)
```bash
docker-compose up --build
```

---

## 🧪 Live Demonstrations & Testing

### 1. External Autonomous AI Buyer Simulation (HMAC-SHA256 Signed)
Demonstrates machine-to-machine commerce where an external AI agent discovers capabilities via `/.well-known`, cryptographically signs requests, and autonomously completes a purchase:
```powershell
python external_agent_simulator/buyer_agent.py
```
**Features demonstrated:**
- **Scenario A**: Authenticated autonomous discovery and purchase of waterproof running shoes under ₹3000 (creates a real Razorpay test order).
- **Scenario B**: Deliberate policy enforcement demo where bot hoarding (50 units) is blocked and audited.
- **Scenario C**: Cryptographic security verification where a tampered/unauthorized signature is rejected with `HTTP 401 Unauthorized`.

### 2. Automated Integration Test Suite (7/7 Passed)
```powershell
pytest -v
```

---

## 🛡️ Trust & Safety Policy Rules

Every transaction is bounded and verified before reaching Razorpay test APIs:
1. **Max Cart Value Cap**: Hard transaction limit (e.g. ₹10,000) to prevent runaway agent transactions.
2. **Item Hoarding Limit**: Maximum 10 units per item per order.
3. **Velocity Limit**: Maximum 5 checkout attempts per session per hour.
4. **Idempotency Guarantee**: `Idempotency-Key` prevents double charges on retried checkouts.
5. **Cryptographic AP2 Authentication**: HMAC-SHA256 request signing with replay protection (300s timestamp window).
6. **Immutable Audit Trail**: Every tool call, agent action, and policy decision (`allowed` or `blocked`) is logged with grounding explanations and exportable as CSV/JSON.

---

*Built with ❤️ for the Razorpay Buildathon — Track 01: AI Growth & Agentic Commerce.*
