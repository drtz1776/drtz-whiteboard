
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from solutions_architect.schemas.question import Question
from solutions_architect.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeManifest,
)


# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

CLASSIFIED_FILE = (
    DATA_DIR / "normalized" / "classified_questions.json"
)

ENRICHED_FILE = (
    DATA_DIR / "enriched" / "enriched_questions.json"
)

TAXONOMY_FILE = DATA_DIR / "taxonomy.json"

KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"

CHUNKS_FILE = KNOWLEDGE_DIR / "chunks.json"

MANIFEST_FILE = (
    KNOWLEDGE_DIR / "source_manifest.json"
)

REPORT_FILE = (
    DATA_DIR / "review" / "validation_report.json"
)


# -------------------------------------------------
# JSON UTILITIES
# -------------------------------------------------

def read_json(path: Path):

    if not path.exists():
        raise FileNotFoundError(
            f"Required file missing: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    temporary.replace(path)


# -------------------------------------------------
# LOAD TAXONOMY
# -------------------------------------------------

def load_taxonomy() -> dict[str, set[str]]:
    """
    Map topic names to permitted category names.

    Matches the values stored by classify.py.
    """

    taxonomy = read_json(TAXONOMY_FILE)

    lookup = {}

    for topic in taxonomy["topics"]:

        lookup[topic["name"]] = {
            category["name"]
            for category in topic["categories"]
        }

    return lookup


# -------------------------------------------------
# LOAD KNOWLEDGE BASE
# -------------------------------------------------

def load_knowledge():

    chunks = [
        KnowledgeChunk.model_validate(record)
        for record in read_json(CHUNKS_FILE)
    ]

    manifest = KnowledgeManifest.model_validate(
        read_json(MANIFEST_FILE)
    )

    if len(chunks) != manifest.total_chunks:
        raise ValueError(
            "Knowledge manifest chunk count mismatch."
        )

    chunk_ids = [c.chunk_id for c in chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate knowledge chunk IDs."
        )

    source_ids = [
        source.source_id
        for source in manifest.sources
    ]

    if len(source_ids) != len(set(source_ids)):
        raise ValueError(
            "Duplicate knowledge source IDs."
        )

    source_map = {
        source.source_id: source
        for source in manifest.sources
    }

    chunk_map = {}

    for chunk in chunks:

        if chunk.source_id not in source_map:
            raise ValueError(
                f"Unknown source for {chunk.chunk_id}"
            )

        if chunk.end_line < chunk.start_line:
            raise ValueError(
                f"Invalid line range: {chunk.chunk_id}"
            )

        chunk_map[chunk.chunk_id] = chunk

    return chunk_map, source_map


# -------------------------------------------------
# LOAD ORIGINAL CLASSIFIED DATASET
# -------------------------------------------------

def load_classified_questions() -> dict[str, Question]:

    records = read_json(CLASSIFIED_FILE)

    questions = [
        Question.model_validate(record)
        for record in records
    ]

    ids = [q.id for q in questions]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate IDs in classified question bank."
        )

    return {
        question.id: question
        for question in questions
    }


# -------------------------------------------------
# NORMALIZE TEXT FOR CLUE MATCHING
# -------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize whitespace and case.

    We deliberately do not use fuzzy matching
    because clues should refer to real phrases.
    """

    return " ".join(
        text.casefold().split()
    )


# -------------------------------------------------
# VALIDATE CLASSIFICATION
# -------------------------------------------------

def check_classification(
    question: Question,
    taxonomy: dict,
    errors: list[str]
) -> None:

    classification = question.classification

    if not classification.topic:
        errors.append("Missing primary topic")
        return

    if classification.topic not in taxonomy:
        errors.append(
            f"Unknown topic: {classification.topic}"
        )
        return

    if not classification.category:
        errors.append("Missing primary category")
        return

    allowed = taxonomy[classification.topic]

    if classification.category not in allowed:
        errors.append(
            "Category does not belong to topic: "
            f"{classification.category}"
        )


# -------------------------------------------------
# VALIDATE LEARNING CONTENT
# -------------------------------------------------

def check_learning(
    question: Question,
    errors: list[str]
) -> None:

    learning = question.learning

    required_text = {
        "title": learning.title,
        "scenario_summary": learning.scenario_summary,
        "heuristic.pattern": learning.heuristic.pattern,
        "heuristic.decision_rule": (
            learning.heuristic.decision_rule
        ),
        "exam_takeaway": learning.exam_takeaway
    }

    for field_name, value in required_text.items():

        if not value.strip():
            errors.append(
                f"Missing learning field: {field_name}"
            )

    required_lists = {
        "requirements": learning.requirements,
        "key_clues": learning.key_clues,
        "service_breakdown": (
            learning.service_breakdown
        ),
        "why_answer_wins": (
            learning.why_answer_wins
        )
    }

    for field_name, values in required_lists.items():

        if not values:
            errors.append(
                f"Missing learning content: {field_name}"
            )

    # Validate individual requirements.
    for requirement in learning.requirements:

        if not requirement.strip():
            errors.append("Empty requirement")

    # Validate clue phrases against the question.
    original_text = normalize_text(
        question.original.question
    )

    for clue in learning.key_clues:

        phrase = normalize_text(clue.phrase)

        if not phrase:
            errors.append("Empty clue phrase")

        elif phrase not in original_text:
            errors.append(
                "Clue not found in original question: "
                + clue.phrase
            )

        if not clue.meaning.strip():
            errors.append(
                "Missing explanation for clue: "
                + clue.phrase
            )

    # Check service explanation completeness.
    for service in learning.service_breakdown:

        if not service.name.strip():
            errors.append("Unnamed AWS service")

        if not service.role.strip():
            errors.append(
                f"Missing role for {service.name}"
            )

        if not service.important_facts:
            errors.append(
                f"No technical facts for {service.name}"
            )

        if any(
            not fact.strip()
            for fact in service.important_facts
        ):
            errors.append(
                f"Empty technical fact for {service.name}"
            )

    for reason in learning.why_answer_wins:

        if not reason.strip():
            errors.append(
                "Empty answer explanation"
            )


# -------------------------------------------------
# VALIDATE ORIGINAL DATA INTEGRITY
# -------------------------------------------------

def check_original(
    question: Question,
    original: Question,
    errors: list[str]
) -> None:
    """
    Ensure enrichment did not silently
    rewrite the original question or answer.
    """

    if question.original != original.original:
        errors.append(
            "Original question or answer changed"
        )

    if question.sources != original.sources:
        errors.append(
            "Original source references changed"
        )

    if question.classification != original.classification:
        errors.append(
            "Classification changed during enrichment"
        )


# -------------------------------------------------
# VALIDATE CITATION REFERENCES
# -------------------------------------------------

def check_evidence(
    question: Question,
    chunk_map: dict,
    source_map: dict,
    errors: list[str]
) -> set[str]:
    """
    Check citation integrity and source identity.

    This checks metadata consistency, not
    whether the reference proves a claim.
    """

    references = question.verification.sources

    cited_ids = set()

    for reference in references:

        if reference.chunk_id in cited_ids:
            errors.append(
                "Duplicate citation: "
                + reference.chunk_id
            )

        cited_ids.add(reference.chunk_id)

        chunk = chunk_map.get(
            reference.chunk_id
        )

        source = source_map.get(
            reference.source_id
        )

        if chunk is None:
            errors.append(
                "Unknown knowledge chunk: "
                + reference.chunk_id
            )
            continue

        if source is None:
            errors.append(
                "Unknown knowledge source: "
                + reference.source_id
            )
            continue

        if chunk.source_id != reference.source_id:
            errors.append(
                "Chunk/source mismatch: "
                + reference.chunk_id
            )

        if reference.source_type != source.source_type:
            errors.append(
                "Source type mismatch: "
                + reference.chunk_id
            )

        if reference.revision != source.revision:
            errors.append(
                "Source revision mismatch: "
                + reference.chunk_id
            )

        if (
            reference.start_line != chunk.start_line
            or reference.end_line != chunk.end_line
        ):
            errors.append(
                "Citation line range mismatch: "
                + reference.chunk_id
            )

        if not reference.url.startswith(
            source.url + "#L"
        ):
            errors.append(
                "Citation URL mismatch: "
                + reference.chunk_id
            )

    # Every claim citation must correspond
    # to a recorded question source reference.
    for claim in question.verification.claims:

        for evidence_id in claim.evidence_ids:

            if evidence_id not in cited_ids:
                errors.append(
                    "Claim uses unrecorded evidence: "
                    + evidence_id
                )

    return cited_ids


# -------------------------------------------------
# EXTRACT EXPECTED CLAIMS
# -------------------------------------------------

def expected_claims(question: Question) -> set[str]:
    """
    Mirror verify.py's claim extraction.
    """

    learning = question.learning

    claims = list(learning.why_answer_wins)

    if learning.heuristic.decision_rule.strip():
        claims.append(
            learning.heuristic.decision_rule
        )

    for service in learning.service_breakdown:
        claims.extend(service.important_facts)

    claims.extend(
        learning.alternatives_and_tradeoffs
    )

    return {
        claim.strip()
        for claim in claims
        if claim.strip()
    }


# -------------------------------------------------
# VALIDATE VERIFICATION CONSISTENCY
# -------------------------------------------------

def check_verification(
    question: Question,
    cited_ids: set[str],
    errors: list[str],
    warnings: list[str]
) -> None:

    verification = question.verification
    status = verification.status

    if status == "pending":
        warnings.append(
            "Evidence audit has not been completed"
        )

    if not cited_ids:
        warnings.append(
            "No knowledge source citations"
        )

    expected = expected_claims(question)

    actual = [
        claim.claim
        for claim in verification.claims
    ]

    if status != "pending":

        if set(actual) != expected:
            errors.append(
                "Verified claims do not match "
                "the current explanation"
            )

        if len(actual) != len(set(actual)):
            errors.append(
                "Duplicate verification claims"
            )

    claim_statuses = {
        claim.status
        for claim in verification.claims
    }

    for claim in verification.claims:

        if (
            claim.status == "supported"
            and not claim.evidence_ids
        ):
            errors.append(
                "Supported claim has no citation: "
                + claim.claim
            )

    if status == "guide_supported":

        if verification.answer_supported is not True:
            errors.append(
                "Guide-supported answer is not marked supported"
            )

        if claim_statuses != {"supported"}:
            errors.append(
                "Guide-supported record contains "
                "unresolved claims"
            )

        if verification.flags:
            errors.append(
                "Guide-supported record has unresolved flags"
            )

    if status == "verified":

        official_sources = [
            ref
            for ref in verification.sources
            if ref.source_type == "aws_documentation"
        ]

        if not official_sources:
            errors.append(
                "Verified record lacks official AWS sources"
            )

        if not verification.reviewed_at:
            errors.append(
                "Verified record lacks review timestamp"
            )

        if verification.answer_supported is not True:
            errors.append(
                "Verified answer is not marked supported"
            )

        if claim_statuses != {"supported"}:
            errors.append(
                "Verified record has unresolved claims"
            )

        if verification.flags:
            errors.append(
                "Verified record contains unresolved flags"
            )

    if (
        status in {"guide_supported", "verified"}
        and question.review.status == "needs_review"
    ):
        errors.append(
            "Supported status conflicts with "
            "existing answer review flag"
        )

    if status == "needs_review":
        warnings.append(
            "Technical evidence requires manual review"
        )

    if status == "insufficient_evidence":
        warnings.append(
            "Available evidence is insufficient"
        )

    if question.review.status == "needs_review":
        warnings.append(
            "Original answer requires review"
        )


# -------------------------------------------------
# VALIDATE COMPLETE DATASET
# -------------------------------------------------

def validate_dataset() -> dict:

    classified = load_classified_questions()

    taxonomy = load_taxonomy()

    chunk_map, source_map = load_knowledge()

    records = read_json(ENRICHED_FILE)

    if not isinstance(records, list):
        raise ValueError(
            "Enriched dataset must be a JSON list."
        )

    results = []

    seen = set()

    valid_count = 0
    invalid_count = 0
    technically_verified = 0
    publish_ready = 0

    for index, record in enumerate(
        records,
        start=1
    ):

        errors = []
        warnings = []

        question_id = (
            record.get("id", f"record_{index}")
            if isinstance(record, dict)
            else f"record_{index}"
        )

        try:

            question = Question.model_validate(
                record
            )

            question_id = question.id

            if question.id in seen:
                errors.append(
                    "Duplicate enriched question ID"
                )

            seen.add(question.id)

            original = classified.get(question.id)

            if original is None:
                errors.append(
                    "Question missing from classified dataset"
                )

            else:
                check_original(
                    question,
                    original,
                    errors
                )

            check_classification(
                question,
                taxonomy,
                errors
            )

            check_learning(
                question,
                errors
            )

            cited_ids = check_evidence(
                question,
                chunk_map,
                source_map,
                errors
            )

            check_verification(
                question,
                cited_ids,
                errors,
                warnings
            )

            if question.verification.status == "verified":
                technically_verified += 1

            ready = (
                not errors
                and question.verification.status == "verified"
                and question.review.status != "needs_review"
                and not warnings
            )

            if ready:
                publish_ready += 1

        except (ValidationError, ValueError) as error:

            errors.append(
                f"Schema validation failed: {error}"
            )

            ready = False

        if errors:
            invalid_count += 1
            result_status = "invalid"

        else:
            valid_count += 1
            result_status = "valid"

        results.append({
            "question_id": question_id,
            "status": result_status,
            "publish_ready": ready,
            "errors": errors,
            "warnings": warnings
        })

    # Identify questions that have not been enriched.
    enriched_ids = seen

    missing_ids = sorted(
        set(classified) - enriched_ids
    )

    status_counts = Counter(
        record["verification"]["status"]
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("verification"), dict)
        and isinstance(
            record["verification"].get("status"),
            str
        )
    )

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "classified_questions": len(classified),
        "enriched_questions": len(records),
        "missing_enrichments": len(missing_ids),
        "missing_question_ids": missing_ids,
        "structurally_valid": valid_count,
        "structurally_invalid": invalid_count,
        "technically_verified": technically_verified,
        "publish_ready": publish_ready,
        "verification_status_counts": dict(
            status_counts
        ),
        "knowledge_sources": len(source_map),
        "knowledge_chunks": len(chunk_map),
        "results": results
    }

    save_json(REPORT_FILE, report)

    return report


# -------------------------------------------------
# COMMAND-LINE INTERFACE
# -------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Validate enriched AWS questions, "
            "citations, and verification metadata."
        )
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit unsuccessfully unless every "
            "question is structurally valid, "
            "enriched, and publish-ready."
        )
    )

    args = parser.parse_args()

    report = validate_dataset()

    print("\nAWS Question Validation")
    print("-----------------------")

    print(
        "Classified questions:",
        report["classified_questions"]
    )

    print(
        "Enriched questions:",
        report["enriched_questions"]
    )

    print(
        "Missing enrichments:",
        report["missing_enrichments"]
    )

    print(
        "Structurally valid:",
        report["structurally_valid"]
    )

    print(
        "Structurally invalid:",
        report["structurally_invalid"]
    )

    print(
        "Marked technically verified:",
        report["technically_verified"]
    )

    print(
        "Publish-ready:",
        report["publish_ready"]
    )

    print("\nVerification statuses:")

    for status, count in sorted(
        report["verification_status_counts"].items()
    ):
        print(f"  {status}: {count}")

    print(f"\nReport: {REPORT_FILE}")

    # Print a small diagnostic sample.
    problematic = [
        result
        for result in report["results"]
        if result["errors"]
    ]

    if problematic:

        print("\nFirst validation errors:")

        for item in problematic[:5]:

            print(f"\n{item['question_id']}")

            for error in item["errors"][:5]:
                print(f"  - {error}")

    if args.strict:

        successful = (
            report["missing_enrichments"] == 0
            and report["structurally_invalid"] == 0
            and report["publish_ready"]
            == report["classified_questions"]
        )

        if not successful:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
