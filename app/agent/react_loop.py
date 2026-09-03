import os
import json
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.tools import (
    tool_search_catalog,
    tool_get_product_details,
    tool_add_to_cart,
    tool_get_cart,
    tool_checkout
)

load_dotenv(override=True)

# System prompt giving strict instructions for ReAct agent
SYSTEM_PROMPT = """You are the AgentCommerce AI Shopping Assistant for a Razorpay merchant.
Your goal is to help customers discover products, check specs, manage their cart, and complete purchases safely.

Instructions:
1. Always base product claims (pricing, stock, specs) strictly on tool outputs from search_catalog or get_product_details.
2. Prices are in Indian Rupees (₹ / INR).
3. Be conversational, helpful, and concise.
4. When a user asks to add an item to their cart, call `add_to_cart`.
5. When a user wants to review their cart, call `get_cart`.
6. When a user clearly confirms they want to proceed with purchase/buy/checkout, call `checkout`.
7. If the policy engine blocks checkout, explain the exact reason politely to the customer.
"""

def create_session_tools(session_id: str):
    @tool
    def search_catalog(query: str, max_price: float = None) -> str:
        """Search the merchant's catalog for products using keywords, category, or semantic intent, with optional max_price filter."""
        return tool_search_catalog(query, max_price)

    @tool
    def get_product_details(product_id: str) -> str:
        """Get full specifications, price, category, and stock for a specific product using its ID (e.g. prod_001)."""
        return tool_get_product_details(product_id)

    @tool
    def add_to_cart(product_id: str, quantity: int = 1) -> str:
        """Add a product and specified quantity into the customer's cart. Requires product_id (e.g. prod_001)."""
        return tool_add_to_cart(session_id, product_id, quantity)

    @tool
    def get_cart() -> str:
        """View the current contents and total price of the customer's cart."""
        return tool_get_cart(session_id)

    @tool
    def checkout() -> str:
        """Complete the purchase by running trust policy validation and creating a Razorpay test order."""
        return tool_checkout(session_id)

    return [search_catalog, get_product_details, add_to_cart, get_cart, checkout]


def run_agent(session_id: str, message: str, chat_history: list = None) -> dict:
    """
    Executes the ReAct agent with Gemini 3.7 Flash and returns the final response
    along with the full Thought/Action/Observation reasoning trace.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "response": "Error: GEMINI_API_KEY is not set in environment.",
            "trace": ["Error: GEMINI_API_KEY missing"]
        }

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=api_key,
            temperature=0.2
        )
        tools = create_session_tools(session_id)
        agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

        # Build message history
        messages = []
        if chat_history:
            for item in chat_history:
                if item.get("role") == "user":
                    messages.append(HumanMessage(content=item.get("message", "")))
                elif item.get("role") == "agent":
                    messages.append(AIMessage(content=item.get("message", "")))
        
        messages.append(HumanMessage(content=message))

        # Invoke the agent graph
        result = agent.invoke({"messages": messages})
        
        trace = []
        final_response = "I couldn't process your request."

        # Extract reasoning trace and final output
        for m in result.get("messages", []):
            if isinstance(m, AIMessage):
                # Check for tool calls
                if hasattr(m, "tool_calls") and m.tool_calls:
                    for tc in m.tool_calls:
                        name = tc.get("name", "tool")
                        args = tc.get("args", {})
                        trace.append(f"Action: {name}\nArgs: {json.dumps(args, ensure_ascii=False)}")
                if m.content:
                    if isinstance(m.content, str) and m.content.strip():
                        final_response = m.content
                    elif isinstance(m.content, list):
                        text_parts = [c.get("text", "") for c in m.content if isinstance(c, dict) and "text" in c]
                        if text_parts:
                            final_response = " ".join(text_parts)
            elif isinstance(m, ToolMessage):
                trace.append(f"Observation: {m.content}")

        return {
            "response": final_response,
            "trace": trace
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "response": f"Encountered an agent execution error: {str(e)}",
            "trace": [f"Exception: {str(e)}"]
        }
