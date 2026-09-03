from app.db.models import TrustPolicy, CartItem, Product, DecisionType, Order
from sqlalchemy.orm import Session
from app.trust.audit_logger import log_action
from datetime import datetime, timezone, timedelta

def check_checkout_policy(db: Session, session_id: str) -> tuple[bool, str]:
    cart_items = db.query(CartItem).filter_by(session_id=session_id).all()
    if not cart_items:
        reason = "Cart is empty. Cannot initiate checkout."
        log_action(db, session_id, "checkout_attempt", DecisionType.blocked, reason)
        return False, reason

    # 1. Check Max Quantity per Item (prevent hoarding / bot draining)
    policy_max_qty = db.query(TrustPolicy).filter_by(name="max_item_quantity").first()
    max_qty_threshold = policy_max_qty.threshold_value if policy_max_qty else 10.0
    for item in cart_items:
        if item.quantity > max_qty_threshold:
            product = db.query(Product).filter_by(id=item.product_id).first()
            p_name = product.name if product else item.product_id
            reason = f"Quantity for '{p_name}' ({item.quantity} units) exceeds maximum single-order limit of {int(max_qty_threshold)}."
            log_action(db, session_id, "checkout_attempt", DecisionType.blocked, reason)
            return False, reason

    # 2. Check Max Cart Value
    policy_max_val = db.query(TrustPolicy).filter_by(name="max_cart_value").first()
    total_value = 0.0
    for item in cart_items:
        product = db.query(Product).filter_by(id=item.product_id).first()
        if product:
            total_value += product.price * item.quantity

    max_val_threshold = policy_max_val.threshold_value if policy_max_val else 10000.0
    if total_value > max_val_threshold:
        reason = f"Cart total (₹{total_value:,.2f}) exceeds maximum allowed transaction threshold (₹{max_val_threshold:,.2f})."
        log_action(db, session_id, "checkout_attempt", DecisionType.blocked, reason)
        return False, reason

    # 3. Check Velocity / Rate Limits (e.g. max orders per session in last 1 hour)
    policy_velocity = db.query(TrustPolicy).filter_by(name="velocity_limit").first()
    max_velocity = policy_velocity.threshold_value if policy_velocity else 5.0
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_orders = db.query(Order).filter(
        Order.session_id == session_id,
        Order.created_at >= one_hour_ago
    ).count()

    if recent_orders >= max_velocity:
        reason = f"Velocity limit exceeded: {recent_orders} checkout attempts in the last hour (max {int(max_velocity)})."
        log_action(db, session_id, "checkout_attempt", DecisionType.blocked, reason)
        return False, reason

    # All policies passed
    log_action(db, session_id, "checkout_attempt", DecisionType.allowed, f"All policies passed for order value ₹{total_value:,.2f}.")
    return True, "Checkout permitted."
