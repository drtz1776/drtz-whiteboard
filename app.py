
from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/projects")
def projects():
    projects = [
        {
            "name": "NFL Scorecards",
            "description": "NFL analytics and matchup scorecards",
            "category": "Sports Analytics",
            "status": "In Development",
            "icon": "🏆",
        },
        {
            "name": "Earnings Dashboard",
            "description": "Track earnings, estimates, and market reactions",
            "category": "Financial Data",
            "status": "Planned",
            "icon": "📈",
        },
        {
            "name": "Mexicali Solar",
            "description": "Analyze land economics and solar development",
            "category": "Land Analysis",
            "status": "Research",
            "icon": "☀️",
        },
        {
            "name": "Satellite Imagery",
            "description": "Geospatial imagery and mapping tools",
            "category": "Geospatial",
            "status": "Planned",
            "icon": "📍",
        },
        {
            "name": "Propane CRM",
            "description": "CRM and operational tools for propane businesses",
            "category": "CRM",
            "status": "Planned",
            "icon": "🗄️",
        },
        {
            "name": "Restaurant App",
            "description": "Restaurant data, reviews, and discovery",
            "category": "Consumer",
            "status": "Planned",
            "icon": "🍴",
        },
        {
            "name": "Marketplace",
            "description": "Simple two-sided marketplace application",
            "category": "Commerce",
            "status": "Planned",
            "icon": "🛍️",
        },
        {
            "name": "YouTube Analytics",
            "description": "Analyze channels, videos, and performance",
            "category": "Media Analytics",
            "status": "Planned",
            "icon": "🎥",
        },
        {
            "name": "Storyline Tools",
            "description": "Tools and experiments for Storyline workflows",
            "category": "AI / Media",
            "status": "Active",
            "icon": "🎞️",
        },
        {
            "name": "Personal Website",
            "description": "The site you're looking at right now",
            "category": "Web Development",
            "status": "In Development",
            "icon": "🌐",
        },
    ]
    return render_template("projects.html")

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
