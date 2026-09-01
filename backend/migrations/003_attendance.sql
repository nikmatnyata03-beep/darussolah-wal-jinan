-- Attendance sessions and per-student records for the first operational module.
-- Run after 002_core_portal.sql in Supabase.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.attendance_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  institution_id uuid NOT NULL REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  class_id uuid NOT NULL REFERENCES darussolah.classes(id) ON DELETE CASCADE,
  attendance_date date NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  opened_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  closed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  opened_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, class_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS darussolah.attendance_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  session_id uuid NOT NULL REFERENCES darussolah.attendance_sessions(id) ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES darussolah.students(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'present', 'excused', 'sick', 'absent', 'late')),
  note text,
  recorded_at timestamptz,
  recorded_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, student_id)
);

CREATE INDEX IF NOT EXISTS attendance_sessions_scope_idx
  ON darussolah.attendance_sessions (tenant_id, institution_id, attendance_date DESC);
CREATE INDEX IF NOT EXISTS attendance_records_session_idx
  ON darussolah.attendance_records (tenant_id, session_id, status);
CREATE INDEX IF NOT EXISTS attendance_records_student_idx
  ON darussolah.attendance_records (tenant_id, student_id, created_at DESC);

DROP TRIGGER IF EXISTS attendance_sessions_updated_at ON darussolah.attendance_sessions;
CREATE TRIGGER attendance_sessions_updated_at BEFORE UPDATE ON darussolah.attendance_sessions
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();
DROP TRIGGER IF EXISTS attendance_records_updated_at ON darussolah.attendance_records;
CREATE TRIGGER attendance_records_updated_at BEFORE UPDATE ON darussolah.attendance_records
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.attendance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE darussolah.attendance_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS attendance_sessions_scope ON darussolah.attendance_sessions;
CREATE POLICY attendance_sessions_scope ON darussolah.attendance_sessions
  FOR SELECT USING (darussolah.has_institution_access(tenant_id, institution_id));
DROP POLICY IF EXISTS attendance_sessions_write ON darussolah.attendance_sessions;
CREATE POLICY attendance_sessions_write ON darussolah.attendance_sessions
  FOR ALL USING (darussolah.has_institution_access(tenant_id, institution_id))
  WITH CHECK (darussolah.has_institution_access(tenant_id, institution_id));

DROP POLICY IF EXISTS attendance_records_scope ON darussolah.attendance_records;
CREATE POLICY attendance_records_scope ON darussolah.attendance_records
  FOR SELECT USING (
    EXISTS (
      SELECT 1
      FROM darussolah.attendance_sessions s
      WHERE s.id = attendance_records.session_id
        AND darussolah.has_institution_access(s.tenant_id, s.institution_id)
    )
    OR darussolah.user_has_student(student_id, tenant_id)
  );
DROP POLICY IF EXISTS attendance_records_write ON darussolah.attendance_records;
CREATE POLICY attendance_records_write ON darussolah.attendance_records
  FOR ALL USING (
    EXISTS (
      SELECT 1
      FROM darussolah.attendance_sessions s
      WHERE s.id = attendance_records.session_id
        AND darussolah.has_institution_access(s.tenant_id, s.institution_id)
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM darussolah.attendance_sessions s
      WHERE s.id = attendance_records.session_id
        AND s.tenant_id = attendance_records.tenant_id
        AND darussolah.has_institution_access(s.tenant_id, s.institution_id)
    )
    AND EXISTS (
      SELECT 1
      FROM darussolah.students st
      WHERE st.id = attendance_records.student_id
        AND st.tenant_id = attendance_records.tenant_id
    )
  );

GRANT SELECT, INSERT, UPDATE ON darussolah.attendance_sessions,
  darussolah.attendance_records TO authenticated;

COMMIT;
