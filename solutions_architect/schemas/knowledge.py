
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------
# KNOWLEDGE SOURCE
# -------------------------------------------------

class KnowledgeSource(BaseModel):
    """
    Represents an original reference document.

    Example:
    A Markdown file from the AWS SAA-C03
    GitHub study-guide repository.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)

    title: str = Field(min_length=1)

    source_type: Literal[
        "community_guide",
        "aws_documentation"
    ]

    repository: str | None = None

    url: str = Field(min_length=1)

    file_path: str | None = None

    revision: str | None = None


# -------------------------------------------------
# KNOWLEDGE CHUNK
# -------------------------------------------------

class KnowledgeChunk(BaseModel):
    """
    A searchable section of a reference document.

    Chunks preserve the source and section
    information needed for citations.
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)

    heading: str = ""

    heading_path: list[str] = Field(
        default_factory=list
    )

    content: str = Field(min_length=1)

    keywords: list[str] = Field(
        default_factory=list
    )

    aws_services: list[str] = Field(
        default_factory=list
    )

    start_line: int = Field(ge=1)

    end_line: int = Field(ge=1)


# -------------------------------------------------
# EVIDENCE MATCH
# -------------------------------------------------

class EvidenceMatch(BaseModel):
    """
    Connects one question to a potentially
    relevant knowledge-base chunk.

    A retrieval match does not automatically
    establish that the answer is correct.
    """

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)

    chunk_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)

    retrieval_method: Literal[
        "keyword",
        "bm25",
        "semantic",
        "manual"
    ]

    relevance_score: float = Field(ge=0)

    evidence_status: Literal[
        "retrieved",
        "supports",
        "contradicts",
        "insufficient"
    ] = "retrieved"


# -------------------------------------------------
# KNOWLEDGE BASE MANIFEST
# -------------------------------------------------

class KnowledgeManifest(BaseModel):
    """
    Tracks the documents used to construct
    a particular version of the knowledge base.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"

    sources: list[KnowledgeSource] = Field(
        default_factory=list
    )

    total_chunks: int = Field(ge=0, default=0)


# -------------------------------------------------
# QUESTION EVIDENCE PACKAGE
# -------------------------------------------------

class QuestionEvidence(BaseModel):
    """
    Groups the retrieved evidence for one question.

    This can be passed to the enrichment pipeline
    alongside the original question and answer.
    """

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)

    matches: list[EvidenceMatch] = Field(
        default_factory=list
    )

    retrieval_status: Literal[
        "matched",
        "no_match",
        "needs_review"
    ] = "no_match"
