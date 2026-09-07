from pathlib import Path

from src.config.logging_config import get_logger


logger = get_logger(__name__)


ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".xml",
    ".sh",
    ".bat",
    ".ps1",
}

ALLOWED_FILENAMES = {
    "README",
    "LICENSE",
    "Dockerfile",
    "Makefile",
}

EXCLUDED_DIRECTORIES = {
    ".git",
    ".github",
    "node_modules",
    "evaluation",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage",
}

MAX_FILE_SIZE = 200_000


def is_useful_file(
    path: str,
    size: int | None = None,
) -> bool:

    path_obj = Path(path)

    if any(
        part in EXCLUDED_DIRECTORIES
        for part in path_obj.parts
    ):
        logger.debug(
            "File excluded: path=%s | reason=excluded_directory",
            path,
        )
        return False

    if path_obj.name in {
        ".env",
        ".env.local",
        ".env.production",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    }:
        logger.debug(
            "File excluded: path=%s | reason=excluded_filename",
            path,
        )
        return False

    if path_obj.name not in ALLOWED_FILENAMES:
        if path_obj.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.debug(
                "File excluded: path=%s | reason=unsupported_extension",
                path,
            )
            return False

    if size is not None and size > MAX_FILE_SIZE:
        logger.debug(
            "File excluded: path=%s | size=%s | max_size=%s",
            path,
            size,
            MAX_FILE_SIZE,
        )
        return False

    return True