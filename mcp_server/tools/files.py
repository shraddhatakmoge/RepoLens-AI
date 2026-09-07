import base64

from mcp_server.github import github


IGNORED_PATHS = {
    ".git",
    ".github",
    ".idea",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}


def should_include(path: str) -> bool:
    parts = path.split("/")

    if any(part in IGNORED_PATHS for part in parts):
        return False

    if path.endswith(".pyc"):
        return False

    return True


async def list_files(
    owner: str,
    repo: str,
    branch: str | None = None,
) -> dict:
    repository = await github.get(
        f"/repos/{owner}/{repo}"
    )

    if branch is None:
        branch = repository["default_branch"]

    data = await github.get(
        f"/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
    )

    files = []
    seen_paths = set()

    for item in data["tree"]:
        if item["type"] != "blob":
            continue

        path = item["path"]

        if not should_include(path):
            continue

        if path in seen_paths:
            continue

        seen_paths.add(path)

        files.append(
            {
                "path": path,
                "sha": item["sha"],
                "size": item.get("size"),
            }
        )

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "total_files": len(files),
        "truncated": data.get("truncated", False),
        "files": files,
    }


async def read_file(
    owner: str,
    repo: str,
    path: str,
    branch: str | None = None,
) -> dict:
    params = {}

    if branch:
        params["ref"] = branch

    data = await github.get(
        f"/repos/{owner}/{repo}/contents/{path}",
        params=params,
    )

    if data.get("type") != "file":
        raise ValueError(f"{path} is not a file.")

    if data.get("encoding") != "base64":
        raise ValueError("Unsupported GitHub file encoding.")

    content = base64.b64decode(data["content"]).decode(
        "utf-8",
        errors="replace",
    )

    return {
        "path": path,
        "size": data.get("size"),
        "sha": data.get("sha"),
        "content": content,
        "url": data.get("html_url"),
    }