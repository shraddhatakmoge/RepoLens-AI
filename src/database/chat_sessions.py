from datetime import datetime, timedelta, timezone
import uuid

import psycopg
from cryptography.fernet import Fernet

from src.config.settings import settings


logger = __import__("logging").getLogger(__name__)


cipher = Fernet(
    settings.auth_encryption_key.encode()
)


def get_connection():

    return psycopg.connect(
        settings.database_url,
        row_factory=psycopg.rows.dict_row,
    )


def init_database():

    connection = get_connection()

    try:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                thread_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                github_login TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )

        connection.execute(
            """
            ALTER TABLE chat_sessions
            ADD COLUMN IF NOT EXISTS github_login TEXT
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_github_login
            ON chat_sessions(github_login)
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                github_login TEXT NOT NULL,
                github_token TEXT NOT NULL,
                github_refresh_token TEXT,
                token_expires_at TIMESTAMPTZ,
                refresh_token_expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                auth_code TEXT,
                auth_code_exchange_expires_at TIMESTAMPTZ
            )
            """
        )

        connection.execute(
            """
            ALTER TABLE auth_sessions
            ADD COLUMN IF NOT EXISTS auth_code TEXT
            """
        )

        connection.execute(
            """
            ALTER TABLE auth_sessions
            ADD COLUMN IF NOT EXISTS auth_code_exchange_expires_at TIMESTAMPTZ
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_auth_code
            ON auth_sessions(auth_code)
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS repository_index_status (
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (owner, repo)
            )
            """
        )

        connection.commit()

        logger.info(
            "Database initialization completed"
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to initialize database"
        )

        raise

    finally:

        connection.close()


def get_indexed_repository(
    owner: str,
    repo: str,
):

    connection = get_connection()

    try:

        return connection.execute(
            """
            SELECT *
            FROM repository_index_status
            WHERE owner = %s
              AND repo = %s
            """,
            (
                owner,
                repo,
            ),
        ).fetchone()

    except Exception:

        logger.exception(
            "Failed to retrieve repository index status"
        )

        raise

    finally:

        connection.close()


def save_indexed_repository(
    owner: str,
    repo: str,
    commit_sha: str,
):

    connection = get_connection()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    try:

        connection.execute(
            """
            INSERT INTO repository_index_status (
                owner,
                repo,
                commit_sha,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (owner, repo)
            DO UPDATE SET
                commit_sha = EXCLUDED.commit_sha,
                updated_at = EXCLUDED.updated_at
            """,
            (
                owner,
                repo,
                commit_sha,
                now,
            ),
        )

        connection.commit()

        logger.info(
            "Repository index status saved: repository=%s/%s | commit=%s",
            owner,
            repo,
            commit_sha,
        )

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to save repository index status"
        )

        raise

    finally:

        connection.close()


def create_auth_session(
    github_login: str,
    github_token: str,
    github_refresh_token: str | None = None,
    token_expires_at: str | None = None,
    refresh_token_expires_at: str | None = None,
    session_id: str | None = None,
):

    connection = get_connection()

    session_id = (
        session_id
        or str(uuid.uuid4())
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    encrypted_token = cipher.encrypt(
        github_token.encode()
    ).decode()

    encrypted_refresh_token = None

    if github_refresh_token:

        encrypted_refresh_token = cipher.encrypt(
            github_refresh_token.encode()
        ).decode()

    try:

        row = connection.execute(
            """
            INSERT INTO auth_sessions (
                session_id,
                github_login,
                github_token,
                github_refresh_token,
                token_expires_at,
                refresh_token_expires_at,
                created_at,
                updated_at,
                auth_code,
                auth_code_exchange_expires_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING *
            """,
            (
                session_id,
                github_login,
                encrypted_token,
                encrypted_refresh_token,
                token_expires_at,
                refresh_token_expires_at,
                now,
                now,
                None,
                None,
            ),
        ).fetchone()

        connection.commit()

        if row:

            row["github_token"] = github_token
            row["github_refresh_token"] = github_refresh_token

        return row

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to create GitHub auth session"
        )

        raise

    finally:

        connection.close()


def get_auth_session(
    session_id: str,
):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT *
            FROM auth_sessions
            WHERE session_id = %s
            """,
            (
                session_id,
            ),
        ).fetchone()

        if not row:
            return None

        row["github_token"] = cipher.decrypt(
            row["github_token"].encode()
        ).decode()

        if row["github_refresh_token"]:

            row["github_refresh_token"] = cipher.decrypt(
                row["github_refresh_token"].encode()
            ).decode()

        return row

    except Exception:

        logger.exception(
            "Failed to retrieve GitHub auth session"
        )

        raise

    finally:

        connection.close()


def exchange_auth_session(
    auth_code: str,
    new_session_id: str,
):

    connection = get_connection()

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(minutes=5)
    reuse_cutoff = now + timedelta(seconds=60)

    try:

        row = connection.execute(
            """
            SELECT *
            FROM auth_sessions
            WHERE session_id = %s
              AND created_at >= %s
            FOR UPDATE
            """,
            (
                auth_code,
                cutoff.isoformat(),
            ),
        ).fetchone()

        if row:

            connection.execute(
                """
                UPDATE auth_sessions
                SET
                    session_id = %s,
                    updated_at = %s,
                    auth_code = %s,
                    auth_code_exchange_expires_at = %s
                WHERE session_id = %s
                """,
                (
                    new_session_id,
                    now.isoformat(),
                    auth_code,
                    reuse_cutoff.isoformat(),
                    auth_code,
                ),
            )

            row["session_id"] = new_session_id
            row["updated_at"] = now
            row["auth_code"] = auth_code
            row["auth_code_exchange_expires_at"] = reuse_cutoff

            connection.commit()

            row["github_token"] = cipher.decrypt(
                row["github_token"].encode()
            ).decode()

            if row["github_refresh_token"]:

                row["github_refresh_token"] = cipher.decrypt(
                    row["github_refresh_token"].encode()
                ).decode()

            logger.info(
                "GitHub auth session exchanged: login=%s",
                row["github_login"],
            )

            return row

        row = connection.execute(
            """
            SELECT *
            FROM auth_sessions
            WHERE auth_code = %s
              AND auth_code_exchange_expires_at >= %s
            FOR UPDATE
            """,
            (
                auth_code,
                now.isoformat(),
            ),
        ).fetchone()

        if not row:

            connection.rollback()

            return None

        connection.commit()

        row["github_token"] = cipher.decrypt(
            row["github_token"].encode()
        ).decode()

        if row["github_refresh_token"]:

            row["github_refresh_token"] = cipher.decrypt(
                row["github_refresh_token"].encode()
            ).decode()

        logger.info(
            "GitHub auth session reused during handoff: login=%s",
            row["github_login"],
        )

        return row

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to exchange GitHub auth session"
        )

        raise

    finally:

        connection.close()


def delete_auth_session(
    session_id: str,
):

    connection = get_connection()

    try:

        connection.execute(
            """
            DELETE FROM auth_sessions
            WHERE session_id = %s
            """,
            (
                session_id,
            ),
        )

        connection.commit()

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to delete GitHub auth session"
        )

        raise

    finally:

        connection.close()


def create_chat_session(
    thread_id: str,
    owner: str,
    repo: str,
    github_login: str,
    title: str = "New Chat",
):

    if not github_login:
        raise ValueError(
            "GitHub login is required to create a chat session."
        )

    connection = get_connection()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    try:

        row = connection.execute(
            """
            INSERT INTO chat_sessions (
                thread_id,
                owner,
                repo,
                github_login,
                title,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING *
            """,
            (
                thread_id,
                owner,
                repo,
                github_login,
                title,
                now,
                now,
            ),
        ).fetchone()

        connection.commit()

        return row

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to create chat session"
        )

        raise

    finally:

        connection.close()


def get_chat_sessions(
    github_login: str,
):

    if not github_login:
        raise ValueError(
            "GitHub login is required to retrieve chat sessions."
        )

    connection = get_connection()

    try:

        return connection.execute(
            """
            SELECT *
            FROM chat_sessions
            WHERE github_login = %s
            ORDER BY updated_at DESC
            """,
            (
                github_login,
            ),
        ).fetchall()

    except Exception:

        logger.exception(
            "Failed to retrieve chat sessions"
        )

        raise

    finally:

        connection.close()


def get_chat_session(
    thread_id: str,
    github_login: str,
):

    if not github_login:
        raise ValueError(
            "GitHub login is required to retrieve a chat session."
        )

    connection = get_connection()

    try:

        return connection.execute(
            """
            SELECT *
            FROM chat_sessions
            WHERE thread_id = %s
              AND github_login = %s
            """,
            (
                thread_id,
                github_login,
            ),
        ).fetchone()

    except Exception:

        logger.exception(
            "Failed to retrieve chat session"
        )

        raise

    finally:

        connection.close()


def rename_chat_session(
    thread_id: str,
    title: str,
    github_login: str,
):

    if not github_login:
        raise ValueError(
            "GitHub login is required to rename a chat session."
        )

    connection = get_connection()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    try:

        row = connection.execute(
            """
            UPDATE chat_sessions
            SET
                title = %s,
                updated_at = %s
            WHERE thread_id = %s
              AND github_login = %s
            RETURNING *
            """,
            (
                title,
                now,
                thread_id,
                github_login,
            ),
        ).fetchone()

        connection.commit()

        return row

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to rename chat session"
        )

        raise

    finally:

        connection.close()


def delete_chat_session(
    thread_id: str,
    github_login: str,
):

    if not github_login:
        raise ValueError(
            "GitHub login is required to delete a chat session."
        )

    connection = get_connection()

    try:

        connection.execute(
            """
            DELETE FROM chat_sessions
            WHERE thread_id = %s
              AND github_login = %s
            """,
            (
                thread_id,
                github_login,
            ),
        )

        connection.commit()

    except Exception:

        connection.rollback()

        logger.exception(
            "Failed to delete chat session"
        )

        raise

    finally:

        connection.close()


init_database()