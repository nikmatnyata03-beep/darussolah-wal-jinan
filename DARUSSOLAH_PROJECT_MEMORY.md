# Memori Proyek Darussolah Wal Jinan

## Sumber dan hasil restore

- Sumber: shared Browser Use session berjudul `Website TPQ Darul Jinan profesional & ramah`.
- Sumber workspace: `77cd0d28-8375-4eac-a8a9-601db6d2740c`.
- Restore saat ini: `outputs/darussolah-wal-jinan-restored/`.
- Hasil: 222 file relevan, 7,595,331 byte, 0 kegagalan.
- Manifest lengkap: `RESTORE_MANIFEST.json`.
- File yang tidak berkaitan dengan Darussolah, termasuk artefak EzzAlgo, tidak disalin.

## Tujuan produk

Satu platform pendidikan multi-lembaga untuk Yayasan Darussolah Wal Jinan dengan tampilan dan alamat publik yang dapat dipisah, tetapi backend, database, authorization, dan data tetap terintegrasi.

Struktur organisasi:

- Yayasan Darussolah Wal Jinan
- TPQ Darul Jinan
- MDT Darussolah
- RA Darussolah
- RTQ Darussolah

Website terpisah berarti pemisahan brand, navigasi, dan konten, bukan database terpisah.

## Permukaan produk

- Website yayasan: profil, sejarah, visi-misi, pengurus, kontak, berita, agenda, galeri, transparansi, pendaftaran, dan tautan empat lembaga.
- Empat microsite: TPQ Darul Jinan, MDT Darussolah, RA Darussolah, dan RTQ Darussolah.
- Pendaftaran terpusat untuk santri baru dan daftar ulang, termasuk dokumen, nomor pendaftaran, verifikasi, dan status penerimaan.
- Portal admin/operator, guru, wali, dan santri.
- Modul absensi, santri, materi/tugas, pengumpulan tugas, feedback, tahfidz, nilai, keuangan, komunikasi, CMS, analitik, kepegawaian, notifikasi, pengaturan, dan export laporan.
- PWA hanya boleh meng-cache shell publik, tidak boleh meng-cache respons API atau dokumen privat.

## Role dan batas akses

- `yayasan_admin`: semua lembaga dan pendaftaran.
- `lembaga_admin`: satu lembaga.
- `operator_pendaftaran`: pendaftaran dan pemeriksaan dokumen sesuai scope.
- `guru`: kelas yang ditugaskan.
- `santri`: data dan aktivitas sendiri.
- `wali`: santri yang ditautkan, dapat lebih dari satu lembaga.

Authorization harus deny-by-default, tenant-scoped, institution/class/child/teacher-scoped, dan diaudit. NIS adalah identifier, bukan password; login memerlukan password/PIN atau OTP awal.

## Aturan data dan keamanan

- Gunakan satu tenant: `yayasan-darussolah-wal-jinan` dengan empat institution scope.
- Pisahkan konten publik dari data santri, wali, kesehatan, konseling, dan dokumen.
- Gunakan UUID internal dan nomor pendaftaran publik yang dibuat server.
- Santri belum aktif sebelum pendaftaran disetujui operator/admin.
- NIS, nomor telepon, URL dokumen, dan nama lengkap anak tidak boleh tampil di halaman publik.
- Dokumen identitas dan file tugas berada pada Supabase Storage private dengan signed URL berumur singkat.
- Catat audit untuk koreksi, export, perubahan role, publish, akses dokumen, dan perpindahan status.
- Gunakan idempotency key untuk submit pendaftaran, sinkronisasi absensi, notifikasi, dan import.
- Jangan menaruh `service_role`, database URL, JWT secret, password, atau credential lain di frontend.
- Payment gateway, WhatsApp automation, biometrik, dan integrasi pemerintah ditunda sampai pilot serta security review selesai.

## Artefak utama

- `index.html`: unified static demo utama.
- `darussolah-wal-jinan.html`: website yayasan versi halaman terpisah.
- `tpq-darul-jinan.html`, `mdt-darussolah.html`, `ra-darussolah.html`, `rtq-darussolah.html`: microsite.
- `login.html`, `wali.html`, `santri.html`, `absensi.html`, `materi.html`, `tahfidz.html`, `nilai.html`: portal dan operasi pembelajaran.
- `cms.html`, `analitik.html`, `kepegawaian.html`, `keuangan.html`, `notifikasi.html`, `pengaturan.html`: operasi admin.
- `darussolah-config.js`: konfigurasi frontend API/Supabase/tenant; kini berisi API URL production dan public publishable key, tanpa service-role key.
- `darussolah-portal.js`: wiring session Supabase Auth, profile, students, classes, dan sign out.
- `darussolah-assets/`: logo yayasan, lembaga, Majelis, dan Mushola.
- `darussolah-foundation-backend/`: FastAPI langsung untuk domain Darussolah.
- `university-nexus-production/`: foundation authorization/runtime/RLS yang lebih luas, dengan schema PostgreSQL `nexus`.
- `darussolah-wal-jinan-master/`: paket master frontend, backend, Supabase, backup, dan dokumentasi.

## Backend Darussolah

Folder: `darussolah-foundation-backend/`

- PostgreSQL schema: `darussolah`.
- Migration utama: `001_initial.sql` sampai `010_cms_page_blocks.sql`.
- Seed demo: `001_demo_data.sql` sampai `005_learning_submissions_demo_data.sql`.
- Private route mencakup profile, students, classes, attendance, learning resources, submissions, review, feedback, admin summary, admin students, staff, content, records, export, dan backup.
- `app/auth.py` memvalidasi token Supabase Auth ES256 melalui JWKS, dengan fallback HS256 hanya jika secret legacy dikonfigurasi.
- `app/db.py` mengisi `app.tenant_id` untuk operasi tenant-scoped dan mengandalkan RLS.
- Source test suite lulus 26 test dengan satu warning deprecation dari Starlette/httpx; compile check backend dan browser syntax check frontend juga lulus.

## Nexus production foundation

Folder: `university-nexus-production/`

- Langkah 1 sampai 13 mencakup authorization deny-by-default, OIDC JWT, tenant resolution, asyncpg repository, audit, migration runner, RLS, academic master data, enrollment integrity, content/profile, dan learning resources.
- PostgreSQL schema: `nexus`, terisolasi dari schema `public` aplikasi lain.
- Rekomendasi provider untuk pilot: Supabase PostgreSQL, Auth, Storage, dan Realtime.
- Untuk deployment dengan Nexus, aktifkan asymmetric signing key dan gunakan issuer, audience, serta JWKS URL; jangan mencampur kontrak ini dengan backend HS256 tanpa keputusan eksplisit.
- README menyatakan artefak belum merupakan deployment produksi lengkap sampai OIDC provider, runtime database, secret management, rate limit, observability, backup, dan frontend database-connected dipasang.

## Keputusan deployment

- Public website: Cloudflare Pages atau Vercel.
- API: Google Cloud Run.
- Database/Auth/Storage: Supabase.
- Backup: GitHub Actions ke S3 atau Backblaze B2, lalu lakukan restore drill.
- Cloud Run awal: `min-instances=0`, `max-instances=1`, resource kecil, Secret Manager, dan budget alert.
- Jalur deployment terdokumentasi di `darussolah-deployment.md` dan `darussolah-cloud-run.md`.
- Situs statis lama pernah diverifikasi di `https://darussolah-wal-jinan.pages.bu.app/`.
- Versi terhubung terbaru dipublikasikan di `https://darussolah-wal-jinan-live.pages.bu.app/`; slug lama tidak dapat ditimpa dari workspace ini karena dimiliki/terkunci oleh publisher sebelumnya.
- Paket source terbaru siap di `outputs/darussolah-frontend-updated.tar.gz` dan `outputs/darussolah-backend-updated.tar.gz`; arsip backend sudah memuat migration `010_cms_page_blocks.sql`; root `index.html` adalah website yayasan dan seluruh konfigurasi client publik sudah disertakan.
- Deployment final: `https://darussolah-wal-jinan.vercel.app/`.
- Repository source resmi: `https://github.com/nikmatnyata03-beep/darussolah-wal-jinan`; `main` terakhir disinkronkan ke commit `73961d6963a598606bc0600d8759e3792acc8d18` dan follow-up frontend/backend sudah terpublikasi.
- Production API deployed ke project `aura-app-496913`, region `asia-southeast2`, service `darussolah-api`; health checks dan endpoint CMS publik sudah live setelah commit CMS terbaru.
- URL API: `https://darussolah-api-653823333936.asia-southeast2.run.app`.
- Image tersimpan di Artifact Registry repository `darussolah`.
- Database URL disimpan di Secret Manager sebagai `darussolah-database-url`; service account Cloud Run memiliki akses Secret Manager.
- CORS Cloud Run mengizinkan situs lama, situs terhubung terbaru, dan domain Vercel final.
- Supabase Auth Site URL memakai domain Vercel final; redirect allowlist mempertahankan domain lama dan domain Vercel.

## Status saat ini

- Prototype frontend tersedia dan aman dipreview; website yayasan terbaru sudah memakai API production, sedangkan data yang tampil tetap sintetis.
- `darussolah-config.js` sudah berisi konfigurasi client publik untuk API dan Supabase.
- Cloud Run production aktif; `/health/live` dan `/health/ready` lulus dengan status `200`.
- Endpoint admin production terdaftar dan merespons `401` tanpa autentikasi, termasuk page-block dan restore routes. Storage resource/submission, API-only table privileges, serta tabel `page_blocks` sudah diterapkan dan diverifikasi di Supabase production.
- Schema live memiliki 24 tabel utama dengan RLS aktif dan tanpa table grants untuk `anon`/`authenticated`; migration history yang terlihat berasal dari track Nexus, jadi urutan filename primary tidak boleh direplay tanpa rekonsiliasi.
- Seed sintetis `001_demo_data.sql` sampai `005_learning_submissions_demo_data.sql` sudah diterapkan: 4 lembaga, 4 kelas, 8 santri demo, 8 record absensi, 3 learning resources, dan 2 submission.
- Endpoint publik foundation, institutions, institution detail, content, posts, teachers, dan page blocks sudah mengembalikan `200` dari domain Vercel final/API production; page blocks foundation mengembalikan 12 blok seed dan teachers kosong sampai data nyata disetujui.
- Website yayasan dan empat microsite Vercel berhasil dimuat; halaman login memuat konfigurasi Supabase dan merespons kegagalan kredensial dari Auth.
- Website yayasan terbaru sudah memanggil API production; login ES256, profil wali, daftar dua santri ter-scope, pendaftaran publik, dan idempotency sudah diuji.
- Route private tanpa token atau dengan token palsu mengembalikan `401`; origin Vercel final menerima CORS `200`.
- Akun dan record sementara untuk acceptance test sudah dihapus; belum ada akun operator/wali permanen.
- Akun awal `admin@admin.com` sudah aktif dengan role aplikasi `yayasan_admin`.
- Akun awal `guru@guru.com` sudah aktif dengan role aplikasi `guru`; sudah memiliki membership dan profil guru pada MDT, RA, RTQ, dan TPQ, serta ditugaskan ke kelas aktif MDT-01, RA-01, RTQ-01, dan TPQ-01.
- Akun wali belum dibuat; email yang sudah dikonfirmasi untuk provisioning adalah `wali@wali.com`.
- Password akun tidak disimpan di memori proyek atau dokumentasi.
- Perbaikan login admin/guru sudah diterapkan di paket frontend dan repository GitHub: role dari API dinormalkan sebagai teks, validasi memakai API privat Cloud Run, dan role tunggal otomatis dipilih ketika pilihan awal tidak cocok.
- Workspace admin/guru sudah menghubungkan absensi, santri, guru, tahfidz, nilai, keuangan, CMS, analitik, notifikasi, pengaturan, filter, form, ekspor, dan preview rapor ke data/API live; query `list_admin_students` diperbaiki agar meneruskan user scope dengan benar.
- Deployment Vercel production sudah otomatis mengambil perbaikan login, retry sesi, pemilihan kelas guru, dan akses lintas halaman admin; semuanya sudah diverifikasi pada production.
- Source backup job dan workflow `.github/workflows/backup.yml` sudah tersedia untuk dump database, Storage multi-bucket, checksum, dan upload S3; job production belum aktif karena GitHub Actions secrets belum ada dan restore drill belum dilakukan.
- Audit static follow-up tersimpan di `outputs/DARUSSOLAH_STATIC_AUDIT.md`; verifikasi live tersimpan di `outputs/DARUSSOLAH_PRODUCTION_VERIFICATION.md`; frontend dan backend follow-up sudah live di Vercel/Cloud Run.
- Arsip ZIP/TAR yang dipulihkan adalah snapshot historis; jangan menganggapnya sebagai deployment yang sudah live.
- Patch authorization terbaru mempersempit akses `lembaga_admin` pada summary, students, staff, records, content, dan export; perbaikan parameter query admin sudah live.
- `tests/test_db_authorization.py` menambahkan pengujian deny-by-default untuk membership lembaga; source terverifikasi 26 test lulus. CMS page blocks, editorial content, teacher biographies, soft delete, export, dan restore confirmation sudah terdeploy dan smoke-tested.

## Urutan pekerjaan berikutnya

1. Gunakan `darussolah-foundation-backend` sebagai jalur pilot resmi.
2. Rekonsiliasi migration `007`-`010`, review RLS termasuk tabel `tenants`, role matrix, dan seluruh seed sebelum data nyata dimasukkan.
3. Buat akun Supabase Auth permanen untuk operator/wali; akun guru sudah aktif dan ditugaskan ke seluruh kelas pilot; konfigurasi frontend publik sudah diisi dan tidak boleh memakai service-role key.
4. Lanjutkan acceptance test CMS dengan sesi admin nyata, absensi retry tanpa duplikasi, signed download materi, upload tugas private, review guru, cross-tenant denial, backup, dan restore.
5. Setelah acceptance test lulus, siapkan backup job, observability, dan keputusan fitur tertunda seperti payment atau WhatsApp.
