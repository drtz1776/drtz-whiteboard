from projects_data import PROJECTS
from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


# PROJECTS OVERVIEW
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


# INDIVIDUAL PROJECT PAGES
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
