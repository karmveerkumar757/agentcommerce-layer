# ⚡ AgentCommerce Layer
### Making a Razorpay Merchant Transactable by an AI Buyer — End to End
**Razorpay Buildathon — Track 01: AI Growth & Agentic Commerce**

---

## 🌟 Executive Summary

AgentCommerce Layer is an autonomous, policy-gated commerce infrastructure that sits in front of a Razorpay merchant's product catalog and checkout pipeline. It makes the merchant **agent-readable and agent-transactable** — allowing both human consumers and external AI buying agents to discover products, evaluate specifications, manage carts, and execute payments via bounded tool execution and Razorpay test-mode payment rails.

Conforms to emerging open agentic commerce patterns (**Unified Agent Protocol / ACP / AP2**).

---

## 🏗️ Architecture: 7-Layer Tree Model

```
                    [ Leaves: Interfaces ]
     Buyer Chat Widget       Autonomous Buyer Simulator      Merchant Dashboard
  (app/static/index.html)   (external_agent_simulator)      (dashboard/app.py)
              \                       |                       /
               -----------------------------------------------
                                      |
                     [ Layer 6: Interoperability Endpoint ]
                     - GET /.well-known/agent-commerce.json
                     - POST /interop/execute
                                      |
                     [ Layer 5: Trust & Verification Gate ]
                     - Policy Engine (Max cart cap, velocity, item limits)
                     - Immutable Audit Logging
                                      |
                     [ Layer 4: Checkout Orchestration ]
                     - Razorpay Test Mode Order API
                     - Cart state persistence
                                      |
                     [ Layer 3: Conversational ReAct Agent ]
                     - Gemini 3.6 Flash + LangGraph ReAct Loop
                     - Live Thought/Action/Observation Traces
                                      |
                     [ Layer 2: Typed Tool Schemas ]
                     - search_catalog, get_product_details, add_to_cart, checkout
                                      |
                     [ Layer 1: Catalog Embedding (Roots) ]
                     - ChromaDB vector store + all-MiniLM-L6-v2 embeddings
```

---

## 🚀 Quickstart Guide

### 1. Environment Setup
Create and activate virtual environment, then install dependencies:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pytest httpx
```

### 2. Configure Environment (`.env`)
Create or edit `.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
DATABASE_URL=sqlite:///./agentcommerce.db
CHROMA_PERSIST_DIR=./chroma_data
```

### 3. Initialize Catalog & Vector Database
Seeds 10 diverse products and default trust policies into SQLite and ChromaDB:
```bash
python scripts/init_db.py
```

### 4. Run the Servers
In **Terminal 1** (FastAPI Backend & Buyer Widget):
```bash
python -m uvicorn app.main:app --port 8000 --reload
```
- Buyer Chat Widget: [http://localhost:8000/static/index.html](http://localhost:8000/static/index.html)
- Discovery Manifest: [http://localhost:8000/.well-known/agent-commerce.json](http://localhost:8000/.well-known/agent-commerce.json)
- Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

In **Terminal 2** (Merchant Evaluation & Audit Dashboard):
```bash
streamlit run dashboard/app.py
```
- Dashboard UI: [http://localhost:8501](http://localhost:8501)

---

## 🧪 Live Demonstrations

### 1. External Autonomous AI Buyer Simulation
Demonstrates machine-to-machine commerce where an external AI agent discovers merchant capabilities via `/.well-known` and autonomously searches, adds to cart, and completes a purchase:
```bash
python external_agent_simulator/buyer_agent.py
```
**Features demonstrated:**
- **Scenario A**: Autonomous discovery and purchase of waterproof running shoes under ₹3000 (creates a real Razorpay test order).
- **Scenario B**: Deliberate policy enforcement demo where an order exceeding the ₹10,000 cart cap is blocked with an explainable reason.

### 2. Run Automated Verification Tests
Executes 5 comprehensive end-to-end integration tests:
```bash
python -m pytest tests/test_end_to_end.py -v
```

---

## 🛡️ Trust & Safety Policy Rules

Every transaction is bounded and verified before reaching Razorpay test APIs:
1. **Max Cart Value Cap**: Hard transaction limit of ₹10,000 to prevent runaway agent transactions.
2. **Item Hoarding Limit**: Maximum 10 units per item per order.
3. **Velocity Limit**: Maximum 5 checkout attempts per session per hour.
4. **Audit Trail**: Every tool call, agent action, and policy decision (`allowed` or `blocked`) is permanently logged in `audit_logs`.
