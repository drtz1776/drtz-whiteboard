
import json
from pathlib import Path
from threading import RLock

from solutions_architect.schemas.question import Question


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

TAXONOMY_FILE = DATA_DIR / "taxonomy.json"

CLASSIFIED_FILE = (
    DATA_DIR / "normalized" / "classified_questions.json"
)

ENRICHED_FILE = (
    DATA_DIR / "enriched" / "enriched_questions.json"
)


# -------------------------------------------------
# JSON LOADING
# -------------------------------------------------

def read_json(path: Path):
    """
    Load JSON from disk.

    Classified questions and taxonomy are required.
    Enriched questions are optional during development.
    """

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# -------------------------------------------------
# CONTENT SERVICE
# -------------------------------------------------

class ContentService:
    """
    Read-only service for the study application.

    Loads taxonomy and questions into memory,
    with automatic reload when a source file
    changes on disk.

    No LLM calls, writes, or database required.
    """

    def __init__(self):
        self._lock = RLock()
        self._file_state = None

        self._topics = []
        self._topic_lookup = {}
        self._category_lookup = {}

        self._questions = {}
        self._category_index = {}

    # ---------------------------------------------
    # CACHE MANAGEMENT
    # ---------------------------------------------

    def _current_file_state(self):
        """
        Track file modification time and size.

        This avoids reading all JSON files
        for every Flask request.
        """

        paths = [
            TAXONOMY_FILE,
            CLASSIFIED_FILE,
            ENRICHED_FILE
        ]

        state = []

        for path in paths:

            if path.exists():
                stat = path.stat()

                state.append((
                    stat.st_mtime_ns,
                    stat.st_size
                ))

            else:
                state.append(None)

        return tuple(state)

    def _ensure_loaded(self):
        """
        Reload when any input file changes.
        """

        with self._lock:

            state = self._current_file_state()

            if state == self._file_state:
                return

            self._load_data()

            self._file_state = state

    # ---------------------------------------------
    # LOAD TAXONOMY
    # ---------------------------------------------

    def _load_taxonomy(self):
        """
        Build topic and category lookups.

        Classification stores topic/category
        names, while the frontend uses IDs.
        """

        if not TAXONOMY_FILE.exists():
            raise FileNotFoundError(
                f"Missing taxonomy: {TAXONOMY_FILE}"
            )

        data = read_json(TAXONOMY_FILE)

        topics = data.get("topics", [])

        topic_lookup = {}
        category_lookup = {}

        for topic in topics:

            topic_id = topic["id"]

            if topic_id in topic_lookup:
                raise ValueError(
                    f"Duplicate topic ID: {topic_id}"
                )

            topic_lookup[topic_id] = topic

            for category in topic["categories"]:

                key = (topic_id, category["id"])

                if key in category_lookup:
                    raise ValueError(
                        f"Duplicate category: {key}"
                    )

                category_lookup[key] = category

        return (
            topics,
            topic_lookup,
            category_lookup
        )

    # ---------------------------------------------
    # LOAD QUESTION DATA
    # ---------------------------------------------

    def _load_questions(self):
        """
        Load classified questions and overlay
        existing enriched records.

        Enriched records are checked against
        the classified source to preserve the
        original question and classification.
        """

        if not CLASSIFIED_FILE.exists():
            raise FileNotFoundError(
                f"Missing questions: {CLASSIFIED_FILE}"
            )

        classified_data = read_json(CLASSIFIED_FILE)

        if not isinstance(classified_data, list):
            raise ValueError(
                "Classified dataset must be a list."
            )

        questions = {}

        for record in classified_data:

            question = Question.model_validate(record)

            if question.id in questions:
                raise ValueError(
                    f"Duplicate question ID: {question.id}"
                )

            questions[question.id] = question

        if ENRICHED_FILE.exists():

            enriched_data = read_json(ENRICHED_FILE)

            if not isinstance(enriched_data, list):
                raise ValueError(
                    "Enriched dataset must be a list."
                )

            enriched_ids = set()

            for record in enriched_data:

                enriched = Question.model_validate(
                    record
                )

                if enriched.id in enriched_ids:
                    raise ValueError(
                        "Duplicate enriched ID: "
                        + enriched.id
                    )

                enriched_ids.add(enriched.id)

                original = questions.get(enriched.id)

                if original is None:
                    raise ValueError(
                        "Enriched question absent from "
                        f"classified bank: {enriched.id}"
                    )

                if (
                    enriched.original != original.original
                    or enriched.sources != original.sources
                    or enriched.classification
                    != original.classification
                ):
                    raise ValueError(
                        "Enrichment changed source data: "
                        + enriched.id
                    )

                questions[enriched.id] = enriched

        return questions

    # ---------------------------------------------
    # BUILD CATEGORY INDEX
    # ---------------------------------------------

    def _build_category_index(
        self,
        topics,
        questions
    ):
        """
        Index question IDs by taxonomy IDs.

        This lets us retrieve questions by
        category without scanning the entire
        bank on each request.
        """

        index = {}

        for topic in topics:

            for category in topic["categories"]:

                index[
                    (topic["id"], category["id"])
                ] = []

        # Map classification names to taxonomy IDs.
        name_to_ids = {}

        for topic in topics:

            for category in topic["categories"]:

                name_to_ids[
                    (topic["name"], category["name"])
                ] = (
                    topic["id"],
                    category["id"]
                )

        for question in questions.values():

            classification = question.classification

            key = (
                classification.topic,
                classification.category
            )

            taxonomy_ids = name_to_ids.get(key)

            # Some questions may be unclassified.
            # They remain accessible by question ID.
            if taxonomy_ids is None:
                continue

            index[taxonomy_ids].append(question.id)

        return index

    # ---------------------------------------------
    # REBUILD IN-MEMORY DATA
    # ---------------------------------------------

    def _load_data(self):

        (
            topics,
            topic_lookup,
            category_lookup
        ) = self._load_taxonomy()

        questions = self._load_questions()

        category_index = self._build_category_index(
            topics,
            questions
        )

        # Replace cached data only after all
        # inputs have loaded successfully.
        self._topics = topics
        self._topic_lookup = topic_lookup
        self._category_lookup = category_lookup

        self._questions = questions
        self._category_index = category_index

    # ---------------------------------------------
    # COPY FOR READ-ONLY ACCESS
    # ---------------------------------------------

    @staticmethod
    def _serialize_question(question: Question) -> dict:
        """
        Return a new dictionary so callers
        cannot mutate cached Question objects.
        """

        return question.model_dump(mode="json")

    @staticmethod
    def _has_learning(question: Question) -> bool:
        """
        A question has enrichment when its
        essential explanation fields are present.
        """

        learning = question.learning

        return bool(
            learning.title.strip()
            and learning.scenario_summary.strip()
            and learning.why_answer_wins
            and learning.exam_takeaway.strip()
        )

    # ---------------------------------------------
    # QUESTION SUMMARY FOR CARDS
    # ---------------------------------------------

    def _question_summary(
        self,
        question: Question
    ) -> dict:

        enriched = self._has_learning(question)

        return {
            "id": question.id,
            "title": (
                question.learning.title
                if enriched
                else question.original.question
            ),
            "question": question.original.question,
            "topic": question.classification.topic,
            "category": question.classification.category,
            "services": list(
                question.classification.services
            ),
            "difficulty": (
                question.classification.difficulty
            ),
            "is_enriched": enriched,
            "verification_status": (
                question.verification.status
            ),
            "needs_review": (
                question.review.status == "needs_review"
                or question.verification.status
                == "needs_review"
            )
        }

    # ---------------------------------------------
    # GET MAIN TOPICS
    # ---------------------------------------------

    def get_topics(self) -> list[dict]:
        """
        Return all main study topics with
        category and question counts.
        """

        self._ensure_loaded()

        with self._lock:

            results = []

            for topic in self._topics:

                count = sum(
                    len(
                        self._category_index.get(
                            (topic["id"], category["id"]),
                            []
                        )
                    )
                    for category in topic["categories"]
                )

                results.append({
                    "id": topic["id"],
                    "name": topic["name"],
                    "description": topic.get(
                        "description", ""
                    ),
                    "category_count": len(
                        topic["categories"]
                    ),
                    "question_count": count
                })

            return results

    # ---------------------------------------------
    # GET CATEGORIES BY TOPIC
    # ---------------------------------------------

    def get_categories(
        self,
        topic_id: str
    ) -> list[dict]:
        """
        Return category cards for a topic.

        Unknown topic IDs return an empty list.
        """

        self._ensure_loaded()

        with self._lock:

            topic = self._topic_lookup.get(
                topic_id
            )

            if topic is None:
                return []

            results = []

            for category in topic["categories"]:

                question_ids = self._category_index.get(
                    (topic_id, category["id"]),
                    []
                )

                results.append({
                    "id": category["id"],
                    "topic_id": topic_id,
                    "name": category["name"],
                    "description": category.get(
                        "description", ""
                    ),
                    "question_count": len(question_ids),
                    "enriched_count": sum(
                        self._has_learning(
                            self._questions[qid]
                        )
                        for qid in question_ids
                    )
                })

            return results

    # ---------------------------------------------
    # GET QUESTION CARDS BY CATEGORY
    # ---------------------------------------------

    def get_questions_by_category(
        self,
        topic_id: str,
        category_id: str
    ) -> list[dict]:
        """
        Return compact question summaries.

        Full explanations are loaded only when
        requesting a specific question detail.
        """

        self._ensure_loaded()

        with self._lock:

            question_ids = self._category_index.get(
                (topic_id, category_id),
                []
            )

            return [
                self._question_summary(
                    self._questions[qid]
                )
                for qid in question_ids
            ]

    # ---------------------------------------------
    # GET COMPLETE QUESTION
    # ---------------------------------------------

    def get_question_by_id(
        self,
        question_id: str
    ) -> dict | None:
        """
        Return the original question,
        stored explanation, and evidence
        references as a JSON-compatible dict.
        """

        self._ensure_loaded()

        with self._lock:

            question = self._questions.get(
                question_id
            )

            if question is None:
                return None

            result = self._serialize_question(
                question
            )

            result["is_enriched"] = (
                self._has_learning(question)
            )

            return result

    # ---------------------------------------------
    # GET APPLICATION STATISTICS
    # ---------------------------------------------

    def get_statistics(self) -> dict:
        """
        Report overall study-library coverage.
        """

        self._ensure_loaded()

        with self._lock:

            questions = list(
                self._questions.values()
            )

            enriched_count = sum(
                self._has_learning(question)
                for question in questions
            )

            verification_counts = {}

            for question in questions:

                status = question.verification.status

                verification_counts[status] = (
                    verification_counts.get(status, 0)
                    + 1
                )

            classified_count = sum(
                bool(
                    question.classification.topic
                    and question.classification.category
                )
                for question in questions
            )

            return {
                "total_questions": len(questions),
                "classified_questions": classified_count,
                "enriched_questions": enriched_count,
                "not_enriched": (
                    len(questions) - enriched_count
                ),
                "verification_status_counts": (
                    verification_counts
                )
            }


# -------------------------------------------------
# SHARED SERVICE INSTANCE
# -------------------------------------------------

_service = ContentService()


# -------------------------------------------------
# PUBLIC SERVICE FUNCTIONS
# -------------------------------------------------

def get_topics() -> list[dict]:
    return _service.get_topics()


def get_categories(topic_id: str) -> list[dict]:
    return _service.get_categories(topic_id)


def get_questions_by_category(
    topic_id: str,
    category_id: str
) -> list[dict]:
    return _service.get_questions_by_category(
        topic_id,
        category_id
    )


def get_question_by_id(
    question_id: str
) -> dict | None:
    return _service.get_question_by_id(
        question_id
    )


def get_statistics() -> dict:
    return _service.get_statistics()


# -------------------------------------------------
# COMMAND-LINE TEST
# -------------------------------------------------

def main():

    statistics = get_statistics()

    print("\nAWS Study Library")
    print("-----------------")

    for key, value in statistics.items():
        print(f"{key}: {value}")

    print("\nTopics:")

    for topic in get_topics():

        print(
            f"- {topic['name']}: "
            f"{topic['question_count']} questions, "
            f"{topic['category_count']} categories"
        )

        categories = get_categories(
            topic["id"]
        )

        for category in categories:

            print(
                f"    {category['name']}: "
                f"{category['question_count']} questions, "
                f"{category['enriched_count']} enriched"
            )


if __name__ == "__main__":
    main()
