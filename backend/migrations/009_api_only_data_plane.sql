-- Keep tenant data behind the API. Supabase Auth and Storage remain available
-- to the browser only where their dedicated policies permit it.

BEGIN;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA darussolah FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA darussolah
  REVOKE ALL ON TABLES FROM anon, authenticated;

COMMIT;
