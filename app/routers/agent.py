from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.agent.react_loop import run_agent
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.db.models import Conversation, Session as DbSession, UserType

router = APIRouter(prefix="/agent", tags=["agent"])

class ChatRequest(BaseModel):
    session_id: str
    message: str

@router.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Ensure session exists
    session = db.query(DbSession).filter_by(id=request.session_id).first()
    if not session:
        session = DbSession(id=request.session_id, user_type=UserType.human)
        db.add(session)
        db.commit()

    # Load recent conversation history for this session (up to last 10 messages)
    recent_convs = (
        db.query(Conversation)
        .filter_by(session_id=request.session_id)
        .order_by(Conversation.id.asc())
        .limit(10)
        .all()
    )
    chat_history = [{"role": c.role, "message": c.message} for c in recent_convs]

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
