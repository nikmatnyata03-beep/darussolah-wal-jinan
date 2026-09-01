-- Safe synthetic attendance data for staging and frontend integration tests.

BEGIN;

WITH target AS (
  SELECT t.id AS tenant_id, i.id AS institution_id, p.id AS program_id,
         ay.id AS academic_year_id, c.id AS class_id
  FROM darussolah.tenants t
  JOIN darussolah.institutions i ON i.tenant_id = t.id AND i.code = 'TPQ'
  JOIN darussolah.programs p ON p.institution_id = i.id AND p.code = 'TAHSIN'
  JOIN darussolah.academic_years ay ON ay.tenant_id = t.id AND ay.name = '2026/2027'
  JOIN darussolah.classes c ON c.institution_id = i.id AND c.program_id = p.id
    AND c.academic_year_id = ay.id AND c.code = 'TPQ-01'
  WHERE t.slug = 'yayasan-darussolah-wal-jinan'
)
INSERT INTO darussolah.students (id, tenant_id, nis, full_name, gender, status)
SELECT item.id, target.tenant_id, item.nis, item.full_name, item.gender, 'active'
FROM target
CROSS JOIN (VALUES
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001'::uuid, 'DJ-TPQ-001', 'Aisyah Zahra', 'female'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0002'::uuid, 'DJ-TPQ-002', 'Naufal Akbar', 'male'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0003'::uuid, 'DJ-TPQ-003', 'Fathimah Nabila', 'female'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0004'::uuid, 'DJ-TPQ-004', 'Rayyan Hakim', 'male'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0005'::uuid, 'DJ-TPQ-005', 'Salwa Nurdini', 'female'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0006'::uuid, 'DJ-TPQ-006', 'Haidar Fawwaz', 'male'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0007'::uuid, 'DJ-TPQ-007', 'Maryam Safira', 'female'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0008'::uuid, 'DJ-TPQ-008', 'Umar Faruq', 'male')
) AS item(id, nis, full_name, gender)
ON CONFLICT (tenant_id, nis) DO UPDATE
SET full_name = EXCLUDED.full_name, gender = EXCLUDED.gender, status = 'active';

WITH target AS (
  SELECT t.id AS tenant_id, i.id AS institution_id, p.id AS program_id,
         ay.id AS academic_year_id, c.id AS class_id
  FROM darussolah.tenants t
  JOIN darussolah.institutions i ON i.tenant_id = t.id AND i.code = 'TPQ'
  JOIN darussolah.programs p ON p.institution_id = i.id AND p.code = 'TAHSIN'
  JOIN darussolah.academic_years ay ON ay.tenant_id = t.id AND ay.name = '2026/2027'
  JOIN darussolah.classes c ON c.institution_id = i.id AND c.program_id = p.id
    AND c.academic_year_id = ay.id AND c.code = 'TPQ-01'
  WHERE t.slug = 'yayasan-darussolah-wal-jinan'
)
INSERT INTO darussolah.enrollments (
  tenant_id, student_id, institution_id, program_id, class_id, academic_year_id, status
)
SELECT target.tenant_id, s.id, target.institution_id, target.program_id,
       target.class_id, target.academic_year_id, 'active'
FROM target
JOIN darussolah.students s ON s.tenant_id = target.tenant_id
WHERE s.nis LIKE 'DJ-TPQ-%'
ON CONFLICT (student_id, institution_id, academic_year_id) DO UPDATE
SET class_id = EXCLUDED.class_id, status = 'active';

WITH target AS (
  SELECT t.id AS tenant_id, i.id AS institution_id, c.id AS class_id
  FROM darussolah.tenants t
  JOIN darussolah.institutions i ON i.tenant_id = t.id AND i.code = 'TPQ'
  JOIN darussolah.programs p ON p.institution_id = i.id AND p.code = 'TAHSIN'
  JOIN darussolah.academic_years ay ON ay.tenant_id = t.id AND ay.name = '2026/2027'
  JOIN darussolah.classes c ON c.institution_id = i.id AND c.program_id = p.id
    AND c.academic_year_id = ay.id AND c.code = 'TPQ-01'
  WHERE t.slug = 'yayasan-darussolah-wal-jinan'
)
INSERT INTO darussolah.attendance_sessions (
  tenant_id, institution_id, class_id, attendance_date, status
)
SELECT tenant_id, institution_id, class_id, DATE '2026-08-12', 'open'
FROM target
ON CONFLICT (tenant_id, class_id, attendance_date) DO UPDATE
SET status = EXCLUDED.status;

WITH target AS (
  SELECT s.id AS session_id, s.tenant_id
  FROM darussolah.attendance_sessions s
  JOIN darussolah.tenants t ON t.id = s.tenant_id
  JOIN darussolah.classes c ON c.id = s.class_id
  WHERE t.slug = 'yayasan-darussolah-wal-jinan'
    AND c.code = 'TPQ-01' AND s.attendance_date = DATE '2026-08-12'
)
INSERT INTO darussolah.attendance_records (
  tenant_id, session_id, student_id, status, recorded_at
)
SELECT target.tenant_id, target.session_id, students.id, item.status,
       CASE WHEN item.status IN ('present', 'late') THEN now() ELSE NULL END
FROM target
JOIN (VALUES
  ('DJ-TPQ-001', 'present'), ('DJ-TPQ-002', 'present'),
  ('DJ-TPQ-003', 'excused'), ('DJ-TPQ-004', 'sick'),
  ('DJ-TPQ-005', 'present'), ('DJ-TPQ-006', 'late'),
  ('DJ-TPQ-007', 'present'), ('DJ-TPQ-008', 'pending')
) AS item(nis, status) ON true
JOIN darussolah.students students ON students.tenant_id = target.tenant_id
  AND students.nis = item.nis
ON CONFLICT (session_id, student_id) DO UPDATE
SET status = EXCLUDED.status, recorded_at = EXCLUDED.recorded_at;

COMMIT;
