
import json
import re
from collections import Counter
from pathlib import Path

from solutions_architect.schemas.question import Question


# -------------------------------------------------
# FILE PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
NORMALIZED_DIR = DATA_DIR / "normalized"

INPUT_FILE = NORMALIZED_DIR / "unique_questions.json"
TAXONOMY_FILE = DATA_DIR / "taxonomy.json"

OUTPUT_FILE = NORMALIZED_DIR / "classified_questions.json"
REPORT_FILE = NORMALIZED_DIR / "classification_report.json"


# -------------------------------------------------
# AWS SERVICE DETECTION
# -------------------------------------------------

# Each canonical service name has phrases that
# may appear in question or answer text.

SERVICE_ALIASES = {
    "Amazon EC2": [
        "amazon ec2", "ec2", "elastic compute cloud"
    ],
    "Amazon S3": [
        "amazon s3", "s3 bucket", "s3 storage",
        "s3 gateway endpoint"
    ],
    "Amazon EBS": [
        "amazon ebs", "ebs volume", "elastic block store"
    ],
    "Amazon EFS": [
        "amazon efs", "elastic file system"
    ],
    "Amazon FSx": [
        "amazon fsx", "fsx for"
    ],
    "Amazon RDS": [
        "amazon rds", "rds", "relational database service"
    ],
    "Amazon Aurora": [
        "amazon aurora", "aurora"
    ],
    "Amazon DynamoDB": [
        "amazon dynamodb", "dynamodb"
    ],
    "Amazon ElastiCache": [
        "elasticache"
    ],
    "Amazon Redshift": [
        "redshift"
    ],
    "Amazon Athena": [
        "amazon athena", "athena"
    ],
    "AWS Lambda": [
        "aws lambda", "lambda function"
    ],
    "Amazon ECS": [
        "amazon ecs", "elastic container service"
    ],
    "Amazon EKS": [
        "amazon eks", "elastic kubernetes service"
    ],
    "AWS Fargate": [
        "fargate"
    ],
    "Amazon SQS": [
        "amazon sqs", "simple queue service", "sqs"
    ],
    "Amazon SNS": [
        "amazon sns", "simple notification service", "sns"
    ],
    "Amazon EventBridge": [
        "eventbridge"
    ],
    "Amazon Kinesis": [
        "amazon kinesis", "kinesis"
    ],
    "Amazon VPC": [
        "amazon vpc", "vpc", "virtual private cloud"
    ],
    "AWS PrivateLink": [
        "privatelink"
    ],
    "AWS Direct Connect": [
        "direct connect"
    ],
    "AWS Transit Gateway": [
        "transit gateway"
    ],
    "Amazon Route 53": [
        "route 53"
    ],
    "Amazon CloudFront": [
        "cloudfront"
    ],
    "AWS Global Accelerator": [
        "global accelerator"
    ],
    "Elastic Load Balancing": [
        "load balancer", "load balancing", "alb", "nlb",
        "elastic load balancing"
    ],
    "Amazon EC2 Auto Scaling": [
        "auto scaling", "autoscaling"
    ],
    "AWS IAM": [
        "iam", "identity and access management"
    ],
    "AWS Organizations": [
        "aws organizations", "service control policy",
        "service control policies", "scp"
    ],
    "AWS KMS": [
        "aws kms", "key management service", "sse-kms"
    ],
    "AWS WAF": [
        "aws waf", "web application firewall"
    ],
    "Amazon CloudWatch": [
        "cloudwatch"
    ],
    "AWS CloudTrail": [
        "cloudtrail"
    ],
    "AWS Config": [
        "aws config"
    ],
    "Amazon GuardDuty": [
        "guardduty"
    ],
    "AWS CloudFormation": [
        "cloudformation"
    ],
    "AWS DMS": [
        "database migration service", "aws dms"
    ],
    "AWS DataSync": [
        "datasync"
    ],
    "AWS Storage Gateway": [
        "storage gateway", "file gateway",
        "volume gateway"
    ],
    "AWS Snow Family": [
        "snowball", "snowmobile", "snow family"
    ]
}


# -------------------------------------------------
# CATEGORY RULES
# -------------------------------------------------

# Keys must match the category IDs in taxonomy.json.
# More specific phrases are weighted more strongly.

CATEGORY_RULES = {
    "vpc-fundamentals": [
        "vpc peering", "cidr", "vpc sharing",
        "resource access manager"
    ],
    "subnets-routing": [
        "private subnet", "public subnet",
        "route table", "nat gateway",
        "internet gateway", "network acl"
    ],
    "vpc-endpoints": [
        "gateway endpoint", "interface endpoint",
        "vpc endpoint", "privatelink",
        "private access to s3"
    ],
    "hybrid-connectivity": [
        "direct connect", "site-to-site vpn",
        "vpn cloudhub", "transit gateway",
        "hybrid connectivity", "on-premises connection"
    ],
    "load-balancing": [
        "application load balancer",
        "network load balancer",
        "target group", "connection draining",
        "load balancing", "alb", "nlb"
    ],
    "dns-global-networking": [
        "route 53", "dns resolver",
        "global accelerator", "cloudfront",
        "dns routing", "edge location"
    ],
    "amazon-s3": [
        "s3 bucket", "multipart upload",
        "s3 transfer acceleration",
        "s3 access point", "object versioning"
    ],
    "s3-storage-classes": [
        "s3 glacier", "s3 standard-ia",
        "intelligent-tiering", "one zone-ia",
        "lifecycle policy", "deep archive"
    ],
    "ebs-instance-store": [
        "ebs volume", "ebs snapshot",
        "instance store", "provisioned iops",
        "fast snapshot restore", "multi-attach"
    ],
    "efs-fsx": [
        "amazon efs", "amazon fsx",
        "nfs", "smb", "lustre",
        "windows file server"
    ],
    "storage-migration": [
        "storage gateway", "datasync",
        "snowball", "file gateway",
        "cached volume", "stored volume"
    ],
    "ec2-pricing": [
        "spot instance", "spot fleet",
        "reserved instance", "savings plan",
        "dedicated host", "instance tenancy"
    ],
    "auto-scaling": [
        "auto scaling group", "scaling policy",
        "predictive scaling", "scheduled scaling",
        "target tracking", "scale out"
    ],
    "lambda-serverless": [
        "lambda function", "lambda layer",
        "provisioned concurrency",
        "serverless function"
    ],
    "containers": [
        "amazon ecs", "amazon eks",
        "fargate", "kubernetes",
        "container orchestration"
    ],
    "deployment-monitoring": [
        "cloudformation", "cloudwatch",
        "elastic beanstalk", "systems manager",
        "maintenance window", "user data script"
    ],
    "rds-aurora": [
        "amazon rds", "amazon aurora",
        "read replica", "multi-az database",
        "aurora global database", "rds proxy"
    ],
    "dynamodb": [
        "dynamodb", "dynamodb streams",
        "dynamodb table", "on-demand capacity mode"
    ],
    "caching": [
        "elasticache", "dax",
        "dynamodb accelerator", "redis",
        "in-memory cache"
    ],
    "analytics-databases": [
        "redshift", "athena",
        "data warehouse", "sql analytics",
        "redshift ml"
    ],
    "database-migration": [
        "database migration service",
        "schema conversion tool",
        "database migration", "aws dms",
        "babelfish"
    ],
    "iam-policies": [
        "iam policy", "iam role",
        "permission boundary", "trust policy",
        "instance profile", "resource-based policy"
    ],
    "organizations-scps": [
        "service control policy",
        "service control policies",
        "aws organizations", "organizational unit",
        "consolidated billing"
    ],
    "encryption-kms": [
        "kms", "sse-kms", "sse-c",
        "encryption key", "client-side encryption",
        "server-side encryption"
    ],
    "network-security": [
        "security group", "network acl",
        "aws waf", "shield advanced",
        "rate-based rule", "geo match"
    ],
    "audit-compliance": [
        "cloudtrail", "aws config",
        "guardduty", "audit trail",
        "compliance monitoring"
    ],
    "high-availability": [
        "high availability", "fault tolerance",
        "availability zone", "automatic failover",
        "resilient architecture"
    ],
    "disaster-recovery": [
        "disaster recovery", "recovery time objective",
        "recovery point objective", "rto", "rpo",
        "pilot light", "warm standby"
    ],
    "decoupling-messaging": [
        "decouple", "sqs", "sns",
        "eventbridge", "message queue",
        "asynchronous processing", "kinesis"
    ],
    "cost-optimization": [
        "most cost-effective", "cost-optimal",
        "minimize costs", "reduce costs",
        "lowest cost", "cheapest"
    ],
    "performance-scalability": [
        "low latency", "high throughput",
        "performance bottleneck",
        "scalability", "traffic spikes"
    ]
}


# -------------------------------------------------
# TEXT MATCHING
# -------------------------------------------------

def contains_phrase(text: str, phrase: str) -> bool:
    """
    Match phrases without matching fragments
    inside unrelated words.
    """

    pattern = (
        r"(?<!\w)"
        + re.escape(phrase)
        + r"(?!\w)"
    )

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE
    ) is not None


def detect_services(text: str) -> list[str]:
    """
    Return all recognized AWS services.
    """

    detected = []

    for service, aliases in SERVICE_ALIASES.items():

        if any(
            contains_phrase(text, alias)
            for alias in aliases
        ):
            detected.append(service)

    return detected


# -------------------------------------------------
# LOAD TAXONOMY
# -------------------------------------------------

def load_taxonomy() -> dict:
    with TAXONOMY_FILE.open(
        "r", encoding="utf-8"
    ) as file:
        taxonomy = json.load(file)

    category_lookup = {}

    for topic in taxonomy["topics"]:
        for category in topic["categories"]:

            category_id = category["id"]

            if category_id in category_lookup:
                raise ValueError(
                    f"Duplicate category ID: {category_id}"
                )

            category_lookup[category_id] = {
                "topic": topic["name"],
                "category": category["name"]
            }

    unknown_rules = (
        set(CATEGORY_RULES)
        - set(category_lookup)
    )

    if unknown_rules:
        raise ValueError(
            f"Unknown category rules: {unknown_rules}"
        )

    return category_lookup


# -------------------------------------------------
# SCORE CATEGORIES
# -------------------------------------------------

def score_categories(
    question_text: str,
    answer_text: str
) -> dict[str, int]:
    """
    Score each category using keyword matches.

    The answer gets a higher weight because
    it often identifies the intended solution.
    """

    scores = {}

    for category_id, keywords in CATEGORY_RULES.items():

        score = 0

        for keyword in keywords:

            if contains_phrase(question_text, keyword):
                score += 1

            if contains_phrase(answer_text, keyword):
                score += 3

        if score > 0:
            scores[category_id] = score

    return scores


# -------------------------------------------------
# CLASSIFY ONE QUESTION
# -------------------------------------------------

def classify_question(
    question: Question,
    category_lookup: dict
) -> tuple[Question, dict]:

    classified = question.model_copy(deep=True)

    question_text = classified.original.question
    answer_text = classified.original.answer

    combined_text = question_text + "\n" + answer_text

    classified.classification.services = detect_services(
        combined_text
    )

    scores = score_categories(
        question_text,
        answer_text
    )

    # No evidence means no assigned category.
    # Do not invent a classification.
    if not scores:

        classified.classification.topic = None
        classified.classification.category = None
        classified.classification.secondary_categories = []

        return classified, {
            "question_id": classified.id,
            "status": "unclassified",
            "candidates": []
        }

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0])
    )

    best_id, best_score = ranked[0]

    # Only assign automatically when the leading
    # category has enough evidence and a clear lead.
    second_score = (
        ranked[1][1]
        if len(ranked) > 1
        else 0
    )

    confident = (
        best_score >= 3
        and best_score > second_score
    )

    # Preserve useful secondary classifications.
    secondary_ids = [
        category_id
        for category_id, score in ranked[1:]
        if score >= 2
    ]

    classified.classification.secondary_categories = [
        category_lookup[category_id]["category"]
        for category_id in secondary_ids
    ]

    status = "classified" if confident else "ambiguous"

    if confident:

        classified.classification.topic = (
            category_lookup[best_id]["topic"]
        )

        classified.classification.category = (
            category_lookup[best_id]["category"]
        )

    else:

        classified.classification.topic = None
        classified.classification.category = None

    return classified, {
        "question_id": classified.id,
        "status": status,
        "candidates": [
            {
                "category_id": category_id,
                "score": score
            }
            for category_id, score in ranked[:5]
        ]
    }


# -------------------------------------------------
# LOAD QUESTION BANK
# -------------------------------------------------

def load_questions() -> list[Question]:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Run deduplicate.py before classify.py."
        )

    with INPUT_FILE.open(
        "r", encoding="utf-8"
    ) as file:
        records = json.load(file)

    return [
        Question.model_validate(record)
        for record in records
    ]


# -------------------------------------------------
# CLASSIFY THE ENTIRE BANK
# -------------------------------------------------

def classify_all_questions():

    questions = load_questions()
    category_lookup = load_taxonomy()

    classified_questions = []
    decisions = []

    for question in questions:

        result, decision = classify_question(
            question,
            category_lookup
        )

        classified_questions.append(result)
        decisions.append(decision)

    status_counts = Counter(
        decision["status"]
        for decision in decisions
    )

    topic_counts = Counter(
        q.classification.topic
        for q in classified_questions
        if q.classification.topic
    )

    report = {
        "total_questions": len(classified_questions),
        "status_counts": dict(status_counts),
        "topic_counts": dict(topic_counts),
        "needs_review": [
            decision
            for decision in decisions
            if decision["status"] != "classified"
        ],
        "all_decisions": decisions
    }

    NORMALIZED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w", encoding="utf-8"
    ) as file:

        json.dump(
            [
                q.model_dump(mode="json")
                for q in classified_questions
            ],
            file,
            indent=2,
            ensure_ascii=False
        )

    with REPORT_FILE.open(
        "w", encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\nClassification Summary")
    print("----------------------")
    print("Total:", len(classified_questions))

    for status, count in status_counts.items():
        print(f"{status}: {count}")

    print("\nQuestions by primary topic:")

    for topic, count in sorted(topic_counts.items()):
        print(f"{topic}: {count}")

    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"Saved: {REPORT_FILE}")


# -------------------------------------------------
# SCRIPT ENTRY POINT
# -------------------------------------------------

if __name__ == "__main__":
    classify_all_questions()
