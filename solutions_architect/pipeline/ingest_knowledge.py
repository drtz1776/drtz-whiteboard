
import hashlib
import json
import re
import subprocess
from pathlib import Path

from solutions_architect.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeSource,
    KnowledgeManifest,
)


# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge_base"

REPO_DIR = (
    KNOWLEDGE_DIR
    / "source"
    / "aws-saa-c03-guides"
)

GUIDES_DIR = REPO_DIR / "topic-guides"

CHUNKS_FILE = KNOWLEDGE_DIR / "chunks.json"

MANIFEST_FILE = KNOWLEDGE_DIR / "source_manifest.json"

REPO_URL = (
    "https://github.com/"
    "RonitSachdev/aws-saa-c03-guides"
)

# Split long sections into smaller line-based chunks.
# This is a character target, not a token count.
MAX_CHARS = 2500


# -------------------------------------------------
# IDENTIFIERS AND REPOSITORY REVISION
# -------------------------------------------------

def stable_id(value: str, prefix: str) -> str:
    """
    Create a deterministic ID from source metadata.
    """

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:20]

    return f"{prefix}_{digest}"


def get_repository_revision() -> str:
    """
    Read the exact Git commit used for ingestion.
    """

    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout.strip()


# -------------------------------------------------
# DISCOVER MARKDOWN GUIDES
# -------------------------------------------------

def discover_guides() -> list[Path]:
    """
    Find Markdown files under topic-guides/.
    """

    if not GUIDES_DIR.is_dir():
        raise FileNotFoundError(
            f"Guide folder not found: {GUIDES_DIR}\n"
            "Clone the repository before ingesting."
        )

    paths = sorted(
        GUIDES_DIR.rglob("*.md"),
        key=lambda path: str(path).casefold()
    )

    if not paths:
        raise ValueError(
            "No Markdown guides found."
        )

    return paths


# -------------------------------------------------
# EXTRACT DOCUMENT TITLE
# -------------------------------------------------

def extract_title(lines: list[str], path: Path) -> str:
    """
    Use the first H1 heading as the document title.
    Fall back to the filename if none exists.
    """

    for line in lines:
        match = re.match(r"^#\s+(.+?)\s*$", line)

        if match:
            return match.group(1).strip()

    return path.stem.replace("-", " ")


# -------------------------------------------------
# PARSE MARKDOWN HEADINGS
# -------------------------------------------------

def split_sections(lines: list[str]) -> list[dict]:
    """
    Split a Markdown document at headings.

    Preserve heading hierarchy and original
    1-based line numbers for evidence citations.

    Headings inside fenced code blocks are ignored.
    """

    sections = []
    heading_stack = []
    current_lines = []
    section_start = 1

    in_fence = False
    fence_char = None
    fence_length = 0

    def flush_section(end_line: int):
        nonlocal current_lines, section_start

        content = "\n".join(current_lines).strip()

        if content:
            sections.append({
                "heading_path": [
                    title for _, title in heading_stack
                ],
                "content": content,
                "start_line": section_start,
                "end_line": end_line
            })

        current_lines = []

    for line_number, line in enumerate(lines, start=1):

        stripped = line.strip()

        fence_match = re.match(
            r"^(`{3,}|~{3,})", stripped
        )

        if fence_match:
            marker = fence_match.group(1)
            char = marker[0]

            if not in_fence:
                in_fence = True
                fence_char = char
                fence_length = len(marker)

            elif (
                char == fence_char
                and len(marker) >= fence_length
                and re.fullmatch(
                    re.escape(char) + r"{3,}\s*",
                    stripped
                )
            ):
                in_fence = False
                fence_char = None
                fence_length = 0

        heading_match = None

        if not in_fence:
            heading_match = re.match(
                r"^(#{1,6})\s+(.+?)\s*#*\s*$",
                line
            )

        if heading_match:

            flush_section(line_number - 1)

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            heading_stack = [
                (existing_level, existing_title)
                for existing_level, existing_title
                in heading_stack
                if existing_level < level
            ]

            heading_stack.append((level, title))

            section_start = line_number
            current_lines.append(line)

        else:
            if not current_lines:
                section_start = line_number

            current_lines.append(line)

    flush_section(len(lines))

    return sections


# -------------------------------------------------
# SPLIT LONG SECTIONS
# -------------------------------------------------

def chunk_section(section: dict) -> list[dict]:
    """
    Split long sections into smaller chunks,
    keeping source line boundaries intact.
    """

    text_lines = section["content"].splitlines()

    chunks = []
    buffer = []
    chunk_start = section["start_line"]
    char_count = 0

    for offset, line in enumerate(text_lines):

        source_line = section["start_line"] + offset

        if buffer and char_count + len(line) + 1 > MAX_CHARS:

            chunks.append({
                "heading_path": section["heading_path"],
                "content": "\n".join(buffer).strip(),
                "start_line": chunk_start,
                "end_line": source_line - 1
            })

            buffer = []
            char_count = 0
            chunk_start = source_line

        if not buffer:
            chunk_start = source_line

        buffer.append(line)
        char_count += len(line) + 1

    if buffer:
        chunks.append({
            "heading_path": section["heading_path"],
            "content": "\n".join(buffer).strip(),
            "start_line": chunk_start,
            "end_line": section["end_line"]
        })

    return [
        chunk for chunk in chunks
        if chunk["content"]
    ]


# -------------------------------------------------
# EXTRACT SEARCH KEYWORDS
# -------------------------------------------------

def extract_keywords(
    title: str,
    heading_path: list[str]
) -> list[str]:
    """
    Generate basic search keywords from
    document and section headings.

    Detailed AWS service tagging comes later.
    """

    text = " ".join([title, *heading_path]).lower()

    words = re.findall(
        r"[a-z0-9][a-z0-9-]*",
        text
    )

    stopwords = {
        "the", "a", "an", "and", "or",
        "of", "to", "for", "in", "on",
        "with", "guide", "aws", "exam",
        "part", "section"
    }

    return sorted({
        word for word in words
        if word not in stopwords
        and len(word) > 1
    })


# -------------------------------------------------
# INGEST ONE GUIDE
# -------------------------------------------------

def ingest_guide(
    path: Path,
    revision: str
) -> tuple[KnowledgeSource, list[KnowledgeChunk]]:
    """
    Create one source record and multiple
    searchable knowledge chunks.
    """

    relative_path = path.relative_to(REPO_DIR)

    lines = path.read_text(
        encoding="utf-8"
    ).splitlines()

    title = extract_title(lines, path)

    source_id = stable_id(
        relative_path.as_posix(),
        "source"
    )

    source_url = (
        f"{REPO_URL}/blob/"
        f"{revision}/{relative_path.as_posix()}"
    )

    source = KnowledgeSource(
        source_id=source_id,
        title=title,
        source_type="community_guide",
        repository=REPO_URL,
        url=source_url,
        file_path=relative_path.as_posix(),
        revision=revision
    )

    sections = split_sections(lines)

    chunks = []

    for section in sections:

        for item in chunk_section(section):

            chunk_id = stable_id(
                (
                    f"{source_id}:"
                    f"{item['start_line']}:"
                    f"{item['end_line']}"
                ),
                "chunk"
            )

            heading_path = item["heading_path"]

            chunk = KnowledgeChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                heading=(
                    heading_path[-1]
                    if heading_path
                    else title
                ),
                heading_path=heading_path,
                content=item["content"],
                keywords=extract_keywords(
                    title,
                    heading_path
                ),
                aws_services=[],
                start_line=item["start_line"],
                end_line=item["end_line"]
            )

            chunks.append(chunk)

    return source, chunks


# -------------------------------------------------
# SAVE JSON
# -------------------------------------------------

def save_json(path: Path, data) -> None:
    """
    Write a JSON file through a temporary file
    so incomplete writes don't replace results.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary_path.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    temporary_path.replace(path)


# -------------------------------------------------
# BUILD KNOWLEDGE BASE
# -------------------------------------------------

def build_knowledge_base() -> None:

    paths = discover_guides()
    revision = get_repository_revision()

    sources = []
    all_chunks = []

    print(f"Repository revision: {revision}")
    print(f"Markdown files: {len(paths)}")

    for path in paths:

        source, chunks = ingest_guide(
            path,
            revision
        )

        sources.append(source)
        all_chunks.extend(chunks)

        print(
            f"{path.name}: "
            f"{len(chunks)} chunks"
        )

    # Verify globally unique identifiers.
    chunk_ids = [
        chunk.chunk_id for chunk in all_chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate knowledge chunk IDs detected."
        )

    # Validate source references.
    source_ids = {
        source.source_id for source in sources
    }

    for chunk in all_chunks:

        if chunk.source_id not in source_ids:
            raise ValueError(
                f"Missing source for {chunk.chunk_id}"
            )

        if chunk.end_line < chunk.start_line:
            raise ValueError(
                f"Invalid line range: {chunk.chunk_id}"
            )

    manifest = KnowledgeManifest(
        schema_version="1.0",
        sources=sources,
        total_chunks=len(all_chunks)
    )

    save_json(
        CHUNKS_FILE,
        [
            chunk.model_dump(mode="json")
            for chunk in all_chunks
        ]
    )

    save_json(
        MANIFEST_FILE,
        manifest.model_dump(mode="json")
    )

    print("\nKnowledge Base Summary")
    print("----------------------")
    print(f"Sources: {len(sources)}")
    print(f"Chunks: {len(all_chunks)}")
    print(f"Revision: {revision}")
    print(f"Saved: {CHUNKS_FILE}")
    print(f"Saved: {MANIFEST_FILE}")


# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------

if __name__ == "__main__":
    build_knowledge_base()
