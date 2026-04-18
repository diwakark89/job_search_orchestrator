from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StageResult:
    stage: str
    success: bool
    processed: int
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    stages: list[StageResult]
    success: bool
    total_processed: int
    total_enriched: int
    total_failed: int


@dataclass
class SubmitJobsResult:
    submitted_row_count: int
    accepted_ids: list[str]
    accepted_urls: list[str]
    rejected_row_indexes: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    jobs_final_row_count: int = 0
    shared_links_row_count: int = 0
