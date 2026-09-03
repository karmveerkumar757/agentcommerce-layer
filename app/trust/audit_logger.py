from app.db.models import AuditLog, DecisionType
from sqlalchemy.orm import Session

def log_action(db: Session, session_id: str, action: str, decision: DecisionType, reason: str):
    log_entry = AuditLog(
        session_id=session_id,
        action=action,
        decision=decision,
        reason=reason
    )
    db.add(log_entry)
    db.commit()
