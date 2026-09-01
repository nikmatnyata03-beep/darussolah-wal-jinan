-- Safe synthetic assignment submissions for staging and frontend integration tests.

BEGIN;

WITH target AS (
  SELECT t.id AS tenant_id, r.id AS resource_id, s.id AS student_id, item.status
  FROM darussolah.tenants t
  JOIN darussolah.learning_resources r ON r.tenant_id = t.id
    AND r.title = 'Latihan surat Al-Fil' AND r.resource_type = 'assignment'
  CROSS JOIN (VALUES
    ('DJ-TPQ-001', 'submitted'),
    ('DJ-TPQ-002', 'late')
  ) AS item(nis, status)
  JOIN darussolah.students s ON s.tenant_id = t.id AND s.nis = item.nis
  WHERE t.slug = 'yayasan-darussolah-wal-jinan'
)
INSERT INTO darussolah.learning_submissions (tenant_id, resource_id, student_id, status, note)
SELECT tenant_id, resource_id, student_id, status, 'Pengumpulan sintetis untuk staging.'
FROM target
ON CONFLICT (resource_id, student_id) DO UPDATE
SET status = EXCLUDED.status, note = EXCLUDED.note;

COMMIT;
