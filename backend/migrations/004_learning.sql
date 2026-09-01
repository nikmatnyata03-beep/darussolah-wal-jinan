-- Learning resources for materials, assignments, and class announcements.
-- Run after 003_attendance.sql in Supabase.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.learning_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  class_id uuid REFERENCES darussolah.classes(id) ON DELETE CASCADE,
  resource_type text NOT NULL CHECK (resource_type IN ('material', 'assignment', 'announcement')),
  title text NOT NULL,
  subject text,
  description text,
  file_path text,
  due_date date,
  status text NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived')),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, institution_id, class_id, resource_type, title)
);

CREATE INDEX IF NOT EXISTS learning_resources_scope_idx
  ON darussolah.learning_resources (tenant_id, institution_id, class_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS learning_resources_type_idx
  ON darussolah.learning_resources (tenant_id, resource_type, due_date);

DROP TRIGGER IF EXISTS learning_resources_updated_at ON darussolah.learning_resources;
CREATE TRIGGER learning_resources_updated_at BEFORE UPDATE ON darussolah.learning_resources
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.learning_resources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS learning_resources_scope ON darussolah.learning_resources;
CREATE POLICY learning_resources_scope ON darussolah.learning_resources
  FOR SELECT USING (
    (
      status = 'published'
      OR darussolah.has_tenant_role(tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'guru'])
    )
    AND (
      darussolah.has_institution_access(tenant_id, institution_id)
      OR EXISTS (
        SELECT 1
        FROM darussolah.enrollments e
        WHERE e.tenant_id = learning_resources.tenant_id
          AND e.institution_id = learning_resources.institution_id
          AND e.status = 'active'
          AND (
            e.class_id = learning_resources.class_id
            OR learning_resources.class_id IS NULL
          )
          AND (
            darussolah.user_has_student(e.student_id, learning_resources.tenant_id)
            OR darussolah.user_is_student(e.student_id, learning_resources.tenant_id)
          )
        )
      OR EXISTS (
        SELECT 1
        FROM darussolah.class_teachers ct
        JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
        WHERE ct.class_id = learning_resources.class_id
          AND ct.tenant_id = learning_resources.tenant_id
          AND tp.user_id = auth.uid()
      )
    )
  );

DROP POLICY IF EXISTS learning_resources_write ON darussolah.learning_resources;
CREATE POLICY learning_resources_write ON darussolah.learning_resources
  FOR ALL USING (
    darussolah.has_institution_access(tenant_id, institution_id)
    OR EXISTS (
      SELECT 1
      FROM darussolah.class_teachers ct
      JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
      WHERE ct.class_id = learning_resources.class_id
        AND ct.tenant_id = learning_resources.tenant_id
        AND tp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    (
      darussolah.has_institution_access(tenant_id, institution_id)
      OR EXISTS (
        SELECT 1
        FROM darussolah.class_teachers ct
        JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
        WHERE ct.class_id = learning_resources.class_id
          AND ct.tenant_id = learning_resources.tenant_id
          AND tp.user_id = auth.uid()
      )
    )
    AND (
      class_id IS NULL
      OR EXISTS (
        SELECT 1 FROM darussolah.classes c
        WHERE c.id = learning_resources.class_id
          AND c.tenant_id = learning_resources.tenant_id
          AND c.institution_id = learning_resources.institution_id
      )
    )
  );

GRANT SELECT, INSERT, UPDATE ON darussolah.learning_resources TO authenticated;

COMMIT;
