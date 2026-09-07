from mcp_server.github import github


async def get_repository(owner: str, repo: str) -> dict:
    data = await github.get(f"/repos/{owner}/{repo}")

    return {
        "name": data["name"],
        "full_name": data["full_name"],
        "description": data["description"],
        "default_branch": data["default_branch"],
        "language": data["language"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "url": data["html_url"],
    }


async def get_readme(
    owner: str,
    repo: str,
    branch: str | None = None,
) -> dict:
    params = {}

    if branch:
        params["ref"] = branch

    data = await github.get(
        f"/repos/{owner}/{repo}/readme",
        params=params,
    )

    import base64

    content = base64.b64decode(data["content"]).decode(
        "utf-8",
        errors="replace",
    )

    return {
        "name": data["name"],
        "path": data["path"],
        "content": content,
        "url": data["html_url"],
    }