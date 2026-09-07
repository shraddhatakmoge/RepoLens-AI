import os

import httpx
import streamlit as st


st.set_page_config(
    page_title="RepoLens AI",
    page_icon="🔎",
    layout="wide",
)


API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000",
)


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

    </style>
    """,
    unsafe_allow_html=True,
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


def api_get(path: str):
    response = httpx.get(
        f"{API_URL}{path}",
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
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


def api_delete(path: str):
    response = httpx.delete(
        f"{API_URL}{path}",
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


def parse_repo_url(url: str):
    parts = url.rstrip("/").split("/")

    if len(parts) < 2:
        raise ValueError(
            "Invalid GitHub repository URL."
        )

    return parts[-2], parts[-1]


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
def confirm_delete_chat(chat):

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


with st.sidebar:

    st.title("🔎 RepoLens AI")

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

        chats = api_get("/chats")

        chats = [
            chat
            for chat in chats
            if chat["title"] != "New Chat"
        ]

    except Exception as e:

        chats = []

        st.error(
            f"Unable to load chats: {e}"
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

                        except Exception as e:

                            st.error(
                                f"Unable to rename chat: {e}"
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


if st.button("Analyze Repository"):

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

        except Exception as e:

            st.error(
                f"Repository indexing failed: {e}"
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

            if e.response.status_code == 404:

                st.session_state.current_thread_id = None

                st.rerun()

            else:

                st.error(
                    f"Unable to load chat: {e}"
                )

                history = []

        except Exception as e:

            st.error(
                f"Unable to load chat: {e}"
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

        st.subheader("💬 New Chat")

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

            with st.chat_message("user"):

                st.write(question)

            with st.chat_message("assistant"):

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
                            st.session_state
                            .current_thread_id
                        ),
                    },
                )

                status.update(
                    label="✍️ Writing...",
                    state="running",
                    expanded=False,
                )

                answer = result["answer"]

                st.write(answer)

                status.update(
                    label="✅ Done",
                    state="complete",
                    expanded=False,
                )

        except httpx.HTTPStatusError as e:

            st.error(
                f"API request failed: "
                f"{e.response.text}"
            )

        except Exception as e:

            st.error(
                f"Something went wrong: {e}"
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