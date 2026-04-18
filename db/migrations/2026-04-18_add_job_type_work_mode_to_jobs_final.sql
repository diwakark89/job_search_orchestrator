ALTER TABLE IF EXISTS public.jobs_final
    ADD COLUMN IF NOT EXISTS job_type text,
    ADD COLUMN IF NOT EXISTS work_mode text;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'jobs_final'
          AND column_name = 'remote_type'
    ) THEN
        UPDATE public.jobs_final
        SET work_mode = CASE
            WHEN remote_type IS NULL THEN work_mode
            WHEN lower(trim(remote_type)) = 'remote' THEN 'remote'
            WHEN lower(trim(remote_type)) = 'hybrid' THEN 'hybrid'
            WHEN lower(trim(remote_type)) IN ('onsite', 'on site', 'on-site') THEN 'on-site'
            ELSE 'other'
        END
        WHERE remote_type IS NOT NULL
          AND (work_mode IS NULL OR trim(work_mode) = '');

        ALTER TABLE public.jobs_final
            DROP COLUMN IF EXISTS remote_type;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'jobs_final_job_type_check'
          AND conrelid = 'public.jobs_final'::regclass
    ) THEN
        ALTER TABLE public.jobs_final
            ADD CONSTRAINT jobs_final_job_type_check
            CHECK (
                job_type IS NULL
                OR job_type IN ('fulltime', 'parttime', 'internship', 'contract', 'temporary', 'other')
            );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'jobs_final_work_mode_check'
          AND conrelid = 'public.jobs_final'::regclass
    ) THEN
        ALTER TABLE public.jobs_final
            ADD CONSTRAINT jobs_final_work_mode_check
            CHECK (
                work_mode IS NULL
                OR work_mode IN ('remote', 'hybrid', 'on-site', 'other')
            );
    END IF;
END $$;