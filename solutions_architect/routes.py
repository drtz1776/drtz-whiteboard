
from flask import (
    Blueprint,
    abort,
    render_template,
    url_for,
)

from solutions_architect.services.content_service import (
    get_topics,
    get_categories,
    get_questions_by_category,
    get_question_by_id,
    get_statistics,
)


# -------------------------------------------------
# FLASK BLUEPRINT
# -------------------------------------------------

bp = Blueprint(
    "solutions_architect",
    __name__,
    url_prefix="/solutions-architect",
    template_folder="templates",
)


# -------------------------------------------------
# HELPER: FIND A TOPIC
# -------------------------------------------------

def find_topic(topic_id: str) -> dict | None:
    """
    Look up one topic by its taxonomy ID.
    """

    return next(
        (
            topic
            for topic in get_topics()
            if topic["id"] == topic_id
        ),
        None,
    )


# -------------------------------------------------
# HELPER: FIND A CATEGORY
# -------------------------------------------------

def find_category(
    topic_id: str,
    category_id: str,
) -> dict | None:
    """
    Look up one category within a topic.
    """

    return next(
        (
            category
            for category in get_categories(topic_id)
            if category["id"] == category_id
        ),
        None,
    )


# -------------------------------------------------
# HELPER: BUILD QUESTION BREADCRUMBS
# -------------------------------------------------

def get_question_location(question: dict) -> dict:
    """
    Resolve a question's classification names
    back to taxonomy IDs for navigation.

    Some questions may not yet be classified.
    Those questions still have detail pages.
    """

    classification = question["classification"]

    topic_name = classification.get("topic")
    category_name = classification.get("category")

    location = {
        "topic": None,
        "category": None,
    }

    if not topic_name:
        return location

    topic = next(
        (
            item
            for item in get_topics()
            if item["name"] == topic_name
        ),
        None,
    )

    if topic is None:
        return location

    location["topic"] = topic

    if not category_name:
        return location

    category = next(
        (
            item
            for item in get_categories(topic["id"])
            if item["name"] == category_name
        ),
        None,
    )

    location["category"] = category

    return location


# -------------------------------------------------
# PAGE 1: MAIN TOPICS
# -------------------------------------------------

@bp.route("/")
def topics():
    """
    Display the six main study topics.

    Each card shows:
    - Topic name
    - Description
    - Category count
    - Question count
    """

    topics_data = get_topics()
    statistics = get_statistics()

    return render_template(
        "solutions_architect/topics.html",
        topics=topics_data,
        statistics=statistics,
        page_title="AWS Solutions Architect",
    )


# -------------------------------------------------
# PAGE 2: TOPIC CATEGORIES
# -------------------------------------------------

@bp.route("/topics/<topic_id>/")
def categories(topic_id: str):
    """
    Display all categories within a topic.

    Example:
    Networking -> VPC Fundamentals,
    VPC Endpoints, Load Balancing, etc.
    """

    topic = find_topic(topic_id)

    if topic is None:
        abort(404)

    categories_data = get_categories(topic_id)

    return render_template(
        "solutions_architect/categories.html",
        topic=topic,
        categories=categories_data,
        page_title=topic["name"],
    )


# -------------------------------------------------
# PAGE 3: CATEGORY QUESTIONS
# -------------------------------------------------

@bp.route(
    "/topics/<topic_id>/categories/<category_id>/"
)
def questions(
    topic_id: str,
    category_id: str,
):
    """
    Display compact question cards.

    A question can appear even when its
    explanation has not been generated yet.
    """

    topic = find_topic(topic_id)

    if topic is None:
        abort(404)

    category = find_category(
        topic_id,
        category_id,
    )

    if category is None:
        abort(404)

    questions_data = get_questions_by_category(
        topic_id,
        category_id,
    )

    return render_template(
        "solutions_architect/questions.html",
        topic=topic,
        category=category,
        questions=questions_data,
        page_title=category["name"],
    )


# -------------------------------------------------
# PAGE 4: QUESTION DETAIL
# -------------------------------------------------

@bp.route("/questions/<question_id>/")
def question_detail(question_id: str):
    """
    Display a complete AWS question breakdown.

    All learning content comes from stored
    enriched JSON. No LLM calls are made.
    """

    question = get_question_by_id(question_id)

    if question is None:
        abort(404)

    location = get_question_location(question)

    verification = question["verification"]
    learning = question["learning"]

    # An enriched question is not necessarily
    # technically verified.
    is_verified = (
        verification["status"] == "verified"
        and question["review"]["status"]
        != "needs_review"
    )

    needs_review = (
        question["review"]["status"] == "needs_review"
        or verification["status"] == "needs_review"
    )

    return render_template(
        "solutions_architect/question_detail.html",
        question=question,
        learning=learning,
        verification=verification,
        is_enriched=question["is_enriched"],
        is_verified=is_verified,
        needs_review=needs_review,
        topic=location["topic"],
        category=location["category"],
        page_title=(
            learning["title"]
            if question["is_enriched"]
            else "AWS Question"
        ),
    )


# -------------------------------------------------
# ENDPOINT REFERENCE
# -------------------------------------------------

# Blueprint endpoint names available to Jinja:
#
# solutions_architect.topics
# solutions_architect.categories
# solutions_architect.questions
# solutions_architect.question_detail
#
# Example:
#
# url_for(
#     "solutions_architect.categories",
#     topic_id="networking"
# )
