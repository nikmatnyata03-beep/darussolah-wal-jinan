# Handoff Darussolah Wal Jinan

## Hasil pemulihan

Materi dari percakapan bersama sudah disalin ke workspace ini. Salinan berisi 277 file dengan total 10,414,130 byte. Semua ukuran file cocok dengan sumber dan tidak ada kegagalan pengunduhan.

- `DARUSSOLAH_COPY_MANIFEST.json` - daftar 277 file beserta ukuran dan SHA-256 hasil salinan.

- `darussolah-wal-jinan-restored/` - 226 file snapshot lengkap: memori proyek, manifest, PRD, demo terpadu, empat microsite, portal admin/guru/wali/santri, backend, migration, seed, dokumentasi, dan arsip historis.
- `darussolah-vercel-frontend/` - frontend terbaru yang dipakai untuk deployment Vercel, termasuk perbaikan login, role, navigasi, PWA, reset password, dan workspace admin/guru live.
- `darussolah-frontend-updated.tar.gz` dan `darussolah-backend-updated.tar.gz` - paket terbaru yang sudah divalidasi dan siap dipindahkan ke proses deployment; arsip backend sudah memuat migration CMS `010`.
- Repository GitHub resmi terakhir tersinkron di `https://github.com/nikmatnyata03-beep/darussolah-wal-jinan`, commit `73961d6963a598606bc0600d8759e3792acc8d18`; fitur CMS page blocks, testimoni, biografi guru, dan restore sudah dipush.
- `darussolah-wal-jinan-reference/` - 12 dokumen dan arsip referensi tambahan yang berkaitan langsung dengan PRD, audit, arsitektur SIM-DWJ, MVP, dan frontend Vercel.

## Sumber memori

Baca `darussolah-wal-jinan-restored/DARUSSOLAH_PROJECT_MEMORY.md` sebelum melanjutkan pekerjaan. File tersebut merangkum keputusan produk, role, keamanan, arsitektur, status production, dan urutan pekerjaan berikutnya dari seluruh percakapan.

## Pemahaman teknis

- Produk adalah satu platform multi-lembaga untuk Yayasan Darussolah Wal Jinan, TPQ Darul Jinan, MDT Darussolah, RA Darussolah, dan RTQ Darussolah.
- Website publik dan microsite dapat dipisah secara brand, tetapi tetap memakai satu tenant dan scope lembaga yang sama.
- Frontend statis memakai Vercel. API utama memakai FastAPI di Google Cloud Run. Supabase dipakai untuk Auth, PostgreSQL, dan Storage private.
- `darussolah-foundation-backend/` adalah jalur pilot resmi. `university-nexus-production/` adalah fondasi alternatif/historis yang lebih luas, bukan pengganti otomatis.
- File privat harus memakai signed URL berumur singkat. Jangan menaruh service-role key, database URL, JWT secret, password, atau credential server di frontend.
- PWA hanya boleh meng-cache shell publik, bukan respons API atau dokumen privat.

## Status yang perlu diingat

- API Cloud Run aktif dan health checks publik sudah diverifikasi. Fitur CMS follow-up sudah live: endpoint page blocks, teachers, dan restore guard sudah diuji di production. Perbaikan Storage untuk materi/submission dan API-only table privileges sudah diterapkan langsung di Supabase production; migration history yang terlihat berasal dari track Nexus, jadi jangan replay migration primary secara buta.
- Akun admin dan guru sudah disiapkan; akun wali permanen belum dibuat.
- Source backup job dan workflow `.github/workflows/backup.yml` sudah tersedia untuk dump database, Storage multi-bucket, checksum, dan upload S3; job production belum aktif karena GitHub Actions secrets belum ada dan restore drill belum dilakukan.
- Patch authorization terbaru sudah membatasi akses `lembaga_admin` pada summary, students, staff, records, content, dan export; perbaikan parameter query admin juga sudah diterapkan. 26 test lulus. CMS follow-up sudah terdeploy melalui integrasi deployment yang sama.
- Audit source terbaru ada di `outputs/DARUSSOLAH_STATIC_AUDIT.md`; hasil verifikasi production ada di `outputs/DARUSSOLAH_PRODUCTION_VERIFICATION.md`; follow-up frontend live di Vercel dan backend live di Cloud Run.
- Arsip ZIP/TAR adalah snapshot historis; jangan menganggap isi arsip sebagai perubahan terbaru.

## Langkah lanjutan

1. Review `DARUSSOLAH_PROJECT_MEMORY.md` dan `darussolah-vercel-frontend/README.md`.
2. Rekonsiliasi migration primary dengan schema live sebelum menambah migration lain; migration CMS `010` sudah diterapkan dan 36 page block seed sudah diverifikasi.
3. Lakukan acceptance test terautentikasi untuk CMS, role admin/guru/wali, absensi, materi, pengumpulan tugas, RLS lintas tenant, backup, dan restore.
4. Jangan memasukkan data nyata sebelum role matrix, RLS, audit, dan backup tervalidasi.
