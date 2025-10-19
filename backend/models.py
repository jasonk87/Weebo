from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from .extensions import Base

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    sessions = relationship('ChatSession', back_populates='user', lazy='selectin')
    facts = relationship('UserFact', back_populates='user', lazy='selectin')

class ChatSession(Base):
    __tablename__ = 'chat_session'
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    title = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    user = relationship('User', back_populates='sessions')
    messages = relationship('ChatMessage', back_populates='session', lazy='selectin', cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = 'chat_message'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey('chat_session.id'), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    session = relationship('ChatSession', back_populates='messages')

class UserFact(Base):
    __tablename__ = 'user_fact'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    fact_key = Column(String(100), nullable=False)
    fact_value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    user = relationship('User', back_populates='facts')
    __table_args__ = (UniqueConstraint('user_id', 'fact_key', name='_user_fact_uc'),)
