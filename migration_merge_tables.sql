-- ============================================================================
-- Migration: Merge jobs_raw, jobs_enriched, job_decisions, job_approvals
--            into jobs_final. Drop merged tables and job_metrics.
--
-- Pre-requisites:
--   - jobs_raw and job_decisions contain NO data.
--   - job_approvals and jobs_enriched can be safely dropped.
--   - job_metrics is replaced by dynamic queries on jobs_final.
--
-- Run this in your Supabase SQL Editor.
-- ============================================================================

BEGIN;

-- ── 1. Add columns from jobs_raw ─────────────────────────────────────────────
ALTER TABLE public.jobs_final
  ADD COLUMN IF NOT EXISTS content_hash  text          NULL,
  ADD COLUMN IF NOT EXISTS external_id   text          NULL,
  ADD COLUMN IF NOT EXISTS location      text          NULL,
  ADD COLUMN IF NOT EXISTS source_platform text        NULL;
ALTER TABLE public.jobs_final DROP CONSTRAINT IF EXISTS jobs_final_job_status_check;
ALTER TABLE public.jobs_final ADD CONSTRAINT jobs_final_job_status_check CHECK (
  job_status IS NULL OR job_status = ANY (ARRAY[
    'SCRAPED'::text,       'ENRICHED'::text,
    'SAVED'::text,         'APPLIED'::text,
    'INTERVIEW'::text,     'INTERVIEWING'::text,
    'OFFER'::text,
    'RESUME_REJECTED'::text, 'INTERVIEW_REJECTED'::text
  ])
);

-- ── 7. Add CHECK constraint for decision ─────────────────────────────────────
ALTER TABLE public.jobs_final ADD CONSTRAINT jobs_final_decision_check CHECK (
  decision IS NULL OR decision = ANY (ARRAY[
    'AUTO_APPROVE'::text, 'REVIEW'::text, 'REJECT'::text
  ])
);

-- ── 8. Add CHECK constraint for user_action ──────────────────────────────────
ALTER TABLE public.jobs_final ADD CONSTRAINT jobs_final_user_action_check CHECK (
  user_action IS NULL OR user_action = ANY (ARRAY[
    'APPROVED'::text, 'REJECTED'::text, 'PENDING'::text
  ])
);

-- ── 9. Add UNIQUE constraint on job_url (NULLs are distinct in Postgres) ─────
ALTER TABLE public.jobs_final
  ADD CONSTRAINT jobs_final_job_url_key UNIQUE (job_url);

-- ── 10. Add UNIQUE index on content_hash ─────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_final_content_hash
  ON public.jobs_final USING btree (content_hash);

-- ── 11. Drop the FK from jobs_final → jobs_raw (no longer needed) ────────────
ALTER TABLE public.jobs_final DROP CONSTRAINT IF EXISTS jobs_final_job_id_fkey;

-- ── 12. Remove job_id column (consolidated to id as single business key) ─────
ALTER TABLE public.jobs_final DROP COLUMN IF EXISTS job_id CASCADE;

-- ── 13. Add UNIQUE constraint on id (primary business key) ────────────────────
ALTER TABLE public.jobs_final DROP CONSTRAINT IF EXISTS jobs_final_job_id_key;
ALTER TABLE public.jobs_final ADD CONSTRAINT jobs_final_id_key UNIQUE (id);

-- ── 14. Drop merged tables in FK dependency order ────────────────────────────
DROP TABLE IF EXISTS public.job_approvals CASCADE;
DROP TABLE IF EXISTS public.job_decisions CASCADE;
DROP TABLE IF EXISTS public.jobs_enriched CASCADE;
DROP TABLE IF EXISTS public.jobs_raw      CASCADE;
DROP TABLE IF EXISTS public.job_metrics   CASCADE;

COMMIT;

-- ── Verification ─────────────────────────────────────────────────────────────
-- Run after migration to confirm new columns exist:
--   SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--   WHERE table_name = 'jobs_final'
--   ORDER BY ordinal_position;
