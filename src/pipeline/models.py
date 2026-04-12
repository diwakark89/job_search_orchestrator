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
