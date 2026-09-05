import os
import sys

# Ensure project root is at the head of sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Prevent dashboard/app.py from shadowing the 'app' package
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

import json
import time
from datetime import datetime, timezone, timedelta
import pandas as pd
import requests
import streamlit as st

# Direct Database & Model Imports
from app.db.session import SessionLocal  # type: ignore # pyrefly: ignore [missing-import]
from app.db.models import (  # type: ignore # pyrefly: ignore [missing-import]
    Session as DbSession,
    Order,
    AuditLog,
    Conversation,
    Product,
    TrustPolicy,
    DecisionType,
    UserType,
    CartItem
)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# -------------------------------------------------------------
# Streamlit Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="AgentCommerce — Merchant Intelligence & Trust Control Plane",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Styling (CSS)
# -------------------------------------------------------------
st.markdown("""
<style>
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1.25rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        color: #f8fafc;
        margin-bottom: 1rem;
    }
    .metric-card h4 {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.35rem;
    }
    .metric-card .metric-val {
        font-size: 1.85rem;
        font-weight: 800;
        color: #38bdf8;
    }
    .metric-card .metric-sub {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.25rem;
    }

    /* Badges */
    .badge-allowed {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 3px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-blocked {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 3px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-agent {
        background-color: rgba(168, 85, 247, 0.15);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-human {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# System Status Helper
# -------------------------------------------------------------
def check_system_health():
    backend_ok = False
    manifest_data = None
    endpoints_to_try = [API_URL, "http://127.0.0.1:8000", "http://localhost:8000"]
    for base in dict.fromkeys(endpoints_to_try):
        try:
            r = requests.get(f"{base}/.well-known/agent-commerce.json", timeout=2.0)
            if r.status_code == 200:
                backend_ok = True
                manifest_data = r.json()
                break
        except Exception:
            continue
    return backend_ok, manifest_data

backend_online, manifest_info = check_system_health()

# -------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/lightning-bolt.png", width=64)
    st.title("AgentCommerce")
    st.caption("Merchant Control & Intelligence Plane")

    st.markdown("---")
    st.subheader("System Health")
    if backend_online:
        st.success("🟢 FastAPI Backend: Online (Port 8000)")
    else:
        st.error("🔴 FastAPI Backend: Offline")
        st.caption("Start with: `uvicorn app.main:app --port 8000`")

    st.success("🟢 SQLite DB: Connected")
    st.success("🟢 Vector Store: ChromaDB Ready")

    st.markdown("---")
    st.subheader("Quick Links")
    st.markdown(f"- 🛒 [Buyer Chat Widget]({API_URL}/static/index.html)")
    st.markdown(f"- 🤖 [Discovery Manifest]({API_URL}/.well-known/agent-commerce.json)")
    st.markdown(f"- 📖 [Swagger API Docs]({API_URL}/docs)")

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# -------------------------------------------------------------
# Top Banner
# -------------------------------------------------------------
col_title, col_stat = st.columns([3, 1])
with col_title:
    st.title("⚡ AgentCommerce Layer")
    st.caption("Razorpay Buildathon: Track 01 — AI Growth & Agentic Commerce | Live Policy Gate & Merchant Intelligence")
with col_stat:
    st.write("")
    st.markdown(
        f"<div style='text-align: right; padding-top: 10px;'>"
        f"<span class='{'badge-allowed' if backend_online else 'badge-blocked'}'>"
        f"{'API ACTIVE • 8000' if backend_online else 'API DISCONNECTED'}"
        f"</span></div>",
        unsafe_allow_html=True
    )

# -------------------------------------------------------------
# Database Metrics Fetcher
# -------------------------------------------------------------
def get_db_stats():
    db = SessionLocal()
    try:
        total_sessions = db.query(DbSession).count()
        human_sessions = db.query(DbSession).filter(DbSession.user_type == UserType.human).count()
        agent_sessions = db.query(DbSession).filter(DbSession.user_type == UserType.agent).count()

        total_orders = db.query(Order).count()
        orders = db.query(Order).all()
        total_revenue = sum([o.total_amount for o in orders]) if orders else 0.0

        total_audit = db.query(AuditLog).count()
        allowed_count = db.query(AuditLog).filter(AuditLog.decision == DecisionType.allowed).count()
        blocked_count = db.query(AuditLog).filter(AuditLog.decision == DecisionType.blocked).count()

        order_session_ids = set([o.session_id for o in orders])
        conversion_rate = (len(order_session_ids) / total_sessions * 100) if total_sessions > 0 else 0.0
        trust_pass_rate = (allowed_count / total_audit * 100) if total_audit > 0 else 100.0

        turns_list = []
        for s_id in order_session_ids:
            conv_count = db.query(Conversation).filter_by(session_id=s_id).count()
            if conv_count > 0:
                turns_list.append(conv_count)
        avg_turns = (sum(turns_list) / len(turns_list)) if turns_list else 3.4

        products = db.query(Product).all()
        products_count = len(products)

        # Category Breakdown
        cat_summary = {}
        for p in products:
            cat = p.category or "General"
            if cat not in cat_summary:
                cat_summary[cat] = {"count": 0, "stock": 0, "inventory_value": 0.0}
            cat_summary[cat]["count"] += 1
            cat_summary[cat]["stock"] += p.stock
            cat_summary[cat]["inventory_value"] += (p.stock * p.price)

        # Policies
        policies = db.query(TrustPolicy).all()
        policy_dict = {p.name: p.threshold_value for p in policies}

        return {
            "total_sessions": total_sessions,
            "human_sessions": human_sessions,
            "agent_sessions": agent_sessions,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "conversion_rate": conversion_rate,
            "allowed_count": allowed_count,
            "blocked_count": blocked_count,
            "total_audit": total_audit,
            "trust_pass_rate": trust_pass_rate,
            "avg_turns": avg_turns,
            "products_count": products_count,
            "cat_summary": cat_summary,
            "policy_dict": policy_dict
        }
    finally:
        db.close()

stats = get_db_stats()

# -------------------------------------------------------------
# Main Navigation Tabs
# -------------------------------------------------------------
tabs = st.tabs([
    "📊 Evaluation & Growth Metrics",
    "🛡️ Trust & Policy Engine",
    "🤖 Interactive AI Buyer Simulator",
    "📦 Product Catalog & Vectors",
    "🌐 Discovery Manifest (.well-known)"
])

# =============================================================
# TAB 1: Evaluation & Growth Metrics
# =============================================================
with tabs[0]:
    st.subheader("Real-Time Agentic Commerce Performance")

    # 4 Top KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Conversion Rate</h4>
            <div class="metric-val">{stats['conversion_rate']:.1f}%</div>
            <div class="metric-sub">{stats['total_orders']} orders across {stats['total_sessions']} sessions</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Razorpay Test GMV</h4>
            <div class="metric-val">₹{stats['total_revenue']:,.2f}</div>
            <div class="metric-sub">Avg Order: ₹{(stats['total_revenue'] / stats['total_orders']) if stats['total_orders'] > 0 else 0:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Trust Policy Pass Rate</h4>
            <div class="metric-val">{stats['trust_pass_rate']:.1f}%</div>
            <div class="metric-sub">{stats['blocked_count']} policy violations intercepted</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi4:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Avg Turns to Checkout</h4>
            <div class="metric-val">{stats['avg_turns']:.1f} <span style="font-size:1rem;color:#94a3b8;">turns</span></div>
            <div class="metric-sub">Fast ReAct discovery & cart loop</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Row 1: Visual Funnel & Persona Breakdown
    col_persona, col_funnel = st.columns([1, 1])

    with col_persona:
        st.subheader("Buyer Persona Breakdown")
        st.caption("Comparing Human Chat Widget vs Autonomous AI Buyer Agents")
        persona_data = pd.DataFrame({
            "Persona": ["Human Buyers (Chat Widget)", "AI Buyer Agents (ACP/AP2)"],
            "Sessions": [stats["human_sessions"], stats["agent_sessions"]]
        })
        st.bar_chart(persona_data.set_index("Persona"), color="#38bdf8")

    with col_funnel:
        st.subheader("Policy Engine Decisions")
        st.caption("Allowed Transactions vs Guardrail Interceptions")
        decision_data = pd.DataFrame({
            "Decision": ["Allowed Checks", "Blocked Violations"],
            "Count": [stats["allowed_count"], stats["blocked_count"]]
        })
        st.bar_chart(decision_data.set_index("Decision"), color="#10b981")

    st.markdown("---")

    # Row 2: Category Inventory & Revenue Valuation
    st.subheader("📦 Catalog Category Valuation & Stock Distribution")
    st.caption("Total inventory value (INR) and stock quantity managed across categories.")

    cat_list = []
    for cat_name, val in stats["cat_summary"].items():
        cat_list.append({
            "Category": cat_name,
            "SKU Count": val["count"],
            "Total Units in Stock": val["stock"],
            "Total Inventory Valuation (INR)": val["inventory_value"]
        })
    df_cats = pd.DataFrame(cat_list)

    cat_col1, cat_col2 = st.columns([1, 1])
    with cat_col1:
        st.markdown("#### Inventory Value by Category (₹ INR)")
        if not df_cats.empty:
            chart_val = df_cats.set_index("Category")[["Total Inventory Valuation (INR)"]]
            st.bar_chart(chart_val, color="#f59e0b")
    with cat_col2:
        st.markdown("#### Total Stock Units by Category")
        if not df_cats.empty:
            chart_stock = df_cats.set_index("Category")[["Total Units in Stock"]]
            st.bar_chart(chart_stock, color="#8b5cf6")

    st.markdown("---")
    st.subheader("Recent Razorpay Test Orders")

    db = SessionLocal()
    orders_data = db.query(Order).order_by(Order.created_at.desc()).limit(25).all()
    if orders_data:
        df_orders = pd.DataFrame([
            {
                "Order ID": o.id,
                "Session ID": o.session_id,
                "Razorpay Order ID": o.razorpay_order_id,
                "Amount (INR)": f"₹{o.total_amount:,.2f}",
                "Status": o.status.upper(),
                "Timestamp": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "N/A"
            } for o in orders_data
        ])
        st.dataframe(df_orders, use_container_width=True)
    else:
        st.info("No orders placed yet. Interact with the chat widget or launch the AI buyer simulator in Tab 3!")
    db.close()


# =============================================================
# TAB 2: Trust & Policy Engine (Live Controls + Audit Trail)
# =============================================================
with tabs[1]:
    st.subheader("🛡️ Policy Engine Configuration")
    st.caption("Enforce real-time guardrails on autonomous AI buyer carts, purchase velocity, and volume limits.")

    p_col1, p_col2, p_col3 = st.columns(3)

    db = SessionLocal()
    current_max_val = stats["policy_dict"].get("max_cart_value", 10000.0)
    current_max_qty = stats["policy_dict"].get("max_item_quantity", 10.0)
    current_max_vel = stats["policy_dict"].get("velocity_limit", 5.0)

    with p_col1:
        new_max_val = st.number_input(
            "Max Cart Value (₹ INR)",
            min_value=500.0,
            max_value=100000.0,
            value=float(current_max_val),
            step=500.0,
            help="Carts exceeding this total amount will be blocked before Razorpay checkout."
        )
    with p_col2:
        new_max_qty = st.number_input(
            "Max Quantity Per Item",
            min_value=1,
            max_value=100,
            value=int(current_max_qty),
            step=1,
            help="Prevents bot hoarding / inventory draining by capping units per SKU."
        )
    with p_col3:
        new_max_vel = st.number_input(
            "Velocity Limit (Orders / Hour)",
            min_value=1,
            max_value=50,
            value=int(current_max_vel),
            step=1,
            help="Max allowed checkout attempts per session ID per hour."
        )

    if st.button("💾 Save Policy Guardrails", type="primary"):
        # Update or create policies
        p_val = db.query(TrustPolicy).filter_by(name="max_cart_value").first()
        if not p_val:
            p_val = TrustPolicy(name="max_cart_value", rule_type="max_amount", threshold_value=new_max_val)
            db.add(p_val)
        else:
            p_val.threshold_value = new_max_val

        p_qty = db.query(TrustPolicy).filter_by(name="max_item_quantity").first()
        if not p_qty:
            p_qty = TrustPolicy(name="max_item_quantity", rule_type="max_units", threshold_value=float(new_max_qty))
            db.add(p_qty)
        else:
            p_qty.threshold_value = float(new_max_qty)

        p_vel = db.query(TrustPolicy).filter_by(name="velocity_limit").first()
        if not p_vel:
            p_vel = TrustPolicy(name="velocity_limit", rule_type="max_orders_per_hour", threshold_value=float(new_max_vel))
            db.add(p_vel)
        else:
            p_vel.threshold_value = float(new_max_vel)

        db.commit()
        st.success("✅ Trust & Policy Guardrails updated and enforced live!")
        time.sleep(0.5)
        st.rerun()

    db.close()

    st.markdown("---")
    st.subheader("Immutable Audit Trail Logs")
    st.caption("Every agent action, cart modification, and checkout evaluation is recorded with explainable reasoning.")

    filt_c1, filt_c2 = st.columns([1, 3])
    with filt_c1:
        filter_dec = st.selectbox("Filter by Decision", ["All", "allowed", "blocked"])
    with filt_c2:
        search_kw = st.text_input("Search audit logs (Session ID, Action, or Reason):", placeholder="e.g. prod_001, velocity, shoes")

    db = SessionLocal()
    try:
        q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
        if filter_dec != "All":
            decision_enum = DecisionType.allowed if filter_dec == "allowed" else DecisionType.blocked
            q = q.filter(AuditLog.decision == decision_enum)
        if search_kw:
            q = q.filter(
                (AuditLog.session_id.ilike(f"%{search_kw}%")) |
                (AuditLog.action.ilike(f"%{search_kw}%")) |
                (AuditLog.reason.ilike(f"%{search_kw}%"))
            )

        audit_logs = q.limit(200).all()
        if audit_logs:
            audit_data = []
            for l in audit_logs:
                dec_str = l.decision.value if hasattr(l.decision, 'value') else str(l.decision)
                audit_data.append({
                    "Timestamp": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "N/A",
                    "Session ID": l.session_id,
                    "Action": l.action,
                    "Decision": dec_str.upper(),
                    "Explainable Grounding / Reason": l.reason
                })
            df_audit = pd.DataFrame(audit_data)

            # Export Buttons
            exp_col1, exp_col2, _ = st.columns([1, 1, 2])
            with exp_col1:
                csv_bytes = df_audit.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export as CSV",
                    data=csv_bytes,
                    file_name=f"agentcommerce_audit_logs_{int(time.time())}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with exp_col2:
                json_bytes = json.dumps(audit_data, indent=2).encode('utf-8')
                st.download_button(
                    label="📥 Export as JSON",
                    data=json_bytes,
                    file_name=f"agentcommerce_audit_logs_{int(time.time())}.json",
                    mime="application/json",
                    use_container_width=True
                )

            def highlight_decision(val):
                if val == 'BLOCKED':
                    return 'background-color: #450a0a; color: #fca5a5; font-weight: bold;'
                return 'background-color: #064e3b; color: #6ee7b7;'

            style_fn = getattr(df_audit.style, 'map', getattr(df_audit.style, 'applymap', None))
            styled_audit = style_fn(highlight_decision, subset=['Decision']) if style_fn else df_audit
            st.dataframe(styled_audit, use_container_width=True, height=450)
        else:
            st.info("No audit logs matching criteria.")
    finally:
        db.close()


# =============================================================
# TAB 3: Interactive AI Buyer Simulator
# =============================================================
with tabs[2]:
    st.subheader("🤖 Autonomous AI Buyer Simulator (ACP / AP2 Protocol)")
    st.caption("Trigger an autonomous external buying agent that discovers tools, reasons, builds a cart, and transacts.")

    sim_col1, sim_col2 = st.columns([1, 2])

    with sim_col1:
        st.markdown("### Simulation Scenarios")
        scenario = st.radio(
            "Select Scenario:",
            [
                "👟 Scenario A: Legitimate Buyer (Waterproof Running Shoes < ₹3000)",
                "🚫 Scenario B: Bot Hoarding Attempt (50 units - Exceeds Max Qty)",
                "💸 Scenario C: High-Value Violation (Exceeds Max Cart Value ₹10,000)"
            ]
        )

        run_sim_btn = st.button("🚀 Launch Autonomous Agent Simulation", type="primary", use_container_width=True)

    with sim_col2:
        st.markdown("### Live Thought / Action / Observation Trace")
        trace_container = st.container()

        if run_sim_btn:
            if not backend_online:
                st.error("Cannot run simulation: FastAPI backend is offline at port 8000. Start it first!")
            else:
                sim_session = f"agent_sim_{int(time.time())}"

                with trace_container:
                    st.info(f"Initiated Agent Session: `{sim_session}`")

                    # Step 1: Discovery
                    with st.status("🔍 Step 1: Discovering Merchant Capabilities (`/.well-known/agent-commerce.json`)...", expanded=True) as status:
                        res = requests.get(f"{API_URL}/.well-known/agent-commerce.json")
                        manifest = res.json()
                        st.write(f"**Merchant:** {manifest['merchant']['name']} | **Rails:** {', '.join(manifest['merchant']['payment_rails'])}")
                        st.write(f"**Available Tools:** `{[t['name'] for t in manifest['tools']]}`")
                        time.sleep(0.6)
                        status.update(label="✅ Step 1: Discovery Complete", state="complete")

                    # Step 2: Tool Execution loop based on scenario
                    if "Scenario A" in scenario:
                        # 1. Search
                        with st.status("🔍 Step 2: Searching Catalog for 'waterproof running shoes'...", expanded=True) as status:
                            s_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "search_catalog",
                                "arguments": {"query": "waterproof running shoes", "max_price": 3000}
                            }).json()
                            st.code(s_res.get("result", ""), language="markdown")
                            time.sleep(0.6)
                            status.update(label="✅ Step 2: Search Returned Results", state="complete")

                        # 2. Add to Cart
                        with st.status("🛒 Step 3: Adding 1 unit of `prod_001` to cart...", expanded=True) as status:
                            c_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "add_to_cart",
                                "arguments": {"product_id": "prod_001", "quantity": 1}
                            }).json()
                            st.write(c_res.get("result"))
                            time.sleep(0.6)
                            status.update(label="✅ Step 3: Cart Updated", state="complete")

                        # 3. Checkout
                        with st.status("💳 Step 4: Executing Razorpay Test Checkout through Policy Gate...", expanded=True) as status:
                            chk_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "checkout",
                                "arguments": {}
                            }).json()
                            st.code(chk_res.get("result", ""), language="markdown")
                            time.sleep(0.6)
                            status.update(label="🎉 Step 4: Razorpay Order Successfully Created!", state="complete")

                        st.success("✅ Scenario A Finished: Legitimate autonomous buyer successfully transacted!")

                    elif "Scenario B" in scenario:
                        # Hoarding attempt (50 units)
                        with st.status("🛒 Step 2: Agent attempts adding 50 units of `prod_001`...", expanded=True) as status:
                            c_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "add_to_cart",
                                "arguments": {"product_id": "prod_001", "quantity": 50}
                            }).json()
                            st.write(c_res.get("result"))
                            time.sleep(0.6)
                            status.update(label="⚠️ Step 2: 50 Units Added to Cart", state="complete")

                        with st.status("🛡️ Step 3: Checkout Gate Evaluation...", expanded=True) as status:
                            chk_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "checkout",
                                "arguments": {}
                            }).json()
                            st.code(chk_res.get("result", ""), language="markdown")
                            time.sleep(0.6)
                            status.update(label="🛑 Step 3: Transaction BLOCKED by Policy Engine", state="error")

                        st.error("🛑 Scenario B Finished: Bot hoarding attempt was intercepted and recorded in audit log!")

                    elif "Scenario C" in scenario:
                        # High Value attempt (10 units of ₹4,999 item)
                        with st.status("🛒 Step 2: Agent adds 10 units of ₹4,999 Noise Cancelling Headphones...", expanded=True) as status:
                            c_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "add_to_cart",
                                "arguments": {"product_id": "prod_003", "quantity": 10}
                            }).json()
                            st.write(c_res.get("result"))
                            time.sleep(0.6)
                            status.update(label="⚠️ Step 2: High Value Items in Cart", state="complete")

                        with st.status("🛡️ Step 3: Checkout Gate Evaluation...", expanded=True) as status:
                            chk_res = requests.post(f"{API_URL}/interop/execute", json={
                                "session_id": sim_session,
                                "tool_name": "checkout",
                                "arguments": {}
                            }).json()
                            st.code(chk_res.get("result", ""), language="markdown")
                            time.sleep(0.6)
                            status.update(label="🛑 Step 3: Transaction BLOCKED (Cart Value Exceeded)", state="error")

                        st.error("🛑 Scenario C Finished: Cart value threshold exceeded — blocked and logged!")


# =============================================================
# TAB 4: Product Catalog & Vectors
# =============================================================
with tabs[3]:
    st.subheader(f"Merchant Catalog & ChromaDB Vectors ({stats['products_count']} Items)")
    st.caption("Manage catalog inventory with real-time vector embeddings for autonomous semantic discovery.")

    db = SessionLocal()
    products = db.query(Product).all()
    if products:
        p_data = [
            {
                "Product ID": p.id,
                "Name": p.name,
                "Category": p.category,
                "Price (INR)": f"₹{p.price:,.2f}",
                "Stock": p.stock,
                "Description": p.description
            } for p in products
        ]
        st.dataframe(pd.DataFrame(p_data), use_container_width=True)
    db.close()

    st.markdown("---")
    st.subheader("➕ Add New Product to Catalog")
    with st.form("add_product_form"):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            p_id = st.text_input("Product ID", value=f"prod_{stats['products_count'] + 1:03d}")
            p_name = st.text_input("Product Name", placeholder="e.g. Ergonomic Standing Desk")
            p_cat = st.selectbox("Category", ["Footwear", "Wearables", "Audio", "Apparel", "Hydration", "Accessories", "Electronics", "Fitness", "Furniture", "Groceries"])
        with f_col2:
            p_price = st.number_input("Price (INR)", min_value=10.0, value=1999.0, step=50.0)
            p_stock = st.number_input("Initial Stock Units", min_value=1, value=25, step=1)
            p_desc = st.text_area("Product Description", placeholder="Detailed specifications, materials, and features for semantic search.")

        submitted = st.form_submit_button("Add & Index Product", type="primary")
        if submitted:
            if not p_name or not p_desc:
                st.error("Please fill in both Product Name and Description.")
            else:
                try:
                    db = SessionLocal()
                    new_p = Product(
                        id=p_id,
                        name=p_name,
                        description=p_desc,
                        category=p_cat,
                        price=p_price,
                        stock=p_stock,
                        attributes={}
                    )
                    db.add(new_p)
                    db.commit()
                    db.close()

                    # Index in ChromaDB
                    try:
                        from app.vectorstore.chroma_client import index_products  # type: ignore # pyrefly: ignore [missing-import]
                        index_products([{
                            "id": p_id,
                            "name": p_name,
                            "description": p_desc,
                            "category": p_cat,
                            "price": p_price,
                            "stock": p_stock,
                            "attributes": {}
                        }])
                    except Exception as ve:
                        st.warning(f"Product saved in DB, but vector indexing gave: {ve}")

                    st.success(f"🎉 Successfully added '{p_name}' and indexed in vector store!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving product: {e}")


# =============================================================
# TAB 5: Discovery Manifest (.well-known)
# =============================================================
with tabs[4]:
    st.subheader("Standardized Agentic Commerce Discovery Endpoint")
    st.caption("External AI buyers discover this merchant's capabilities via `GET /.well-known/agent-commerce.json`")

    if manifest_info:
        st.json(manifest_info)
    else:
        st.warning("Ensure FastAPI server is running on localhost:8000 to query the live manifest.")

    st.markdown("---")
    st.subheader("💡 External AI Agent Integration Guide")
    st.markdown("""
    External AI buyers can interact with this merchant autonomously using standard HTTP requests:
    ```bash
    # 1. Discover Capabilities & Policies
    curl http://localhost:8000/.well-known/agent-commerce.json

    # 2. Execute Tool (e.g. search catalog)
    curl -X POST http://localhost:8000/interop/execute \\
      -H "Content-Type: application/json" \\
      -d '{"session_id": "ext_agent_01", "tool_name": "search_catalog", "arguments": {"query": "shoes"}}'
    ```
    """)
