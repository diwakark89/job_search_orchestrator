from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant.
Return strict JSON only with keys:
- tech_stack: array of strings
- experience_level: one of [Intern, Junior, Mid, Senior, Staff, Principal, Lead, Unknown]
- remote_type: one of [Onsite, Hybrid, Remote, Unknown]
- visa_sponsorship: boolean or null
- english_friendly: boolean or null

If unsure, use null booleans and Unknown enum fields. No markdown.
"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract structured job metadata from this job description:

{description}
"""

CANONICAL_TECH_STACK: dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react": "React",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "py": "Python",
    "python": "Python",
    "csharp": "C#",
    "c#": "C#",
    "dotnet": ".NET",
    ".net": ".NET",
    "golang": "Go",
    "go": "Go",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
}

ALLOWED_EXPERIENCE_LEVELS: set[str] = {
    "Intern",
    "Junior",
    "Mid",
    "Senior",
    "Staff",
    "Principal",
    "Lead",
    "Unknown",
}

ALLOWED_REMOTE_TYPES: set[str] = {
    "Onsite",
    "Hybrid",
    "Remote",
    "Unknown",
}
