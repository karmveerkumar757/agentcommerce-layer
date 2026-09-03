from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.db.models import CartItem

router = APIRouter(prefix="/cart", tags=["cart"])

class AddToCartRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1

@router.post("/add")
def add_to_cart(request: AddToCartRequest, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter_by(session_id=request.session_id, product_id=request.product_id).first()
    if item:
        item.quantity += request.quantity
    else:
        item = CartItem(session_id=request.session_id, product_id=request.product_id, quantity=request.quantity)
        db.add(item)
    db.commit()
    return {"status": "success"}

@router.get("/get/{session_id}")
def get_cart(session_id: str, db: Session = Depends(get_db)):
    items = db.query(CartItem).filter_by(session_id=session_id).all()
    return items
