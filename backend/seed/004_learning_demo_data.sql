-- Safe synthetic learning data for staging and frontend integration tests.

BEGIN;

WITH target AS (
  SELECT t.id AS tenant_id, i.id AS institution_id, c.id AS class_id
  FROM darussolah.tenants t
  JOIN darussolah.institutions i ON i.tenant_id = t.id AND i.code = 'TPQ'
  JOIN darussolah.classes c ON c.tenant_id = t.id AND c.institution_id = i.id
  JOIN darussolah.programs p ON p.id = c.program_id AND p.code = 'TAHSIN'
  JOIN darussolah.academic_years ay ON ay.id = c.academic_year_id
    AND ay.name = '2026/2027'
  WHERE t.slug = 'yayasan-darussolah-wal-jinan' AND c.code = 'TPQ-01'
)
INSERT INTO darussolah.learning_resources (
  tenant_id, institution_id, class_id, resource_type, title, subject,
  description, file_path, due_date, status, published_at
)
SELECT target.tenant_id, target.institution_id, target.class_id, item.resource_type,
       item.title, item.subject, item.description, item.file_path, item.due_date,
       'published', now()
FROM target
CROSS JOIN (VALUES
  ('material', 'Mengenal mad thabi''i', 'Tahsin', 'Latihan bacaan dasar untuk kelas Iqra 2.', 'learning/tpq-01/mad-thabii.pdf', NULL::date),
  ('assignment', 'Latihan surat Al-Fil', 'Tahsin', 'Baca dan kirim rekaman surat Al-Fil sebelum pertemuan berikutnya.', 'learning/tpq-01/latihan-al-fil.pdf', DATE '2026-08-22'),
  ('material', 'Murottal surat An-Naba', 'Tahfidz', 'Audio murojaah untuk Juz Amma.', 'learning/tpq-01/murottal-an-naba.mp3', NULL::date)
) AS item(resource_type, title, subject, description, file_path, due_date)
ON CONFLICT DO NOTHING;

COMMIT;
