import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import json

load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

collection = client.get_or_create_collection(name="products_collection")

# Fast load from local cache if present; gracefully downloads in CI or fresh environments
try:
    model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
except Exception:
    model = SentenceTransformer('all-MiniLM-L6-v2')

def get_product_embedding(text: str) -> list[float]:
    return model.encode(text).tolist()

def index_products(products: list[dict]):
    ids = []
    embeddings = []
    metadatas = []
    documents = []

    for p in products:
        text = f"{p['name']} - {p['description']} - Category: {p['category']}"
        ids.append(p["id"])
        documents.append(text)
        embeddings.append(get_product_embedding(text))
        metadatas.append({
            "name": p["name"],
            "category": p["category"],
            "price": p["price"],
            "stock": p["stock"],
            "attributes": json.dumps(p.get("attributes", {}))
        })
    
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents
    )

def search_products(query: str, top_k: int = 5, filters: dict = None) -> list[dict]:
    query_embedding = get_product_embedding(query)
    
    where = {}
    if filters:
        if "category" in filters:
            where["category"] = filters["category"]
        if "max_price" in filters:
            where["price"] = {"$lte": filters["max_price"]}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where if where else None
    )
    
    if not results['ids'] or not results['ids'][0]:
        return []
    
    formatted_results = []
    for i in range(len(results['ids'][0])):
        formatted_results.append({
            "id": results['ids'][0][i],
            "metadata": results['metadatas'][0][i],
            "document": results['documents'][0][i],
            "distance": results['distances'][0][i] if 'distances' in results and results['distances'] else None
        })
    return formatted_results
