
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


# --------------------------------------------
# ORIGINAL SOURCE DATA
# --------------------------------------------

class QuestionSource(BaseModel):
    file: str
    position: int = Field(ge=1)


class OriginalQuestion(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    options: list[str] | None = None


# --------------------------------------------
# QUESTION CLASSIFICATION
# --------------------------------------------

class QuestionClassification(BaseModel):
    topic: str | None = None
    category: str | None = None
    secondary_categories: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    difficulty: Literal[
        "beginner",
        "intermediate",
        "advanced"
    ] | None = None


# --------------------------------------------
# QUESTION DECONSTRUCTION
# --------------------------------------------

class QuestionClue(BaseModel):
    phrase: str
    meaning: str


class QuestionHeuristic(BaseModel):
    pattern: str = ""
    decision_rule: str = ""
    exceptions: list[str] = Field(default_factory=list)


class ServiceExplanation(BaseModel):
    name: str
    role: str
    important_facts: list[str] = Field(default_factory=list)


class QuestionLearning(BaseModel):
    title: str = ""
    scenario_summary: str = ""

    requirements: list[str] = Field(default_factory=list)
    key_clues: list[QuestionClue] = Field(default_factory=list)

    heuristic: QuestionHeuristic = Field(
        default_factory=QuestionHeuristic
    )

    service_breakdown: list[ServiceExplanation] = Field(
        default_factory=list
    )

    why_answer_wins: list[str] = Field(default_factory=list)

    alternatives_and_tradeoffs: list[str] = Field(
        default_factory=list
    )

    exam_takeaway: str = ""


# --------------------------------------------
# CONTENT REVIEW
# --------------------------------------------

class QuestionReview(BaseModel):
    status: Literal[
        "pending",
        "needs_review",
        "verified"
    ] = "pending"

    verified_answer: str | None = None
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------
# COMPLETE QUESTION
# --------------------------------------------

class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)

    sources: list[QuestionSource] = Field(min_length=1)

    original: OriginalQuestion

    classification: QuestionClassification = Field(
        default_factory=QuestionClassification
    )

    learning: QuestionLearning = Field(
        default_factory=QuestionLearning
    )

    review: QuestionReview = Field(
        default_factory=QuestionReview
    )
