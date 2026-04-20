-- Migration: 2026-04-19 — Merge shared_links into jobs_final, then drop shared_links
--
-- Apply this migration BEFORE deploying the updated application code.
--
-- Step 1: Back-fill source_platform from shared_links.source for any jobs_final rows
--         that currently have no source_platform but have a matching shared_links entry.
--         Rows that already have a source_platform value (e.g. "linkedin") are untouched.
UPDATE jobs_final
SET source_platform = sl.source
FROM shared_links sl
WHERE jobs_final.job_url = sl.url
  AND jobs_final.source_platform IS NULL;

-- Step 2: Drop the shared_links table.
--         Orphaned shared_links rows (no matching jobs_final entry) are discarded.
DROP TABLE shared_links;
