import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from app.db.session import engine, SessionLocal
from app.db.models import Base, Product, TrustPolicy
from app.vectorstore.chroma_client import index_products

def init_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Loading synthetic catalog...")
    catalog_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'synthetic_catalog.json')
    with open(catalog_path, 'r') as f:
        products_data = json.load(f)
    
    db = SessionLocal()
    
    # Check if we already have products
    existing = db.query(Product).first()
    if not existing:
        print("Inserting products into SQLite...")
        for p_data in products_data:
            product = Product(
                id=p_data["id"],
                name=p_data["name"],
                description=p_data["description"],
                category=p_data["category"],
                price=p_data["price"],
                stock=p_data["stock"],
                attributes=p_data.get("attributes", {})
            )
            db.add(product)
            
        print("Creating default trust policies...")
        policy1 = TrustPolicy(name="max_cart_value", rule_type="max_amount", threshold_value=10000.0)
        policy2 = TrustPolicy(name="velocity_limit", rule_type="max_orders_per_hour", threshold_value=5.0)
        policy3 = TrustPolicy(name="max_item_quantity", rule_type="max_units", threshold_value=10.0)
        db.add_all([policy1, policy2, policy3])
            
        db.commit()
        
        print("Indexing products in ChromaDB...")
        index_products(products_data)
        
        print("Initialization complete!")
    else:
        print("Database already initialized.")
        
    db.close()

if __name__ == "__main__":
    init_db()
