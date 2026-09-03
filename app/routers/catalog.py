from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.vectorstore.chroma_client import search_products
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.db.models import Product

router = APIRouter(prefix="/catalog", tags=["catalog"])

class SearchRequest(BaseModel):
    query: str
    filters: dict = None

@router.post("/search")
def search(request: SearchRequest):
    results = search_products(request.query, filters=request.filters)
    return {"results": results}

@router.get("/product/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        return {"error": "Not found"}
    return product
