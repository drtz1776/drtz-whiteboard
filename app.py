
from flask import Flask, render_template

app = Flask(__name__)

PROJECTS = [
    {
        "slug": "solutions-architect",
        "name": "Solutions Architect",
        "description": "Interactive game for practicing SAA-C03 exam questions",
        "category": "Learning",
        "status": "In Development"
    },
    {
        "slug": "nfl-scorecards",
        "name": "NFL Scorecards",
        "description": "NFL analytics and matchup scorecards",
        "category": "Analytics",
        "status": "In Development"
    },
    {
        "slug": "restaurant-promos",
        "name": "Restaurant Promos",
        "description": "Restaurant Weekly Promos",
        "category": "Consumer",
        "status": "Planned"
    },
    {
        "slug": "propane-crm",
        "name": "Suburban Propane CRM",
        "description": "CRM and operational tools",
        "category": "CRM",
        "status": "Planned"
    },
    {
        "slug": "earnings-dashboard",
        "name": "Earnings Dashboard",
        "description": "Track earnings, estimates, and market reactions",
        "category": "Financial Data",
        "status": "Planned"
    },
    {
        "slug": "mexicali-land",
        "name": "Mexicali Land Development",
        "description": "Analyze land economics and solar development",
        "category": "Land Analysis",
        "status": "Research"
    },
    {
        "slug": "tiktok-seo",
        "name": "TikTok SEO",
        "description": "TikTok ads & recommendations",
        "category": "Analytics",
        "status": "Planned"
    },
    {
        "slug": "fb-marketplace",
        "name": "Facebook Marketplace MCP",
        "description": "Facebook Marketplace MCP & Analytics",
        "category": "Consumer",
        "status": "Planned"
    },
    {
        "slug": "youtube-transcription",
        "name": "YouTube Transcription",
        "description": "Channel and video transcription",
        "category": "Research",
        "status": "Planned"
    },
    {
        "slug": "satellite-imagery",
        "name": "Satellite Imagery",
        "description": "Geospatial imagery and mapping tools",
        "category": "Geospatial",
        "status": "Planned"
    },
    {
        "slug": "personal-website",
        "name": "Personal Website",
        "description": "My personal development whiteboard",
        "category": "Web Development",
        "status": "In Development"
    }
]

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/projects")
def projects():

    stats = {
        "total": len(PROJECTS),

        "in_development": sum(
            p["status"] == "In Development"
            for p in PROJECTS
        ),

        "planned": sum(
            p["status"] == "Planned"
            for p in PROJECTS
        ),

        "research": sum(
            p["status"] == "Research"
            for p in PROJECTS
        )
    }

    return render_template(
        "projects.html",
        projects=PROJECTS,
        stats=stats
    )

# INDIVIDUAL POROJECT PAGES
@app.route("/projects/<slug>")
def project_detail(slug):

    project = next(
        (p for p in PROJECTS if p["slug"] == slug),
        None
    )

    if project is None:
        abort(404)

    return render_template(
        "project_detail.html",
        project=project,
        projects=PROJECTS
    )


@app.route("/solutions-architect")
def solutions_architect():
    return render_template("solutions_architect.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/books")
def books():
    return render_template("books.html")


@app.route("/resume")
def resume():
    return render_template("resume.html")


if __name__ == "__main__":
    app.run(debug=True)
