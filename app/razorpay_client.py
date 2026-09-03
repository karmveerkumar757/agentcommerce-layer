import razorpay
import os
from dotenv import load_dotenv

load_dotenv()

key_id = os.getenv("RAZORPAY_KEY_ID")
key_secret = os.getenv("RAZORPAY_KEY_SECRET")

client = razorpay.Client(auth=(key_id, key_secret)) if key_id and key_secret else None

def create_order(amount: float, currency: str = "INR", receipt: str = None) -> dict:
    if not client:
        return {"id": "mock_rzp_order_123", "status": "created", "amount": amount * 100}
        
    data = {
        "amount": int(amount * 100), 
        "currency": currency,
        "receipt": receipt
    }
    return client.order.create(data=data)
