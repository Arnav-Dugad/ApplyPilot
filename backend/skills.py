"""Deterministic skill taxonomy: canonical names, aliases, and related skills for partial credit."""
from __future__ import annotations

import re

# canonical -> aliases (all lowercase). Canonical names are what users see.
TAXONOMY: dict[str, tuple[str, ...]] = {
    # languages
    "python": ("python3", "py"), "java": (), "javascript": ("js", "ecmascript"), "typescript": ("ts",),
    "c++": ("cpp", "c plus plus"), "c": ("ansi c",), "c#": ("csharp", "c sharp"), "go": ("golang",), "rust": (),
    "kotlin": (), "swift": (), "scala": (), "ruby": (), "php": (), "r": ("r language",), "matlab": (),
    "sql": ("structured query language",), "bash": ("shell scripting",), "dart": (), "haskell": (), "julia": (),
    "solidity": (), "verilog": (), "vhdl": (),
    # web / frontend
    "react": ("react.js", "reactjs"), "next.js": ("nextjs",), "vue": ("vue.js", "vuejs"), "angular": ("angularjs",),
    "svelte": (), "html": ("html5",), "css": ("css3",), "tailwind": ("tailwindcss", "tailwind css"), "redux": (),
    "graphql": (), "rest api": ("restful", "rest apis", "restful apis", "rest"), "grpc": (), "websockets": ("websocket",),
    # backend
    "node.js": ("node", "nodejs"), "express": ("express.js",), "django": (), "flask": (), "fastapi": (),
    "spring": ("spring boot", "springboot"), ".net": ("dotnet", "asp.net"), "rails": ("ruby on rails",),
    "microservices": ("microservice",), "distributed systems": ("distributed computing",), "system design": (),
    # data / storage
    "postgresql": ("postgres", "psql"), "mysql": (), "mongodb": ("mongo",), "redis": (), "sqlite": (),
    "elasticsearch": ("elastic search",), "cassandra": (), "dynamodb": (), "kafka": ("apache kafka",),
    "spark": ("apache spark", "pyspark"), "hadoop": (), "airflow": ("apache airflow",), "dbt": (), "snowflake": (),
    "bigquery": (), "etl": ("data pipelines", "data pipeline"), "data structures": ("data structure",),
    "algorithms": ("algorithm", "algorithmic"),
    # ml / ai
    "machine learning": ("ml",), "deep learning": ("dl",), "artificial intelligence": (), "nlp": ("natural language processing",),
    "computer vision": (), "llms": ("llm", "large language models", "large language model"), "pytorch": ("torch",),
    "tensorflow": ("tf",), "keras": (), "scikit-learn": ("sklearn", "scikit learn"), "pandas": (), "numpy": (),
    "statistics": ("statistical analysis",), "data analysis": ("data analytics",), "data science": (),
    "reinforcement learning": ("rl",), "mlops": (), "hugging face": ("huggingface", "transformers"),
    # cloud / devops
    "aws": ("amazon web services",), "azure": ("microsoft azure",), "gcp": ("google cloud", "google cloud platform"),
    "docker": ("containerization",), "kubernetes": ("k8s",), "terraform": (), "ci/cd": ("cicd", "continuous integration", "github actions", "jenkins"),
    "linux": ("unix",), "git": ("github", "version control"), "networking": ("tcp/ip",), "cybersecurity": ("information security", "application security", "network security", "security engineering"),
    # mobile
    "android": (), "ios": (), "react native": (), "flutter": (),
    # tools / other
    "excel": ("microsoft excel", "spreadsheets"), "tableau": (), "power bi": ("powerbi",), "figma": (), "jira": (),
    "agile": ("scrum",), "testing": ("unit testing", "test automation", "pytest", "jest", "junit"), "oop": ("object-oriented", "object oriented programming"),
    "embedded systems": ("firmware",), "robotics": ("ros",), "blockchain": ("web3",), "cloud computing": (),
    "operating systems": ("os internals",), "compilers": ("compiler",), "databases": ("dbms",),
    "financial modeling": ("financial modelling",),
}

# Knowing the key skill earns half credit for the related requirement.
RELATED: dict[str, tuple[str, ...]] = {
    "typescript": ("javascript",), "javascript": ("typescript",), "react": ("javascript", "typescript", "next.js", "react native"),
    "next.js": ("react",), "react native": ("react",), "node.js": ("javascript", "typescript", "express"), "express": ("node.js",),
    "postgresql": ("sql", "mysql", "databases"), "mysql": ("sql", "postgresql", "databases"), "sql": ("postgresql", "mysql", "sqlite", "databases"),
    "databases": ("sql", "postgresql", "mysql", "mongodb"), "sqlite": ("sql",), "mongodb": ("databases",),
    "pytorch": ("tensorflow", "deep learning", "machine learning"), "tensorflow": ("pytorch", "keras", "deep learning"), "keras": ("tensorflow",),
    "deep learning": ("machine learning", "pytorch", "tensorflow"), "machine learning": ("deep learning", "scikit-learn", "data science"),
    "scikit-learn": ("machine learning",), "data science": ("machine learning", "data analysis", "pandas"), "pandas": ("numpy", "data analysis", "python"),
    "numpy": ("pandas", "python"), "llms": ("nlp", "machine learning", "hugging face"), "nlp": ("llms", "machine learning"),
    "aws": ("gcp", "azure", "cloud computing"), "gcp": ("aws", "azure", "cloud computing"), "azure": ("aws", "gcp", "cloud computing"),
    "cloud computing": ("aws", "gcp", "azure"), "docker": ("kubernetes",), "kubernetes": ("docker",), "java": ("kotlin", "scala", "spring"),
    "kotlin": ("java", "android"), "spring": ("java",), "c++": ("c", "rust"), "c": ("c++",), "rust": ("c++", "go"), "go": ("rust",),
    "flask": ("django", "fastapi", "python"), "django": ("flask", "fastapi", "python"), "fastapi": ("flask", "django", "python"),
    "spark": ("hadoop", "etl"), "etl": ("airflow", "spark", "sql"), "airflow": ("etl",), "vue": ("react", "angular"), "angular": ("react", "vue", "typescript"),
    "data structures": ("algorithms",), "algorithms": ("data structures",), "tableau": ("power bi", "data analysis"), "power bi": ("tableau", "data analysis"),
    "linux": ("bash",), "bash": ("linux",), "microservices": ("distributed systems", "rest api"), "distributed systems": ("microservices", "system design"),
}

_ALIASES = {alias: canonical for canonical, aliases in TAXONOMY.items() for alias in (canonical, *aliases)}
# Short or ambiguous tokens are only trusted when written exactly, to avoid matching ordinary words.
_AMBIGUOUS = {"r", "c", "go", "ml", "rl", "ts", "js", "py", "tf", "dl", "rest", "node"}
_PATTERN = re.compile(
    r"(?<![\w+#.])(" + "|".join(sorted((re.escape(a) for a in _ALIASES), key=len, reverse=True)) + r")(?![\w+#])",
    re.IGNORECASE,
)


def canonical(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip().lower())
    return _ALIASES.get(text, text)


def find_skills(text: str) -> list[str]:
    """Skills mentioned in text, in first-seen order. Ambiguous short aliases require exact casing."""
    found: list[str] = []
    for match in _PATTERN.finditer(text):
        token = match.group(1)
        lowered = token.lower()
        if lowered in _AMBIGUOUS and not _exact_mention(token):
            continue
        if lowered == "spring" and re.match(r"(?i)\s*('?\d{2,4}|semester|term|break|quarter|session|internship|intake|co-?op|and summer|/|or )", text[match.end():match.end() + 14]):
            continue  # "Spring 2027" is a season, not the Java framework
        if lowered == "go" and not re.search(r"(?i)\bgo(lang)?\b\s*(,|and|or|/|\)|developer|programming|language)", text[match.start():match.end() + 14]):
            continue
        skill = _ALIASES[lowered]
        if skill not in found:
            found.append(skill)
    return found


def _exact_mention(token: str) -> bool:
    # "R", "C", "Go", "ML", "JS" are meaningful in their conventional casing only.
    return token in {"R", "C", "Go", "ML", "RL", "TS", "JS", "TF", "DL", "REST", "Node", "Py"}


def related_credit(skill: str, known: set[str]) -> bool:
    return any(r in known for r in RELATED.get(skill, ()))


# How each skill is written on a CV. Anything not listed is title-cased.
DISPLAY = {
    ".net": ".NET", "aws": "AWS", "c#": "C#", "c++": "C++", "ci/cd": "CI/CD", "css": "CSS", "dbt": "dbt", "etl": "ETL", "fastapi": "FastAPI", "gcp": "Google Cloud",
    "git": "Git", "graphql": "GraphQL", "grpc": "gRPC", "html": "HTML", "ios": "iOS", "javascript": "JavaScript", "llms": "LLMs", "matlab": "MATLAB", "mlops": "MLOps",
    "mongodb": "MongoDB", "mysql": "MySQL", "next.js": "Next.js", "nlp": "NLP", "node.js": "Node.js", "numpy": "NumPy", "oop": "OOP", "pandas": "pandas", "php": "PHP",
    "postgresql": "PostgreSQL", "power bi": "Power BI", "pytorch": "PyTorch", "rest api": "REST APIs", "scikit-learn": "scikit-learn", "sql": "SQL", "sqlite": "SQLite",
    "tensorflow": "TensorFlow", "typescript": "TypeScript", "verilog": "Verilog", "vhdl": "VHDL", "websockets": "WebSockets", "dynamodb": "DynamoDB", "bigquery": "BigQuery",
    "elasticsearch": "Elasticsearch", "hugging face": "Hugging Face", "react native": "React Native", "r": "R", "c": "C", "go": "Go", "redux": "Redux", "rails": "Rails",
}


def display(skill: str) -> str:
    key = canonical(skill)
    return DISPLAY.get(key) or " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in key.split())
