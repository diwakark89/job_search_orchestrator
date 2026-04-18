from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant.
Return strict JSON only with keys:
- tech_stack: array of strings
- experience_level: one of [Intern, Junior, Mid, Senior, Staff, Principal, Lead, Unknown]
- work_mode: one of [remote, hybrid, on-site, other]

If unsure, use Unknown for experience_level and other for work_mode. No markdown.
"""

BATCH_EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant.
Return strict JSON only with this shape:
{
    "results": [
        {
            "id": "<input id>",
            "tech_stack": ["<technology>"],
            "experience_level": "Intern|Junior|Mid|Senior|Staff|Principal|Lead|Unknown",
            "work_mode": "remote|hybrid|on-site|other"
        }
    ]
}

Rules:
- Return exactly one result object for each input item.
- Preserve each input id exactly.
- Do not omit ids, add explanations, or include markdown.
- If unsure, use Unknown for experience_level, other for work_mode, and an empty array for tech_stack.
"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract structured job metadata from this job description:

{description}
"""

BATCH_EXTRACTION_USER_PROMPT_TEMPLATE = """Extract structured job metadata for each item in this JSON array:

{items_json}
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
