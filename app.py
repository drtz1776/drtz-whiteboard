
from flask import Flask, render_template, abort

from projects_data import PROJECTS
from solutions_architect.routes import bp as solutions_architect_bp


app = Flask(__name__)

# Register Solutions Architect study application
app.register_blueprint(solutions_architect_bp)


# HOME
@app.route("/")
def home():
    return render_template("index.html")


# PROJECTS OVERVIEW
@app.route("/projects")
def projects():
    return render_template(
        "projects.html",
        projects=PROJECTS
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


# ABOUT
@app.route("/about")
def about():
    return render_template("about.html")


# BOOKS
@app.route("/books")
def books():
    return render_template("books.html")


# RESUME
@app.route("/resume")
def resume():
    return render_template("resume.html")


if __name__ == "__main__":
    app.run(debug=True)
