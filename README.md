# Frontend Darussolah Wal Jinan

Paket static frontend siap di-deploy ke Vercel.

## Deploy

1. Extract paket frontend ini.
2. Upload seluruh isi folder ke GitHub, atau pilih folder tersebut saat membuat project Vercel.
3. Di Vercel gunakan preset **Other** atau static site.
4. Kosongkan build command dan output directory, lalu klik **Deploy**.

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
- Deploy ulang paket ini agar perbaikan keamanan dan akses admin berlaku di situs publik.

Paket ini tidak berisi backend, database URL, password, atau credential server.
