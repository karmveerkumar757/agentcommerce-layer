from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Session as DbSession, UserType, AuditLog, DecisionType
from app.trust.audit_logger import log_action
from app.agent.tools import (
    tool_search_catalog,
    tool_get_product_details,
    tool_add_to_cart,
    tool_get_cart,
    tool_checkout
)

router = APIRouter(tags=["interop"])

@router.get("/.well-known/agent-commerce.json")
def get_manifest():
    """
    Standardized discovery manifest for external autonomous AI Buyer Agents.
    Conforms to open agentic commerce interoperability patterns (ACP / AP2 / UAP).
    """
    return {
        "version": "1.0.0",
        "merchant": {
            "name": "Razorpay AgentCommerce Merchant",
            "currency": "INR",
            "payment_rails": ["Razorpay-TestMode"],
            "country": "IN"
        },
        "protocols": ["AgentCommerce-v1", "ACP-compatible", "AP2-gated"],
        "endpoints": {
            "discovery": "/.well-known/agent-commerce.json",
            "execute": "/interop/execute"
        },
        "tools": [
            {
                "name": "search_catalog",
                "description": "Semantic and keyword search across merchant inventory with optional price limit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword, category, or product intent"},
                        "max_price": {"type": "number", "description": "Maximum unit price in INR"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_product_details",
                "description": "Retrieve full specs, stock count, and price details for a product ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Product ID (e.g. prod_001)"}
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "add_to_cart",
                "description": "Add a specified quantity of a product to the external agent's cart.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Product ID"},
                        "quantity": {"type": "integer", "description": "Quantity to order", "default": 1}
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "get_cart",
                "description": "Retrieve the current contents and total price of the external agent's cart.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "checkout",
                "description": "Submit cart to Razorpay test-mode transaction execution through the Trust & Policy Gate.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ],
        "trust_policies": {
            "max_cart_value_inr": 10000.0,
            "max_item_quantity": 10,
            "audit_logging": True
        }
    }

class ToolCallRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier for the autonomous buyer agent")
    tool_name: str = Field(..., description="Name of tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool execution")

@router.post("/interop/execute")
def execute_tool(request: ToolCallRequest, db: Session = Depends(get_db)):
    """
    Direct machine-to-machine endpoint for external AI buying agents.
    Executes merchant tools with full session persistence and audit trail.
    """
    # Ensure agent session is registered
    session = db.query(DbSession).filter_by(id=request.session_id).first()
    if not session:
        session = DbSession(id=request.session_id, user_type=UserType.agent)
        db.add(session)
        db.commit()

    tool_name = request.tool_name
    args = request.arguments

    try:
        if tool_name == "search_catalog":
            query = args.get("query", "")
            max_price = args.get("max_price")
            result = tool_search_catalog(query, max_price)
            log_action(db, request.session_id, "interop:search_catalog", DecisionType.allowed, f"Query: '{query}', MaxPrice: {max_price}")
            return {"status": "success", "tool": tool_name, "result": result}

        elif tool_name == "get_product_details":
            product_id = args.get("product_id")
            if not product_id:
                raise HTTPException(status_code=400, detail="Missing required argument 'product_id'")
            result = tool_get_product_details(product_id)
            log_action(db, request.session_id, "interop:get_product_details", DecisionType.allowed, f"ProductId: {product_id}")
            return {"status": "success", "tool": tool_name, "result": result}

        elif tool_name == "add_to_cart":
            product_id = args.get("product_id")
            quantity = int(args.get("quantity", 1))
            if not product_id:
                raise HTTPException(status_code=400, detail="Missing required argument 'product_id'")
            result = tool_add_to_cart(request.session_id, product_id, quantity)
            log_action(db, request.session_id, "interop:add_to_cart", DecisionType.allowed, f"Added {quantity} of {product_id}")
            return {"status": "success", "tool": tool_name, "result": result}

        elif tool_name == "get_cart":
            result = tool_get_cart(request.session_id)
            log_action(db, request.session_id, "interop:get_cart", DecisionType.allowed, "Retrieved cart")
            return {"status": "success", "tool": tool_name, "result": result}

        elif tool_name == "checkout":
            result = tool_checkout(request.session_id)
            is_blocked = "blocked by" in result.lower()
            return {
                "status": "blocked" if is_blocked else "success",
                "tool": tool_name,
                "result": result
            }

        else:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not recognized in manifest")

    except HTTPException:
        raise
    except Exception as e:
        log_action(db, request.session_id, f"interop:{tool_name}", DecisionType.blocked, f"Execution error: {str(e)}")
        return {"status": "error", "tool": tool_name, "error": str(e)}
