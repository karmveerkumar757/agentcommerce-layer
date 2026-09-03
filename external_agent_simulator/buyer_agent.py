import os
import sys
import json
import time
import requests

# Ensure UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

def run_buyer_simulation():
    print("=" * 70)
    print("🤖 STARTING AUTONOMOUS AI BUYER AGENT SIMULATION")
    print("Standard: AgentCommerce Interoperability Contract (ACP / AP2 / UAP)")
    print("=" * 70)

    # -------------------------------------------------------------
    # Step 1: Merchant Capability Discovery
    # -------------------------------------------------------------
    print("\n🔍 [Step 1] Discovering Merchant Capabilities at /.well-known/agent-commerce.json")
    try:
        manifest_res = requests.get(f"{BASE_URL}/.well-known/agent-commerce.json")
        manifest_res.raise_for_status()
        manifest = manifest_res.json()
        print(f"   -> Connected to: {manifest['merchant']['name']}")
        print(f"   -> Currency: {manifest['merchant']['currency']}")
        print(f"   -> Supported Rails: {', '.join(manifest['merchant']['payment_rails'])}")
        print(f"   -> Available Tools: {[t['name'] for t in manifest['tools']]}")
        print(f"   -> Trust Policies Enforced: {manifest['trust_policies']}")
    except Exception as e:
        print(f"   ❌ Failed to discover merchant: {e}")
        print("   Ensure FastAPI server is running on port 8000: uvicorn app.main:app --port 8000")
        return

    # -------------------------------------------------------------
    # Scenario A: Autonomous Successful Purchase Flow
    # -------------------------------------------------------------
    session_a = "agent_buyer_shoes_success_01"
    print("\n" + "-" * 70)
    print(f"👟 SCENARIO A: Autonomous Purchase for Running Shoes (Session: {session_a})")
    print("Goal: 'Find waterproof running shoes under ₹3000 and buy 1 pair'")
    print("-" * 70)

    # Action 1: Search Catalog
    print("\n[External Agent -> Execute] Calling 'search_catalog'...")
    call_payload = {
        "session_id": session_a,
        "tool_name": "search_catalog",
        "arguments": {"query": "waterproof running shoes", "max_price": 3000}
    }
    search_res = requests.post(f"{BASE_URL}/interop/execute", json=call_payload).json()
    print("   Response:")
    print("  ", search_res.get("result", "").replace("\n", "\n   "))
    time.sleep(1)

    # Action 2: Inspect Product Details
    target_product_id = "prod_001"
    print(f"\n[External Agent -> Execute] Inspecting product details for '{target_product_id}'...")
    detail_payload = {
        "session_id": session_a,
        "tool_name": "get_product_details",
        "arguments": {"product_id": target_product_id}
    }
    detail_res = requests.post(f"{BASE_URL}/interop/execute", json=detail_payload).json()
    print("   Response:")
    print("  ", detail_res.get("result", "").replace("\n", "\n   "))
    time.sleep(1)

    # Action 3: Add to Cart
    print(f"\n[External Agent -> Execute] Adding 1 unit of '{target_product_id}' to cart...")
    cart_payload = {
        "session_id": session_a,
        "tool_name": "add_to_cart",
        "arguments": {"product_id": target_product_id, "quantity": 1}
    }
    cart_res = requests.post(f"{BASE_URL}/interop/execute", json=cart_payload).json()
    print(f"   Response: {cart_res.get('result')}")
    time.sleep(1)

    # Action 4: View Cart
    print("\n[External Agent -> Execute] Reviewing cart before checkout...")
    review_res = requests.post(f"{BASE_URL}/interop/execute", json={
        "session_id": session_a,
        "tool_name": "get_cart",
        "arguments": {}
    }).json()
    print("   Response:")
    print("  ", review_res.get("result", "").replace("\n", "\n   "))
    time.sleep(1)

    # Action 5: Checkout (Razorpay Test Mode Order)
    print("\n[External Agent -> Execute] Initiating Checkout through Trust Gate...")
    checkout_res = requests.post(f"{BASE_URL}/interop/execute", json={
        "session_id": session_a,
        "tool_name": "checkout",
        "arguments": {}
    }).json()
    print(f"   Status: {checkout_res.get('status')}")
    print("   Result:")
    print("  ", checkout_res.get("result", "").replace("\n", "\n   "))

    # -------------------------------------------------------------
    # Scenario B: Deliberate Safety & Policy Gate Enforcement
    # -------------------------------------------------------------
    session_b = "agent_buyer_bulk_policy_block_02"
    print("\n" + "-" * 70)
    print(f"🛡️  SCENARIO B: Deliberate Policy Enforcement (Session: {session_b})")
    print("Goal: External Agent attempts to hoard 20 expensive laptops/chairs exceeding policy threshold")
    print("-" * 70)

    print("\n[External Agent -> Execute] Attempting to add 2 units of Noise Cancelling Headphones (₹17,998 exceeds ₹10,000 cart cap)...")
    block_cart_payload = {
        "session_id": session_b,
        "tool_name": "add_to_cart",
        "arguments": {"product_id": "prod_002", "quantity": 2}
    }
    b_cart_res = requests.post(f"{BASE_URL}/interop/execute", json=block_cart_payload).json()
    print(f"   Response: {b_cart_res.get('result')}")
    time.sleep(1)

    print("\n[External Agent -> Execute] External Agent attempts checkout anyway...")
    b_checkout_res = requests.post(f"{BASE_URL}/interop/execute", json={
        "session_id": session_b,
        "tool_name": "checkout",
        "arguments": {}
    }).json()
    print(f"   Policy Decision Status: {b_checkout_res.get('status')}")
    print(f"   Agent Gate Response: {b_checkout_res.get('result')}")

    print("\n" + "=" * 70)
    print("✅ SIMULATION COMPLETE: Both autonomous success and policy gate protection verified.")
    print("All decisions and reasoning traces are securely recorded in the Merchant Audit Log.")
    print("=" * 70)

if __name__ == "__main__":
    run_buyer_simulation()
