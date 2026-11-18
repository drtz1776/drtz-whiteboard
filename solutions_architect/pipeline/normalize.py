
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from solutions_architect.schemas.question import (
    Question,
    QuestionSource,
    OriginalQuestion,
)


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

RAW_DIR = BASE_DIR / "data" / "raw"
NORMALIZED_DIR = BASE_DIR / "data" / "normalized"

OUTPUT_FILE = NORMALIZED_DIR / "questions.json"


# -------------------------------------------------
# GENERATE A STABLE QUESTION ID
# -------------------------------------------------

def generate_question_id(question_text: str) -> str:
    """
    Generate a stable ID from the question text.

    Identical question text produces the same ID.
    """

    normalized_text = " ".join(
        question_text.split()
    ).casefold()

    question_hash = hashlib.sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()[:16]

    return f"q_{question_hash}"


# -------------------------------------------------
# READ A QUIZLET JSON FILE
# -------------------------------------------------

def load_quizlet_file(file_path: Path) -> list[dict]:
    """
    Load a Quizlet JSON export.

    Expected format:
    [
        {
            "term": "Question text",
            "definition": "Correct answer"
        }
    ]
    """

    with file_path.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{file_path.name} must contain a JSON list."
        )

    return data


# -------------------------------------------------
# NORMALIZE AN INDIVIDUAL QUESTION
# -------------------------------------------------

def normalize_question(
    record: dict,
    source_file: str,
    position: int
) -> Question:
    """
    Convert one Quizlet record into our
    standardized Pydantic Question model.
    """

    if not isinstance(record, dict):
        raise ValueError(
            f"Record {position} in {source_file} "
            "must be a JSON object."
        )

    question_text = record.get("term")
    answer_text = record.get("definition")

    if not isinstance(question_text, str):
        raise ValueError(
            f"Invalid question text at "
            f"{source_file}, record {position}."
        )

    if not isinstance(answer_text, str):
        raise ValueError(
            f"Invalid answer text at "
            f"{source_file}, record {position}."
        )

    question_text = question_text.strip()
    answer_text = answer_text.strip()

    if not question_text or not answer_text:
        raise ValueError(
            f"Empty question or answer at "
            f"{source_file}, record {position}."
        )

    question = Question(
        id=generate_question_id(question_text),
        sources=[
            QuestionSource(
                file=source_file,
                position=position
            )
        ],
        original=OriginalQuestion(
            question=question_text,
            answer=answer_text,
            options=None
        )
    )

    return question


# -------------------------------------------------
# NORMALIZE ALL JSON FILES
# -------------------------------------------------

def normalize_all_questions() -> list[Question]:
    """
    Read every JSON file in data/raw,
    normalize the records, and return
    a list of validated Question objects.
    """

    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {RAW_DIR}"
        )

    json_files = sorted(
        RAW_DIR.glob("*.json"),
        key=lambda path: path.name.casefold()
    )

    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in {RAW_DIR}"
        )

    normalized_questions = []
    errors = []

    for file_path in json_files:

        print(f"Processing: {file_path.name}")

        try:
            records = load_quizlet_file(file_path)

        except (ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"{file_path.name}: {error}"
            )
            continue

        for position, record in enumerate(
            records,
            start=1
        ):

            try:
                question = normalize_question(
                    record=record,
                    source_file=file_path.name,
                    position=position
                )

                normalized_questions.append(question)

            except (ValueError, ValidationError) as error:
                errors.append(
                    f"{file_path.name}, "
                    f"record {position}: {error}"
                )

    print("\nNormalization summary")
    print("---------------------")
    print(f"Files found: {len(json_files)}")
    print(f"Questions normalized: {len(normalized_questions)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors encountered:")

        for error in errors:
            print(f"- {error}")

        # Avoid silently creating an incomplete
        # question bank when a source fails.
        raise ValueError(
            "Normalization failed. "
            "Correct the source errors above."
        )

    return normalized_questions


# -------------------------------------------------
# SAVE THE NORMALIZED QUESTIONS
# -------------------------------------------------

def save_normalized_questions(
    questions: list[Question]
) -> None:
    """
    Export validated Question objects
    into a formatted JSON file.
    """

    NORMALIZED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_data = [
        question.model_dump(mode="json")
        for question in questions
    ]

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(f"\nSaved to: {OUTPUT_FILE}")


# -------------------------------------------------
# SCRIPT ENTRY POINT
# -------------------------------------------------

def main():
    questions = normalize_all_questions()

    save_normalized_questions(questions)


if __name__ == "__main__":
    main()
