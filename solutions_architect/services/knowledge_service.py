
import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from solutions_architect.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeManifest,
    KnowledgeSource,
)

import json


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge_base"

CHUNKS_FILE = KNOWLEDGE_DIR / "chunks.json"

MANIFEST_FILE = KNOWLEDGE_DIR / "source_manifest.json"


# -------------------------------------------------
# SEARCH CONFIGURATION
# -------------------------------------------------

STOPWORDS = {
    "a", "an", "and", "are", "as", "at",
    "be", "by", "can", "does", "for",
    "from", "how", "in", "is", "it",
    "of", "on", "or", "our", "the",
    "their", "this", "to", "use",
    "using", "what", "when", "which",
    "with", "would", "you", "your",
    "company", "solution", "recommend",
    "following", "architect", "aws"
}


# -------------------------------------------------
# SEARCH RESULT
# -------------------------------------------------

@dataclass
class KnowledgeSearchResult:
    """
    A ranked knowledge chunk with its source.

    The score measures search relevance,
    not technical correctness.
    """

    chunk: KnowledgeChunk
    source: KnowledgeSource
    score: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk.chunk_id,
            "source_id": self.source.source_id,
            "title": self.source.title,
            "heading": self.chunk.heading,
            "content": self.chunk.content,
            "score": round(self.score, 4),
            "url": (
                f"{self.source.url}"
                f"#L{self.chunk.start_line}"
                f"-L{self.chunk.end_line}"
            ),
            "start_line": self.chunk.start_line,
            "end_line": self.chunk.end_line,
        }


# -------------------------------------------------
# TOKENIZATION
# -------------------------------------------------

def tokenize(text: str) -> list[str]:
    """
    Convert text into searchable terms.

    Preserve technical expressions such as:
    multi-az, s3, ec2, rpo, and sse-kms.
    """

    text = text.casefold()

    tokens = re.findall(
        r"[a-z0-9]+(?:[-_][a-z0-9]+)*",
        text
    )

    return [
        token
        for token in tokens
        if token not in STOPWORDS
    ]


# -------------------------------------------------
# KNOWLEDGE SEARCH SERVICE
# -------------------------------------------------

class KnowledgeService:
    """
    Loads the local knowledge base and builds
    an in-memory BM25 search index.

    Intended to be initialized once and reused
    when matching multiple questions.
    """

    def __init__(
        self,
        chunks_file: Path = CHUNKS_FILE,
        manifest_file: Path = MANIFEST_FILE
    ):

        self.chunks_file = Path(chunks_file)
        self.manifest_file = Path(manifest_file)

        self.chunks = self._load_chunks()
        self.manifest = self._load_manifest()

        self.sources = {
            source.source_id: source
            for source in self.manifest.sources
        }

        self._validate_references()

        self.documents = [
            self._build_search_document(chunk)
            for chunk in self.chunks
        ]

        self.tokenized_documents = [
            tokenize(document)
            for document in self.documents
        ]

        if not any(self.tokenized_documents):
            raise ValueError(
                "Knowledge base contains no searchable text."
            )

        self.bm25 = BM25Okapi(
            self.tokenized_documents
        )

    # ---------------------------------------------
    # LOAD DATA
    # ---------------------------------------------

    def _load_chunks(self) -> list[KnowledgeChunk]:

        if not self.chunks_file.exists():
            raise FileNotFoundError(
                f"Missing file: {self.chunks_file}\n"
                "Run ingest_knowledge.py first."
            )

        with self.chunks_file.open(
            "r",
            encoding="utf-8"
        ) as file:
            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError(
                "chunks.json must contain a JSON list."
            )

        if not records:
            raise ValueError(
                "Knowledge base contains no chunks."
            )

        return [
            KnowledgeChunk.model_validate(record)
            for record in records
        ]

    def _load_manifest(self) -> KnowledgeManifest:

        if not self.manifest_file.exists():
            raise FileNotFoundError(
                f"Missing file: {self.manifest_file}\n"
                "Run ingest_knowledge.py first."
            )

        with self.manifest_file.open(
            "r",
            encoding="utf-8"
        ) as file:
            record = json.load(file)

        return KnowledgeManifest.model_validate(
            record
        )

    # ---------------------------------------------
    # CHECK SOURCE REFERENCES
    # ---------------------------------------------

    def _validate_references(self) -> None:

        if self.manifest.total_chunks != len(self.chunks):
            raise ValueError(
                "Manifest chunk count does not match chunks.json."
            )

        chunk_ids = [
            chunk.chunk_id
            for chunk in self.chunks
        ]

        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError(
                "Duplicate chunk IDs found."
            )

        for chunk in self.chunks:

            if chunk.source_id not in self.sources:
                raise ValueError(
                    f"Missing source for {chunk.chunk_id}"
                )

    # ---------------------------------------------
    # BUILD SEARCHABLE DOCUMENTS
    # ---------------------------------------------

    def _build_search_document(
        self,
        chunk: KnowledgeChunk
    ) -> str:
        """
        Give section headings additional
        importance during BM25 ranking.
        """

        source = self.sources[chunk.source_id]

        headings = " ".join(chunk.heading_path)
        keywords = " ".join(chunk.keywords)
        services = " ".join(chunk.aws_services)

        return " ".join([
            source.title,
            source.title,
            headings,
            headings,
            keywords,
            services,
            chunk.content
        ])

    # ---------------------------------------------
    # SEARCH
    # ---------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> list[KnowledgeSearchResult]:
        """
        Find the most relevant knowledge chunks.

        Args:
            query: AWS question or search phrase
            top_k: Maximum number of results
            min_score: Minimum BM25 relevance score

        Returns:
            Ranked knowledge results
        """

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(
            query_tokens
        )

        ranked_indices = sorted(
            range(len(self.chunks)),
            key=lambda index: scores[index],
            reverse=True
        )

        results = []

        for index in ranked_indices:

            score = float(scores[index])

            # Exclude zero and negative relevance.
            if score <= 0 or score < min_score:
                continue

            chunk = self.chunks[index]
            source = self.sources[chunk.source_id]

            results.append(
                KnowledgeSearchResult(
                    chunk=chunk,
                    source=source,
                    score=score
                )
            )

            if len(results) >= top_k:
                break

        return results

    # ---------------------------------------------
    # DIRECT LOOKUP
    # ---------------------------------------------

    def get_chunk(
        self,
        chunk_id: str
    ) -> KnowledgeChunk | None:
        """
        Retrieve a chunk by its exact ID.
        """

        return next(
            (
                chunk
                for chunk in self.chunks
                if chunk.chunk_id == chunk_id
            ),
            None
        )

    def get_source(
        self,
        source_id: str
    ) -> KnowledgeSource | None:

        return self.sources.get(source_id)


# -------------------------------------------------
# COMMAND-LINE TEST
# -------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Search the AWS knowledge base."
    )

    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Search phrase or question."
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum number of results."
    )

    args = parser.parse_args()

    service = KnowledgeService()

    results = service.search(
        query=args.query,
        top_k=args.top_k
    )

    print("\nKnowledge Search")
    print("----------------")
    print(f"Indexed chunks: {len(service.chunks)}")
    print(f"Query: {args.query}")
    print(f"Matches: {len(results)}")

    for index, result in enumerate(
        results,
        start=1
    ):

        print(f"\n{index}. {result.source.title}")
        print(f"   Section: {result.chunk.heading}")
        print(f"   BM25 score: {result.score:.3f}")
        print(
            "   Lines:",
            result.chunk.start_line,
            "-",
            result.chunk.end_line
        )
        print(f"   Source: {result.to_dict()['url']}")

        preview = " ".join(
            result.chunk.content.split()
        )[:250]

        print(f"   Preview: {preview}...")


if __name__ == "__main__":
    main()
