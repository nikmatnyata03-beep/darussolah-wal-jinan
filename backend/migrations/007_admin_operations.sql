-- Operational records for the admin workspace.
-- Run after 006_learning_submission_storage.sql.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.admin_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  module text NOT NULL CHECK (module ~ '^[a-z][a-z0-9_-]{1,40}$'),
  record_key text NOT NULL DEFAULT gen_random_uuid()::text,
  entity_id uuid,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, module, record_key)
);

ALTER TABLE darussolah.teacher_profiles
  ADD COLUMN IF NOT EXISTS employment_type text NOT NULL DEFAULT 'fixed';
ALTER TABLE darussolah.teacher_profiles
  ADD COLUMN IF NOT EXISTS weekly_hours integer NOT NULL DEFAULT 0;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'teacher_profiles_employment_type_check'
      AND conrelid = 'darussolah.teacher_profiles'::regclass
  ) THEN
    ALTER TABLE darussolah.teacher_profiles
      ADD CONSTRAINT teacher_profiles_employment_type_check CHECK (employment_type IN ('fixed', 'honor'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS admin_records_module_idx
  ON darussolah.admin_records (tenant_id, module, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS admin_records_entity_idx
  ON darussolah.admin_records (tenant_id, entity_id, module);

DROP TRIGGER IF EXISTS admin_records_updated_at ON darussolah.admin_records;
CREATE TRIGGER admin_records_updated_at BEFORE UPDATE ON darussolah.admin_records
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.admin_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_records_scope ON darussolah.admin_records;
CREATE POLICY admin_records_scope ON darussolah.admin_records
  FOR SELECT USING (
    tenant_id = darussolah.current_tenant_id()
    AND (
      darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru'])
      OR (
        module IN ('grades', 'tahfidz', 'schedule')
        AND darussolah.has_tenant_role(tenant_id, ARRAY['wali', 'santri'])
      )
    )
  );
DROP POLICY IF EXISTS admin_records_write ON darussolah.admin_records;
CREATE POLICY admin_records_write ON darussolah.admin_records
  FOR ALL USING (
    tenant_id = darussolah.current_tenant_id()
    AND darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru'])
  )
  WITH CHECK (
    tenant_id = darussolah.current_tenant_id()
    AND darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru'])
  );

GRANT SELECT, INSERT, UPDATE ON darussolah.admin_records TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA darussolah TO authenticated, service_role;

-- Public CMS media is still uploaded by an authenticated admin and stored in a
-- tenant-prefixed path so it can be audited and replaced without exposing the
-- rest of the storage service.
INSERT INTO storage.buckets (id, name, public)
VALUES ('site-media', 'site-media', true)
ON CONFLICT (id) DO UPDATE SET public = EXCLUDED.public;

DROP POLICY IF EXISTS site_media_admin_insert ON storage.objects;
CREATE POLICY site_media_admin_insert ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'site-media'
    AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
    AND darussolah.has_tenant_role(
      ((storage.foldername(name))[1])::uuid,
      ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']
    )
  );
DROP POLICY IF EXISTS site_media_public_read ON storage.objects;
CREATE POLICY site_media_public_read ON storage.objects
  FOR SELECT TO public USING (bucket_id = 'site-media');
DROP POLICY IF EXISTS site_media_admin_update ON storage.objects;
CREATE POLICY site_media_admin_update ON storage.objects
  FOR UPDATE TO authenticated
  USING (
    bucket_id = 'site-media'
    AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
    AND darussolah.has_tenant_role(
      ((storage.foldername(name))[1])::uuid,
      ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']
    )
  )
  WITH CHECK (bucket_id = 'site-media');

COMMIT;
