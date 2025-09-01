import sqlite3
import os

DB_FILE = "ai_assistant.db"

def init_db(db_path=DB_FILE):
    """Initializes the database and creates tables if they don't exist."""
    # This check is important for testing, where we might re-initialize often.
    # For production, this function would typically run only once.
    db_is_new = not os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if db_is_new:
        cursor = conn.cursor()

        # Users Table
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Chat Sessions Table
        cursor.execute("""
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)

        # Chat Messages Table
        cursor.execute("""
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
        )
        """)

        # User Facts Table (for RAG)
        cursor.execute("""
        CREATE TABLE user_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, fact_key)
        )
        """)

        conn.commit()
        print(f"Database '{db_path}' initialized.")

    conn.close()

def get_or_create_user(db_conn, username="default_user"):
    """Get a user by username, or create them if they don't exist."""
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user:
        user_id = user['id']
    else:
        cursor.execute("INSERT INTO users (username) VALUES (?)", (username,))
        db_conn.commit()
        user_id = cursor.lastrowid
    return user_id

def create_chat_session(db_conn, session_id, user_id, title="New Conversation"):
    """Creates a new chat session."""
    db_conn.execute(
        "INSERT OR IGNORE INTO chat_sessions (id, user_id, title) VALUES (?, ?, ?)",
        (session_id, user_id, title)
    )
    db_conn.commit()

def add_chat_message(db_conn, session_id, role, content):
    """Adds a message to a chat session's history."""
    db_conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    db_conn.commit()
    # Update session title with the first user message
    if role == 'user':
        cursor = db_conn.cursor()
        cursor.execute("SELECT title FROM chat_sessions WHERE id = ?", (session_id,))
        title = cursor.fetchone()['title']
        if title == "New Conversation":
            new_title = content[:50]
            db_conn.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (new_title, session_id))
            db_conn.commit()


def get_session_history(db_conn, session_id):
    """Retrieves the message history for a given session."""
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    history = [dict(row) for row in cursor.fetchall()]
    return history

def get_all_sessions(db_conn, user_id):
    """Retrieves all sessions for a given user."""
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT id, title FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    sessions = [dict(row) for row in cursor.fetchall()]
    return sessions

def get_latest_session(db_conn, user_id):
    """Retrieves the most recent session for a given user."""
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT id, title FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    session = cursor.fetchone()
    if session:
        return dict(session)
    return None

def save_fact(db_conn, user_id, fact_key, fact_value):
    """Saves a fact for a given user, updating if it exists."""
    db_conn.execute(
        """
        INSERT INTO user_facts (user_id, fact_key, fact_value)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, fact_key) DO UPDATE SET
        fact_value = excluded.fact_value,
        created_at = CURRENT_TIMESTAMP
        """,
        (user_id, fact_key, fact_value)
    )
    db_conn.commit()
    return f"Fact '{fact_key}' saved."

def get_user_facts(db_conn, user_id):
    """Retrieves all facts for a given user."""
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT fact_key, fact_value FROM user_facts WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    facts = [dict(row) for row in cursor.fetchall()]
    return facts

def delete_session(db_conn, session_id):
    """Deletes a session and all its messages."""
    cursor = db_conn.cursor()
    # Use a transaction to ensure both deletes succeed or fail together
    try:
        cursor.execute("BEGIN")
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        cursor.execute("COMMIT")
        return {"status": "success", "message": "Session deleted."}
    except Exception as e:
        cursor.execute("ROLLBACK")
        raise e

def update_session_title(db_conn, session_id, new_title):
    """Updates the title of a chat session."""
    db_conn.execute(
        "UPDATE chat_sessions SET title = ? WHERE id = ?",
        (new_title, session_id)
    )
    db_conn.commit()
    return {"status": "success", "message": "Session title updated."}
