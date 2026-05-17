from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.submit import submit_jobs_for_enrichment


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="End-to-end smoke test for submit_jobs_for_enrichment.",
    )
    parser.add_argument(
        "--dotenv",
        type=Path,
        default=Path(".env"),
        help="Path to the .env file used to load Supabase settings.",
    )
    parser.add_argument(
        "--company-name",
        default="Acme Corp",
        help="Company name for the synthetic job row.",
    )
    parser.add_argument(
        "--role-title",
        default="Backend Engineer",
        help="Role title for the synthetic job row.",
    )
    parser.add_argument(
        "--description",
        default="Build APIs.",
        help="Job description for the synthetic row.",
    )
    parser.add_argument(
        "--job-type",
        default="fulltime",
        help="Canonical job_type value.",
    )
    parser.add_argument(
        "--work-mode",
        default="hybrid",
        help="Canonical work_mode value.",
    )
    parser.add_argument(
        "--job-url",
        default=None,
        help="Explicit job_url. When omitted, a unique URL is generated.",
    )
    parser.add_argument(
        "--keep-row",
        action="store_true",
        help="Keep inserted row (skip cleanup patch is_deleted=true).",
    )
    return parser


def make_job_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"https://example.com/jobs/python-smoke-{suffix}"


def select_inserted_row(repo: SupabaseRepository, accepted_id: str) -> list[dict[str, Any]]:
    selected = repo.select_rows(
        table="jobs_final",
        columns="id,job_url,job_status,is_deleted",
        filters={"id": accepted_id, "is_deleted": False},
    )
    if not selected.success:
        raise RuntimeError(f"Verification select failed: {selected.error}")
    if not isinstance(selected.data, list):
        raise RuntimeError("Verification select returned non-list payload.")
    return selected.data


def cleanup_row(repo: SupabaseRepository, accepted_id: str) -> list[dict[str, Any]]:
    cleanup = repo.patch_rows(
        table="jobs_final",
        payload={"is_deleted": True},
        filters={"id": accepted_id},
    )
    if not cleanup.success:
        raise RuntimeError(f"Cleanup patch failed: {cleanup.error}")

    verify_cleanup = repo.select_rows(
        table="jobs_final",
        columns="id,is_deleted",
        filters={"id": accepted_id},
    )
    if not verify_cleanup.success:
        raise RuntimeError(f"Cleanup verification select failed: {verify_cleanup.error}")
    if not isinstance(verify_cleanup.data, list):
        raise RuntimeError("Cleanup verification returned non-list payload.")

    return verify_cleanup.data


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    load_dotenv(args.dotenv)

    config = load_config()
    repo = SupabaseRepository(client=PostgrestClient(config=config))

    job_url = make_job_url(args.job_url)
    row = {
        "company_name": args.company_name,
        "role_title": args.role_title,
        "job_url": job_url,
        "description": args.description,
        "job_type": args.job_type,
        "work_mode": args.work_mode,
    }

    result = submit_jobs_for_enrichment(repo=repo, rows=[row])
    accepted_id = result.accepted_ids[0]

    payload: dict[str, Any] = {
        "submit_result": {
            "submitted_row_count": result.submitted_row_count,
            "accepted_ids": result.accepted_ids,
            "accepted_urls": result.accepted_urls,
            "rejected_row_indexes": result.rejected_row_indexes,
            "errors": result.errors,
            "jobs_final_row_count": result.jobs_final_row_count,
            "has_shared_links_row_count": hasattr(result, "shared_links_row_count"),
        },
        "verification_select": select_inserted_row(repo=repo, accepted_id=accepted_id),
    }

    if args.keep_row:
        payload["cleanup"] = {
            "performed": False,
            "reason": "--keep-row set",
        }
    else:
        payload["cleanup"] = {
            "performed": True,
            "verification": cleanup_row(repo=repo, accepted_id=accepted_id),
        }

    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
