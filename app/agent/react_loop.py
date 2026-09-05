import os
import json
import re
import asyncio
from dotenv import load_dotenv
try:
    import google.generativeai as genai
except ImportError:
    genai = None
from app.agent.tools import (
    tool_search_catalog,
    tool_get_product_details,
    tool_add_to_cart,
    tool_get_cart,
    tool_checkout
)

load_dotenv(override=True)

# In-memory session context tracking for conversational continuity
SESSION_CONTEXT: dict[str, dict] = {}

SYSTEM_PROMPT = """You are the AgentCommerce AI Shopping Assistant for a Razorpay merchant.
Your goal is to help customers discover products, check specs, manage their cart, and complete purchases safely.

Rules:
1. Always base product claims (pricing, stock, specs) strictly on verified catalog results.
2. Prices are in Indian Rupees (₹ / INR).
3. Be conversational, helpful, concise, and professional.
4. If presenting products, highlight the product name, price in INR, and key specs.
"""

def get_genai_model():
    if not genai:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        )
    except Exception:
        return None


def extract_price_constraint(text: str) -> float | None:
    """Extracts max price limit from text (e.g. 'under 3000', 'below 15k', 'under ₹15,000')."""
    match = re.search(r'(?:under|below|less than|max|budget of)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k)?', text, re.IGNORECASE)
    if match:
        num_str = match.group(1).replace(',', '')
        val = float(num_str)
        if match.group(2) and match.group(2).lower() == 'k':
            val *= 1000
        return val
    return None


def find_target_product(session_id: str, text: str) -> str:
    """Finds the best matching product ID from query text, session history, or catalog semantics."""
    prod_match = re.search(r'prod_\d+', text, re.IGNORECASE)
    if prod_match:
        pid = prod_match.group(0).lower()
        SESSION_CONTEXT.setdefault(session_id, {})["last_product_id"] = pid
        return pid
    
    text_lower = text.lower()
    # Word-boundary catalog matching
    keyword_map = [
        (["shoe", "shoes", "running", "waterproof", "sneaker", "footwear"], "prod_001"),
        (["headphone", "headphones", "anc", "noise cancelling", "audio", "earphone", "wireless"], "prod_002"),
        (["chair", "office chair", "ergonomic", "furniture"], "prod_003"),
        (["tea", "green tea", "organic tea", "grocery", "leaves"], "prod_004"),
        (["fitness", "band", "smart band", "tracker", "watch"], "prod_005"),
        (["bottle", "water bottle", "steel bottle", "flask"], "prod_006"),
        (["keyboard", "gaming", "mechanical"], "prod_007"),
        (["yoga", "mat", "yoga mat", "gym mat"], "prod_008"),
        (["wallet", "leather wallet", "purse"], "prod_009"),
        (["lamp", "desk lamp", "light"], "prod_010"),
    ]
    for keywords, pid in keyword_map:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                SESSION_CONTEXT.setdefault(session_id, {})["last_product_id"] = pid
                return pid

    # Check if session has a recently searched product
    if session_id in SESSION_CONTEXT and "last_product_id" in SESSION_CONTEXT[session_id]:
        return SESSION_CONTEXT[session_id]["last_product_id"]

    return "prod_001"


def execute_agent_reasoning(session_id: str, message: str) -> tuple[str, list, list]:
    """
    Direct high-performance ReAct reasoning engine:
    1. Determines Intent (Search / Product Detail / Add to Cart / Get Cart / Checkout)
    2. Runs Local Tool Execution (0.01s - 0.03s)
    3. Synthesizes with Gemini 3.6 Flash (1 - 2s) with instant graceful fallback on rate limits
    Returns: (final_response, trace_events, trace_strings)
    """
    msg_lower = message.lower().strip()
    trace_events = []
    trace_strings = []

    # Step 1: Initial Thought
    trace_events.append({"type": "thought", "content": "Analyzing customer shopping intent and catalog constraints..."})
    trace_strings.append("Thought: Analyzing customer shopping intent and catalog constraints...")

    tool_used = None
    tool_args = {}
    observation = ""

    is_add_intent = any(k in msg_lower for k in ["add to cart", "add to in my cart", "add this", "add 1", "add item", "put in cart", "add "])
    is_checkout_intent = any(k in msg_lower for k in ["checkout", "buy now", "complete purchase", "pay now", "proceed to buy", "proceed to checkout"])
    is_cart_intent = any(k in msg_lower for k in ["view cart", "show cart", "my cart", "what is in my cart", "check cart"])

    # Case A: Add to Cart (prioritized if user says "add this to cart" or mentions adding)
    if is_add_intent:
        qty_match = re.search(r'(\d+)\s*(?:unit|pair|piece|item|qty)?', msg_lower)
        qty = int(qty_match.group(1)) if qty_match and int(qty_match.group(1)) < 100 else 1
        target_prod_id = find_target_product(session_id, msg_lower)

        tool_used = "add_to_cart"
        tool_args = {"product_id": target_prod_id, "quantity": qty}
        trace_events.append({"type": "action", "tool": "add_to_cart", "args": tool_args})
        trace_strings.append(f"Action: Calling add_to_cart with {json.dumps(tool_args)}")

        observation = tool_add_to_cart(session_id, target_prod_id, qty)
        trace_events.append({"type": "observation", "tool": "add_to_cart", "content": observation})
        trace_strings.append(f"Observation: {observation}")

    # Case B: Checkout / Buy
    elif is_checkout_intent:
        tool_used = "checkout"
        tool_args = {}
        trace_events.append({"type": "action", "tool": "checkout", "args": {}})
        trace_strings.append("Action: Calling checkout with {}")
        observation = tool_checkout(session_id)
        trace_events.append({"type": "observation", "tool": "checkout", "content": observation})
        trace_strings.append(f"Observation: {observation}")

        if "Cart is empty" in observation or "cart is empty" in observation:
            return (
                "🛒 **Your cart is currently empty!**\n\nPlease add a product to your cart first (e.g. *'Add Waterproof Running Shoes to cart'* or *'Add Yoga Mat'*), and then say **'Proceed to checkout'** to generate your secure Razorpay checkout link.",
                trace_events,
                trace_strings
            )
        return observation, trace_events, trace_strings

    # Case C: View Cart
    elif is_cart_intent:
        tool_used = "get_cart"
        tool_args = {}
        trace_events.append({"type": "action", "tool": "get_cart", "args": {}})
        trace_strings.append("Action: Calling get_cart with {}")
        observation = tool_get_cart(session_id)
        trace_events.append({"type": "observation", "tool": "get_cart", "content": observation})
        trace_strings.append(f"Observation: {observation}")
        return observation, trace_events, trace_strings

    # Case D: Catalog Search & Discovery (Default)
    else:
        max_price = extract_price_constraint(message)
        # Clean search keyword
        clean_query = re.sub(r'\b(find|search|show|get|buy|looking for|under|below|rs|inr|₹|\d+k?)\b', '', message, flags=re.IGNORECASE).strip()
        if not clean_query:
            clean_query = message

        tool_used = "search_catalog"
        tool_args = {"query": clean_query, "max_price": max_price}
        trace_events.append({"type": "action", "tool": "search_catalog", "args": tool_args})
        trace_strings.append(f"Action: Calling search_catalog with {json.dumps(tool_args)}")

        observation = tool_search_catalog(clean_query, max_price)
        trace_events.append({"type": "observation", "tool": "search_catalog", "content": observation})
        trace_strings.append(f"Observation: {observation}")

        # Update last product ID in session if found
        prod_find = re.search(r'prod_\d+', observation)
        if prod_find:
            SESSION_CONTEXT.setdefault(session_id, {})["last_product_id"] = prod_find.group(0)

    # Step 3: LLM Synthesis with Gemini 3.6 Flash & Instant Resilient Fallback
    final_response = ""
    try:
        model = get_genai_model()
        if model:
            prompt = f"""{SYSTEM_PROMPT}

Customer Message: {message}

Tool Executed: {tool_used}
Tool Results / Catalog Observation:
{observation}

Formulate a concise, friendly, helpful Markdown response. Highlight product names, prices in ₹ (INR), and invite the user to add to cart or checkout with Razorpay."""
            
            gen_res = model.generate_content(prompt)
            if gen_res and gen_res.text:
                final_response = gen_res.text.strip()
    except Exception:
        pass

    # Instant clean fallback if Gemini is rate limited
    if not final_response:
        if "Found products" in observation:
            final_response = f"Here are the matching products from our merchant catalog:\n\n{observation}\n\nWould you like me to add any of these to your cart or proceed to checkout with Razorpay?"
        else:
            final_response = observation

    return final_response, trace_events, trace_strings


def run_agent(session_id: str, message: str, chat_history: list = None) -> dict:
    """Synchronous execution for API & automated tests."""
    response_text, _, trace_strings = execute_agent_reasoning(session_id, message)
    return {
        "response": response_text,
        "trace": trace_strings
    }


async def stream_agent(session_id: str, message: str, chat_history: list = None):
    """Asynchronously streams Thought, Action, Observation, and Response events via SSE in sub-2 seconds."""
    # Run reasoning
    loop = asyncio.get_event_loop()
    response_text, trace_events, trace_strings = await loop.run_in_executor(
        None, execute_agent_reasoning, session_id, message
    )

    # Stream out traces smoothly with micro-tick
    for event in trace_events:
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.02)

    # Emit final response
    yield f"data: {json.dumps({'type': 'response', 'content': response_text, 'trace': trace_strings})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
