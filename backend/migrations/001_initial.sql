-- PostgreSQL schema for the public Darussolah foundation site.
-- Run this file once against the project's Supabase/PostgreSQL database.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS darussolah;

CREATE OR REPLACE FUNCTION darussolah.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION darussolah.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
$$;

CREATE TABLE IF NOT EXISTS darussolah.tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  name text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS darussolah.foundation_sites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  slug text NOT NULL,
  name text NOT NULL,
  hero_title text,
  established_year integer CHECK (established_year BETWEEN 1800 AND 2200),
  tagline text,
  description text,
  logo_url text,
  phone text,
  email text,
  address text,
  is_published boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS darussolah.institutions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  code text NOT NULL,
  name text NOT NULL,
  institution_type text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS darussolah.institution_sites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  slug text NOT NULL,
  name text NOT NULL,
  hero_title text,
  tagline text,
  description text,
  logo_url text,
  phone text,
  email text,
  address text,
  theme jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_published boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institution_id),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS darussolah.site_content (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  site_kind text NOT NULL CHECK (site_kind IN ('foundation', 'institution')),
  foundation_site_id uuid REFERENCES darussolah.foundation_sites(id) ON DELETE CASCADE,
  institution_id uuid REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  content_type text NOT NULL,
  slug text NOT NULL,
  title text NOT NULL,
  excerpt text,
  body text,
  cover_url text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  sort_order integer NOT NULL DEFAULT 0,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (site_kind = 'foundation' AND foundation_site_id IS NOT NULL AND institution_id IS NULL)
    OR (site_kind = 'institution' AND foundation_site_id IS NULL AND institution_id IS NOT NULL)
  ),
  UNIQUE (tenant_id, site_kind, slug)
);

CREATE TABLE IF NOT EXISTS darussolah.teacher_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  display_name text NOT NULL,
  role_title text,
  subject text,
  short_bio text,
  education text,
  photo_url text,
  sort_order integer NOT NULL DEFAULT 0,
  is_published boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE SEQUENCE IF NOT EXISTS darussolah.registration_application_no_seq;

CREATE TABLE IF NOT EXISTS darussolah.registration_applications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id),
  application_no text NOT NULL DEFAULT (
    'REG-' || to_char(current_date, 'YYYY') || '-' ||
    lpad(nextval('darussolah.registration_application_no_seq')::text, 6, '0')
  ),
  registration_type text NOT NULL DEFAULT 'new' CHECK (registration_type IN ('new', 're_registration')),
  academic_year text NOT NULL CHECK (academic_year ~ '^[0-9]{4}([/-][0-9]{4})?$'),
  student_full_name text NOT NULL,
  birth_place text,
  birth_date date,
  gender text CHECK (gender IN ('male', 'female')),
  address text,
  father_name text,
  father_phone text,
  mother_name text,
  mother_phone text,
  guardian_name text,
  guardian_phone text,
  notes text,
  idempotency_key text,
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewing', 'accepted', 'rejected', 'enrolled')),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, application_no),
  UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS site_content_public_idx
  ON darussolah.site_content (tenant_id, site_kind, status, sort_order, published_at DESC);
CREATE INDEX IF NOT EXISTS teachers_public_idx
  ON darussolah.teacher_profiles (tenant_id, institution_id, is_published, sort_order);
CREATE INDEX IF NOT EXISTS registrations_tenant_status_idx
  ON darussolah.registration_applications (tenant_id, status, created_at DESC);

DROP TRIGGER IF EXISTS tenants_updated_at ON darussolah.tenants;
CREATE TRIGGER tenants_updated_at BEFORE UPDATE ON darussolah.tenants
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS foundation_sites_updated_at ON darussolah.foundation_sites;
CREATE TRIGGER foundation_sites_updated_at BEFORE UPDATE ON darussolah.foundation_sites
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS institutions_updated_at ON darussolah.institutions;
CREATE TRIGGER institutions_updated_at BEFORE UPDATE ON darussolah.institutions
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS institution_sites_updated_at ON darussolah.institution_sites;
CREATE TRIGGER institution_sites_updated_at BEFORE UPDATE ON darussolah.institution_sites
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS site_content_updated_at ON darussolah.site_content;
CREATE TRIGGER site_content_updated_at BEFORE UPDATE ON darussolah.site_content
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS teacher_profiles_updated_at ON darussolah.teacher_profiles;
CREATE TRIGGER teacher_profiles_updated_at BEFORE UPDATE ON darussolah.teacher_profiles
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS registrations_updated_at ON darussolah.registration_applications;
CREATE TRIGGER registrations_updated_at BEFORE UPDATE ON darussolah.registration_applications
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.foundation_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.institution_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.site_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.teacher_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.registration_applications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS foundation_sites_tenant_isolation ON darussolah.foundation_sites;
CREATE POLICY foundation_sites_tenant_isolation ON darussolah.foundation_sites
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS institutions_tenant_isolation ON darussolah.institutions;
CREATE POLICY institutions_tenant_isolation ON darussolah.institutions
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS institution_sites_tenant_isolation ON darussolah.institution_sites;
CREATE POLICY institution_sites_tenant_isolation ON darussolah.institution_sites
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS site_content_tenant_isolation ON darussolah.site_content;
CREATE POLICY site_content_tenant_isolation ON darussolah.site_content
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS teacher_profiles_tenant_isolation ON darussolah.teacher_profiles;
CREATE POLICY teacher_profiles_tenant_isolation ON darussolah.teacher_profiles
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS registrations_tenant_isolation ON darussolah.registration_applications;
CREATE POLICY registrations_tenant_isolation ON darussolah.registration_applications
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());

COMMIT;
