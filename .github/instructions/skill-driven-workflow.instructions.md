---
description: "Use when the user attaches an instruction, prompt, or SKILL.md file and asks to follow it. Guides best-effort skill-first execution, linked-reference loading, and repo-verified documentation updates."
name: "Skill-Driven Workflow"
---

# Skill-Driven Workflow

- Treat an attached instruction or prompt file as authoritative task context.
- Read the referenced file before planning, editing files, or running implementation commands.
- If the file references related guidance (for example, another skill or references/instructions.md), load and follow those files before acting.
- Extract explicit user rules from the current conversation and convert them into actionable constraints for the current task.
- Prefer repository-verified facts over assumptions when writing docs or instructions.
- Before updating project docs, verify commands and workflows against current files such as pyproject.toml, README.md, and CI workflows.
- Keep instruction outputs concise, actionable, and directly executable.
- If a required file cannot be found, report the missing path and use the closest matching reference that exists.
