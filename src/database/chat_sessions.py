import os
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from src.config.logging_config import get_logger


logger = get_logger(__name__)


import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    connection = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )

    logger.debug(
        "PostgreSQL database connection opened"
    )

    return connection


def init_chat_sessions():

    logger.info(
        "Initializing chat sessions database"
    )

    connection = get_connection()

    try:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

        logger.info(
            "Chat sessions table initialized successfully"
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to initialize chat sessions table"
        )

        raise

    finally:

        connection.close()


def create_chat_session(
    thread_id: str,
    owner: str,
    repo: str,
    title: str = "New Chat",
):

    logger.info(
        "Creating chat session: thread_id=%s | repository=%s/%s",
        thread_id,
        owner,
        repo,
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    try:

        connection.execute(
            """
            INSERT INTO chat_sessions
            (thread_id, title, owner, repo, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                thread_id,
                title,
                owner,
                repo,
                now,
                now,
            ),
        )

        connection.commit()

        logger.info(
            "Chat session created successfully: thread_id=%s",
            thread_id,
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to create chat session: thread_id=%s",
            thread_id,
        )

        raise

    finally:

        connection.close()


def get_chat_sessions():

    logger.info(
        "Fetching chat sessions"
    )

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT *
            FROM chat_sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()

        sessions = list(rows)

        logger.info(
            "Chat sessions fetched: sessions=%s",
            len(sessions),
        )

        return sessions

    except Exception:

        logger.exception(
            "Failed to fetch chat sessions"
        )

        raise

    finally:

        connection.close()


def update_chat_session(
    thread_id: str,
    title: str,
):

    logger.info(
        "Updating chat session: thread_id=%s | title=%s",
        thread_id,
        title,
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    try:

        connection.execute(
            """
            UPDATE chat_sessions
            SET title = %s, updated_at = %s
            WHERE thread_id = %s
            """,
            (
                title,
                now,
                thread_id,
            ),
        )

        connection.commit()

        logger.info(
            "Chat session updated successfully: thread_id=%s",
            thread_id,
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to update chat session: thread_id=%s",
            thread_id,
        )

        raise

    finally:

        connection.close()


def delete_chat_session(
    thread_id: str,
):

    logger.info(
        "Deleting chat session: thread_id=%s",
        thread_id,
    )

    connection = get_connection()

    try:

        connection.execute(
            """
            DELETE FROM chat_sessions
            WHERE thread_id = %s
            """,
            (thread_id,),
        )

        connection.commit()

        logger.info(
            "Chat session deleted successfully: thread_id=%s",
            thread_id,
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to delete chat session: thread_id=%s",
            thread_id,
        )

        raise

    finally:

        connection.close()