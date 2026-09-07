from mcp_server.github import github


async def get_commits(
    owner: str,
    repo: str,
    limit: int = 10,
) -> dict:
    limit = max(1, min(limit, 100))

    data = await github.get(
        f"/repos/{owner}/{repo}/commits",
        params={"per_page": limit},
    )

    commits = []

    for commit in data:
        commits.append(
            {
                "sha": commit["sha"],
                "message": commit["commit"]["message"],
                "author": commit["commit"]["author"]["name"],
                "date": commit["commit"]["author"]["date"],
                "url": commit["html_url"],
            }
        )

    return {
        "repository": f"{owner}/{repo}",
        "count": len(commits),
        "commits": commits,
    }