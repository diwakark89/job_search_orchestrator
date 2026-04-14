-- ============================================================================
-- Migration: Normalize job_status values to uppercase only.
--
-- Converts all display-form values in jobs_final.job_status to their
-- uppercase equivalents, then replaces the CHECK constraint to allow
-- only uppercase values.
--
-- Run this in your Supabase SQL Editor AFTER migration_merge_tables.sql.
-- ============================================================================

BEGIN;

-- ── 1. Migrate existing display-form values to uppercase ─────────────────────
UPDATE public.jobs_final SET job_status = 'SAVED'              WHERE job_status = 'Saved';
UPDATE public.jobs_final SET job_status = 'APPLIED'            WHERE job_status = 'Applied';
UPDATE public.jobs_final SET job_status = 'INTERVIEW'          WHERE job_status = 'Interview';
UPDATE public.jobs_final SET job_status = 'INTERVIEWING'       WHERE job_status = 'Interviewing';
UPDATE public.jobs_final SET job_status = 'OFFER'              WHERE job_status = 'Offer';
UPDATE public.jobs_final SET job_status = 'RESUME_REJECTED'    WHERE job_status = 'Resume-Rejected';
UPDATE public.jobs_final SET job_status = 'INTERVIEW_REJECTED' WHERE job_status = 'Interview-Rejected';

-- ── 2. Replace CHECK constraint with uppercase-only values ───────────────────
ALTER TABLE public.jobs_final DROP CONSTRAINT IF EXISTS jobs_final_job_status_check;
ALTER TABLE public.jobs_final ADD CONSTRAINT jobs_final_job_status_check CHECK (
  job_status IS NULL OR job_status = ANY (ARRAY[
    'SCRAPED'::text,
    'ENRICHED'::text,
    'SAVED'::text,
    'APPLIED'::text,
    'INTERVIEW'::text,
    'INTERVIEWING'::text,
    'OFFER'::text,
    'RESUME_REJECTED'::text,
    'INTERVIEW_REJECTED'::text
  ])
);

COMMIT;

-- ── Verification ─────────────────────────────────────────────────────────────
-- Confirm no display-form values remain:
--   SELECT DISTINCT job_status FROM public.jobs_final ORDER BY job_status;
