import json
import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)

from src.rag.retriever import retrieve
from src.config.logging_config import setup_logging, get_logger


setup_logging()

logger = get_logger(__name__)


DATASET_PATH = Path("evaluation/dataset.json")


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def get_unique_paths(documents):
    paths = []

    for document in documents:
        path = document.metadata.get("path")

        if path and path not in paths:
            paths.append(path)

    return paths


def calculate_hit(retrieved_paths, expected_files, k):
    top_k = retrieved_paths[:k]

    return any(
        file in top_k
        for file in expected_files
    )


def calculate_recall(retrieved_paths, expected_files, k):
    top_k = retrieved_paths[:k]

    retrieved_expected = sum(
        file in top_k
        for file in expected_files
    )

    return retrieved_expected / len(expected_files)


def evaluate(owner, repo):
    dataset = load_dataset()

    namespace = f"{owner}-{repo}"

    total = len(dataset)

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_4 = 0

    recall_at_4 = 0

    failed = 0

    logger.info(
        "Evaluation started: repository=%s/%s | questions=%s",
        owner,
        repo,
        total,
    )

    for index, item in enumerate(dataset, start=1):

        question = item["question"]
        expected_files = item["expected_files"]

        logger.info(
            "Evaluating question %s/%s: %s",
            index,
            total,
            question,
        )

        try:
            documents = retrieve(
                query=question,
                namespace=namespace,
                k=4,
            )

            retrieved_paths = get_unique_paths(
                documents
            )

            if calculate_hit(
                retrieved_paths,
                expected_files,
                1,
            ):
                hit_at_1 += 1

            if calculate_hit(
                retrieved_paths,
                expected_files,
                3,
            ):
                hit_at_3 += 1

            if calculate_hit(
                retrieved_paths,
                expected_files,
                4,
            ):
                hit_at_4 += 1

            recall_at_4 += calculate_recall(
                retrieved_paths,
                expected_files,
                4,
            )

            print()
            print(f"Question {index}: {question}")
            print(f"Expected: {expected_files}")
            print(f"Retrieved: {retrieved_paths[:4]}")

        except Exception:
            failed += 1

            logger.exception(
                "Evaluation failed for question %s",
                index,
            )

    successful = total - failed

    print()
    print("=" * 60)
    print("RepoLens AI Retrieval Evaluation")
    print("=" * 60)

    if successful == 0:
        print("No questions were evaluated successfully.")
        return

    print(f"Total questions : {total}")
    print(f"Successful      : {successful}")
    print(f"Failed          : {failed}")
    print()

    print(
        f"Hit@1           : {hit_at_1 / successful:.2%}"
    )

    print(
        f"Hit@3           : {hit_at_3 / successful:.2%}"
    )

    print(
        f"Hit@4           : {hit_at_4 / successful:.2%}"
    )

    print(
        f"Recall@4        : {recall_at_4 / successful:.2%}"
    )

    print("=" * 60)


if __name__ == "__main__":

    if len(sys.argv) != 3:
        print(
            "Usage: uv run python evaluation/evaluate.py <owner> <repo>"
        )
        sys.exit(1)

    owner = sys.argv[1]
    repo = sys.argv[2]

    evaluate(
        owner=owner,
        repo=repo,
    )