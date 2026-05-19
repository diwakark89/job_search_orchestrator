-- Expands jobs_final job_status lifecycle values for automated apply orchestration.
-- Safe to run on existing environments.

alter table if exists public.jobs_final
drop constraint if exists jobs_final_job_status_check;

alter table if exists public.jobs_final
add constraint jobs_final_job_status_check check (
  (
    (job_status is null)
    or (
      job_status = any (
        array[
          'SCRAPED'::text,
          'ENRICHED'::text,
          'SAVED'::text,
          'READY_TO_APPLY'::text,
          'WAITING_CONFIRMATION'::text,
          'APPLIED'::text,
          'INTERVIEW'::text,
          'INTERVIEWING'::text,
          'OFFER'::text,
          'RESUME_REJECTED'::text,
          'INTERVIEW_REJECTED'::text
        ]
      )
    )
  )
);