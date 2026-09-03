from sqlalchemy import Column, String, Integer, Float, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserType(enum.Enum):
    human = "human"
    agent = "agent"

class DecisionType(enum.Enum):
    allowed = "allowed"
    blocked = "blocked"

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    category = Column(String, index=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    attributes = Column(JSON) 

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, index=True)
    user_type = Column(Enum(UserType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String, nullable=False) # user, agent, tool
    message = Column(String, nullable=False)
    reasoning_trace = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class CartItem(Base):
    __tablename__ = "cart_items"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    product_id = Column(String, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    razorpay_order_id = Column(String)
    status = Column(String, default="created")
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    action = Column(String, nullable=False)
    decision = Column(Enum(DecisionType), nullable=False)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TrustPolicy(Base):
    __tablename__ = "trust_policies"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    rule_type = Column(String, nullable=False) # e.g. "max_cart_value"
    threshold_value = Column(Float, nullable=False)
