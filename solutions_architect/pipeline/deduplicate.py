
import json
from collections import defaultdict
from pathlib import Path

from solutions_architect.schemas.question import Question


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

NORMALIZED_DIR = BASE_DIR / "data" / "normalized"

INPUT_FILE = NORMALIZED_DIR / "questions.json"

OUTPUT_FILE = NORMALIZED_DIR / "unique_questions.json"

REPORT_FILE = NORMALIZED_DIR / "deduplication_report.json"


# -------------------------------------------------
# NORMALIZE ANSWERS FOR COMPARISON
# -------------------------------------------------

def normalize_answer(answer: str) -> str:
    """
    Normalize whitespace and capitalization
    for answer comparison.

    Does not modify the original stored answer.
    """

    return " ".join(answer.split()).casefold()


# -------------------------------------------------
# LOAD NORMALIZED QUESTIONS
# -------------------------------------------------

def load_questions() -> list[Question]:
    """
    Load and validate questions from
    normalized/questions.json.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            "Run normalize.py first."
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "Normalized questions must be a JSON list."
        )

    return [
        Question.model_validate(record)
        for record in data
    ]


# -------------------------------------------------
# GROUP QUESTIONS BY STABLE ID
# -------------------------------------------------

def group_questions(
    questions: list[Question]
) -> dict[str, list[Question]]:
    """
    Group questions sharing the same stable ID.
    """

    grouped = defaultdict(list)

    for question in questions:
        grouped[question.id].append(question)

    return dict(grouped)


# -------------------------------------------------
# MERGE DUPLICATE QUESTION RECORDS
# -------------------------------------------------

def merge_question_group(
    group: list[Question]
) -> tuple[Question, dict | None]:
    """
    Consolidate a group of identical questions.

    Preserve all sources and detect differences
    between their provided answers.
    """

    if not group:
        raise ValueError("Cannot merge an empty group.")

    # Make a copy so original objects are untouched.
    merged = group[0].model_copy(deep=True)

    # Preserve all source references.
    seen_sources = set()
    all_sources = []

    for question in group:
        for source in question.sources:

            source_key = (
                source.file,
                source.position
            )

            if source_key not in seen_sources:
                seen_sources.add(source_key)
                all_sources.append(source)

    merged.sources = all_sources

    # Group answer variants by normalized text.
    answer_variants = defaultdict(list)

    for question in group:
        answer_key = normalize_answer(
            question.original.answer
        )

        answer_variants[answer_key].append({
            "answer": question.original.answer,
            "sources": [
                source.model_dump()
                for source in question.sources
            ]
        })

    conflict = None

    if len(answer_variants) > 1:

        # Do not arbitrarily decide which answer
        # should be considered correct.
        merged.review.status = "needs_review"

        merged.review.notes.append(
            "Conflicting answers found in source files. "
            "The original answer is provisional."
        )

        conflict = {
            "question_id": merged.id,
            "question": merged.original.question,
            "answer_variants": [
                {
                    "normalized_answer": key,
                    "occurrences": entries
                }
                for key, entries in answer_variants.items()
            ]
        }

    return merged, conflict


# -------------------------------------------------
# DEDUPLICATE THE COMPLETE QUESTION BANK
# -------------------------------------------------

def deduplicate_questions(
    questions: list[Question]
) -> tuple[list[Question], dict]:
    """
    Consolidate duplicate questions and create
    a detailed processing report.
    """

    grouped = group_questions(questions)

    unique_questions = []
    conflicts = []
    duplicate_groups = []

    for question_id, group in grouped.items():

        merged, conflict = merge_question_group(group)

        unique_questions.append(merged)

        if len(group) > 1:
            duplicate_groups.append({
                "question_id": question_id,
                "occurrences": len(group),
                "sources": [
                    source.model_dump()
                    for source in merged.sources
                ]
            })

        if conflict is not None:
            conflicts.append(conflict)

    report = {
        "total_input_records": len(questions),
        "total_unique_questions": len(unique_questions),
        "duplicate_records_removed": (
            len(questions) - len(unique_questions)
        ),
        "duplicate_question_groups": len(duplicate_groups),
        "answer_conflict_groups": len(conflicts),
        "duplicates": duplicate_groups,
        "answer_conflicts": conflicts
    }

    return unique_questions, report


# -------------------------------------------------
# SAVE RESULTS
# -------------------------------------------------

def save_results(
    questions: list[Question],
    report: dict
) -> None:
    """
    Save the deduplicated questions
    and processing report.
    """

    NORMALIZED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            [
                question.model_dump(mode="json")
                for question in questions
            ],
            file,
            indent=2,
            ensure_ascii=False
        )

    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(f"\nSaved questions: {OUTPUT_FILE}")
    print(f"Saved report: {REPORT_FILE}")


# -------------------------------------------------
# SCRIPT ENTRY POINT
# -------------------------------------------------

def main():

    questions = load_questions()

    unique_questions, report = deduplicate_questions(
        questions
    )

    save_results(unique_questions, report)

    print("\nDeduplication Summary")
    print("----------------------")

    print(
        "Input records:",
        report["total_input_records"]
    )

    print(
        "Unique questions:",
        report["total_unique_questions"]
    )

    print(
        "Duplicate records removed:",
        report["duplicate_records_removed"]
    )

    print(
        "Duplicate groups:",
        report["duplicate_question_groups"]
    )

    print(
        "Answer conflicts:",
        report["answer_conflict_groups"]
    )


if __name__ == "__main__":
    main()
