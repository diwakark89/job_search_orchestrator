create table public.jobs_final (
  id uuid not null default gen_random_uuid (),
  company_name text null,
  role_title text null,
  job_url text null,
  match_score numeric null,
  saved_at timestamp with time zone not null default now(),
  description text null,
  job_status text null default 'Saved'::text,
  is_deleted boolean not null default false,
  modified_at timestamp with time zone null default now(),
  language text null default 'English'::text,
  content_hash text null,
  location text null,
  source_platform text null,
  tech_stack text[] null,
  experience_level text null,
  decision text null,
  reason text null,
  confidence numeric null,
  user_action text null,
  approved_at timestamp with time zone null,
  job_type text null,
  work_mode text null,
  constraint jobs_final_pkey primary key (id),
  constraint jobs_final_job_url_key unique (job_url),
  constraint jobs_final_job_type_check check (
    (
      (job_type is null)
      or (
        job_type = any (
          array[
            'fulltime'::text,
            'parttime'::text,
            'internship'::text,
            'contract'::text,
            'temporary'::text,
            'other'::text
          ]
        )
      )
    )
  ),
  constraint jobs_final_decision_check check (
    (
      (decision is null)
      or (
        decision = any (
          array[
            'AUTO_APPROVE'::text,
            'REVIEW'::text,
            'REJECT'::text
          ]
        )
      )
    )
  ),
  constraint jobs_final_job_status_check check (
    (
      (job_status is null)
      or (
        job_status = any (
          array[
            'SCRAPED'::text,
            'ENRICHED'::text,
            'SAVED'::text,
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
  ),
  constraint jobs_final_user_action_check check (
    (
      (user_action is null)
      or (
        user_action = any (
          array[
            'APPROVED'::text,
            'REJECTED'::text,
            'PENDING'::text
          ]
        )
      )
    )
  ),
  constraint jobs_final_work_mode_check check (
    (
      (work_mode is null)
      or (
        work_mode = any (
          array[
            'remote'::text,
            'hybrid'::text,
            'on-site'::text,
            'other'::text
          ]
        )
      )
    )
  )
) TABLESPACE pg_default;

create unique INDEX IF not exists idx_jobs_final_content_hash on public.jobs_final using btree (content_hash) TABLESPACE pg_default;

create index IF not exists idx_jobs_final_saved_at on public.jobs_final using btree (saved_at desc) TABLESPACE pg_default;

create index IF not exists idx_jobs_final_job_status_modified_at on public.jobs_final using btree (job_status, modified_at desc) TABLESPACE pg_default;

create trigger jobs_final_set_modified_at BEFORE
update on jobs_final for EACH row
execute FUNCTION set_modified_at ();