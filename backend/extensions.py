import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

basedir = os.path.abspath(os.path.dirname(__file__))
DATABASE_URL = "sqlite+aiosqlite:///" + os.path.join(basedir, "ai_assistant.db")

async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionMaker = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()
