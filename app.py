import os
import time

import httpx
import streamlit as st
from streamlit_cookies_controller import CookieController


st.set_page_config(
    page_title="RepoLens AI",
    page_icon="🔎",
    layout="wide",
)


API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000",
)

AUTH_COOKIE_NAME = "repolens_session"
AUTH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


st.markdown(
    """
    <style>

    div[data-testid="stPopover"] button svg {
        display: none !important;
    }

    div[data-testid="stPopover"] button {
        justify-content: center !important;
        align-items: center !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    div[data-testid="element-container"]:has(
        iframe[title*="streamlit_cookies_controller"]
    ) {
        display: none;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


controller = CookieController(
    key="repolens_auth_cookie"
)


if "current_thread_id" not in st.session_state:
    st.session_state.current_thread_id = None

if "repo_ready" not in st.session_state:
    st.session_state.repo_ready = False

if "owner" not in st.session_state:
    st.session_state.owner = None

if "repo" not in st.session_state:
    st.session_state.repo = None

if "active_menu" not in st.session_state:
    st.session_state.active_menu = None

if "rename_chat_id" not in st.session_state:
    st.session_state.rename_chat_id = None

if "delete_chat_id" not in st.session_state:
    st.session_state.delete_chat_id = None

if "auth_session_id" not in st.session_state:
    st.session_state.auth_session_id = None

if "github_login" not in st.session_state:
    st.session_state.github_login = None

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def exchange_auth_code(
    auth_code: str,
):

    response = httpx.post(
        f"{API_URL}/auth/exchange",
        json={
            "auth_code": auth_code,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def remove_auth_cookie():

    try:

        if controller.get(AUTH_COOKIE_NAME) is not None:
            controller.remove(AUTH_COOKIE_NAME)

    except Exception:
        pass


def save_auth_session(
    session_id: str,
    github_login: str,
):

    st.session_state.auth_session_id = session_id
    st.session_state.github_login = github_login
    st.session_state.authenticated = True

    is_local = (
        st.context.url.startswith("http://localhost")
        or st.context.url.startswith("http://127.0.0.1")
    )

    controller.set(
        AUTH_COOKIE_NAME,
        session_id,
        max_age=AUTH_COOKIE_MAX_AGE,
        secure=not is_local,
        same_site="lax",
    )

    time.sleep(0.5)


def restore_auth_session():

    try:

        controller.refresh()

        time.sleep(0.2)

        cookie_session_id = controller.get(
            AUTH_COOKIE_NAME
        )

        if not cookie_session_id:
            return False

        response = httpx.get(
            f"{API_URL}/auth/me",
            headers={
                "X-RepoLens-Session": cookie_session_id
            },
            timeout=30,
        )

        if response.status_code != 200:

            remove_auth_cookie()

            return False

        data = response.json()

        st.session_state.auth_session_id = (
            cookie_session_id
        )

        st.session_state.github_login = (
            data["github_login"]
        )

        st.session_state.authenticated = True

        return True

    except Exception:

        return False


def api_headers():

    if not st.session_state.auth_session_id:
        return {}

    return {
        "X-RepoLens-Session": (
            st.session_state.auth_session_id
        )
    }


def api_get(
    path: str,
):

    response = httpx.get(
        f"{API_URL}{path}",
        headers=api_headers(),
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


def api_post(
    path: str,
    payload: dict,
):

    response = httpx.post(
        f"{API_URL}{path}",
        json=payload,
        headers=api_headers(),
        timeout=300,
    )

    response.raise_for_status()

    return response.json()


def api_patch(
    path: str,
    payload: dict,
):

    response = httpx.patch(
        f"{API_URL}{path}",
        json=payload,
        headers=api_headers(),
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


def api_delete(
    path: str,
):

    response = httpx.delete(
        f"{API_URL}{path}",
        headers=api_headers(),
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


def friendly_api_error(
    response: httpx.Response,
    action: str,
):

    messages = {
        400: "Please check the information provided and try again.",
        401: "Your GitHub session has expired. Please sign in again.",
        403: "You do not have permission to access this resource.",
        404: (
            f"We couldn't find the requested {action}. "
            "Please check the details and try again."
        ),
        409: (
            "This request could not be completed because "
            "of a conflict. Please try again."
        ),
        422: (
            f"We couldn't process the {action}. "
            "Please check the repository and try again."
        ),
        429: (
            "Too many requests right now. "
            "Please wait a moment and try again."
        ),
        500: (
            f"We couldn't complete {action} right now. "
            "Please try again in a few minutes."
        ),
        502: (
            f"The AI service is temporarily unavailable "
            f"while processing {action}. Please try again shortly."
        ),
        503: (
            f"The service is temporarily unavailable "
            f"while processing {action}. Please try again shortly."
        ),
        504: (
            f"{action.capitalize()} took too long to complete. "
            "Please try again."
        ),
    }

    return messages.get(
        response.status_code,
        (
            f"Something went wrong while processing "
            f"{action}. Please try again."
        ),
    )


def logout():

    try:

        if st.session_state.auth_session_id:

            api_post(
                "/auth/logout",
                {},
            )

    except Exception:
        pass

    remove_auth_cookie()

    st.session_state.auth_session_id = None
    st.session_state.github_login = None
    st.session_state.authenticated = False
    st.session_state.current_thread_id = None
    st.session_state.repo_ready = False
    st.session_state.owner = None
    st.session_state.repo = None

    st.query_params.clear()

    st.rerun()


def parse_repo_url(
    url: str,
):

    parts = url.rstrip("/").split("/")

    if len(parts) < 2:

        raise ValueError(
            "Invalid GitHub repository URL."
        )

    owner = parts[-2]
    repo = parts[-1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:

        raise ValueError(
            "Invalid GitHub repository URL."
        )

    return owner, repo


def create_chat():

    result = api_post(
        "/chats",
        {
            "owner": st.session_state.owner,
            "repo": st.session_state.repo,
        },
    )

    st.session_state.current_thread_id = (
        result["thread_id"]
    )


@st.dialog("Delete chat?")
def confirm_delete_chat(
    chat,
):

    st.write(
        f"This will permanently delete **{chat['title']}**."
    )

    st.caption(
        "Your repository data in Pinecone will not be deleted."
    )

    col1, col2 = st.columns(
        2,
        gap="small",
    )

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True,
        ):

            st.session_state.delete_chat_id = None

            st.rerun()

    with col2:

        if st.button(
            "Delete",
            type="primary",
            use_container_width=True,
        ):

            try:

                api_delete(
                    f"/chats/{chat['thread_id']}"
                )

                if (
                    st.session_state.current_thread_id
                    == chat["thread_id"]
                ):

                    st.session_state.current_thread_id = None

                st.session_state.delete_chat_id = None
                st.session_state.rename_chat_id = None

                st.rerun()

            except httpx.HTTPStatusError as e:

                st.error(
                    friendly_api_error(
                        e.response,
                        "chat deletion",
                    )
                )

            except httpx.TimeoutException:

                st.error(
                    "Deleting the chat took too long. "
                    "Please try again."
                )

            except Exception:

                st.error(
                    "We couldn't delete this chat right now. "
                    "Please try again."
                )


auth_code = st.query_params.get(
    "auth_code"
)


if not st.session_state.authenticated:

    restore_auth_session()


if auth_code and not st.session_state.authenticated:

    try:

        with st.spinner(
            "Signing you in with GitHub..."
        ):

            result = exchange_auth_code(
                auth_code
            )

        save_auth_session(
            session_id=result["session_id"],
            github_login=result["github_login"],
        )

        st.query_params.clear()

        st.rerun()

    except httpx.HTTPStatusError as e:

        remove_auth_cookie()

        st.query_params.clear()

        if e.response.status_code == 401:

            st.error(
                "GitHub authentication could not be completed. "
                "Please sign in again."
            )

        else:

            st.error(
                friendly_api_error(
                    e.response,
                    "GitHub authentication",
                )
            )

    except httpx.TimeoutException:

        remove_auth_cookie()

        st.query_params.clear()

        st.error(
            "GitHub sign-in took too long. "
            "Please try again."
        )

    except Exception:

        remove_auth_cookie()

        st.query_params.clear()

        st.error(
            "We couldn't complete GitHub sign-in. "
            "Please try again."
        )


if not st.session_state.authenticated:

    st.title("🔎 RepoLens AI")

    st.subheader(
        "GitHub Repository Investigator"
    )

    st.write(
        "Sign in with GitHub to analyze public "
        "and private repositories you have access to."
    )

    st.html(
        f"""
        <a
            href="{API_URL}/auth/github/login"
            target="_self"
            style="
                display: block;
                width: 100%;
                padding: 0.75rem 1rem;
                text-align: center;
                border: 1px solid rgba(128, 128, 128, 0.5);
                border-radius: 0.5rem;
                text-decoration: none;
                color: inherit;
                font-weight: 600;
                box-sizing: border-box;
            "
        >
            🐙 Continue with GitHub
        </a>
        """
    )

    st.stop()


with st.sidebar:

    st.title("🔎 RepoLens AI")

    st.caption(
        f"GitHub: @{st.session_state.github_login}"
    )

    if st.button(
        "Logout",
        use_container_width=True,
    ):

        logout()

    st.divider()

    if st.button(
        "＋ New Chat",
        use_container_width=True,
    ):

        if st.session_state.repo_ready:

            st.session_state.current_thread_id = None
            st.session_state.active_menu = None
            st.session_state.rename_chat_id = None

            st.rerun()

        else:

            st.info(
                "Analyze a repository first."
            )

    st.divider()

    st.caption("Chats")

    try:

        chats = api_get(
            "/chats"
        )

        chats = [
            chat
            for chat in chats
            if chat["title"] != "New Chat"
        ]

    except httpx.HTTPStatusError as e:

        if e.response.status_code == 401:

            logout()

        chats = []

    except Exception:

        chats = []

        st.error(
            "Unable to load your chats right now. "
            "Please try again."
        )

    for chat in chats:

        row_col, menu_col = st.columns(
            [6, 1],
            gap="small",
        )

        with row_col:

            if st.button(
                chat["title"],
                key=f"chat_{chat['thread_id']}",
                use_container_width=True,
            ):

                st.session_state.current_thread_id = (
                    chat["thread_id"]
                )

                st.session_state.owner = (
                    chat["owner"]
                )

                st.session_state.repo = (
                    chat["repo"]
                )

                st.session_state.repo_ready = True
                st.session_state.active_menu = None
                st.session_state.rename_chat_id = None

                st.rerun()

        with menu_col:

            with st.popover(
                "⋮",
                use_container_width=True,
            ):

                if st.button(
                    "Rename",
                    key=f"rename_{chat['thread_id']}",
                    use_container_width=True,
                ):

                    st.session_state.rename_chat_id = (
                        chat["thread_id"]
                    )

                    st.rerun()

                if st.button(
                    "Delete",
                    key=f"delete_{chat['thread_id']}",
                    use_container_width=True,
                ):

                    st.session_state.delete_chat_id = (
                        chat["thread_id"]
                    )

                    st.rerun()

        if (
            st.session_state.rename_chat_id
            == chat["thread_id"]
        ):

            new_title = st.text_input(
                "Rename chat",
                value=chat["title"],
                key=f"rename_input_{chat['thread_id']}",
            )

            rename_col1, rename_col2 = st.columns(
                2,
                gap="small",
            )

            with rename_col1:

                if st.button(
                    "Save",
                    key=f"save_rename_{chat['thread_id']}",
                    use_container_width=True,
                ):

                    new_title = new_title.strip()

                    if new_title:

                        try:

                            api_patch(
                                f"/chats/{chat['thread_id']}",
                                {
                                    "title": new_title,
                                },
                            )

                            st.session_state.rename_chat_id = None

                            st.rerun()

                        except httpx.HTTPStatusError as e:

                            st.error(
                                friendly_api_error(
                                    e.response,
                                    "chat rename",
                                )
                            )

                        except httpx.TimeoutException:

                            st.error(
                                "Renaming the chat took too long. "
                                "Please try again."
                            )

                        except Exception:

                            st.error(
                                "We couldn't rename this chat right now. "
                                "Please try again."
                            )

            with rename_col2:

                if st.button(
                    "Cancel",
                    key=f"cancel_rename_{chat['thread_id']}",
                    use_container_width=True,
                ):

                    st.session_state.rename_chat_id = None

                    st.rerun()


st.caption(
    "AI-powered GitHub Repository Investigator"
)


repo_url = st.text_input(
    "GitHub Repository URL",
    placeholder="https://github.com/owner/repository",
)


if st.button(
    "Analyze Repository"
):

    if not repo_url:

        st.error(
            "Enter a GitHub repository URL."
        )

    else:

        try:

            owner, repo = parse_repo_url(
                repo_url
            )

            with st.status(
                "🔎 Reading repository...",
                expanded=False,
            ) as status:

                result = api_post(
                    "/repositories/index",
                    {
                        "owner": owner,
                        "repo": repo,
                    },
                )

                documents_count = result[
                    "documents"
                ]

                chunks_count = result[
                    "chunks"
                ]

                status.update(
                    label="✅ Repository ready",
                    state="complete",
                    expanded=False,
                )

            st.session_state.owner = owner
            st.session_state.repo = repo
            st.session_state.repo_ready = True
            st.session_state.current_thread_id = None

            st.success(
                f"Repository indexed: "
                f"{documents_count} files → "
                f"{chunks_count} chunks"
            )

            st.rerun()

        except ValueError:

            st.error(
                "Please enter a valid GitHub repository URL."
            )

        except httpx.HTTPStatusError as e:

            if e.response.status_code == 401:

                logout()

            else:

                st.error(
                    friendly_api_error(
                        e.response,
                        "repository analysis",
                    )
                )

        except httpx.TimeoutException:

            st.error(
                "Repository analysis is taking longer than expected. "
                "Please try again in a moment."
            )

        except Exception:

            st.error(
                "We couldn't analyze this repository right now. "
                "Please check the repository URL and your GitHub access, "
                "then try again."
            )


if st.session_state.repo_ready:

    chat = None

    if st.session_state.current_thread_id:

        try:

            result = api_get(
                f"/chats/{st.session_state.current_thread_id}"
            )

            chat = result["chat"]
            history = result["history"]

        except httpx.HTTPStatusError as e:

            if e.response.status_code == 401:

                logout()

            elif e.response.status_code == 404:

                st.session_state.current_thread_id = None

                st.rerun()

            else:

                st.error(
                    friendly_api_error(
                        e.response,
                        "chat",
                    )
                )

                history = []

        except httpx.TimeoutException:

            st.error(
                "Loading this chat took too long. "
                "Please try again."
            )

            history = []

        except Exception:

            st.error(
                "We couldn't load this chat right now. "
                "Please try again."
            )

            history = []

    else:

        history = []

    st.divider()

    if chat:

        st.subheader(
            f"💬 {chat['title']}"
        )

        for message in history:

            with st.chat_message(
                message["role"]
            ):

                st.write(
                    message["content"]
                )

    else:

        st.subheader(
            "💬 New Chat"
        )

    question = st.chat_input(
        "Ask anything about this repository..."
    )

    if question:

        try:

            if not st.session_state.current_thread_id:

                create_chat()

                result = api_get(
                    f"/chats/{st.session_state.current_thread_id}"
                )

                chat = result["chat"]

            if chat["title"] == "New Chat":

                title = question.strip()

                if len(title) > 40:

                    title = (
                        title[:40]
                        .rstrip()
                        + "..."
                    )

                api_patch(
                    f"/chats/{chat['thread_id']}",
                    {
                        "title": title,
                    },
                )

                chat["title"] = title

            with st.chat_message(
                "user"
            ):

                st.write(
                    question
                )

            with st.chat_message(
                "assistant"
            ):

                status = st.status(
                    "💭 Thinking...",
                    expanded=False,
                )

                result = api_post(
                    "/chat",
                    {
                        "question": question,
                        "owner": (
                            st.session_state.owner
                        ),
                        "repo": (
                            st.session_state.repo
                        ),
                        "thread_id": (
                            st.session_state.current_thread_id
                        ),
                    },
                )

                status.update(
                    label="✍️ Writing...",
                    state="running",
                    expanded=False,
                )

                answer = result[
                    "answer"
                ]

                st.write(
                    answer
                )

                status.update(
                    label="✅ Done",
                    state="complete",
                    expanded=False,
                )

        except httpx.HTTPStatusError as e:

            if e.response.status_code == 401:

                logout()

            else:

                st.error(
                    friendly_api_error(
                        e.response,
                        "your chat request",
                    )
                )

        except httpx.TimeoutException:

            st.error(
                "The request took too long to complete. "
                "Please try again."
            )

        except Exception:

            st.error(
                "Something went wrong while processing your request. "
                "Please try again."
            )

        else:

            st.rerun()

    st.divider()

    st.caption(
        f"Repository: "
        f"{st.session_state.owner}/"
        f"{st.session_state.repo}"
    )


if st.session_state.delete_chat_id:

    delete_chat = next(
        (
            chat
            for chat in chats
            if chat["thread_id"]
            == st.session_state.delete_chat_id
        ),
        None,
    )

    if delete_chat:

        confirm_delete_chat(
            delete_chat
        )