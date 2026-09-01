-- Safe to re-run. Replace the placeholder contact details before production use.

BEGIN;

INSERT INTO darussolah.tenants (slug, name, status)
VALUES ('yayasan-darussolah-wal-jinan', 'Yayasan Darussolah Wal Jinan', 'active')
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name, status = EXCLUDED.status;

INSERT INTO darussolah.foundation_sites (
  tenant_id, slug, name, hero_title, established_year, tagline, description,
  logo_url, phone, email, address, is_published
)
SELECT id, 'yayasan-darussolah-wal-jinan', name,
       'Membentuk Generasi Qurani, Berilmu, dan Berakhlak Mulia',
       2010,
       'Pendidikan Islam Terpadu untuk Masa Depan yang Gemilang',
       'Yayasan pendidikan Islam yang menaungi lembaga pendidikan terpadu dengan fokus pada Al-Quran, ilmu pengetahuan, dan akhlak.',
       NULL, NULL, NULL, NULL, true
FROM darussolah.tenants
WHERE slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (tenant_id) DO UPDATE
SET name = EXCLUDED.name,
    hero_title = EXCLUDED.hero_title,
    established_year = EXCLUDED.established_year,
    tagline = EXCLUDED.tagline,
    description = EXCLUDED.description,
    is_published = EXCLUDED.is_published;

INSERT INTO darussolah.institutions (tenant_id, code, name, institution_type)
SELECT id, item.code, item.name, item.institution_type
FROM darussolah.tenants,
     (VALUES
       ('TPQ', 'TPQ Darul Jinan', 'quran'),
       ('MDT', 'MDT Darussolah', 'diniyah'),
       ('RA', 'RA Darussolah', 'early_childhood'),
       ('RTQ', 'RTQ Darussolah', 'quran_tahfidz')
     ) AS item(code, name, institution_type)
WHERE tenants.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (tenant_id, code) DO UPDATE
SET name = EXCLUDED.name, institution_type = EXCLUDED.institution_type, status = 'active';

INSERT INTO darussolah.institution_sites (
  tenant_id, institution_id, slug, name, hero_title, tagline, description, is_published
)
SELECT i.tenant_id, i.id, lower(i.code), i.name,
       i.name || ' | Yayasan Darussolah Wal Jinan',
       'Pendidikan Islam terpadu yang hangat, disiplin, dan berprestasi.',
       'Profil, program pendidikan, berita, dan informasi pendaftaran ' || i.name || '.',
       true
FROM darussolah.institutions i
JOIN darussolah.tenants t ON t.id = i.tenant_id
WHERE t.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (institution_id) DO UPDATE
SET slug = EXCLUDED.slug,
    name = EXCLUDED.name,
    hero_title = EXCLUDED.hero_title,
    tagline = EXCLUDED.tagline,
    description = EXCLUDED.description,
    is_published = EXCLUDED.is_published;

INSERT INTO darussolah.site_content (
  tenant_id, site_kind, foundation_site_id, content_type, slug, title,
  excerpt, body, status, sort_order, published_at
)
SELECT t.id, 'foundation', f.id, 'announcement', 'pendaftaran-peserta-didik-baru',
       'Pendaftaran Peserta Didik Baru',
       'Informasi pendaftaran dan program pendidikan Yayasan Darussolah Wal Jinan.',
       'Silakan gunakan formulir pendaftaran pada website untuk mengirim data awal calon peserta didik.',
       'published', 1, now()
FROM darussolah.tenants t
JOIN darussolah.foundation_sites f ON f.tenant_id = t.id
WHERE t.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (tenant_id, site_kind, slug) DO UPDATE
SET title = EXCLUDED.title, excerpt = EXCLUDED.excerpt, body = EXCLUDED.body,
    status = EXCLUDED.status, published_at = EXCLUDED.published_at;

COMMIT;
