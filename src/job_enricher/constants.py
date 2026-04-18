from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant.
Return strict JSON only with keys:
- tech_stack: array of strings
- experience_level: one of [Intern, Junior, Mid, Senior, Staff, Principal, Lead, Unknown]
- remote_type: one of [Onsite, Hybrid, Remote, Unknown]

If unsure, use Unknown enum fields. No markdown.
"""

BATCH_EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant.
Return strict JSON only with this shape:
{
    "results": [
        {
            "id": "<input id>",
            "tech_stack": ["<technology>"],
            "experience_level": "Intern|Junior|Mid|Senior|Staff|Principal|Lead|Unknown",
            "remote_type": "Onsite|Hybrid|Remote|Unknown"
        }
    ]
}

Rules:
- Return exactly one result object for each input item.
- Preserve each input id exactly.
- Do not omit ids, add explanations, or include markdown.
- If unsure, use Unknown enum fields and an empty array for tech_stack.
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

ALLOWED_REMOTE_TYPES: set[str] = {
    "Onsite",
    "Hybrid",
    "Remote",
    "Unknown",
}
