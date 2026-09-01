-- Safe synthetic staging data for the first portal screens. No real people.

BEGIN;

INSERT INTO darussolah.academic_years (tenant_id, name, starts_on, ends_on, status)
SELECT id, '2026/2027', DATE '2026-07-01', DATE '2027-06-30', 'active'
FROM darussolah.tenants
WHERE slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (tenant_id, name) DO UPDATE
SET starts_on = EXCLUDED.starts_on, ends_on = EXCLUDED.ends_on, status = EXCLUDED.status;

INSERT INTO darussolah.programs (tenant_id, institution_id, code, name, level)
SELECT i.tenant_id, i.id, item.code, item.name, item.level
FROM darussolah.institutions i
JOIN darussolah.tenants t ON t.id = i.tenant_id
JOIN (
  VALUES
    ('TPQ', 'TAHSIN', 'Tahsin dan Tilawah', 'dasar'),
    ('MDT', 'DINIAH', 'Diniyah dan Akhlak', 'dasar'),
    ('RA', 'USIA-DINI', 'Pendidikan Anak Usia Dini', 'usia_dini'),
    ('RTQ', 'TAHFIDZ', 'Tahfidz dan Murojaah', 'tahfidz')
) AS item(institution_code, code, name, level) ON item.institution_code = i.code
WHERE t.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (institution_id, code) DO UPDATE
SET name = EXCLUDED.name, level = EXCLUDED.level, status = 'active';

INSERT INTO darussolah.classes (
  tenant_id, institution_id, program_id, academic_year_id, code, name, capacity, status
)
SELECT i.tenant_id, i.id, p.id, ay.id, item.class_code, item.class_name, item.capacity, 'active'
FROM darussolah.institutions i
JOIN darussolah.tenants t ON t.id = i.tenant_id
JOIN darussolah.programs p ON p.institution_id = i.id
JOIN darussolah.academic_years ay ON ay.tenant_id = i.tenant_id AND ay.name = '2026/2027'
JOIN (
  VALUES
    ('TPQ', 'TAHSIN', 'TPQ-01', 'Iqra 1-2', 25),
    ('MDT', 'DINIAH', 'MDT-01', 'Diniyah Dasar', 25),
    ('RA', 'USIA-DINI', 'RA-01', 'Kelompok A', 20),
    ('RTQ', 'TAHFIDZ', 'RTQ-01', 'Tahfidz Pemula', 20)
) AS item(institution_code, program_code, class_code, class_name, capacity)
  ON item.institution_code = i.code AND item.program_code = p.code
WHERE t.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (academic_year_id, institution_id, code) DO UPDATE
SET name = EXCLUDED.name, capacity = EXCLUDED.capacity, status = 'active';

COMMIT;
