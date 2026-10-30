# EcoPatch — audit sebelum deployment dan bukti TDD

Audit 30 Oktober 2026. Hasil pekerjaan berada di salinan ini, bukan proyek asli.

## Lingkup dan integritas
- Sumber: /Users/Pedro/ecopatch-web-1, commit ba4e195e5dd57ebad61f22208d6a2861dede5efe.
- Salinan kerja: /Users/Pedro/Documents/ChatGPT/Pra UTS/TDD.
- Repository Git terpisah, branch codex/predeploy-tdd; tidak ada remote, push, atau deployment.
- .env, database, media pengguna, dan .git sumber tidak disalin. Pengujian memakai database dan upload sementara.
- Audit mencakup seluruh aplikasi. Batas hanya My EcoPatch pada permintaan sebelumnya berlaku untuk wireframe Figma; laporan ini bukan hasil pembuatan wireframe.
- Tidak ada redesign, perubahan template, aset SVG, font, atau skema database. Dua perbaikan CSS membatasi teks panjang pada kontrol yang meluber.

## Bug yang diperbaiki
1. Filter tanggal jurnal tidak valid dan tanggal kalender ekstrem sebelumnya memicu HTTP 500.
2. ID tanaman/patch tidak valid, terlalu panjang, dan digit Unicode yang tidak dapat dikonversi ditolak atau diarahkan ke fallback aman.
3. Nama tanaman jurnal kosong ditolak; nama dengan garis miring dapat dibuka kembali.
4. Penghapusan jurnal lama tanpa nama tanaman kembali ke daftar tanpa gagal redirect.
5. Upload jurnal memverifikasi isi gambar dan batas 5 MB pada form maupun upload cepat, memakai validator bersama.
6. Tanggal awal jurnal mengikuti tanggal lokal aplikasi, bukan tanggal host.
7. Email profil duplikat ditolak tanpa menolak email milik pengguna sendiri.
8. Logout memakai POST; GET tidak mengubah sesi.
9. Tombol password profil dan teks dropdown tambah tanaman tidak meluber pada breakpoint sempit.
10. Konfigurasi produksi memvalidasi secret, mendukung host/CSRF/database dari environment, dan mengaktifkan default HTTPS/cookie aman saat DEBUG=False.

## Validasi
- 611 test backend lolos (95,684 detik). Statement coverage 98,65%; branch coverage 94,27%; keduanya melewati gate >90%.
- 261 pemeriksaan browser: 29 halaman x 9 lebar (320, 360, 390, 414, 600, 768, 820, 1024, 1440). Lolos status halaman, overflow horizontal, error JavaScript, dan HTTP aset lokal.
- 20 pemeriksaan interaksi pada 320, 390, 768, 1440: CRUD My EcoPatch, HTMX tanaman, pembatalan hapus, modal profil, pencarian tanaman, serta complete/undo Smart Care. Semua lolos.
- Pembandingan desktop: 26 dari 29 screenshot identik setelah normalisasi animasi. Tiga memiliki variasi piksel dekorasi SVG animasi (daftar kebun, daftar jurnal, tambah tanaman); sumber SVG tidak berubah. Ini bukan klaim semua screenshot identik.
- Smoke test DEBUG=False: migrasi database SQLite baru, collectstatic, 12 endpoint halaman/aset lolos. check --deploy tidak memiliki ERROR; masih ada W005 dan W021 untuk HSTS subdomain/preload yang membutuhkan keputusan domain.
- Django system check lolos, tidak ada migrasi baru, dan diff whitespace bersih.
- Open-Meteo nyata berhasil mengambil tujuh hari cuaca Depok. Browser memakai stub cuaca agar hasil layout deterministik; penanganan kegagalan diuji pada backend.

Bukti lokal berada di qa/artifacts/: tests-final.txt, coverage.json, htmlcov/index.html, after-layout.json, functional.json, paired-visual.json, production-smoke.json, serta screenshot before/after. Artefak diabaikan Git; kode penguji dan laporan ini dilacak.

## Coverage dan batasnya
Coverage menghitung main, my_ecopatch, plant_library, smart_care, garden_journal, seed_exchange, dan ecopatch_project dengan branch tracking aktif. Yang dikecualikan hanya migrasi, file test, dan bootstrap ASGI/WSGI. Tidak ada pengecualian cabang untuk menaikkan angka.
qa/check_coverage.py menolak hasil jika statement ATAU branch tidak lebih dari 90%. Persentase agregat tidak berarti setiap file atau aplikasi memiliki branch coverage >90%.

## Bukti Red–Green–Refactor
Gunakan git log --oneline untuk membuka perubahan nyata:
- 8c00dee Red: regresi input/upload/akun; 1fee271 Green: perbaikan.
- 4ea9b60 Red: syarat konfigurasi produksi; 2eaeac8 Green: implementasi.
- 87b25a9 Red: pemeriksaan overflow browser; 41fbd97 Green: dropdown.
- 619f585 Refactor: validasi upload bersama dan perluasan pengujian alur.
- 8cd633a Red: hapus jurnal lama tanpa nama; b3ed5d3 Green: redirect aman.

Commit Red memang diuji gagal sebelum perbaikan. Riwayat ini dimulai saat audit salinan; tidak menggantikan riwayat kontribusi tim atau membuktikan disiplin checkpoint semester sebelumnya.

## Pemetaan ke rubrik individual (70%)
| Komponen | Bobot internal | Bukti dan batas |
|---|---:|---|
| CRUD | 35% | Validasi form, alur tambah/baca/edit/hapus, otorisasi dan input negatif diuji. Fitur tambahan dinilai dosen berdasarkan implementasi sebenarnya. |
| Interaktivitas/responsiveness | 10% | HTMX tanaman dan pengujian lintas viewport. Create/edit/delete kebun masih memakai POST/redirect; belum seluruh CRUD memakai AJAX atau optimistic UI. |
| Security | 10% | Ownership, sesi, POST logout, validasi upload, konfigurasi produksi. Belum mengklaim audit keamanan menyeluruh atau rate limiting baru. |
| Testing | 10% | Coverage agregat >90%, test backend dan browser, serta bukti Red–Green–Refactor. Nilai akhir tetap keputusan penguji. |
| Git/ownership | 10% | Commit audit terpisah dan dapat ditinjau; checkpoint historis dan kontribusi membantu tim harus dibuktikan dari repository tim. |
| Demo/live coding | 25% | Harus dijelaskan dan dipraktikkan sendiri; coverage tidak menggantikan pemahaman kode. |

## Peta demo My EcoPatch
Buka my_ecopatch/urls.py untuk rute, views.py untuk request dan pembatasan user, forms.py untuk validasi, dan models.py untuk EcoPatch/PatchPlant. Template berada di templates/my_ecopatch; interaksi di my_ecopatch/static/my_ecopatch/garden.js dan tampilan di my_ecopatch/static/my_ecopatch/garden.css.
Urutan demo: daftar kebun → tambah kebun → detail → tambah tanaman → ganti status → edit kebun → batal/hapus tanaman → batal/hapus kebun. Jelaskan request HTMX yang mengganti #patch-plants dan query yang selalu membatasi kepemilikan.
Latihan live coding: tambah satu aturan validasi di form, tulis test gagal dahulu, implementasikan, jalankan test terarah lalu seluruh suite. Jangan mengarang commit masa lalu.

## Menjalankan ulang
Dari folder TDD, gunakan environment Python terpisah:

```sh
cd '/Users/Pedro/Documents/ChatGPT/Pra UTS/TDD'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m coverage run qa/run_tests.py --noinput
.venv/bin/python -m coverage json
.venv/bin/python qa/check_coverage.py
.venv/bin/python -m coverage html
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Browser QA memakai data sintetis dan server khusus, bukan akun/database nyata:

```sh
npm install --prefix qa
npx --prefix qa playwright install chromium
AUDIT_OUTPUT=/tmp/ecopatch-qa AUDIT_PORT=8766 .venv/bin/python qa/serve_audit.py
```

Di terminal lain:

```sh
AUDIT_OUTPUT=/tmp/ecopatch-qa AUDIT_URL=http://127.0.0.1:8766 node qa/responsive_audit.cjs after
AUDIT_OUTPUT=/tmp/ecopatch-qa AUDIT_URL=http://127.0.0.1:8766 node qa/functional_audit.cjs
```

## Sebelum deployment nyata
Salin .env.example menjadi .env dan isi nilai nyata sesuai hosting. Atur DEBUG=False, SECRET_KEY acak yang kuat, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, dan DATABASE_URL jika memakai PostgreSQL. Aktifkan BEHIND_HTTPS_PROXY hanya bila reverse proxy tepercaya mengontrol header HTTPS.
Uji di staging: TLS/redirect dan proxy, PostgreSQL nyata beserta konkurensi, SMTP reset password, Google OAuth callback, persistence media, backup/restore, serta beban aplikasi. Seluruh test saat audit memakai SQLite; SMTP/OAuth diuji melalui mock, bukan pengiriman/login eksternal.
Jangan menonaktifkan validasi produksi untuk menyembunyikan kesalahan environment. HSTS include-subdomains/preload perlu keputusan pemilik domain. Belum ada deployment nyata dalam pekerjaan ini.
