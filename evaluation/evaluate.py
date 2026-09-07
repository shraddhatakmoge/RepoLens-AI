import json
import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)

from src.config.logging_config import get_logger, setup_logging
from src.rag.retriever import retrieve


setup_logging()

logger = get_logger(__name__)


DATASET_PATH = Path("evaluation/dataset.json")
RESULTS_PATH = Path("evaluation/results.json")


def load_dataset():
    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_unique_paths(documents):
    paths = []

    for document in documents:
        path = document.metadata.get("path")

        if path and path not in paths:
            paths.append(path)

    return paths


def calculate_hit(
    retrieved_paths,
    expected_files,
    k,
):
    top_k = retrieved_paths[:k]

    return any(
        expected_file in top_k
        for expected_file in expected_files
    )


def calculate_recall(
    retrieved_paths,
    expected_files,
    k,
):
    top_k = retrieved_paths[:k]

    retrieved_expected = sum(
        expected_file in top_k
        for expected_file in expected_files
    )

    return retrieved_expected / len(expected_files)


def evaluate(
    owner,
    repo,
):
    dataset = load_dataset()

    namespace = f"{owner}-{repo}"

    total = len(dataset)

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_4 = 0
    recall_at_4 = 0

    failed = 0

    evaluation_results = []

    logger.info(
        "Evaluation started: repository=%s/%s | questions=%s",
        owner,
        repo,
        total,
    )

    for index, item in enumerate(
        dataset,
        start=1,
    ):
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

            hit_1 = calculate_hit(
                retrieved_paths,
                expected_files,
                1,
            )

            hit_3 = calculate_hit(
                retrieved_paths,
                expected_files,
                3,
            )

            hit_4 = calculate_hit(
                retrieved_paths,
                expected_files,
                4,
            )

            recall_4 = calculate_recall(
                retrieved_paths,
                expected_files,
                4,
            )

            if hit_1:
                hit_at_1 += 1

            if hit_3:
                hit_at_3 += 1

            if hit_4:
                hit_at_4 += 1

            recall_at_4 += recall_4

            result = {
                "question_number": index,
                "question": question,
                "expected_files": expected_files,
                "retrieved_files": retrieved_paths[:4],
                "hit_at_1": hit_1,
                "hit_at_3": hit_3,
                "hit_at_4": hit_4,
                "recall_at_4": recall_4,
            }

            evaluation_results.append(result)

            print()
            print(
                f"Question {index}: {question}"
            )
            print(
                f"Expected: {expected_files}"
            )
            print(
                f"Retrieved: {retrieved_paths[:4]}"
            )
            print(
                f"Hit@1={hit_1} | "
                f"Hit@3={hit_3} | "
                f"Hit@4={hit_4} | "
                f"Recall@4={recall_4:.2f}"
            )

        except Exception:
            failed += 1

            logger.exception(
                "Evaluation failed for question %s",
                index,
            )

            evaluation_results.append(
                {
                    "question_number": index,
                    "question": question,
                    "expected_files": expected_files,
                    "retrieved_files": [],
                    "hit_at_1": False,
                    "hit_at_3": False,
                    "hit_at_4": False,
                    "recall_at_4": 0,
                    "error": True,
                }
            )

    successful = total - failed

    if successful == 0:
        print(
            "No questions were evaluated successfully."
        )
        return

    metrics = {
        "total_questions": total,
        "successful": successful,
        "failed": failed,
        "hit_at_1": hit_at_1 / successful,
        "hit_at_3": hit_at_3 / successful,
        "hit_at_4": hit_at_4 / successful,
        "recall_at_4": recall_at_4 / successful,
    }

    output = {
        "repository": f"{owner}/{repo}",
        "namespace": namespace,
        "metrics": metrics,
        "questions": evaluation_results,
    }

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=4,
        )

    print()
    print("=" * 60)
    print("RepoLens AI Retrieval Evaluation")
    print("=" * 60)

    print(
        f"Total questions : {total}"
    )

    print(
        f"Successful      : {successful}"
    )

    print(
        f"Failed          : {failed}"
    )

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

    print()
    print(
        f"Detailed results saved to: {RESULTS_PATH}"
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