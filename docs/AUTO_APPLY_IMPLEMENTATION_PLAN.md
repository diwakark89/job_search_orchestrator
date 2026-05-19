# Auto Apply Implementation Plan

This document is the quick entrypoint for the Android plus job_manager plus OpenClaw plus Playwright implementation plan.

## Plan Document

- Full phased plan with task IDs AJH-AUTO-001 through AJH-AUTO-045:
  - plan/feature-android-openclaw-auto-apply-1.md

## Scope Summary

- Daily scrape ingestion
- Enrichment and AI scoring
- Android approval control layer
- automation_sessions orchestration
- OpenClaw plus Playwright apply worker
- Pause before submit and Android final confirmation
- Resume and final submit
- Reliability, testing, and rollout runbook

## Current Status

- Documented and ready for iterative implementation.
- Foundation lifecycle status updates already started in codebase.
- Automation lifecycle actions (approve, reject, create apply session) are exposed via CLI only, not HTTP.
