# Darussolah Wal Jinan

Repository ini berisi frontend statis dan backend FastAPI untuk Darussolah Wal Jinan.

- `index.html` dan halaman HTML lain adalah frontend yang siap di-deploy ke Vercel.
- `backend/` berisi API FastAPI, migration PostgreSQL/Supabase, seed demo, dan test.

## Deploy

1. Deploy isi repository ini ke Vercel sebagai static site.
2. Di Vercel gunakan preset **Other** atau static site.
3. Kosongkan build command dan output directory, lalu klik **Deploy**.

`index.html` adalah halaman utama website yayasan. Halaman portal dan microsite tersedia sebagai file HTML terpisah.

## Setelah deploy

- `darussolah-config.js` sudah berisi API URL dan konfigurasi Supabase publik.
- Publishable/anon key boleh berada di frontend; jangan menambahkan service-role key.
- Domain production: `https://darussolah-wal-jinan.vercel.app`.
- Origin Vercel sudah ditambahkan ke allowlist CORS Cloud Run.
- Supabase Auth Site URL dan Redirect URLs sudah diarahkan ke domain Vercel.
- Validasi role pada halaman login memakai API privat Cloud Run, bukan schema database yang tidak diekspos.
- `vercel.json` menambahkan CSP, anti-clickjacking, `nosniff`, referrer policy, dan permissions policy.
- Login menyimpan sesi di `sessionStorage` kecuali pengguna memilih ingat perangkat; library Supabase dipin ke versi exact dengan SRI.
- `reset-password.html` menyediakan alur reset kata sandi melalui Supabase Auth.
- Pendaftaran tidak lagi menyimpan PII di `localStorage` jika API belum aktif atau gagal.
- Wali tidak lagi menerima fixture anak/keuangan dari HTML statis; data ditampilkan dari respons API setelah guard sesi selesai.
- Workspace admin/guru memakai endpoint live untuk absensi, santri, guru, tahfidz, nilai, keuangan, CMS, analitik, notifikasi, dan pengaturan.
- Deploy ulang paket ini agar perbaikan keamanan dan akses admin berlaku di situs publik.

## Backend

Jalankan migration `backend/migrations/001_initial.sql` sampai `backend/migrations/008_learning_resource_storage.sql` secara berurutan. Detail local run, route, dan deployment ada di `backend/README.md`.

Repository ini tidak berisi database URL, password, atau credential server.
