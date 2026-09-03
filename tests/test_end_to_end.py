import pytest
import os
import sys
import uuid
import time
import json
import hmac
import hashlib

# Ensure root package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Product, TrustPolicy, Order, CartItem, AuditLog, DecisionType
from app.vectorstore.chroma_client import search_products
from app.agent.tools import tool_search_catalog, tool_add_to_cart, tool_get_cart, tool_checkout

client = TestClient(app)

def test_discovery_manifest():
    """Verify standard /.well-known/agent-commerce.json discovery manifest."""
    response = client.get("/.well-known/agent-commerce.json")
    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["currency"] == "INR"
    assert "search_catalog" in [t["name"] for t in data["tools"]]
    assert "checkout" in [t["name"] for t in data["tools"]]
    assert "/interop/execute" in data["endpoints"]["execute"]
    assert data["security"]["auth_type"] == "HMAC-SHA256"

def test_semantic_catalog_search():
    """Verify semantic vector search returns matching products from ChromaDB."""
    results = search_products("waterproof shoe", top_k=2)
    assert len(results) > 0
    first_prod = results[0]
    assert "shoe" in first_prod["metadata"]["name"].lower() or "shoe" in first_prod["document"].lower()

def test_interop_search_and_cart_flow():
    """Verify external agent can search, add to cart, and review cart via /interop/execute."""
    session_id = f"test_agent_{uuid.uuid4().hex[:8]}"

    # 1. Search
    res = client.post("/interop/execute", json={
        "session_id": session_id,
        "tool_name": "search_catalog",
        "arguments": {"query": "headphones"}
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "headphones" in res.json()["result"].lower()

    # 2. Add to cart
    res_cart = client.post("/interop/execute", json={
        "session_id": session_id,
        "tool_name": "add_to_cart",
        "arguments": {"product_id": "prod_002", "quantity": 1}
    })
    assert res_cart.status_code == 200
    assert res_cart.json()["status"] == "success"

    # 3. Get cart
    res_get = client.post("/interop/execute", json={
        "session_id": session_id,
        "tool_name": "get_cart",
        "arguments": {}
    })
    assert res_get.status_code == 200
    assert "Wireless Noise Cancelling Headphones" in res_get.json()["result"]

def test_policy_engine_deliberate_block():
    """Verify trust & verification policy engine enforces safety boundaries when cart exceeds limits."""
    session_id = f"test_policy_block_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        # Add 2 items of prod_002 (Headphones: each 8,999 INR = 17,998 INR, exceeding max cart limit of 10,000)
        cart_res = tool_add_to_cart(session_id, "prod_002", 2)
        assert "successfully added" in cart_res.lower()
        
        # Attempt checkout
        res = tool_checkout(session_id)
        assert "blocked by" in res.lower()
        
        # Verify blocked event in audit log
        log_entry = db.query(AuditLog).filter_by(session_id=session_id, decision=DecisionType.blocked).first()
        assert log_entry is not None
        assert "exceeds" in log_entry.reason.lower()
    finally:
        # Clean up
        db.query(CartItem).filter_by(session_id=session_id).delete()
        db.commit()
        db.close()

def test_successful_checkout_and_razorpay_order():
    """Verify an allowed transaction creates an active order and clears cart."""
    session_id = f"test_success_order_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        # Add 1 item (prod_004 = 450 INR)
        tool_add_to_cart(session_id, "prod_004", 1)
        
        checkout_msg = tool_checkout(session_id)
        assert "checkout successful" in checkout_msg.lower()
        assert "razorpay order id" in checkout_msg.lower()

        # Check DB Order record
        order = db.query(Order).filter_by(session_id=session_id).first()
        assert order is not None
        assert order.total_amount == 450.0

        # Check Cart is cleared
        cart_count = db.query(CartItem).filter_by(session_id=session_id).count()
        assert cart_count == 0
    finally:
        db.close()

def test_hmac_request_signing_security():
    """Verify that valid HMAC-SHA256 signatures are accepted and tampered ones return 401."""
    secret = b"agentcommerce_secret_2026"
    session_id = f"test_hmac_agent_{uuid.uuid4().hex[:8]}"
    payload = {
        "session_id": session_id,
        "tool_name": "get_cart",
        "arguments": {}
    }
    body_str = json.dumps(payload, separators=(',', ':'))
    ts = str(int(time.time()))

    # 1. Valid Signature Test
    valid_sig = hmac.new(secret, f"{ts}.{body_str}".encode("utf-8"), hashlib.sha256).hexdigest()
    res_valid = client.post(
        "/interop/execute",
        content=body_str,
        headers={
            "Content-Type": "application/json",
            "X-Signature-SHA256": valid_sig,
            "X-Timestamp": ts
        }
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "success"

    # 2. Tampered / Invalid Signature Test
    invalid_sig = "deadbeef1234567890abcdefdeadbeef1234567890abcdefdeadbeef12345678"
    res_invalid = client.post(
        "/interop/execute",
        content=body_str,
        headers={
            "Content-Type": "application/json",
            "X-Signature-SHA256": invalid_sig,
            "X-Timestamp": ts
        }
    )
    assert res_invalid.status_code == 401
    assert "Unauthorized" in res_invalid.text

def test_checkout_idempotency_guarantee():
    """Verify that retrying checkout with the same Idempotency-Key returns existing order without duplicates."""
    session_id = f"test_idemp_{uuid.uuid4().hex[:8]}"
    idemp_key = f"idemp_{uuid.uuid4().hex}"

    # Add item
    tool_add_to_cart(session_id, "prod_001", 1)

    # First checkout
    res1 = client.post(
        "/checkout/initiate",
        json={"session_id": session_id, "idempotency_key": idemp_key}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    order_id1 = data1["order_id"]

    # Second checkout retry with same key
    res2 = client.post(
        "/checkout/initiate",
        json={"session_id": session_id, "idempotency_key": idemp_key}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "success"
    assert data2["order_id"] == order_id1
    assert data2.get("idempotent_replay") is True
