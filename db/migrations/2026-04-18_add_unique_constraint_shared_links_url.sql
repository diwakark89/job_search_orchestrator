-- Migration: Add unique constraint on shared_links.url
-- Required for PostgREST ON CONFLICT (url) upserts used by insert_shared_links().
-- Run in Supabase SQL Editor. Idempotent: DO block skips if constraint already exists.

DO $$
BEGIN
    -- Remove duplicate urls keeping the earliest inserted row
    DELETE FROM shared_links a
    USING shared_links b
    WHERE a.id > b.id AND a.url = b.url;

    -- Add the unique constraint if it does not already exist
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'shared_links_url_key'
          AND conrelid = 'shared_links'::regclass
    ) THEN
        ALTER TABLE shared_links ADD CONSTRAINT shared_links_url_key UNIQUE (url);
    END IF;
END $$;
