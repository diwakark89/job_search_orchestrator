---
goal: End-to-end automated job apply pipeline with Android control plane and OpenClaw worker
version: 1.0
date_created: 2026-05-19
last_updated: 2026-05-19
owner: diwakark89
status: Planned
tags: [implementation-plan, android, openclaw, playwright, supabase, orchestration]
---

# Introduction

This plan defines how to implement the full lifecycle:

Scrape -> Enrich -> Android Approve -> Create Session -> OpenClaw Applies -> Pause -> Android Confirm -> Submit -> Done.

The architecture roles remain:

- Android app = control panel
- job_manager = brain and orchestration layer
- OpenClaw = browser automation worker
- Playwright = execution engine
- Supabase = single source of truth

## 1. Requirements and Constraints

- REQ-001: Daily scraping must ingest new jobs into jobs_final with job_status=SCRAPED.
- REQ-002: Enrichment must write scoring and decision metadata to jobs_final.
- REQ-003: Android approval must control progression into apply automation.
- REQ-004: Automation session state must be persisted and resumable.
- REQ-005: Final submit must require explicit user confirmation in Android.
- SEC-001: Keep existing API key protection for mutation endpoints.
- CON-001: Supabase remains the canonical state source.
- CON-002: Keep lifecycle orchestration actions CLI-only; do not expose automation lifecycle mutation endpoints via HTTP.

## 2. Current Gaps in job_manager

- GAP-001: No dedicated apply orchestration stage after enrichment.
- GAP-002: automation_sessions exists as CRUD only; no worker consumes RUNNING or RESUMING sessions.
- GAP-003: No Playwright apply implementation exists in src.
- GAP-004: WAITING_CONFIRMATION and READY_TO_APPLY lifecycle values were not part of prior status flow.
- GAP-005: Android currently relies on generic table updates; critical transitions are not guarded by orchestration rules.

## 3. Task IDs by Phase

### Phase 1: Daily Scraping (from your Phase 1)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-001 | Add daily scheduler entrypoint for scrape + submit orchestration | Runnable command and schedule docs |
| AJH-AUTO-002 | Enforce per-day cap and source guardrails (about 10 jobs/day) | Guardrail config and logs |
| AJH-AUTO-003 | Persist rows to jobs_final with SCRAPED via submit flow | Verified ingest behavior |
| AJH-AUTO-004 | Add run correlation id and ingest summary logs | Observability baseline |

### Phase 2: Enrichment + AI Scoring (from your Phase 2)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-005 | Extend enrich pipeline output contract for match_score, decision, reason, tech stack fields | Updated service contract |
| AJH-AUTO-006 | Normalize and validate enrichment fields before persistence | Validation coverage |
| AJH-AUTO-007 | Update ENRICHED transition behavior and metrics tracking | Stage metrics |
| AJH-AUTO-008 | Add tests for enrichment payload integrity and status transitions | Passing test cases |

### Phase 3: Android Approval Human Layer (from your Phase 3)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-009 | Add Android review queue endpoint for ENRICHED candidates | Read endpoint |
| AJH-AUTO-010 | Add approve action endpoint setting user_action=APPROVED | Mutation endpoint |
| AJH-AUTO-011 | Move approved jobs to READY_TO_APPLY (or SAVED fallback mode flag) | Controlled transition |
| AJH-AUTO-012 | Add reject action endpoint setting user_action=REJECTED | Rejection path |
| AJH-AUTO-013 | Persist approved_at and action metadata | Auditability |

### Phase 4: Create Application Task (from your Phase 4)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-014 | Create orchestration service to open automation_sessions for approved jobs | Service function |
| AJH-AUTO-015 | Initialize session_status=RUNNING and current_step=OPEN_JOB_PAGE | Deterministic session start |
| AJH-AUTO-016 | Prevent duplicate active session per job_id | Idempotency guard |
| AJH-AUTO-017 | Add API/CLI trigger for session creation | Operator surface |

### Phase 5: OpenClaw Application Worker (from your Phase 5)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-018 | Add worker loop to fetch RUNNING sessions ordered by updated_at | Worker dispatcher |
| AJH-AUTO-019 | Add Playwright/OpenClaw adapter interface for apply workflow | Port and adapter contracts |
| AJH-AUTO-020 | Implement open job page and click apply step | Step handler |
| AJH-AUTO-021 | Implement form fill and resume upload steps | Step handlers |
| AJH-AUTO-022 | Persist current_step transitions and recoverable errors | Session state progression |
| AJH-AUTO-023 | Mark FAILED with last_error on terminal failures | Failure semantics |

### Phase 6: Pause for Human Confirmation (from your Phase 6)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-024 | Save Playwright browser state artifact before final submit | browser_state_path written |
| AJH-AUTO-025 | Save screenshot artifact for Android preview | screenshot_path written |
| AJH-AUTO-026 | Transition session_status to WAITING_USER | Paused session |
| AJH-AUTO-027 | Transition job_status to WAITING_CONFIRMATION | Waiting confirmation queue |
| AJH-AUTO-028 | Build summary payload for Android final review | Review contract |

### Phase 7: Android Final Approval (from your Phase 7)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-029 | Add final decision endpoint: SUBMIT or CANCEL | Android action endpoint |
| AJH-AUTO-030 | SUBMIT decision transitions session_status to RESUMING | Resume trigger |
| AJH-AUTO-031 | CANCEL decision transition to agreed terminal state | Cancel semantics |
| AJH-AUTO-032 | Add permission and validation checks for final actions | Safe mutation flow |

### Phase 8: Resume and Submit (from your Phase 8)

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-033 | Worker consumes RESUMING sessions and restores browser state | Resume execution |
| AJH-AUTO-034 | Execute final submit action with retry policy | Final submit handler |
| AJH-AUTO-035 | On success set session_status=COMPLETED | Completed session |
| AJH-AUTO-036 | On success set job_status=APPLIED | Applied job state |
| AJH-AUTO-037 | Add completion telemetry and post-submit audit logs | Operational visibility |

### Final State and Operational Hardening

| Task ID | Description | Deliverable |
|---|---|---|
| AJH-AUTO-038 | Add lifecycle transition guard module for legal state changes | Transition policy layer |
| AJH-AUTO-039 | Add integration tests for full scrape-to-apply flow | End-to-end test path |
| AJH-AUTO-040 | Add failure injection tests for pause/resume and stale browser artifacts | Reliability tests |
| AJH-AUTO-041 | Add dashboards and counters for session statuses and apply success rate | Runtime metrics |
| AJH-AUTO-042 | Update integration docs for CLI-only orchestration contract | Docs published |
| AJH-AUTO-043 | Update schema docs and migration notes | Data contract docs |
| AJH-AUTO-044 | Add operator runbook for stuck sessions and retries | Incident playbook |
| AJH-AUTO-045 | Add staged rollout checklist and feature-flag gates | Safer production rollout |

## 4. Suggested File Targets

- src/service/automation.py (new lifecycle service)
- src/service/automation_worker.py (new worker loop)
- src/service/lifecycle.py (new transition guard policy)
- src/automation_sessions/cli.py (CLI lifecycle commands)
- src/common/constants.py (status vocabulary)
- src/common/validators.py (status validation)
- db/03_alter_jobs_final_job_status_values.sql (status migration)
- db/04_alter_automation_sessions_lifecycle.sql (future automation session lifecycle changes)
- docs/INTEGRATION.md (API lifecycle updates)
- docs/SUPABASE_SCHEMA.md (state machine updates)
- tests/test_automation_lifecycle.py (new lifecycle tests)
- tests/test_automation_worker.py (new worker tests)

## 5. Verification Checklist

1. Unit tests for validator, lifecycle policy, and orchestration service.
2. CLI tests for approve/reject/session-create, plus API tests for remaining HTTP surfaces.
3. Worker tests for RUNNING and RESUMING pickup, retry, and failure paths.
4. Manual dry-run using sandbox data from scrape through final decision.
5. One controlled live apply smoke test to validate APPLIED terminal state.
