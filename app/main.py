from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import catalog, agent, cart, checkout, audit, interop
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="AgentCommerce Layer API")

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

from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")
