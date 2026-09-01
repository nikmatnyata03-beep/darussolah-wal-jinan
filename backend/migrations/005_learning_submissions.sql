-- Assignment submissions and teacher review records.
-- Run after 004_learning.sql in Supabase.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.learning_submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  resource_id uuid NOT NULL REFERENCES darussolah.learning_resources(id) ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES darussolah.students(id) ON DELETE CASCADE,
  file_path text,
  note text,
  status text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'late', 'reviewed', 'returned')),
  score numeric(5, 2) CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
  feedback text,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  reviewed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (resource_id, student_id)
);

CREATE INDEX IF NOT EXISTS learning_submissions_scope_idx
  ON darussolah.learning_submissions (tenant_id, resource_id, status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS learning_submissions_student_idx
  ON darussolah.learning_submissions (tenant_id, student_id, submitted_at DESC);

CREATE OR REPLACE FUNCTION darussolah.user_can_submit_learning_resource(
  target_tenant uuid, target_resource uuid, target_student uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM darussolah.learning_resources r
    JOIN darussolah.enrollments e
      ON e.tenant_id = r.tenant_id AND e.institution_id = r.institution_id
     AND e.status = 'active' AND e.student_id = target_student
     AND (r.class_id IS NULL OR e.class_id = r.class_id)
    WHERE r.id = target_resource AND r.tenant_id = target_tenant
      AND r.resource_type = 'assignment' AND r.status = 'published'
      AND (
        darussolah.user_has_student(target_student, target_tenant)
        OR darussolah.user_is_student(target_student, target_tenant)
      )
  );
$$;

GRANT EXECUTE ON FUNCTION darussolah.user_can_submit_learning_resource(uuid, uuid, uuid)
  TO authenticated;

DROP TRIGGER IF EXISTS learning_submissions_updated_at ON darussolah.learning_submissions;
CREATE TRIGGER learning_submissions_updated_at BEFORE UPDATE ON darussolah.learning_submissions
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.learning_submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS learning_submissions_scope ON darussolah.learning_submissions;
CREATE POLICY learning_submissions_scope ON darussolah.learning_submissions
  FOR SELECT USING (
    EXISTS (
      SELECT 1
      FROM darussolah.learning_resources r
      WHERE r.id = learning_submissions.resource_id
        AND r.tenant_id = learning_submissions.tenant_id
        AND (
          darussolah.has_institution_access(r.tenant_id, r.institution_id)
          OR EXISTS (
            SELECT 1
            FROM darussolah.class_teachers ct
            JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
            WHERE ct.class_id = r.class_id AND ct.tenant_id = r.tenant_id
              AND tp.user_id = auth.uid()
           )
           OR darussolah.user_has_student(learning_submissions.student_id, learning_submissions.tenant_id)
           OR darussolah.user_is_student(learning_submissions.student_id, learning_submissions.tenant_id)
        )
        AND (
          r.status = 'published'
          OR darussolah.has_tenant_role(r.tenant_id, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin', 'guru'])
        )
    )
   );

DROP POLICY IF EXISTS learning_submissions_submit ON darussolah.learning_submissions;
CREATE POLICY learning_submissions_submit ON darussolah.learning_submissions
  FOR INSERT WITH CHECK (
    darussolah.user_can_submit_learning_resource(tenant_id, resource_id, student_id)
    AND (file_path IS NULL OR file_path LIKE
      'submissions/' || tenant_id::text || '/' || student_id::text || '/' || resource_id::text || '/%')
    AND status IN ('submitted', 'late')
    AND reviewed_by IS NULL AND reviewed_at IS NULL
  );

DROP POLICY IF EXISTS learning_submissions_review ON darussolah.learning_submissions;
CREATE POLICY learning_submissions_review ON darussolah.learning_submissions
  FOR UPDATE USING (
    EXISTS (
      SELECT 1
      FROM darussolah.learning_resources r
      WHERE r.id = learning_submissions.resource_id
        AND r.tenant_id = learning_submissions.tenant_id
        AND (
          darussolah.has_institution_access(r.tenant_id, r.institution_id)
          OR EXISTS (
            SELECT 1
            FROM darussolah.class_teachers ct
            JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
            WHERE ct.class_id = r.class_id AND ct.tenant_id = r.tenant_id
              AND tp.user_id = auth.uid()
          )
        )
    )
  )
  WITH CHECK (reviewed_by = auth.uid());

GRANT SELECT, INSERT, UPDATE ON darussolah.learning_submissions TO authenticated;

COMMIT;
