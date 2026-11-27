
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------
# QUESTION SOURCE
# -------------------------------------------------

class QuestionSource(BaseModel):
    """
    Tracks the original Quizlet file
    and position of a question.
    """

    file: str
    position: int = Field(ge=1)


# -------------------------------------------------
# ORIGINAL QUESTION
# -------------------------------------------------

class OriginalQuestion(BaseModel):
    """
    Preserve the source question and answer
    without silently rewriting either.
    """

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    options: list[str] | None = None


# -------------------------------------------------
# CLASSIFICATION
# -------------------------------------------------

class QuestionClassification(BaseModel):

    topic: str | None = None
    category: str | None = None

    secondary_categories: list[str] = Field(
        default_factory=list
    )

    services: list[str] = Field(
        default_factory=list
    )

    difficulty: Literal[
        "beginner",
        "intermediate",
        "advanced"
    ] | None = None


# -------------------------------------------------
# LEARNING CONTENT
# -------------------------------------------------

class QuestionClue(BaseModel):

    phrase: str
    meaning: str


class QuestionHeuristic(BaseModel):

    pattern: str = ""
    decision_rule: str = ""

    exceptions: list[str] = Field(
        default_factory=list
    )


class ServiceExplanation(BaseModel):

    name: str
    role: str

    important_facts: list[str] = Field(
        default_factory=list
    )


class QuestionLearning(BaseModel):
    """
    Educational explanation generated once
    during the offline enrichment pipeline.
    """

    title: str = ""
    scenario_summary: str = ""

    requirements: list[str] = Field(
        default_factory=list
    )

    key_clues: list[QuestionClue] = Field(
        default_factory=list
    )

    heuristic: QuestionHeuristic = Field(
        default_factory=QuestionHeuristic
    )

    service_breakdown: list[ServiceExplanation] = Field(
        default_factory=list
    )

    why_answer_wins: list[str] = Field(
        default_factory=list
    )

    alternatives_and_tradeoffs: list[str] = Field(
        default_factory=list
    )

    exam_takeaway: str = ""


# -------------------------------------------------
# ORIGINAL REVIEW STATUS
# -------------------------------------------------

class QuestionReview(BaseModel):
    """
    Tracks source-answer conflicts and
    other manual review requirements.
    """

    status: Literal[
        "pending",
        "needs_review",
        "verified"
    ] = "pending"

    verified_answer: str | None = None

    notes: list[str] = Field(
        default_factory=list
    )


# -------------------------------------------------
# EVIDENCE SOURCE REFERENCE
# -------------------------------------------------

class QuestionEvidenceReference(BaseModel):
    """
    A source passage associated with a question.

    IDs connect this reference to the knowledge
    base. The source URL allows the frontend
    to display the original reference.

    Retrieval alone does not prove correctness.
    """

    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)

    source_type: Literal[
        "community_guide",
        "aws_documentation"
    ]

    title: str = Field(min_length=1)

    heading: str = ""

    url: str = Field(min_length=1)

    revision: str | None = None

    start_line: int | None = Field(
        default=None,
        ge=1
    )

    end_line: int | None = Field(
        default=None,
        ge=1
    )


# -------------------------------------------------
# INDIVIDUAL CLAIM VERIFICATION
# -------------------------------------------------

class VerifiedClaim(BaseModel):
    """
    Records whether specific technical claims
    are supported by retrieved evidence.
    """

    claim: str = Field(min_length=1)

    status: Literal[
        "pending",
        "supported",
        "contradicted",
        "insufficient_evidence"
    ] = "pending"

    evidence_ids: list[str] = Field(
        default_factory=list
    )

    explanation: str = ""


# -------------------------------------------------
# OVERALL QUESTION VERIFICATION
# -------------------------------------------------

class QuestionVerification(BaseModel):
    """
    Tracks the supporting material and
    verification state of a question.

    An LLM-generated explanation must never
    automatically receive verified status.
    """

    status: Literal[
        "pending",
        "guide_supported",
        "insufficient_evidence",
        "needs_review",
        "verified"
    ] = "pending"

    answer_supported: bool | None = None

    sources: list[QuestionEvidenceReference] = Field(
        default_factory=list
    )

    claims: list[VerifiedClaim] = Field(
        default_factory=list
    )

    flags: list[str] = Field(
        default_factory=list
    )

    reviewed_at: str | None = None


# -------------------------------------------------
# COMPLETE QUESTION MODEL
# -------------------------------------------------

class Question(BaseModel):
    """
    Canonical representation of a question.

    Used throughout normalization,
    deduplication, classification,
    enrichment, verification, and Flask.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)

    sources: list[QuestionSource] = Field(
        min_length=1
    )

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

    verification: QuestionVerification = Field(
        default_factory=QuestionVerification
    )
