from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.trust.policy_engine import check_checkout_policy
from app.db.models import CartItem, Product, Order
import uuid
from app.razorpay_client import create_order

router = APIRouter(prefix="/checkout", tags=["checkout"])

class CheckoutRequest(BaseModel):
    session_id: str

@router.post("/initiate")
def initiate_checkout(request: CheckoutRequest, db: Session = Depends(get_db)):
    allowed, reason = check_checkout_policy(db, request.session_id)
    if not allowed:
        return {"status": "blocked", "reason": reason}
        
    cart_items = db.query(CartItem).filter_by(session_id=request.session_id).all()
    if not cart_items:
        return {"status": "error", "reason": "Cart is empty"}
        
    total = sum([item.quantity * db.query(Product).filter_by(id=item.product_id).first().price for item in cart_items])
    
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
    
    return {
        "status": "success",
        "order_id": order_id,
        "razorpay_order_id": rzp_order_id,
        "amount": total,
        "currency": "INR"
    }
