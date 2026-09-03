from app.vectorstore.chroma_client import search_products
from app.db.session import SessionLocal
from app.db.models import Product, CartItem, Order
from app.trust.policy_engine import check_checkout_policy
from app.razorpay_client import create_order
import uuid

def tool_search_catalog(query: str, max_price: float = None) -> str:
    """Searches the product catalog using semantic similarity and optional price filter."""
    filters = {}
    if max_price:
        filters["max_price"] = float(max_price)
    results = search_products(query, top_k=3, filters=filters)
    if not results:
        return "No products found matching the query."
    
    response = "Found products:\n"
    for r in results:
        response += f"- {r['metadata']['name']} (ID: {r['id']}) - ₹{r['metadata']['price']:,}\n"
        response += f"  Description: {r['document']}\n"
        response += f"  Stock: {r['metadata']['stock']} available\n"
    return response

def tool_get_product_details(product_id: str) -> str:
    """Retrieves full details for a product given its ID."""
    db = SessionLocal()
    try:
        p = db.query(Product).filter_by(id=product_id.strip()).first()
        if not p:
            return f"Product '{product_id}' not found."
        return (
            f"Product Details:\n"
            f"- Name: {p.name}\n"
            f"- ID: {p.id}\n"
            f"- Price: ₹{p.price:,.2f}\n"
            f"- Stock: {p.stock} units available\n"
            f"- Category: {p.category}\n"
            f"- Description: {p.description}\n"
            f"- Attributes: {p.attributes}"
        )
    finally:
        db.close()

def tool_add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> str:
    """Adds a specified quantity of a product to the user's shopping cart."""
    db = SessionLocal()
    try:
        p = db.query(Product).filter_by(id=product_id.strip()).first()
        if not p:
            return f"Error: Product '{product_id}' does not exist in catalog."
        
        if quantity <= 0:
            return "Error: Quantity must be at least 1."
            
        if p.stock < quantity:
            return f"Error: Only {p.stock} units of '{p.name}' in stock (requested {quantity})."

        item = db.query(CartItem).filter_by(session_id=session_id, product_id=product_id.strip()).first()
        if item:
            item.quantity += quantity
        else:
            item = CartItem(session_id=session_id, product_id=product_id.strip(), quantity=quantity)
            db.add(item)
        db.commit()
        return f"Successfully added {quantity} unit(s) of '{p.name}' to cart. Unit price: ₹{p.price:,.2f}."
    finally:
        db.close()

def tool_get_cart(session_id: str) -> str:
    """Retrieves the current items and total amount in the user's cart."""
    db = SessionLocal()
    try:
        cart_items = db.query(CartItem).filter_by(session_id=session_id).all()
        if not cart_items:
            return "Your cart is currently empty."
        
        output = "Current Cart:\n"
        total = 0.0
        for item in cart_items:
            p = db.query(Product).filter_by(id=item.product_id).first()
            if p:
                item_total = p.price * item.quantity
                total += item_total
                output += f"- {p.name} (ID: {p.id}) x {item.quantity} = ₹{item_total:,.2f}\n"
        output += f"Total Cart Value: ₹{total:,.2f}"
        return output
    finally:
        db.close()

def tool_checkout(session_id: str) -> str:
    """Initiates checkout with Razorpay test-mode API after passing trust & verification policy gating."""
    db = SessionLocal()
    try:
        allowed, reason = check_checkout_policy(db, session_id)
        if not allowed:
            return f"Checkout blocked by Trust Policy Engine: {reason}"
            
        cart_items = db.query(CartItem).filter_by(session_id=session_id).all()
        if not cart_items:
            return "Cart is empty. Add products before checking out."
            
        total = 0.0
        for item in cart_items:
            p = db.query(Product).filter_by(id=item.product_id).first()
            if p:
                total += p.price * item.quantity
        
        order_id = f"order_{uuid.uuid4().hex[:10]}"
        rzp_order = create_order(total, receipt=order_id)
        rzp_order_id = rzp_order.get("id", f"rzp_mock_{uuid.uuid4().hex[:8]}")
        
        order = Order(
            id=order_id,
            session_id=session_id,
            total_amount=total,
            status="created",
            razorpay_order_id=rzp_order_id
        )
        db.add(order)
        # Clear cart upon successful order creation
        db.query(CartItem).filter_by(session_id=session_id).delete()
        db.commit()
        
        return (
            f"Checkout Successful! Razorpay Order Created.\n"
            f"- Order ID: {order_id}\n"
            f"- Razorpay Order ID: {rzp_order_id}\n"
            f"- Total Amount: ₹{total:,.2f}\n"
            f"- Status: Active (Test Mode)"
        )
    finally:
        db.close()
