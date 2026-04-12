from __future__ import annotations

from common.client import OperationResult
from repository.supabase import SupabaseRepository


def select_decisions_for_job(repo: SupabaseRepository, job_id: str) -> OperationResult:
    """Fetch all decisions for a job, ordered by creation (newest first).
    
    Args:
        repo: SupabaseRepository instance
        job_id: The job UUID to query decisions for
        
    Returns:
        OperationResult with list of job_decisions rows in data field
    """
    return repo.select_rows(
        table="job_decisions",
        filters={"job_id": job_id},
        order_by="created_at",
        ascending=False,
    )


def select_approvals_for_job(repo: SupabaseRepository, job_id: str) -> OperationResult:
    """Fetch all approvals for a job, ordered by creation (newest first).
    
    Useful for displaying approval history and audit trail.
    
    Args:
        repo: SupabaseRepository instance
        job_id: The job UUID to query approvals for
        
    Returns:
        OperationResult with list of job_approvals rows in data field
    """
    return repo.select_rows(
        table="job_approvals",
        filters={"job_id": job_id},
        order_by="created_at",
        ascending=False,
    )
