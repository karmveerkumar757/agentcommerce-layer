from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.agent.react_loop import run_agent, stream_agent
from app.db.session import get_db, SessionLocal
from sqlalchemy.orm import Session
from app.db.models import Conversation, Session as DbSession, UserType
import json

router = APIRouter(prefix="/agent", tags=["agent"])

class ChatRequest(BaseModel):
    session_id: str
    message: str

def get_or_create_session(db: Session, session_id: str):
    session = db.query(DbSession).filter_by(id=session_id).first()
    if not session:
        session = DbSession(id=session_id, user_type=UserType.human)
        db.add(session)
        db.commit()
    return session

def get_recent_history(db: Session, session_id: str):
    recent_convs = (
        db.query(Conversation)
        .filter_by(session_id=session_id)
        .order_by(Conversation.id.asc())
        .limit(10)
        .all()
    )
    return [{"role": c.role, "message": c.message} for c in recent_convs]


@router.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    get_or_create_session(db, request.session_id)
    chat_history = get_recent_history(db, request.session_id)

    user_msg = Conversation(session_id=request.session_id, role="user", message=request.message)
    db.add(user_msg)
    db.commit()

    agent_output = run_agent(request.session_id, request.message, chat_history=chat_history)
    
    agent_msg = Conversation(
        session_id=request.session_id, 
        role="agent", 
        message=agent_output["response"],
        reasoning_trace=agent_output["trace"]
    )
    db.add(agent_msg)
    db.commit()
    
    return {"response": agent_output["response"], "trace": agent_output["trace"]}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streams live ReAct reasoning trace (Thought -> Action -> Observation -> Final Answer)
    as Server-Sent Events (SSE).
    """
    db = SessionLocal()
    try:
        get_or_create_session(db, request.session_id)
        chat_history = get_recent_history(db, request.session_id)

        user_msg = Conversation(session_id=request.session_id, role="user", message=request.message)
        db.add(user_msg)
        db.commit()
    finally:
        db.close()

    async def event_generator():
        final_response_text = ""
        full_trace = []
        async for sse_chunk in stream_agent(request.session_id, request.message, chat_history=chat_history):
            # Intercept final response for DB persistence
            if sse_chunk.startswith("data: "):
                try:
                    payload = json.loads(sse_chunk[6:].strip())
                    if payload.get("type") == "response":
                        final_response_text = payload.get("content", "")
                        full_trace = payload.get("trace", [])
                except Exception:
                    pass
            yield sse_chunk

        # Persist agent response
        if final_response_text:
            db_save = SessionLocal()
            try:
                agent_msg = Conversation(
                    session_id=request.session_id,
                    role="agent",
                    message=final_response_text,
                    reasoning_trace=full_trace
                )
                db_save.add(agent_msg)
                db_save.commit()
            finally:
                db_save.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
