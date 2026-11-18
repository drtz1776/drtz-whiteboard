
import argparse
import json
import os
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

from solutions_architect.schemas.question import (
    Question,
    QuestionClue,
    QuestionHeuristic,
    QuestionLearning,
    ServiceExplanation,
)


# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"

INPUT_FILE = (
    DATA_DIR / "normalized" / "classified_questions.json"
)

OUTPUT_FILE = (
    DATA_DIR / "enriched" / "enriched_questions.json"
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


# -------------------------------------------------
# STRUCTURED LLM OUTPUT
# -------------------------------------------------

class EnrichmentResult(BaseModel):
    """
    Expected response from the language model.

    These fields map to QuestionLearning
    in our existing question.py schema.
    """

    title: str
    scenario_summary: str

    requirements: list[str]

    key_clues: list[QuestionClue]

    heuristic: QuestionHeuristic

    service_breakdown: list[ServiceExplanation]

    why_answer_wins: list[str]

    alternatives_and_tradeoffs: list[str]

    exam_takeaway: str

    answer_concerns: list[str] = Field(
        description=(
            "Possible errors, outdated terminology, "
            "or missing facts affecting the source answer. "
            "Empty list if no concerns are identified."
        )
    )


# -------------------------------------------------
# SYSTEM INSTRUCTIONS
# -------------------------------------------------

SYSTEM_PROMPT = """
You are an expert AWS Solutions Architect educator.

Your task is to DECONSTRUCT AWS SAA-C03 exam
questions into concise, technically rigorous
educational explanations.

The goal is understanding architectural decisions,
not memorizing answer strings.

Follow these instructions:

1. Preserve the original scenario and its meaning.

2. Write a short, descriptive title.

3. Summarize the actual architectural problem.

4. Extract the functional and nonfunctional
   requirements from the question.

5. Identify 3-6 useful clues from the original
   question. For each clue, explain why it matters.
   Prefer exact phrases from the source.

6. Derive the architectural heuristic:
   - pattern: recognizable scenario pattern
   - decision_rule: what solution the pattern suggests
   - exceptions: situations where the rule changes

7. Explain the main AWS services:
   - name
   - role in this scenario
   - 2-4 relevant technical facts

8. Explain why the PROVIDED ANSWER satisfies
   the scenario's requirements.

9. Explain important tradeoffs and alternative
   solutions only when technically relevant.

10. End with a concise, memorable exam takeaway.

CRITICAL ACCURACY RULES:

- Treat the provided answer as an unverified
  source answer, NOT guaranteed ground truth.
- Do not invent missing multiple-choice options.
- Do not claim other choices are incorrect unless
  the scenario supplies enough information.
- Identify potentially outdated AWS behavior.
- Flag incorrect or ambiguous source answers
  in answer_concerns.
- Do not silently replace the provided answer.
- Differentiate actual requirements from assumptions.
- Avoid invented AWS limits, prices, and guarantees.
- Do not assume an AWS service is appropriate merely
  because its name appears in the question.
- Explain tradeoffs using the question's constraints.

STYLE:

- Clear, educational, and technically precise.
- Explain WHY, not merely WHAT.
- Prefer short, information-dense bullet points.
- Use AWS terminology accurately.
- No unnecessary introductions or filler.

Return the structured result requested by the API.
"""


# -------------------------------------------------
# LOAD CLASSIFIED QUESTIONS
# -------------------------------------------------

def load_questions() -> list[Question]:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing input: {INPUT_FILE}\n"
            "Run classify.py first."
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        records = json.load(file)

    return [
        Question.model_validate(record)
        for record in records
    ]


# -------------------------------------------------
# LOAD PREVIOUSLY ENRICHED QUESTIONS
# -------------------------------------------------

def load_existing_results() -> dict[str, Question]:
    """
    Support resuming an interrupted run.
    Already enriched questions are not regenerated.
    """

    if not OUTPUT_FILE.exists():
        return {}

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        records = json.load(file)

    questions = [
        Question.model_validate(record)
        for record in records
    ]

    return {
        question.id: question
        for question in questions
    }


# -------------------------------------------------
# BUILD THE QUESTION PROMPT
# -------------------------------------------------

def build_question_prompt(question: Question) -> str:

    payload = {
        "question_id": question.id,
        "original_question": question.original.question,
        "source_answer": question.original.answer,
        "answer_options": question.original.options,
        "classification": (
            question.classification.model_dump()
        ),
        "existing_review": (
            question.review.model_dump()
        )
    }

    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False
    )


# -------------------------------------------------
# CALL THE LANGUAGE MODEL
# -------------------------------------------------

def generate_enrichment(
    client: OpenAI,
    question: Question
) -> EnrichmentResult:

    response = client.responses.parse(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=[
            {
                "role": "user",
                "content": build_question_prompt(question)
            }
        ],
        text_format=EnrichmentResult
    )

    result = response.output_parsed

    if result is None:
        raise ValueError(
            "Model returned no parsed enrichment."
        )

    return result


# -------------------------------------------------
# APPLY ENRICHMENT TO QUESTION
# -------------------------------------------------

def apply_enrichment(
    question: Question,
    result: EnrichmentResult
) -> Question:

    enriched = question.model_copy(deep=True)

    enriched.learning = QuestionLearning(
        title=result.title,
        scenario_summary=result.scenario_summary,
        requirements=result.requirements,
        key_clues=result.key_clues,
        heuristic=result.heuristic,
        service_breakdown=result.service_breakdown,
        why_answer_wins=result.why_answer_wins,
        alternatives_and_tradeoffs=(
            result.alternatives_and_tradeoffs
        ),
        exam_takeaway=result.exam_takeaway
    )

    # Preserve existing review flags.
    # AI-generated explanations are not verified.
    if result.answer_concerns:

        enriched.review.status = "needs_review"

        for concern in result.answer_concerns:
            note = f"AI review concern: {concern}"

            if note not in enriched.review.notes:
                enriched.review.notes.append(note)

    return enriched


# -------------------------------------------------
# SAVE CHECKPOINT SAFELY
# -------------------------------------------------

def save_results(
    results: dict[str, Question]
) -> None:
    """
    Save after each successful enrichment.

    Write to a temporary file first so an
    interrupted write does not destroy output.
    """

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    data = [
        question.model_dump(mode="json")
        for question in results.values()
    ]

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

    temporary_file.replace(OUTPUT_FILE)


# -------------------------------------------------
# MAIN ENRICHMENT PIPELINE
# -------------------------------------------------

def enrich_questions(
    limit: int,
    question_id: str | None = None
) -> None:

    questions = load_questions()
    existing_results = load_existing_results()

    # Existing source-answer conflicts must be
    # reviewed before we teach those answers.
    candidates = [
        question
        for question in questions
        if question.review.status != "needs_review"
        and question.id not in existing_results
        and (
            question_id is None
            or question.id == question_id
        )
    ]

    if question_id is not None:
        matches = [
            q for q in questions
            if q.id == question_id
        ]

        if not matches:
            raise ValueError(
                f"Question ID not found: {question_id}"
            )

    selected = candidates[:limit]

    if not selected:
        print("No eligible new questions to enrich.")
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not configured."
        )

    client = OpenAI(
        timeout=120.0,
        max_retries=2
    )

    print(f"Model: {MODEL}")
    print(f"Questions selected: {len(selected)}")

    succeeded = 0
    failed = 0

    for index, question in enumerate(selected, start=1):

        print(
            f"\n[{index}/{len(selected)}] "
            f"Processing {question.id}"
        )

        try:
            result = generate_enrichment(
                client,
                question
            )

            enriched = apply_enrichment(
                question,
                result
            )

            existing_results[question.id] = enriched

            save_results(existing_results)

            succeeded += 1

            print(f"Saved: {result.title}")

            if result.answer_concerns:
                print(
                    "Review needed:",
                    len(result.answer_concerns),
                    "concern(s)"
                )

        except Exception as error:

            failed += 1

            print(
                f"Failed: {question.id}: "
                f"{type(error).__name__}: {error}"
            )

    print("\nEnrichment Summary")
    print("------------------")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    print(f"Total saved: {len(existing_results)}")
    print(f"Output: {OUTPUT_FILE}")


# -------------------------------------------------
# COMMAND-LINE INTERFACE
# -------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate structured explanations "
            "for AWS SAA study questions."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum new questions to process."
    )

    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Enrich one specific question ID."
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    enrich_questions(
        limit=args.limit,
        question_id=args.id
    )


if __name__ == "__main__":
    main()
