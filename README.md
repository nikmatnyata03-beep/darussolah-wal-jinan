# Frontend Darussolah Wal Jinan

Paket static frontend siap di-deploy ke Vercel.

## Deploy

1. Extract file ZIP ini.
2. Upload seluruh isi folder ke GitHub, atau pilih folder tersebut saat membuat project Vercel.
3. Di Vercel gunakan preset **Other** atau static site.
4. Kosongkan build command dan output directory, lalu klik **Deploy**.

`index.html` adalah halaman utama website yayasan. Halaman portal dan microsite tersedia sebagai file HTML terpisah.

## Setelah deploy

- `darussolah-config.js` sudah berisi API URL dan konfigurasi Supabase publik.
- Publishable/anon key boleh berada di frontend; jangan menambahkan service-role key.
- Kirim URL Vercel final agar origin tersebut ditambahkan ke allowlist CORS Cloud Run.
- Sebelum login production, set Supabase Auth Site URL dan Redirect URLs ke domain Vercel final.

Paket ini tidak berisi backend, database URL, password, atau credential server.
