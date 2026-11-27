
import argparse
import json
from collections import Counter
from pathlib import Path

from solutions_architect.schemas.question import Question
from solutions_architect.schemas.knowledge import (
    EvidenceMatch,
    QuestionEvidence,
)

from solutions_architect.services.knowledge_service import (
    KnowledgeService,
)


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"

QUESTIONS_FILE = (
    DATA_DIR / "normalized" / "classified_questions.json"
)

EVIDENCE_FILE = (
    DATA_DIR / "knowledge_base" / "question_evidence.json"
)

REPORT_FILE = (
    DATA_DIR / "knowledge_base" / "matching_report.json"
)


# -------------------------------------------------
# RETRIEVAL CONFIGURATION
# -------------------------------------------------

TOP_K = 5
SEARCH_DEPTH = 15

# Reciprocal Rank Fusion smoothing constant.
RRF_K = 60

# Minimum BM25 score for a candidate to enter
# the ranking process.
MIN_BM25_SCORE = 0.01


# -------------------------------------------------
# LOAD CLASSIFIED QUESTIONS
# -------------------------------------------------

def load_questions() -> list[Question]:

    if not QUESTIONS_FILE.exists():
        raise FileNotFoundError(
            f"Missing question bank: {QUESTIONS_FILE}\n"
            "Run classify.py first."
        )

    with QUESTIONS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "Classified questions must be a JSON list."
        )

    questions = [
        Question.model_validate(record)
        for record in records
    ]

    ids = [question.id for question in questions]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate question IDs found. "
            "Run deduplication before matching."
        )

    return questions


# -------------------------------------------------
# BUILD SEARCH QUERIES
# -------------------------------------------------

def build_search_queries(question: Question) -> list[str]:
    """
    Create multiple search queries representing
    the scenario, answer, and classification.

    The queries are used independently so that
    one long question cannot dominate retrieval.
    """

    classification = question.classification

    scenario_query = question.original.question

    answer_query = " ".join([
        question.original.answer,
        *classification.services
    ])

    topic_query = " ".join(
        part
        for part in [
            classification.topic,
            classification.category,
            *classification.services
        ]
        if part
    )

    queries = [
        scenario_query,
        answer_query,
        topic_query
    ]

    # Remove empty or identical queries while
    # retaining their original order.
    unique_queries = []
    seen = set()

    for query in queries:

        query = " ".join(query.split())
        normalized = query.casefold()

        if query and normalized not in seen:
            seen.add(normalized)
            unique_queries.append(query)

    return unique_queries


# -------------------------------------------------
# COMBINE SEARCH RESULTS
# -------------------------------------------------

def reciprocal_rank_fusion(
    result_lists: list[list],
    limit: int
) -> list[tuple[str, float]]:
    """
    Combine several ranked search result lists.

    RRF uses each chunk's position in the
    results rather than comparing raw BM25
    scores from different queries.

    The returned score is a ranking signal,
    not an accuracy probability.
    """

    fused_scores = {}

    for results in result_lists:

        for rank, result in enumerate(
            results,
            start=1
        ):

            chunk_id = result.chunk.chunk_id

            contribution = 1.0 / (RRF_K + rank)

            fused_scores[chunk_id] = (
                fused_scores.get(chunk_id, 0.0)
                + contribution
            )

    return sorted(
        fused_scores.items(),
        key=lambda item: (-item[1], item[0])
    )[:limit]


# -------------------------------------------------
# MATCH ONE QUESTION
# -------------------------------------------------

def match_question(
    question: Question,
    knowledge_service: KnowledgeService,
    top_k: int = TOP_K
) -> QuestionEvidence:
    """
    Retrieve relevant knowledge chunks for
    a single AWS question.

    This stage does not determine whether
    the provided answer is factually correct.
    """

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    queries = build_search_queries(question)

    result_lists = []

    for query in queries:

        results = knowledge_service.search(
            query=query,
            top_k=max(SEARCH_DEPTH, top_k),
            min_score=MIN_BM25_SCORE
        )

        result_lists.append(results)

    fused_ranking = reciprocal_rank_fusion(
        result_lists,
        limit=top_k
    )

    matches = []

    for chunk_id, score in fused_ranking:

        chunk = knowledge_service.get_chunk(chunk_id)

        if chunk is None:
            raise ValueError(
                f"Retrieved chunk disappeared: {chunk_id}"
            )

        matches.append(
            EvidenceMatch(
                question_id=question.id,
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                retrieval_method="bm25",
                relevance_score=score,
                evidence_status="retrieved"
            )
        )

    return QuestionEvidence(
        question_id=question.id,
        matches=matches,
        retrieval_status=(
            "matched" if matches else "no_match"
        )
    )


# -------------------------------------------------
# SAVE OUTPUTS SAFELY
# -------------------------------------------------

def save_json(path: Path, data) -> None:
    """
    Write to a temporary file before replacing
    the output to avoid partially written JSON.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    temporary_file.replace(path)


# -------------------------------------------------
# MATCH THE QUESTION BANK
# -------------------------------------------------

def match_all_questions(
    limit: int | None = None,
    question_id: str | None = None,
    top_k: int = TOP_K
) -> None:

    questions = load_questions()

    if question_id is not None:
        questions = [
            question
            for question in questions
            if question.id == question_id
        ]

        if not questions:
            raise ValueError(
                f"Question not found: {question_id}"
            )

    if limit is not None:
        questions = questions[:limit]

    if not questions:
        raise ValueError("No questions selected.")

    # Load the BM25 index only once.
    knowledge_service = KnowledgeService()

    all_evidence = []
    report_items = []

    print("\nQuestion-to-Knowledge Matching")
    print("------------------------------")
    print(f"Questions selected: {len(questions)}")
    print(
        "Knowledge chunks:",
        len(knowledge_service.chunks)
    )

    for index, question in enumerate(
        questions,
        start=1
    ):

        evidence = match_question(
            question,
            knowledge_service,
            top_k=top_k
        )

        all_evidence.append(evidence)

        top_match = (
            evidence.matches[0]
            if evidence.matches
            else None
        )

        # Report source-answer conflicts separately.
        # Retrieval must not erase these flags.
        report_items.append({
            "question_id": question.id,
            "retrieval_status": evidence.retrieval_status,
            "source_answer_review_status": (
                question.review.status
            ),
            "matches_found": len(evidence.matches),
            "top_chunk_id": (
                top_match.chunk_id
                if top_match
                else None
            ),
            "top_source_id": (
                top_match.source_id
                if top_match
                else None
            )
        })

        print(
            f"[{index}/{len(questions)}] "
            f"{question.id}: "
            f"{len(evidence.matches)} matches"
        )

    status_counts = Counter(
        record.retrieval_status
        for record in all_evidence
    )

    review_counts = Counter(
        item["source_answer_review_status"]
        for item in report_items
    )

    report = {
        "questions_processed": len(questions),
        "knowledge_chunks_indexed": (
            len(knowledge_service.chunks)
        ),
        "matches_per_question_limit": top_k,
        "retrieval_status_counts": dict(status_counts),
        "source_answer_review_counts": dict(review_counts),
        "questions": report_items
    }

    save_json(
        EVIDENCE_FILE,
        [
            record.model_dump(mode="json")
            for record in all_evidence
        ]
    )

    save_json(
        REPORT_FILE,
        report
    )

    print("\nMatching Summary")
    print("----------------")
    print(f"Questions: {len(all_evidence)}")
    print(
        "Matched:",
        status_counts.get("matched", 0)
    )
    print(
        "No matches:",
        status_counts.get("no_match", 0)
    )
    print(f"Saved: {EVIDENCE_FILE}")
    print(f"Report: {REPORT_FILE}")


# -------------------------------------------------
# COMMAND LINE ENTRY POINT
# -------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Match AWS exam questions to locally "
            "indexed study-guide sections."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum questions to process."
    )

    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Process a specific question ID."
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help="Evidence chunks per question."
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    match_all_questions(
        limit=args.limit,
        question_id=args.id,
        top_k=args.top_k
    )


if __name__ == "__main__":
    main()
