from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.trust.policy_engine import check_checkout_policy
from app.db.models import CartItem, Product, Order
import uuid
from app.razorpay_client import create_order

router = APIRouter(prefix="/checkout", tags=["checkout"])

# In-memory idempotency cache for active requests: idempotency_key -> order response
IDEMPOTENCY_CACHE = {}

class CheckoutRequest(BaseModel):
    session_id: str = Field(..., description="Unique session ID of the shopper or agent")
    idempotency_key: Optional[str] = Field(None, description="Optional unique key to prevent duplicate checkouts on network retries")


@router.post("/initiate")
def initiate_checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    idempotency_header: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Evaluates cart against Trust & Policy Gate, creates a Razorpay test order,
    and guarantees idempotency against network retries.
    """
    idemp_key = request.idempotency_key or idempotency_header

    # 1. Idempotency Check: Return cached response if this key was already processed
    if idemp_key and idemp_key in IDEMPOTENCY_CACHE:
        cached_resp = IDEMPOTENCY_CACHE[idemp_key]
        return {**cached_resp, "idempotent_replay": True}

    # 2. Evaluate Policy Gate
    allowed, reason = check_checkout_policy(db, request.session_id)
    if not allowed:
        return {"status": "blocked", "reason": reason}

    # 3. Fetch Cart Items
    cart_items = db.query(CartItem).filter_by(session_id=request.session_id).all()
    if not cart_items:
        return {"status": "error", "reason": "Cart is empty"}

    total = sum([item.quantity * db.query(Product).filter_by(id=item.product_id).first().price for item in cart_items])

    # 4. Generate Razorpay Test Order
    order_id = f"order_{uuid.uuid4().hex[:10]}"
    rzp_order = create_order(total, receipt=order_id)
    rzp_order_id = rzp_order.get("id", f"rzp_mock_{uuid.uuid4().hex[:8]}")

    order = Order(
        id=order_id,
        session_id=request.session_id,
        total_amount=total,
        status="created",
        razorpay_order_id=rzp_order_id
    )
    db.add(order)
    # Clear cart on checkout
    db.query(CartItem).filter_by(session_id=request.session_id).delete()
    db.commit()

    response_payload = {
        "status": "success",
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "amount": total,
        "currency": "INR"
    }

    # Cache for idempotency if key was provided
    if idemp_key:
        IDEMPOTENCY_CACHE[idemp_key] = response_payload

    return response_payload
