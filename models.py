from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, UniqueConstraint, Index
from sqlalchemy.orm import mapped_column, Mapped
from config.db import Base

class BrokerCredential(Base):
    __tablename__ = "broker_credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    broker: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(80), default="default")
    key_id_enc: Mapped[str] = mapped_column(String(512))
    secret_key_enc: Mapped[str] = mapped_column(String(1024))
    base_url_enc: Mapped[str] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("user_id","broker","label", name="uq_cred_user_broker_label"),
        Index("ix_cred_user_active","user_id","is_active"),
    )

class TickSize(Base):
    __tablename__ = "tick_sizes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    exchange: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str] = mapped_column(String(40))
    tick_size: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id","exchange","symbol", name="uq_tick_user_ex_sym"),)
