"""Interview prep packs: likely questions, company notes, and the candidate's own matching projects."""
from __future__ import annotations

import json
import re
from typing import Any

from .skills import RELATED, canonical, find_skills

TECHNICAL: dict[str, list[str]] = {
    "python": ["How do lists, tuples, sets, and dicts differ, and when would you pick each?", "What are generators, and why might you use one instead of a list?", "Explain the GIL and how it affects multithreaded Python."],
    "java": ["What's the difference between an interface and an abstract class?", "How does garbage collection work in the JVM at a high level?", "Explain equals() and hashCode(), and why they must agree."],
    "javascript": ["Explain closures with an example.", "How does the event loop handle promises versus setTimeout?", "What's the difference between == and ===?"],
    "typescript": ["What problems does TypeScript's type system catch that JavaScript can't?", "When would you use a union type versus an interface with optional fields?"],
    "react": ["How does React decide when to re-render a component?", "When would you reach for useMemo or useCallback — and when not?", "How would you manage state that many components share?"],
    "node.js": ["How does Node handle many concurrent requests on one thread?", "How would you structure error handling in an Express API?"],
    "c++": ["Explain RAII and why it matters.", "What's the difference between a pointer and a reference?", "When would you use unique_ptr versus shared_ptr?"],
    "c": ["What happens in memory when you call malloc and free?", "Explain undefined behaviour with an example."],
    "go": ["How do goroutines and channels work together?", "How does Go handle errors, and why no exceptions?"],
    "rust": ["Explain ownership and borrowing.", "When would you use Rc versus Arc?"],
    "sql": ["Explain the different JOIN types with an example.", "How would you find the second-highest salary in a table?", "What's an index, and when can it hurt performance?"],
    "postgresql": ["How would you diagnose a slow query in PostgreSQL?", "What are transactions and isolation levels?"],
    "machine learning": ["Explain the bias–variance trade-off.", "How would you handle an imbalanced dataset?", "How do you know a model isn't overfitting?"],
    "deep learning": ["What does backpropagation compute?", "Why do we use batch normalization or dropout?"],
    "pytorch": ["Walk through a minimal PyTorch training loop.", "What does model.eval() change?"],
    "llms": ["How does retrieval-augmented generation work?", "How would you evaluate an LLM feature before shipping it?"],
    "data structures": ["When would you use a hash map versus a balanced tree?", "Implement a queue using two stacks."],
    "algorithms": ["Find the kth largest element in an array — what's the complexity?", "Detect a cycle in a linked list.", "Explain how you'd approach a dynamic programming problem."],
    "system design": ["Design a URL shortener.", "How would you design a rate limiter?"],
    "distributed systems": ["What does the CAP theorem say, practically?", "How would you make an operation idempotent?"],
    "aws": ["Which AWS services would you use to host a simple web app, and why?", "What's the difference between S3 and EBS?"],
    "docker": ["What's the difference between an image and a container?", "How would you make a Docker image smaller?"],
    "kubernetes": ["What problem does a Kubernetes Deployment solve?", "What's the difference between a Service and an Ingress?"],
    "git": ["What's the difference between merge and rebase?", "How would you undo a commit that's already pushed?"],
    "rest api": ["What makes an API RESTful?", "How would you version an API?"],
    "statistics": ["Explain a p-value to a non-technical person.", "What's the difference between correlation and causation — give an example."],
    "data analysis": ["Walk through how you'd investigate a sudden drop in a key metric.", "How would you design an A/B test?"],
    "excel": ["How would you use a pivot table to summarise sales by region and month?", "VLOOKUP versus INDEX/MATCH — when does it matter?"],
    "cybersecurity": ["Explain SQL injection and how to prevent it.", "What's the difference between authentication and authorization?"],
    "linux": ["How would you find which process is using a port?", "Explain file permissions like 755."],
}
ROLE_QUESTIONS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"(?i)data|analyst|analytics"), ["Tell me about a time data changed a decision.", "How do you check that a dataset is trustworthy before analysing it?"]),
    (re.compile(r"(?i)machine learning|\bml\b|\bai\b|research"), ["Walk me through an ML project end to end, including how you evaluated it.", "How would you explain your model's predictions to a stakeholder?"]),
    (re.compile(r"(?i)front ?end|ui|web"), ["How do you make a web page accessible?", "How would you speed up a slow-loading page?"]),
    (re.compile(r"(?i)back ?end|platform|infrastructure|server"), ["How would you design an API that thousands of clients call per second?", "How do you debug a production issue you can't reproduce locally?"]),
    (re.compile(r"(?i)product|program|manager"), ["How would you prioritise three features with one sprint of time?", "Tell me about a product you love and one thing you'd change."]),
    (re.compile(r"(?i)security"), ["How would you threat-model a login page?", "Tell me about a security issue you found or fixed."]),
    (re.compile(r"(?i)quant|trading|finance"), ["What's the expected number of coin flips to get two heads in a row?", "How would you value a simple option intuitively?"]),
    (re.compile(r"(?i)design"), ["Walk me through a design decision you changed after user feedback.", "How do you balance consistency with a new idea?"]),
]
BEHAVIOURAL = [
    "Tell me about yourself — in two minutes.",
    "Describe a project you're proud of. What was your specific contribution?",
    "Tell me about a time you disagreed with a teammate. What happened?",
    "Describe a time you failed or missed a deadline. What did you learn?",
    "Tell me about something you learned quickly under pressure.",
]


def _projects(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projects = []
    for f in facts:
        if f.get("category") != "projects" or f.get("status") != "VERIFIED":
            continue
        value = f.get("value", f.get("value_json"))
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {"name": f["fact_key"].replace("_", " "), "description": value}
        if isinstance(value, dict):
            skills = [canonical(s) for s in value.get("skills") or []] or find_skills(f"{value.get('name', '')} {value.get('description', '')}")
            projects.append({"name": value.get("name") or f["fact_key"].replace("_", " ").title(), "description": value.get("description") or "", "skills": skills, "link": value.get("link")})
    return projects


def build_pack(job: dict[str, Any], facts: list[dict[str, Any]], notes: str = "") -> dict[str, Any]:
    required = [canonical(s) for s in job.get("required_skills") or []]
    preferred = [canonical(s) for s in job.get("preferred_skills") or []]
    company, role = job.get("company") or "the company", job.get("role") or "this role"
    technical = []
    for skill in required + preferred:
        for question in TECHNICAL.get(skill, [])[:2]:
            technical.append({"skill": skill, "question": question})
    technical = technical[:12]
    role_specific = [q for pattern, qs in ROLE_QUESTIONS if pattern.search(role) for q in qs][:4]
    company_questions = [f"Why {company}, and why this {role} role specifically?", f"What do you know about {company}'s products and customers?", f"What would you want to learn in your first month at {company}?"]
    wanted = set(required + preferred)
    def overlap(project: dict[str, Any]) -> set[str]:  # a PostgreSQL project also shows SQL
        have = set(project["skills"])
        return {w for w in wanted if w in have or any(r in have for r in RELATED.get(w, ()))}

    projects = sorted(_projects(facts), key=lambda p: -len(overlap(p)))
    matched = [{**p, "overlap": sorted(overlap(p))} for p in projects if overlap(p)][:4]
    summary = job.get("ai_summary") or {}
    company_notes = [x for x in [summary.get("summary"), *(summary.get("highlights") or [])] if x]
    if not company_notes and job.get("description"):
        company_notes = [s.strip() for s in re.split(r"(?<=[.!?])\s+", job["description"])[:3] if len(s.strip()) > 30]
    return {
        "role": role, "company": company, "technical": technical, "role_specific": role_specific, "company_questions": company_questions,
        "behavioural": BEHAVIOURAL, "projects": matched, "unmatched_skills": sorted(wanted - {s for p in matched for s in p["overlap"]})[:8],
        "company_notes": company_notes[:4], "your_notes": notes, "questions_to_ask": ["What does a great first three months look like for an intern on this team?", "How is intern work reviewed and shipped?", f"What's something you wish you'd known before joining {company}?"],
    }
