from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    api_id = Column(Integer, ForeignKey("apis.id"), nullable=False, index=True)
    price_monthly = Column(Numeric(10, 2), default=0)
    description = Column(Text, nullable=True)
    max_rps = Column(Integer, default=0, nullable=False)
    period = Column(String(20), default="/월", nullable=False)
    features = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api = relationship("Api", back_populates="plans")
    user_api_plans = relationship("UserApiPlan", back_populates="plan")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)

    apis = relationship("Api", back_populates="company")


class Api(Base):
    __tablename__ = "apis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    task_key = Column(String(100), nullable=True)
    task_label = Column(String(100), nullable=True)
    card_sublabel = Column(String(200), nullable=True)
    model_display = Column(String(100), nullable=True)
    tags = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    company = relationship("Company", back_populates="apis")
    plans = relationship("Plan", back_populates="api")
    user_api_plans = relationship("UserApiPlan", back_populates="api")


class UserApiPlan(Base):
    __tablename__ = "user_api_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    api_id = Column(Integer, ForeignKey("apis.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "api_id", name="uq_user_api_plan"),)

    user = relationship("User", back_populates="user_api_plans")
    api = relationship("Api", back_populates="user_api_plans")
    plan = relationship("Plan", back_populates="user_api_plans")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user_api_plans = relationship("UserApiPlan", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(500), nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")
