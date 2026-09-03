import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.routers import catalog, agent, cart, checkout, audit, interop
from app.db.session import engine
from app.db.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agentcommerce")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Diagnostic Health Check
    logger.info("⚡ Initializing AgentCommerce Layer...")
    
    # 1. Verify Database Schema
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database schema verified & ready.")
    except Exception as e:
        logger.error(f"❌ Database initialization warning: {e}")

    # 2. Check Key Environment Variables
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or "your_gemini" in gemini_key:
        logger.warning("⚠️  GEMINI_API_KEY is not configured. ReAct agent will run in degraded mode.")
    else:
        logger.info("✅ Google Gemini LLM key detected.")

    rzp_key = os.getenv("RAZORPAY_KEY_ID")
    if not rzp_key or "your_razorpay" in rzp_key:
        logger.warning("⚠️  RAZORPAY_KEY_ID is using mock test fallback.")
    else:
        logger.info(f"✅ Razorpay Test Rails active (Key ID: {rzp_key[:8]}...)")

    yield
    logger.info("⚡ AgentCommerce Layer shutting down cleanly.")


app = FastAPI(
    title="AgentCommerce Layer API",
    description="Autonomous Policy-Gated Agentic Commerce Gateway on Razorpay Payment Rails",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(agent.router)
app.include_router(cart.router)
app.include_router(checkout.router)
app.include_router(audit.router)
app.include_router(interop.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "healthy",
        "service": "AgentCommerce Layer",
        "protocols": ["ACP-v1", "AP2-gated", "UAP-ready"],
        "rails": "Razorpay TestMode"
    }
