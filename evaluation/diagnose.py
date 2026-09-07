import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)

from src.vectorstore.pinecone_store import (
    similarity_search,
    bm25_search,
    reciprocal_rank_fusion,
    rerank_documents,
)
from src.config.logging_config import setup_logging


setup_logging()


DATASET_PATH = Path("evaluation/dataset.json")


def load_dataset():
    import json

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_paths(documents):
    paths = []

    for document in documents:
        path = document.metadata.get("path")

        if path and path not in paths:
            paths.append(path)

    return paths


def contains_expected(
    paths,
    expected_files,
):
    return any(
        expected_file in paths
        for expected_file in expected_files
    )


def diagnose(owner, repo):

    dataset = load_dataset()

    namespace = f"{owner}-{repo}"

    print()
    print("=" * 70)
    print("RepoLens Retrieval Diagnosis")
    print("=" * 70)

    for index, item in enumerate(
        dataset,
        start=1,
    ):

        question = item["question"]
        expected_files = item["expected_files"]

        dense_results = similarity_search(
            query=question,
            namespace=namespace,
            k=20,
        )

        bm25_results = bm25_search(
            query=question,
            namespace=namespace,
            k=20,
        )

        fused_results = reciprocal_rank_fusion(
            result_lists=[
                dense_results,
                bm25_results,
            ],
            k=15,
        )

        final_results = rerank_documents(
            query=question,
            documents=fused_results,
            k=4,
        )

        dense_paths = get_paths(
            dense_results
        )

        bm25_paths = get_paths(
            bm25_results
        )

        fused_paths = get_paths(
            fused_results
        )

        final_paths = get_paths(
            final_results
        )

        if contains_expected(
            final_paths,
            expected_files,
        ):
            continue

        print()
        print("-" * 70)
        print(f"Question {index}: {question}")
        print(f"Expected: {expected_files}")
        print()

        print(
            f"1. Dense Top 20: "
            f"{contains_expected(dense_paths, expected_files)}"
        )

        print(
            f"   {dense_paths}"
        )

        print()

        print(
            f"2. BM25 Top 20: "
            f"{contains_expected(bm25_paths, expected_files)}"
        )

        print(
            f"   {bm25_paths}"
        )

        print()

        print(
            f"3. RRF Top 15: "
            f"{contains_expected(fused_paths, expected_files)}"
        )

        print(
            f"   {fused_paths}"
        )

        print()

        print(
            f"4. BGE Top 4: "
            f"{contains_expected(final_paths, expected_files)}"
        )

        print(
            f"   {final_paths}"
        )

    print()
    print("=" * 70)
    print("Diagnosis completed")
    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) != 3:
        print(
            "Usage: uv run python evaluation/diagnose.py <owner> <repo>"
        )
        sys.exit(1)

    diagnose(
        owner=sys.argv[1],
        repo=sys.argv[2],
    )