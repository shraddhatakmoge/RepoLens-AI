import httpx

from src.config.logging_config import get_logger
from src.config.settings import settings


logger = get_logger(__name__)


class GitHubClient:

    def __init__(self):
        self.base_url = "https://api.github.com"

    def headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "Authorization": f"Bearer {settings.github_token}",
        }

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ):

        url = f"{self.base_url}{endpoint}"

        logger.info(
            "GitHub API request: endpoint=%s",
            endpoint,
        )

        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:

                response = await client.get(
                    url,
                    headers=self.headers(),
                    params=params,
                )

        except httpx.TimeoutException:

            logger.exception(
                "GitHub API request timed out: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub API request timed out."
            )

        except httpx.RequestError:

            logger.exception(
                "GitHub API request failed: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "Unable to connect to GitHub."
            )

        logger.info(
            "GitHub API response: endpoint=%s | status=%s",
            endpoint,
            response.status_code,
        )

        if response.status_code == 404:

            logger.warning(
                "GitHub resource not found: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub resource not found."
            )

        if response.status_code == 401:

            logger.error(
                "GitHub authentication failed: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub token is invalid or expired."
            )

        if response.status_code == 403:

            logger.warning(
                "GitHub access denied or rate limited: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub API access denied or rate limit exceeded."
            )

        if response.status_code == 429:

            logger.warning(
                "GitHub rate limit exceeded: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub API rate limit exceeded."
            )

        try:
            response.raise_for_status()

        except httpx.HTTPStatusError:

            logger.exception(
                "GitHub API returned an unexpected error: endpoint=%s | status=%s",
                endpoint,
                response.status_code,
            )

            raise ValueError(
                "GitHub API request failed."
            )

        try:
            data = response.json()

        except ValueError:

            logger.exception(
                "Invalid JSON response from GitHub: endpoint=%s",
                endpoint,
            )

            raise ValueError(
                "GitHub returned an invalid response."
            )

        logger.info(
            "GitHub API request completed: endpoint=%s",
            endpoint,
        )

        return data


github = GitHubClient()