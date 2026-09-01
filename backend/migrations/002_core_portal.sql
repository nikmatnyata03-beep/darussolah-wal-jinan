-- Core identity and portal tables for the Darussolah education platform.
-- Run after 001_initial.sql in Supabase. Auth users are created by Supabase Auth.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.user_profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  full_name text NOT NULL,
  phone text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'invited')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS darussolah.user_roles (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru', 'wali', 'santri')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, tenant_id, role)
);

CREATE TABLE IF NOT EXISTS darussolah.institution_memberships (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  membership_role text NOT NULL CHECK (membership_role IN ('lembaga_admin', 'operator_pendaftaran', 'guru')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, institution_id, membership_role)
);

CREATE TABLE IF NOT EXISTS darussolah.guardians (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  full_name text NOT NULL,
  phone text,
  email text,
  relationship text NOT NULL DEFAULT 'guardian',
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS darussolah.students (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  nis text,
  full_name text NOT NULL,
  birth_place text,
  birth_date date,
  gender text CHECK (gender IN ('male', 'female')),
  address text,
  emergency_phone text,
  status text NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'active', 'leave', 'graduated', 'transferred', 'inactive')),
  photo_url text,
  public_photo_consent boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, nis)
);

ALTER TABLE darussolah.students
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS darussolah.guardian_students (
  guardian_id uuid NOT NULL REFERENCES darussolah.guardians(id) ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES darussolah.students(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  relationship text NOT NULL DEFAULT 'guardian',
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (guardian_id, student_id)
);

CREATE TABLE IF NOT EXISTS darussolah.academic_years (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  name text NOT NULL,
  starts_on date NOT NULL,
  ends_on date NOT NULL CHECK (ends_on > starts_on),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'closed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS darussolah.programs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  code text NOT NULL,
  name text NOT NULL,
  level text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institution_id, code)
);

CREATE TABLE IF NOT EXISTS darussolah.classes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  program_id uuid NOT NULL REFERENCES darussolah.programs(id) ON DELETE RESTRICT,
  academic_year_id uuid NOT NULL REFERENCES darussolah.academic_years(id) ON DELETE RESTRICT,
  code text NOT NULL,
  name text NOT NULL,
  capacity integer CHECK (capacity IS NULL OR capacity > 0),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (academic_year_id, institution_id, code)
);

CREATE TABLE IF NOT EXISTS darussolah.teacher_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  display_name text NOT NULL,
  role_title text,
  subject text,
  short_bio text,
  education text,
  photo_url text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 001_initial.sql already has a public teacher profile table. Add the private
-- account link and lifecycle flag without recreating or losing those rows.
ALTER TABLE darussolah.teacher_profiles
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE darussolah.teacher_profiles
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'teacher_profiles_status_check'
      AND conrelid = 'darussolah.teacher_profiles'::regclass
  ) THEN
    ALTER TABLE darussolah.teacher_profiles
      ADD CONSTRAINT teacher_profiles_status_check CHECK (status IN ('active', 'inactive'));
  END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS darussolah.class_teachers (
  class_id uuid NOT NULL REFERENCES darussolah.classes(id) ON DELETE CASCADE,
  teacher_id uuid NOT NULL REFERENCES darussolah.teacher_profiles(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  is_homeroom boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (class_id, teacher_id)
);

CREATE TABLE IF NOT EXISTS darussolah.enrollments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES darussolah.students(id) ON DELETE RESTRICT,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE RESTRICT,
  program_id uuid NOT NULL REFERENCES darussolah.programs(id) ON DELETE RESTRICT,
  class_id uuid REFERENCES darussolah.classes(id) ON DELETE RESTRICT,
  academic_year_id uuid NOT NULL REFERENCES darussolah.academic_years(id) ON DELETE RESTRICT,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'withdrawn', 'pending')),
  starts_on date NOT NULL DEFAULT current_date,
  ends_on date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (student_id, institution_id, academic_year_id)
);

CREATE TABLE IF NOT EXISTS darussolah.audit_logs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  before_data jsonb,
  after_data jsonb,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_roles_lookup_idx ON darussolah.user_roles (user_id, tenant_id);
CREATE INDEX IF NOT EXISTS institution_memberships_lookup_idx ON darussolah.institution_memberships (user_id, tenant_id, institution_id);
CREATE INDEX IF NOT EXISTS students_tenant_status_idx ON darussolah.students (tenant_id, status, full_name);
CREATE INDEX IF NOT EXISTS enrollments_scope_idx ON darussolah.enrollments (tenant_id, institution_id, academic_year_id, status);
CREATE INDEX IF NOT EXISTS audit_logs_tenant_created_idx ON darussolah.audit_logs (tenant_id, created_at DESC);

DROP TRIGGER IF EXISTS user_profiles_updated_at ON darussolah.user_profiles;
CREATE TRIGGER user_profiles_updated_at BEFORE UPDATE ON darussolah.user_profiles
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS guardians_updated_at ON darussolah.guardians;
CREATE TRIGGER guardians_updated_at BEFORE UPDATE ON darussolah.guardians
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS students_updated_at ON darussolah.students;
CREATE TRIGGER students_updated_at BEFORE UPDATE ON darussolah.students
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS academic_years_updated_at ON darussolah.academic_years;
CREATE TRIGGER academic_years_updated_at BEFORE UPDATE ON darussolah.academic_years
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS programs_updated_at ON darussolah.programs;
CREATE TRIGGER programs_updated_at BEFORE UPDATE ON darussolah.programs
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS classes_updated_at ON darussolah.classes;
CREATE TRIGGER classes_updated_at BEFORE UPDATE ON darussolah.classes
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS teacher_profiles_updated_at ON darussolah.teacher_profiles;
CREATE TRIGGER teacher_profiles_updated_at BEFORE UPDATE ON darussolah.teacher_profiles
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS enrollments_updated_at ON darussolah.enrollments;
CREATE TRIGGER enrollments_updated_at BEFORE UPDATE ON darussolah.enrollments
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.institution_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.guardian_students ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.academic_years ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.teacher_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.class_teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.audit_logs ENABLE ROW LEVEL SECURITY;

-- Allow public Supabase clients to read only published public content. The
-- existing app.tenant_id policies remain available to the FastAPI service.
DROP POLICY IF EXISTS foundation_sites_public_read ON darussolah.foundation_sites;
CREATE POLICY foundation_sites_public_read ON darussolah.foundation_sites
  FOR SELECT USING (is_published);
DROP POLICY IF EXISTS institutions_public_read ON darussolah.institutions;
CREATE POLICY institutions_public_read ON darussolah.institutions
  FOR SELECT USING (status = 'active');
DROP POLICY IF EXISTS institution_sites_public_read ON darussolah.institution_sites;
CREATE POLICY institution_sites_public_read ON darussolah.institution_sites
  FOR SELECT USING (is_published);
DROP POLICY IF EXISTS site_content_public_read ON darussolah.site_content;
CREATE POLICY site_content_public_read ON darussolah.site_content
  FOR SELECT USING (status = 'published');
DROP POLICY IF EXISTS teacher_profiles_public_read ON darussolah.teacher_profiles;
CREATE POLICY teacher_profiles_public_read ON darussolah.teacher_profiles
  FOR SELECT USING (is_published AND status = 'active');

CREATE OR REPLACE FUNCTION darussolah.has_tenant_role(target_tenant uuid, allowed_roles text[])
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM darussolah.user_roles
    WHERE user_id = auth.uid() AND tenant_id = target_tenant AND role = ANY(allowed_roles)
  );
$$;

CREATE OR REPLACE FUNCTION darussolah.has_institution_access(target_tenant uuid, target_institution uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT darussolah.has_tenant_role(target_tenant, ARRAY['super_admin', 'yayasan_admin'])
      OR EXISTS (
        SELECT 1 FROM darussolah.institution_memberships
        WHERE user_id = auth.uid() AND tenant_id = target_tenant AND institution_id = target_institution
      );
$$;

CREATE OR REPLACE FUNCTION darussolah.user_owns_guardian(target_guardian uuid, target_tenant uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM darussolah.guardians
    WHERE id = target_guardian AND tenant_id = target_tenant AND user_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION darussolah.user_has_student(target_student uuid, target_tenant uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM darussolah.guardian_students gs
    JOIN darussolah.guardians g ON g.id = gs.guardian_id
    WHERE gs.student_id = target_student AND gs.tenant_id = target_tenant AND g.user_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION darussolah.user_is_student(target_student uuid, target_tenant uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM darussolah.students
    WHERE id = target_student AND tenant_id = target_tenant AND user_id = auth.uid()
  );
$$;

DROP POLICY IF EXISTS user_profiles_self_or_admin ON darussolah.user_profiles;
CREATE POLICY user_profiles_self_or_admin ON darussolah.user_profiles
  FOR ALL USING (id = auth.uid() OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']))
  WITH CHECK (id = auth.uid() OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));

DROP POLICY IF EXISTS user_roles_self_or_admin ON darussolah.user_roles;
CREATE POLICY user_roles_self_or_admin ON darussolah.user_roles
  FOR SELECT USING (user_id = auth.uid() OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));
DROP POLICY IF EXISTS user_roles_admin_write ON darussolah.user_roles;
CREATE POLICY user_roles_admin_write ON darussolah.user_roles
  FOR ALL USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']))
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));

DROP POLICY IF EXISTS institution_memberships_self_or_admin ON darussolah.institution_memberships;
CREATE POLICY institution_memberships_self_or_admin ON darussolah.institution_memberships
  FOR SELECT USING (user_id = auth.uid() OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));
DROP POLICY IF EXISTS institution_memberships_admin_write ON darussolah.institution_memberships;
CREATE POLICY institution_memberships_admin_write ON darussolah.institution_memberships
  FOR ALL USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']))
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));

DROP POLICY IF EXISTS guardians_scope ON darussolah.guardians;
CREATE POLICY guardians_scope ON darussolah.guardians
  FOR ALL USING (
    user_id = auth.uid()
    OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin'])
  )
  WITH CHECK (user_id = auth.uid() OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']));

DROP POLICY IF EXISTS students_scope ON darussolah.students;
CREATE POLICY students_scope ON darussolah.students
  FOR ALL USING (
    darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin'])
    OR darussolah.user_has_student(id, tenant_id)
    OR darussolah.user_is_student(id, tenant_id)
    OR EXISTS (SELECT 1 FROM darussolah.enrollments e WHERE e.student_id = students.id AND e.tenant_id = students.tenant_id AND darussolah.has_institution_access(e.tenant_id, e.institution_id))
  )
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']));

DROP POLICY IF EXISTS guardian_students_scope ON darussolah.guardian_students;
CREATE POLICY guardian_students_scope ON darussolah.guardian_students
  FOR ALL USING (
    darussolah.user_owns_guardian(guardian_id, tenant_id)
    OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran'])
  )
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']));

DROP POLICY IF EXISTS academic_years_scope ON darussolah.academic_years;
CREATE POLICY academic_years_scope ON darussolah.academic_years
  FOR SELECT USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru', 'wali', 'santri']));
DROP POLICY IF EXISTS academic_years_admin_write ON darussolah.academic_years;
CREATE POLICY academic_years_admin_write ON darussolah.academic_years
  FOR ALL USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']))
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin']));

DROP POLICY IF EXISTS programs_scope ON darussolah.programs;
CREATE POLICY programs_scope ON darussolah.programs
  FOR SELECT USING (darussolah.has_institution_access(tenant_id, institution_id) OR darussolah.has_tenant_role(tenant_id, ARRAY['wali', 'santri']));
DROP POLICY IF EXISTS programs_admin_write ON darussolah.programs;
CREATE POLICY programs_admin_write ON darussolah.programs
  FOR ALL USING (darussolah.has_institution_access(tenant_id, institution_id))
  WITH CHECK (darussolah.has_institution_access(tenant_id, institution_id));

DROP POLICY IF EXISTS classes_scope ON darussolah.classes;
CREATE POLICY classes_scope ON darussolah.classes
  FOR SELECT USING (darussolah.has_institution_access(tenant_id, institution_id) OR darussolah.has_tenant_role(tenant_id, ARRAY['wali', 'santri']));
DROP POLICY IF EXISTS classes_admin_write ON darussolah.classes;
CREATE POLICY classes_admin_write ON darussolah.classes
  FOR ALL USING (darussolah.has_institution_access(tenant_id, institution_id))
  WITH CHECK (darussolah.has_institution_access(tenant_id, institution_id));

DROP POLICY IF EXISTS teacher_profiles_scope ON darussolah.teacher_profiles;
CREATE POLICY teacher_profiles_scope ON darussolah.teacher_profiles
  FOR SELECT USING (darussolah.has_institution_access(tenant_id, institution_id) OR user_id = auth.uid());
DROP POLICY IF EXISTS teacher_profiles_admin_write ON darussolah.teacher_profiles;
CREATE POLICY teacher_profiles_admin_write ON darussolah.teacher_profiles
  FOR ALL USING (darussolah.has_institution_access(tenant_id, institution_id))
  WITH CHECK (darussolah.has_institution_access(tenant_id, institution_id));

DROP POLICY IF EXISTS class_teachers_scope ON darussolah.class_teachers;
CREATE POLICY class_teachers_scope ON darussolah.class_teachers
  FOR SELECT USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru', 'wali', 'santri']));
DROP POLICY IF EXISTS class_teachers_admin_write ON darussolah.class_teachers;
CREATE POLICY class_teachers_admin_write ON darussolah.class_teachers
  FOR ALL USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin']))
  WITH CHECK (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin']));

DROP POLICY IF EXISTS enrollments_scope ON darussolah.enrollments;
CREATE POLICY enrollments_scope ON darussolah.enrollments
  FOR SELECT USING (darussolah.has_institution_access(tenant_id, institution_id) OR darussolah.user_has_student(student_id, tenant_id));
DROP POLICY IF EXISTS enrollments_admin_write ON darussolah.enrollments;
CREATE POLICY enrollments_admin_write ON darussolah.enrollments
  FOR ALL USING (darussolah.has_institution_access(tenant_id, institution_id))
  WITH CHECK (darussolah.has_institution_access(tenant_id, institution_id));

DROP POLICY IF EXISTS audit_logs_admin_read ON darussolah.audit_logs;
CREATE POLICY audit_logs_admin_read ON darussolah.audit_logs
  FOR SELECT USING (darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin']));
DROP POLICY IF EXISTS audit_logs_insert ON darussolah.audit_logs;
CREATE POLICY audit_logs_insert ON darussolah.audit_logs
  FOR INSERT WITH CHECK (actor_user_id = auth.uid() AND darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran', 'guru']));

-- Supabase REST can use the custom schema only when it is exposed and granted.
-- RLS remains the authoritative row-level control.
GRANT USAGE ON SCHEMA darussolah TO anon, authenticated, service_role;
GRANT SELECT ON darussolah.foundation_sites, darussolah.institutions,
  darussolah.institution_sites, darussolah.site_content,
  darussolah.teacher_profiles TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON darussolah.user_profiles,
  darussolah.user_roles, darussolah.institution_memberships,
  darussolah.guardians, darussolah.students, darussolah.guardian_students,
  darussolah.academic_years, darussolah.programs, darussolah.classes,
  darussolah.class_teachers, darussolah.enrollments, darussolah.audit_logs
  TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA darussolah TO authenticated, service_role;

COMMIT;
