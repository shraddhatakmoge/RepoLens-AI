from mcp_server.github import github


async def search_code(
    owner: str,
    repo: str,
    query: str,
) -> dict:
    search_query = f"{query} repo:{owner}/{repo}"

    data = await github.get(
        "/search/code",
        params={
            "q": search_query,
            "per_page": 30,
        },
    )

    results = [
        {
            "name": item["name"],
            "path": item["path"],
            "sha": item["sha"],
            "url": item["html_url"],
        }
        for item in data.get("items", [])
    ]

    return {
        "query": query,
        "repository": f"{owner}/{repo}",
        "total_matches": data.get("total_count", 0),
        "results": results,
    }