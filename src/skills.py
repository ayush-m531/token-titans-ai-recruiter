"""skills.py - one place to clean skill names, used by parser, db and screening."""

SYNONYMS = {
    "ml": "machine learning", "dl": "deep learning", "ai": "artificial intelligence",
    "nlp": "natural language processing", "cv": "computer vision",
    "js": "javascript", "ts": "typescript", "py": "python", "python3": "python",
    "k8s": "kubernetes", "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "postgres": "postgresql", "mssql": "sql server", "golang": "go",
    "node": "node.js", "nodejs": "node.js", "react.js": "react", "reactjs": "react",
    "css3": "css", "html5": "html",
    "angular.js": "angular", "angularjs": "angular",
    "vue.js": "vue", "vuejs": "vue",
}


def normalise_skill(s):
    """'  ML ' -> 'machine learning'"""
    s = " ".join(str(s).lower().split())     # lowercase + clean spaces
    return SYNONYMS.get(s, s)
