import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("data/chat_history.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()
    connection.close()


def create_conversation(
    owner: str,
    repo: str,
    title: str = "New Chat",
):
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO conversations
        (id, title, owner, repo, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            title,
            owner,
            repo,
            now,
            now,
        ),
    )

    connection.commit()
    connection.close()

    return conversation_id


def get_conversations():
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM conversations
        ORDER BY updated_at DESC
        """
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_messages(conversation_id: str):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        """,
        (conversation_id,),
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def add_message(
    conversation_id: str,
    role: str,
    content: str,
):
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO messages
        (id, conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            role,
            content,
            now,
        ),
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (
            now,
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def update_title(
    conversation_id: str,
    title: str,
):
    connection = get_connection()

    connection.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ?
        """,
        (
            title,
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()