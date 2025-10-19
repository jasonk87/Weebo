from sqlalchemy.future import select
from sqlalchemy import desc
from .extensions import AsyncSessionMaker, async_engine, Base
from .models import User, ChatSession, ChatMessage, UserFact

async def init_db():
    """Initializes the database and creates tables if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_or_create_user(username="default_user"):
    """Get a user by username, or create them if they don't exist."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(select(User).filter_by(username=username))
        user = result.scalar_one_or_none()
        if user:
            return user

        new_user = User(username=username)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user

async def create_chat_session(session_id, user_id, title="New Conversation"):
    """Creates a new chat session if it doesn't exist."""
    async with AsyncSessionMaker() as session:
        session_obj = await session.get(ChatSession, session_id)
        if not session_obj:
            new_session = ChatSession(id=session_id, user_id=user_id, title=title)
            session.add(new_session)
            await session.commit()

async def add_chat_message(session_id, role, content):
    """Adds a message to a chat session's history."""
    async with AsyncSessionMaker() as session:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        session.add(message)

        if role == 'user':
            session_obj = await session.get(ChatSession, session_id)
            if session_obj and session_obj.title == "New Conversation":
                session_obj.title = content[:50]

        await session.commit()

async def get_session_history(session_id):
    """Retrieves the message history for a given session."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(
            select(ChatSession).filter_by(id=session_id)
        )
        session_obj = result.scalar_one_or_none()
        if not session_obj:
            return []

        messages = sorted(session_obj.messages, key=lambda m: m.created_at)
        return [{'role': msg.role, 'content': msg.content} for msg in messages]

async def get_all_sessions(user_id):
    """Retrieves all sessions for a given user."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(
            select(User).filter_by(id=user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return []

        sessions = sorted(user.sessions, key=lambda s: s.created_at, reverse=True)
        return [{'id': s.id, 'title': s.title} for s in sessions]

async def get_latest_session(user_id):
    """Retrieves the most recent session for a given user."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(
            select(ChatSession)
            .filter_by(user_id=user_id)
            .order_by(desc(ChatSession.created_at))
            .limit(1)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj:
            return {'id': session_obj.id, 'title': session_obj.title}
        return None

async def save_fact(user_id, fact_key, fact_value):
    """Saves a fact for a given user, updating if it exists."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(
            select(UserFact).filter_by(user_id=user_id, fact_key=fact_key)
        )
        fact = result.scalar_one_or_none()
        if fact:
            fact.fact_value = fact_value
        else:
            fact = UserFact(user_id=user_id, fact_key=fact_key, fact_value=fact_value)
            session.add(fact)

        await session.commit()
        return f"Fact '{fact_key}' saved."

async def get_user_facts(user_id):
    """Retrieves all facts for a given user."""
    async with AsyncSessionMaker() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            return []

        facts = sorted(user.facts, key=lambda f: f.created_at, reverse=True)
        return [{'fact_key': f.fact_key, 'fact_value': f.fact_value} for f in facts]

async def delete_session(session_id):
    """Deletes a session and all its messages."""
    async with AsyncSessionMaker() as session:
        session_obj = await session.get(ChatSession, session_id)
        if session_obj:
            await session.delete(session_obj)
            await session.commit()
            return {"status": "success", "message": "Session deleted."}
        return {"status": "error", "message": "Session not found."}

async def update_session_title(session_id, new_title):
    """Updates the title of a chat session."""
    async with AsyncSessionMaker() as session:
        session_obj = await session.get(ChatSession, session_id)
        if session_obj:
            session_obj.title = new_title
            await session.commit()
            return {"status": "success", "message": "Session title updated."}
        return {"status": "error", "message": "Session not found."}
