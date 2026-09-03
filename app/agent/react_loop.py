import os
import json
import asyncio
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


def build_messages_history(message: str, chat_history: list = None):
    messages = []
    if chat_history:
        for item in chat_history:
            if item.get("role") == "user":
                messages.append(HumanMessage(content=item.get("message", "")))
            elif item.get("role") == "agent":
                messages.append(AIMessage(content=item.get("message", "")))
    messages.append(HumanMessage(content=message))
    return messages


def run_agent(session_id: str, message: str, chat_history: list = None) -> dict:
    """
    Executes the ReAct agent with Gemini 3.6 Flash and returns the final response
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

        messages = build_messages_history(message, chat_history)
        result = agent.invoke({"messages": messages})
        
        trace = []
        final_response = "I couldn't process your request."

        for m in result.get("messages", []):
            if isinstance(m, AIMessage):
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
        return {
            "response": f"Encountered an agent execution error: {str(e)}",
            "trace": [f"Exception: {str(e)}"]
        }


async def stream_agent(session_id: str, message: str, chat_history: list = None):
    """
    Asynchronously streams live Thought, Action, and Observation events
    from the LangGraph ReAct loop as Server-Sent Events (SSE).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield f"data: {json.dumps({'type': 'error', 'message': 'GEMINI_API_KEY not configured'})}\n\n"
        return

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=api_key,
            temperature=0.2
        )
        tools = create_session_tools(session_id)
        agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
        messages = build_messages_history(message, chat_history)

        # Initial thought event
        yield f"data: {json.dumps({'type': 'thought', 'content': 'Analyzing customer request and reasoning over merchant catalog...'})}\n\n"
        await asyncio.sleep(0.05)

        final_answer = ""
        full_trace = []

        # Run stream in thread pool to avoid blocking async event loop
        loop = asyncio.get_event_loop()
        stream_iter = agent.stream({"messages": messages}, stream_mode="updates")

        def get_next_chunk():
            try:
                return next(stream_iter)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, get_next_chunk)
            if chunk is None:
                break

            for node_name, node_state in chunk.items():
                for m in node_state.get("messages", []):
                    if isinstance(m, AIMessage):
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                tool_name = tc.get("name", "tool")
                                tool_args = tc.get("args", {})
                                full_trace.append(f"Action: {tool_name} with {json.dumps(tool_args)}")
                                yield f"data: {json.dumps({'type': 'action', 'tool': tool_name, 'args': tool_args})}\n\n"
                                await asyncio.sleep(0.05)
                        if m.content:
                            content_str = m.content if isinstance(m.content, str) else " ".join([c.get("text", "") for c in m.content if isinstance(c, dict)])
                            if content_str.strip():
                                final_answer = content_str

                    elif isinstance(m, ToolMessage):
                        obs_content = str(m.content)
                        tool_label = getattr(m, "name", "tool")
                        full_trace.append(f"Observation: {obs_content}")
                        yield f"data: {json.dumps({'type': 'observation', 'tool': tool_label, 'content': obs_content})}\n\n"
                        await asyncio.sleep(0.05)

        # Emit final response
        if not final_answer:
            final_answer = "I have processed your request."
        yield f"data: {json.dumps({'type': 'response', 'content': final_answer, 'trace': full_trace})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
