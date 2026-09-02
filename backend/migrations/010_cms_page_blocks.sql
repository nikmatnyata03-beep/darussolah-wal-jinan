-- Flexible public page sections and layout metadata for the production CMS.
-- Run after 009_api_only_data_plane.sql.

BEGIN;

CREATE TABLE IF NOT EXISTS darussolah.page_blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES darussolah.tenants(id) ON DELETE CASCADE,
  site_kind text NOT NULL CHECK (site_kind IN ('foundation', 'institution')),
  foundation_site_id uuid REFERENCES darussolah.foundation_sites(id) ON DELETE CASCADE,
  institution_id uuid REFERENCES darussolah.institutions(id) ON DELETE CASCADE,
  page_slug text NOT NULL CHECK (page_slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  block_key text NOT NULL CHECK (block_key ~ '^[a-z][a-z0-9_-]{1,80}$'),
  block_type text NOT NULL CHECK (block_type ~ '^[a-z][a-z0-9_-]{1,50}$'),
  title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 240),
  body text,
  media_url text,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  sort_order integer NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (site_kind = 'foundation' AND foundation_site_id IS NOT NULL AND institution_id IS NULL)
    OR (site_kind = 'institution' AND foundation_site_id IS NULL AND institution_id IS NOT NULL)
  ),
  UNIQUE (tenant_id, site_kind, page_slug, block_key)
);

CREATE INDEX IF NOT EXISTS page_blocks_public_idx
  ON darussolah.page_blocks (tenant_id, site_kind, page_slug, status, sort_order, updated_at DESC);
CREATE INDEX IF NOT EXISTS page_blocks_target_idx
  ON darussolah.page_blocks (tenant_id, foundation_site_id, institution_id, status);

DROP TRIGGER IF EXISTS page_blocks_updated_at ON darussolah.page_blocks;
CREATE TRIGGER page_blocks_updated_at BEFORE UPDATE ON darussolah.page_blocks
FOR EACH ROW EXECUTE FUNCTION darussolah.set_updated_at();

ALTER TABLE darussolah.page_blocks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS page_blocks_tenant_isolation ON darussolah.page_blocks;
CREATE POLICY page_blocks_tenant_isolation ON darussolah.page_blocks
  USING (tenant_id = darussolah.current_tenant_id())
  WITH CHECK (tenant_id = darussolah.current_tenant_id());
DROP POLICY IF EXISTS page_blocks_public_read ON darussolah.page_blocks;
CREATE POLICY page_blocks_public_read ON darussolah.page_blocks
  FOR SELECT USING (status = 'published');

-- Seed the editable foundation sections without inventing testimonials or
-- teacher biographies. Content editors can add those records from the CMS.
INSERT INTO darussolah.page_blocks (
  tenant_id, site_kind, foundation_site_id, page_slug, block_key, block_type,
  title, body, settings, status, sort_order
)
SELECT t.id, 'foundation', f.id, 'home', item.block_key, item.block_type,
       item.title, item.body, item.settings::jsonb, 'published', item.sort_order
FROM darussolah.tenants t
JOIN darussolah.foundation_sites f ON f.tenant_id = t.id
CROSS JOIN (VALUES
  ('hero-main', 'hero', 'Tempat ilmu bertumbuh, adab menjadi arah.',
   'Darussolah Wal Jinan menghadirkan ruang belajar yang dekat dengan keluarga: hangat dalam pendampingan, tertib dalam proses, dan luas dalam manfaat.',
   '{"eyebrow":"Satu rumah, banyak kebaikan","image_url":"https://plus.unsplash.com/premium_photo-1726812032548-5b44c4c50df8?auto=format&fit=crop&w=1200&q=85","sticker":"Ilmu","sticker_caption":"Adab · Amal","card_title":"4 ruang","card_text":"TPQ · MDT · RA · RTQ"}', 10),
  ('about-main', 'about', 'Mendidik bukan hanya menambah tahu.',
   'Darussolah Wal Jinan adalah rumah bersama untuk menghadirkan pendidikan Al-Quran, diniyah, dan anak usia dini yang bertumbuh dengan pendampingan manusiawi.',
   '{"eyebrow":"Tentang yayasan","quote":"Ilmu yang tumbuh bersama adab akan menjadi amal yang panjang.","note_title":"Dekat dengan keluarga","note_text":"Pendidikan yang hadir dalam keseharian, bukan hanya di ruang kelas."}', 20),
  ('units-main', 'units', 'Temukan tempat tumbuh yang tepat.',
   'Empat lembaga, empat pendekatan, satu perhatian: mendampingi anak dan keluarga agar terus bertumbuh.',
   '{"eyebrow":"Ruang belajar kami"}', 30),
  ('experience-main', 'experience', 'Lebih mudah untuk belajar bersama.',
   'Informasi penting tidak tercecer. Keluarga, guru, dan santri punya ruang yang saling terhubung.',
   '{"eyebrow":"Satu ekosistem"}', 40),
  ('news-main', 'news', 'Yang sedang hidup di ruang belajar.',
   'Cerita, kegiatan, dan kabar terbaru dari ruang belajar Darussolah.',
   '{"eyebrow":"Kabar dan kegiatan"}', 50),
  ('agenda-main', 'agenda', 'Mari hadir bersama.',
   'Informasi jadwal pertemuan, perubahan kelas, dan agenda yayasan dirangkum untuk keluarga.',
   '{"eyebrow":"Agenda rutin"}', 60),
  ('application-main', 'application', 'Langkah pertama dimulai dari sini.',
   'Isi data singkat untuk memberi tahu minat Anda. Tim pendaftaran akan membantu menjelaskan pilihan lembaga dan tahapan berikutnya.',
   '{"eyebrow":"Penerimaan santri"}', 70),
  ('support-main', 'support', 'Pendidikan adalah kerja bersama.',
   'Yayasan, guru, orang tua, dan masyarakat mengambil bagian agar ruang belajar tetap hangat dan berkelanjutan.',
   '{"eyebrow":"Tumbuh bersama"}', 80),
  ('faq-main', 'faq', 'Hal yang sering ingin diketahui.',
   'Belum menemukan jawaban yang Anda cari? Tim yayasan siap membantu menjelaskan langkah berikutnya.',
   '{"eyebrow":"Pertanyaan umum"}', 90),
  ('contact-main', 'contact', 'Kami senang mendengar cerita Anda.',
   'Untuk pertanyaan pendaftaran, kerja sama, atau informasi kegiatan, tinggalkan pesan.',
   '{"eyebrow":"Mari terhubung"}', 100),
  ('testimonials-main', 'testimonials', 'Cerita yang tumbuh bersama kami.',
   'Kutipan orang tua dan siswa yang sudah disetujui untuk tampil di halaman publik.',
   '{"eyebrow":"Cerita keluarga"}', 110),
  ('teachers-main', 'teachers', 'Guru yang mendampingi dengan hati.',
   'Kenali para guru yang hadir dalam proses belajar anak setiap hari.',
   '{"eyebrow":"Para pendamping"}', 120)
) AS item(block_key, block_type, title, body, settings, sort_order)
WHERE t.slug = 'yayasan-darussolah-wal-jinan'
ON CONFLICT (tenant_id, site_kind, page_slug, block_key) DO NOTHING;

-- Give every institution microsite the same editable block contract. The
-- existing static copy remains the safe fallback until an editor publishes a
-- replacement block.
INSERT INTO darussolah.page_blocks (
  tenant_id, site_kind, institution_id, page_slug, block_key, block_type,
  title, body, settings, status, sort_order
)
SELECT s.tenant_id, 'institution', s.institution_id, s.slug, item.block_key, item.block_type,
       CASE item.block_key WHEN 'hero-main' THEN s.name ELSE item.title END,
       CASE item.block_key WHEN 'hero-main' THEN COALESCE(s.description, s.tagline, s.name) ELSE item.body END,
       item.settings::jsonb, 'published', item.sort_order
FROM darussolah.institution_sites s
CROSS JOIN (VALUES
  ('hero-main', 'hero', 'Ruang belajar yang dekat dengan keluarga.', 'Belajar dengan ritme yang hangat, terarah, dan bertumbuh bersama.', '{}', 10),
  ('about-main', 'about', 'Tentang lembaga.', 'Profil lembaga dapat diperbarui oleh admin.', '{}', 20),
  ('posts-main', 'news', 'Kegiatan terbaru.', 'Informasi kegiatan dan pengumuman untuk santri, wali, dan guru.', '{}', 30),
  ('testimonials-main', 'testimonials', 'Cerita keluarga.', 'Kisah dan kutipan yang sudah disetujui untuk tampil publik.', '{}', 40),
  ('teachers-main', 'teachers', 'Guru kami.', 'Para pendamping belajar di lembaga ini.', '{}', 50),
  ('registration-main', 'application', 'Mulai dari satu formulir.', 'Tim lembaga akan membantu tahap berikutnya.', '{}', 60)
) AS item(block_key, block_type, title, body, settings, sort_order)
ON CONFLICT (tenant_id, site_kind, page_slug, block_key) DO NOTHING;

COMMIT;
