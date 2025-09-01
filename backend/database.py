from .app import db_sql_alchemy as db
from .models import User, ChatSession, ChatMessage, UserFact
from sqlalchemy import desc

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    db.create_all()

def get_or_create_user(username="default_user"):
    """Get a user by username, or create them if they don't exist."""
    user = User.query.filter_by(username=username).first()
    if user:
        return user

    new_user = User(username=username)
    db.session.add(new_user)
    db.session.commit()
    return new_user

def create_chat_session(session_id, user_id, title="New Conversation"):
    """Creates a new chat session if it doesn't exist."""
    session = db.session.get(ChatSession, session_id)
    if not session:
        new_session = ChatSession(id=session_id, user_id=user_id, title=title)
        db.session.add(new_session)
        db.session.commit()

def add_chat_message(session_id, role, content):
    """Adds a message to a chat session's history."""
    message = ChatMessage(session_id=session_id, role=role, content=content)
    db.session.add(message)

    # Update session title with the first user message
    if role == 'user':
        session = ChatSession.query.get(session_id)
        if session and session.title == "New Conversation":
            session.title = content[:50]

    db.session.commit()

def get_session_history(session_id):
    """Retrieves the message history for a given session."""
    session = db.session.get(ChatSession, session_id)
    if not session:
        return []

    # Assuming messages are ordered by their primary key `id` which is auto-incrementing
    messages = sorted(session.messages, key=lambda m: m.created_at)
    return [{'role': msg.role, 'content': msg.content} for msg in messages]

def get_all_sessions(user_id):
    """Retrieves all sessions for a given user."""
    user = db.session.get(User, user_id)
    if not user:
        return []
    sessions = sorted(user.sessions, key=lambda s: s.created_at, reverse=True)
    return [{'id': s.id, 'title': s.title} for s in sessions]

def get_latest_session(user_id):
    """Retrieves the most recent session for a given user."""
    session = ChatSession.query.filter_by(user_id=user_id).order_by(desc(ChatSession.created_at)).first()
    if session:
        return {'id': session.id, 'title': session.title}
    return None

def save_fact(user_id, fact_key, fact_value):
    """Saves a fact for a given user, updating if it exists."""
    fact = UserFact.query.filter_by(user_id=user_id, fact_key=fact_key).first()
    if fact:
        fact.fact_value = fact_value
    else:
        fact = UserFact(user_id=user_id, fact_key=fact_key, fact_value=fact_value)
        db.session.add(fact)
    db.session.commit()
    return f"Fact '{fact_key}' saved."

def get_user_facts(user_id):
    """Retrieves all facts for a given user."""
    user = db.session.get(User, user_id)
    if not user:
        return []
    facts = sorted(user.facts, key=lambda f: f.created_at, reverse=True)
    return [{'fact_key': f.fact_key, 'fact_value': f.fact_value} for f in facts]

def delete_session(session_id):
    """Deletes a session and all its messages."""
    session = db.session.get(ChatSession, session_id)
    if session:
        db.session.delete(session)
        db.session.commit()
        return {"status": "success", "message": "Session deleted."}
    return {"status": "error", "message": "Session not found."}

def update_session_title(session_id, new_title):
    """Updates the title of a chat session."""
    session = db.session.get(ChatSession, session_id)
    if session:
        session.title = new_title
        db.session.commit()
        return {"status": "success", "message": "Session title updated."}
    return {"status": "error", "message": "Session not found."}
