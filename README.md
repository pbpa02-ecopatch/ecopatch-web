# EcoPatch Web

> **Small Spaces, Greener Living**

EcoPatch adalah platform **sustainable urban gardening** berbasis web yang membantu masyarakat perkotaan memanfaatkan ruang terbatas seperti balkon, teras, rooftop, halaman kecil, maupun area indoor menjadi ruang hijau yang lebih produktif dan terkelola.

Repository ini merupakan implementasi **website EcoPatch menggunakan Django** untuk Proyek Tengah Semester mata kuliah Pemrograman Berbasis Platform Gasal 2026/2027.

---

## Anggota Kelompok

| No. | Nama                  | NPM          |
| --: | --------------------- | ------------ |
|   1 | Nurul Fikryati Bena   | `2506534825` |
|   2 | Haikal Rafka A Rahman | `2506553383` |
|   3 | Salwa Alifia Putri    | `2506620280` |
|   4 | Nur Azizah            | `2506547935` |
|   5 | Rheina Uliana         | `2506600801` |

---

## Tentang EcoPatch

Banyak masyarakat perkotaan tertarik untuk mulai berkebun, tetapi sering menghadapi beberapa kendala seperti keterbatasan ruang, tidak mengetahui tanaman yang cocok dengan kondisi tempat tinggal, kesulitan mengatur perawatan tanaman, serta tidak memiliki media untuk mencatat perkembangan tanaman.

EcoPatch hadir untuk membantu pengguna mengelola kegiatan berkebun secara lebih sederhana melalui satu platform.

Pengguna dapat:

* mencari tanaman yang sesuai dengan kondisi ruang;
* mendapatkan rekomendasi tanaman;
* membuat kebun pribadi melalui **My EcoPatch**;
* mengelola tanaman yang sedang ditanam;
* membuat jadwal perawatan tanaman;
* melihat informasi cuaca;
* mencatat perkembangan tanaman melalui **Garden Journal**;
* berbagi atau menukar bibit dan tanaman melalui **Seed Exchange**.

EcoPatch mendukung konsep **Sustainable Living**, khususnya pada subtema **Urban Farming**, dengan mendorong pemanfaatan ruang terbatas sebagai area hijau dan penggunaan kembali bibit maupun tanaman melalui aktivitas pertukaran antarpengguna.

---

## Permasalahan yang Diselesaikan

EcoPatch dirancang untuk menjawab beberapa permasalahan berikut:

1. Pengguna tidak mengetahui tanaman yang sesuai dengan kondisi ruang tempat tinggalnya.
2. Pengguna kesulitan menentukan kebutuhan dasar tanaman seperti sinar matahari dan penyiraman.
3. Pengguna sering lupa atau kesulitan mengatur jadwal perawatan tanaman.
4. Pengguna tidak memiliki tempat untuk mencatat perkembangan tanaman dari waktu ke waktu.
5. Pengguna memiliki bibit, stek, atau tanaman berlebih yang masih dapat dimanfaatkan oleh pengguna lain.

---

## Target Pengguna

Target pengguna utama EcoPatch adalah:

* mahasiswa yang tinggal di kos;
* penghuni apartemen;
* masyarakat perkotaan dengan lahan terbatas;
* pemula yang ingin mulai berkebun;
* pengguna yang ingin menerapkan gaya hidup lebih berkelanjutan.

---

## Fitur Utama

EcoPatch memiliki lima modul utama:

1. **Plant Library & Recommendation**
2. **My EcoPatch**
3. **Smart Care**
4. **Garden Journal**
5. **Seed Exchange**

Selain lima modul tersebut, sistem juga memiliki fitur autentikasi pengguna, pencarian, filtering, serta integrasi Public API.

---

## Daftar Anggota dan Pembagian Modul

| Nama                  | NPM          | Modul                          | Model Utama              |
| --------------------- | ------------ | ------------------------------ | ------------------------ |
| Nurul Fikryati Bena   | `2506534825` | Plant Library & Recommendation | `Plant`                  |
| Haikal Rafka A Rahman | `2506553383` | My EcoPatch                    | `EcoPatch`, `PatchPlant` |
| Salwa Alifia Putri    | `2506620280` | Smart Care                     | `CareTask`               |
| Nur Azizah            | `2506547935` | Garden Journal                 | `GardenJournal`          |
| Rheina Uliana         | `2506600801` | Seed Exchange                  | `SeedExchange`           |

---

## Modul Aplikasi

### 1. Plant Library & Recommendation

**PIC:** Nurul Fikryati Bena
**Model utama:** `Plant`

Modul Plant Library menyediakan katalog tanaman yang dapat digunakan pengguna sebagai referensi sebelum menambahkan tanaman ke EcoPatch miliknya.

Fitur utama:

* melihat daftar tanaman;
* melihat detail tanaman;
* menambah data tanaman;
* mengubah data tanaman;
* menghapus data tanaman;
* mencari tanaman berdasarkan nama;
* filter berdasarkan kategori;
* filter berdasarkan kebutuhan sinar matahari;
* filter berdasarkan tingkat kesulitan;
* filter berdasarkan indoor atau outdoor;
* filter berdasarkan kebutuhan ruang;
* memberikan rekomendasi tanaman berdasarkan kondisi EcoPatch pengguna.

Rekomendasi dilakukan menggunakan filtering data pada Django dan tidak menggunakan Machine Learning atau AI.

#### Initial Data

Plant Library akan memiliki minimal **60 data tanaman**.

| Kategori                  | Jumlah |
| ------------------------- | -----: |
| Vegetables                |     15 |
| Herbs                     |     10 |
| Fruit / Container Plants  |      8 |
| Flowers                   |     12 |
| Indoor / Low-Light Plants |     10 |
| Aromatic / Useful Plants  |      5 |
| **Total**                 | **60** |

Contoh atribut tanaman:

* nama;
* nama ilmiah;
* kategori;
* kebutuhan sinar matahari;
* frekuensi penyiraman;
* tingkat kesulitan;
* indoor/outdoor;
* kebutuhan ruang;
* deskripsi.

---

### 2. My EcoPatch

**PIC:** Haikal Rafka A Rahman
**Model utama:** `EcoPatch`, `PatchPlant`

My EcoPatch merupakan modul yang memungkinkan pengguna membuat dan mengelola kebun virtual miliknya.

Pengguna dapat memasukkan informasi seperti:

* nama EcoPatch;
* tipe ruang;
* ukuran ruang;
* paparan sinar matahari;
* kota;
* tujuan berkebun.

Contoh tipe ruang:

* Balcony
* Indoor
* Terrace
* Rooftop
* Small Yard

Fitur utama:

* membuat EcoPatch;
* melihat EcoPatch;
* mengubah EcoPatch;
* menghapus EcoPatch;
* menambahkan tanaman dari Plant Library;
* menentukan jumlah tanaman;
* mencatat tanggal mulai menanam;
* mengubah status tanaman;
* menghapus tanaman dari EcoPatch.

Status tanaman dapat berupa:

* `Planned`
* `Planted`
* `Growing`
* `Harvested`
* `Removed`

---

### 3. Smart Care

**PIC:** Salwa Alifia Putri
**Model utama:** `CareTask`

Smart Care membantu pengguna mengatur aktivitas perawatan tanaman.

Jenis aktivitas yang tersedia antara lain:

* Watering
* Fertilizing
* Pruning
* Repotting
* Harvesting
* Inspection

Fitur utama:

* membuat Care Task;
* melihat daftar aktivitas;
* mengubah Care Task;
* menghapus Care Task;
* menandai tugas sebagai selesai;
* melihat aktivitas berdasarkan tanggal;
* menampilkan informasi cuaca;
* menampilkan rekomendasi sederhana berdasarkan kondisi cuaca.

Contoh tampilan:

```text
Today's Care

Depok
Temperature: 29°C
Humidity: 78%
Rain Probability: 70%

High chance of rain today.
Check soil condition before watering.

[ ] Water Cabai
[ ] Fertilize Tomato
[✓] Check Basil
```

---

### 4. Garden Journal

**PIC:** Nur Azizah
**Model utama:** `GardenJournal`

Garden Journal digunakan untuk mencatat perkembangan tanaman dari waktu ke waktu.

Modul ini menggunakan data berbasis teks dan **tidak menggunakan upload gambar atau file**.

Data jurnal dapat meliputi:

* EcoPatch;
* tanaman;
* tanggal;
* judul;
* catatan;
* kondisi tanaman;
* tinggi tanaman opsional.

Contoh kondisi tanaman:

* Healthy
* Needs Attention
* Wilting
* Flowering
* Fruiting
* Ready to Harvest

Fitur utama:

* membuat jurnal;
* melihat jurnal;
* mengubah jurnal;
* menghapus jurnal;
* melihat timeline perkembangan tanaman;
* filter berdasarkan EcoPatch;
* filter berdasarkan tanaman;
* filter berdasarkan kondisi tanaman;
* filter berdasarkan tanggal;
* melihat jumlah jurnal tiap tanaman.

---

### 5. Seed Exchange

**PIC:** Rheina Uliana
**Model utama:** `SeedExchange`

Seed Exchange merupakan fitur komunitas yang memungkinkan pengguna berbagi atau menukar material tanaman yang masih dapat dimanfaatkan.

Item yang dapat dibagikan:

* Seed
* Seedling
* Cutting
* Plant

Jenis transaksi:

* `Give Away`
* `Swap`

Status listing:

* `Available`
* `Reserved`
* `Completed`

Fitur utama:

* membuat listing;
* melihat listing;
* mengubah listing;
* menghapus listing;
* filter berdasarkan jenis item;
* filter berdasarkan tanaman;
* filter berdasarkan kota;
* filter berdasarkan jenis transaksi;
* filter berdasarkan status.

EcoPatch tidak menyediakan fitur pembayaran karena Seed Exchange difokuskan pada kegiatan berbagi dan pertukaran.

---

## Public API

EcoPatch menggunakan **satu Public API eksternal**, yaitu **Open-Meteo API**.

### Open-Meteo API

Open-Meteo digunakan pada modul **Smart Care** untuk memperoleh informasi cuaca berdasarkan kota yang dipilih pengguna.

Data yang digunakan antara lain:

* temperature;
* relative humidity;
* precipitation;
* rain probability;
* weather condition.

**Open-Meteo Weather Forecast API**

#### Cara Kerja

Pengguna tidak perlu memasukkan latitude dan longitude secara manual. Pengguna cukup memilih kota yang tersedia di dalam EcoPatch.

Contoh kota:

```text
Jakarta
Bogor
Depok
Tangerang
Bekasi
Bandung
Semarang
Yogyakarta
Surabaya
Malang
Medan
Makassar
```

Koordinat kota disimpan sebagai data internal.

Contoh:

```python
CITY_COORDINATES = {
    "Jakarta": (-6.20, 106.81),
    "Depok": (-6.40, 106.82),
    "Bogor": (-6.59, 106.79),
    "Bandung": (-6.91, 107.61),
}
```

Alur penggunaan API:

```text
User memilih kota
        ↓
EcoPatch mengambil koordinat kota
        ↓
Request ke Open-Meteo API
        ↓
Data cuaca diterima
        ↓
Data ditampilkan pada Smart Care
```

Informasi cuaca kemudian dapat digunakan untuk menghasilkan pesan sederhana.

Contoh:

```text
Rain Probability >= 70%
→ High chance of rain. Check soil before watering.

Temperature >= 32°C
→ Hot weather today. Check your plants' moisture.
```

Open-Meteo berfungsi sebagai sumber data cuaca, sedangkan logika rekomendasi sederhana diproses oleh aplikasi EcoPatch.

---

## Peran Pengguna

EcoPatch memiliki tiga jenis pengguna.

### Guest

Guest dapat:

* melihat homepage;
* melihat Plant Library;
* mencari tanaman;
* menggunakan filter tanaman;
* melihat Seed Exchange.

Guest tidak dapat:

* membuat EcoPatch;
* membuat Care Task;
* membuat Garden Journal;
* membuat Seed Exchange listing;
* mengubah atau menghapus data milik pengguna lain.

### Registered User

Registered User dapat:

* membuat dan mengelola EcoPatch;
* menambahkan tanaman ke EcoPatch;
* membuat Care Task;
* melihat informasi cuaca;
* membuat Garden Journal;
* membuat Seed Exchange listing;
* mengubah data miliknya sendiri;
* menghapus data miliknya sendiri.

### Admin

Admin dapat:

* mengelola Plant Library;
* mengelola data pengguna;
* mengelola data aplikasi;
* melakukan moderasi Seed Exchange;
* mengelola master data yang dibutuhkan sistem.

---

### Plant Library

Filter tanaman dapat diperbarui secara dinamis berdasarkan:

* kategori;
* sunlight;
* difficulty;
* indoor/outdoor.

### My EcoPatch

Pengguna dapat menambahkan tanaman ke EcoPatch secara dinamis.

### Smart Care

Status Care Task dapat diubah melalui tombol:

```text
Mark as Completed
```

### Garden Journal

Timeline jurnal dapat difilter berdasarkan tanaman atau kondisi tanaman.

### Seed Exchange

Listing dapat difilter berdasarkan:

* Available
* Give Away
* Swap

---

## Struktur Repository

Repository website:

```text
ecopatch-web
```

Branch utama:

```text
main
dev
```

Branch masing-masing modul:

```text
feature/plant-library
feature/my-ecopatch
feature/smart-care
feature/garden-journal
feature/seed-exchange
```

---

## Deployment

**PWS Deployment:**
`[Belum tersedia]`

---

## Figma

**Design / Wireframe:**
`[Belum tersedia]`
