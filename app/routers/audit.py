from fastapi import APIRouter, Depends
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.db.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs")
def get_logs(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return logs
