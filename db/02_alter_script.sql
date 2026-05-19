create table if not exists public.automation_sessions (
	id uuid primary key default gen_random_uuid (),
	job_id uuid not null
		references public.jobs_final (id)
		on delete cascade,
	automation_type text not null
		check (
			automation_type = any (
				array[
					'JOB_APPLY'::text
				]
			)
		),
	session_status text not null default 'RUNNING'::text
		check (
			session_status = any (
				array[
					'RUNNING'::text,
					'WAITING_USER'::text,
					'RESUMING'::text,
					'COMPLETED'::text,
					'FAILED'::text
				]
			)
		),
	current_step text null,
	browser_state_path text null,
	screenshot_path text null,
	last_error text null,
	retry_count integer not null default 0,
	started_at timestamp with time zone not null default now(),
	updated_at timestamp with time zone not null default now()
) TABLESPACE pg_default;

create index if not exists idx_automation_sessions_job_id on public.automation_sessions using btree (job_id) TABLESPACE pg_default;

create index if not exists idx_automation_sessions_status_updated_at on public.automation_sessions using btree (session_status, updated_at desc) TABLESPACE pg_default;

create or replace function public.set_automation_sessions_updated_at()
returns trigger
language plpgsql
as $$
begin
	new.updated_at = now();
	return new;
end;
$$;

drop trigger if exists automation_sessions_set_updated_at on public.automation_sessions;

create trigger automation_sessions_set_updated_at before
update on automation_sessions for each row
execute function public.set_automation_sessions_updated_at();
