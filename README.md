# Tugas 1: Eksplorasi dan Analisis Dataset Besar Indonesia
**Mata Kuliah:** Analisis Big Data  
**Kelas:** Analisis Big Data (B)  
**Nama:** Rikza Ahmad Nur Muhammad  
**NIM:** 202310370311265  
**Repository:** `tugas1-abd-2026`  

---

## 1. Informasi Proyek dan Dataset

Tugas 1 mengkaji data riwayat revisi Wikipedia Bahasa Indonesia berskala puluhan juta baris menggunakan paradigma *Single-Node Renaissance* dengan tumpukan teknologi modern: **Polars** (*lazy DataFrame*), **DuckDB** (*in-process SQL OLAP*), dan **Plotly** (*interactive visualization*).

| Item | Deskripsi |
|---|---|
| **Nama Dataset** | Wikipedia Bahasa Indonesia — dump *stub meta history* `idwiki-20260901` |
| **Sumber Data** | https://dumps.wikimedia.org/idwiki/20260901/ |
| **Lisensi Data** | Konten Wikipedia: CC BY-SA 4.0; dump tunduk pada Wikimedia Terms of Use |
| **Ukuran Data Mentah** | `idwiki-20260901-stub-meta-history1.xml.gz` (2,34 GB) |
| **Ukuran Data Olahan** | `idwiki_revisions.parquet` (1,96 GB, kompresi Zstandard) |
| **Dimensi Data** | **27.771.250 baris** dan 15 kolom (melebihi batas minimal 500 MB / 1 juta baris) |
| **Cakupan Waktu** | 24 Januari 2003 – 1 September 2026 |
| **Unit Analisis** | 1 baris = 1 revisi (suntingan) pada 1 halaman Wikipedia |

---

## 2. Struktur Repository

```text
.
├── .github/
│   └── workflows/
│       └── lint_check.yml             # GitHub Actions Autograding
├── data/
│   ├── README.md                     # Dokumentasi dataset & petunjuk download
│   ├── raw/                          # Tempat penyimpanan dump XML mentah (.gitignore)
│   └── processed/                    # Tempat penyimpanan file Parquet (.gitignore)
├── notebooks/
│   ├── 01_data_profiling.ipynb       # Milestone 1: Data Profiling (Polars Lazy)
│   ├── 02_data_cleaning.ipynb        # Milestone 2: Cleaning & Validasi (DuckDB & GE)
│   └── 03_eda_and_insights.ipynb     # Milestone 3 & Final: Analisis Temporal, Ruang & Insight
├── output/
│   └── figures/                      # 8 file visualisasi interaktif Plotly (.html)
├── src/
│   ├── __init__.py
│   └── convert_idwiki_to_parquet.py  # Skrip ETL streaming XML ke Parquet
├── Dockerfile                        # Konfigurasi container JupyterLab
├── identitas.md                      # File identitas mahasiswa (Nama dan NIM)
├── requirements.txt                  # Dependensi Python
└── README.md                         # Laporan utama proyek dan AI Disclosure Statement
```

---

## 3. Ringkasan Eksekusi Tiap Milestone

### Milestone 1: Setup Repositori dan Data Profiling (`01_data_profiling.ipynb`)
* **Ekstraksi Data:** Skrip `src/convert_idwiki_to_parquet.py` mengonversi dump XML terkompresi secara streaming menggunakan `iterparse` per blok 200.000 baris ke format Apache Parquet (`zstd`), menghasilkan file 1,96 GB tanpa membebani memori kerja.
* **Profiling Skema dan Dimensi:** Dilakukan dengan Polars Lazy API (`scan_parquet()`). Terdata 15 kolom dengan tipe data terstruktur (Int64, Int16, String, Boolean, Timestamp).
* **Missing Values:**
  * `parent_rev_id` memiliki 1.488.750 baris null (5,36%). Terbukti secara semantik bahwa seluruh baris null ini adalah revisi perdana saat halaman pertama kali dibuat.
  * `comment` memiliki 5.670.672 baris null (20,42%), menunjukkan suntingan tanpa catatan ringkasan.
  * `contributor_name` terisi 100% tanpa nilai null karena diisi nama pengguna terdaftar atau alamat IP bagi kontributor anonim.
* **Cakupan Waktu:** Data mencakup 24 tahun riwayat dari revisi pertama (24 Januari 2003) hingga 1 September 2026.

### Milestone 2: Data Quality dan Data Cleaning (`02_data_cleaning.ipynb`)
* **DuckDB `SUMMARIZE`:** Profiling komprehensif dijalankan menggunakan mesin DuckDB langsung pada file Parquet untuk mengevaluasi sebaran min, max, kuartil, dan null rate.
* **Deduplikasi:** Pengecekan keunikan pada kunci primer `rev_id` menunjukkan tidak ditemukan duplikasi revisi (seluruh 27.771.250 baris unik).
* **Penanganan Outlier:** Kolom ukuran teks (`text_bytes`) menunjukkan rentang ekstrem (0 hingga 21,3 MB). Karena artikel ensiklopedia berukuran panjang merupakan artikel nyata (bukan anomali teknis), data tidak dihapus. Untuk stabilisasi metrik statistik, diterapkan transformasi **Winsorizing** pada batas persentil 1 (P1: 17 byte) dan persentil 99 (P99: 104.995 byte).
* **Validasi Skema & Aturan:**
  * Pengujian otomatis menggunakan framework **Great Expectations** pada sampel deterministik ~300.000 baris.
  * Pengujian menyeluruh berbasis aturan global DuckDB pada 27,7 juta baris: memastikan `rev_id > 0`, `text_bytes >= 0`, dan integritas relasi `parent_rev_id`.
* **Penyimpanan:** File bersih disimpan via streaming `sink_parquet()` ke `data/processed/idwiki_revisions_clean.parquet`.

### Milestone 3 & Final: Analisis Temporal, Ruang, dan Visualisasi (`03_eda_and_insights.ipynb`)
* **Arsitektur Komputasi Dua Tahap:**
  1. *DuckDB:* Menangani agregasi agregat berat berbasis SQL dengan batas alokasi memori 1 GB serta mekanisme *disk spilling*.
  2. *Polars:* Memproses tabel ringkasan kecil untuk kalkulasi deret waktu (rolling mean, persentase YoY, matriks pivot).
* **Visualisasi:** Menghasilkan 8 visualisasi interaktif Plotly yang diekspor ke folder `output/figures/`.

---

## 4. Delapan Insight Analitik Utama

Berdasarkan hasil analisis data 27,7 juta baris revisi, diperoleh 8 wawasan analitik mendalam:

1. **I1 — Puncak Pertumbuhan dan Perlambatan Relatif**  
   Volume revisi tahunan Wikipedia Indonesia mencapai titik tertinggi pada **2022 (2.641.295 revisi)** dan **2023 (2.438.911 revisi)**. Setelah itu terjadi stabilisasi di kisaran 1,5–2,0 juta revisi per tahun. Hingga September 2026 tercatat 902.231 revisi (ekuivalen laju ~1,35 juta/tahun), menunjukkan fase pertumbuhan kuantitas artikel telah melandai dibanding periode 2021–2023. (*Rujukan: Figur 1, 2*)

2. **I2 — Lonjakan Ekstrem Januari 2022 Akibat Aktivitas Bot**  
   Bulan **Januari 2022 menyumbang 796.415 revisi (2,9% dari seluruh total dataset)** hanya dalam tempo satu bulan. Dari total suntingan tersebut, hanya **2,5% yang merupakan revisi anonim** dan **70,2% berflag minor**. Analisis kontributor membuktikan bahwa 72% revisi bulan tersebut (573.119 suntingan) dilakukan oleh satu akun otomasi, yaitu **Wagino Bot**. Lonjakan serupa terjadi pada Februari 2016 (601.498 revisi). (*Rujukan: Figur 2, 4*)

3. **I3 — Konsentrasi Kontribusi pada Akun Otomasi (Bot)**  
   Struktur kontributor Wikipedia Indonesia sangat terkonsentrasi pada segelintir akun otomasi. Lima kontributor paling aktif seluruhnya merupakan bot. **Wagino Bot memegang 4.324.592 revisi (15,6% dari total seluruh revisi)** dan menyentuh 1.066.155 halaman. Gabungan 12 kontributor teratas menghasilkan 10.516.615 revisi (37,9%), sementara hanya ada 331.071 akun manusia terdaftar dan 7,9% revisi berasal dari pengguna anonim/IP. (*Rujukan: Figur 7*)

4. **I4 — Karakteristik Pola Waktu Diurnal (Malam Hari WIB)**  
   Pola penyuntingan lebih dipengaruhi oleh jam dalam sehari dibanding perbedaan hari dalam sepekan. Jam aktivitas tersibuk berada pada rentang **13:00–14:00 UTC, setara dengan 20:00–21:00 WIB** (mencapai lebih dari 1,46 juta revisi per jam). Sebanyak **24,8% revisi** terkumpul di jam 12:00–16:00 UTC (malam WIB). Sebaliknya, distribusi hari relatif stabil: hari Kamis mencatat aktivitas tertinggi (15,1%) dan Minggu terendah (13,6%). (*Rujukan: Figur 3*)

5. **I5 — Distribusi Ruang Nama (Namespace)**  
   Ruang nama Artikel utama (Namespace 0) mencakup **73,31% revisi (20.358.320 revisi)**. Namun demikian, ruang kerja kolaborasi memiliki porsi signifikan: ruang Pengguna/User (Namespace 3) menyerap **7,86%**, melampaui ruang Diskusi Artikel (Namespace 1) sebesar **7,40%**, diikuti Kategori (3,82%) dan Template (2,34%). Terdapat total 28 namespace berbeda pada sistem MediaWiki yang digunakan. (*Rujukan: Figur 5*)

6. **I6 — Konsentrasi Suntingan pada Halaman Berpola 'Daftar' dan Layanan Publik**  
   Berlaku hukum Pareto pada halaman artikel: **1% halaman artikel paling aktif (14.586 judul) menanggung 23,7% dari seluruh total revisi artikel**. Halaman dengan suntingan terbanyak didominasi oleh halaman informasi berkala dan transportasi: *Daftar acara MDTV (6.672)*, *Transjakarta (5.285)*, dan *Daftar stasiun radio di Sulawesi Utara (5.172)*. Rasio anonimitas sangat bervariasi antar topik: 71,3% pada daftar stasiun radio vs 4,2% pada ajang hiburan televisi. (*Rujukan: Figur 6*)

7. **I7 — Penurunan Proporsi Suntingan Minor Sepanjang Dekade**  
   Proporsi revisi yang ditandai sebagai *minor edit* mengalami penurunan tajam dari **65,2% pada periode awal (2003–2009)** menjadi **35,0% pada periode modern (2022–2026)**. Di sisi lain, revisi yang menyertakan ringkasan komentar turun dari 83,0% ke 77,9%. Hal ini mencerminkan pergeseran karakter pemeliharaan Wikipedia dari koreksi tipo kecil manual ke suntingan otomatis berskala besar. (*Rujukan: Figur 1*)

8. **I8 — Pertumbuhan Signifikan Ukuran Artikel (9x Lipat)**  
   Kualitas dan panjang artikel Wikipedia Bahasa Indonesia berkembang pesat. Nilai median `text_bytes` artikel meningkat secara konsisten: **814 byte (2004)** -> **2.455 byte (2010)** -> **3.899 byte (2022)** -> **5.900 byte (2025)** -> **7.347 byte (2026)**. Rata-rata ter-winsorize turut naik dari 2.286 byte menjadi 18.396 byte, membuktikan pengayaan konten ensiklopedia yang semakin mendalam. (*Rujukan: Figur 8*)

---

## 5. Daftar Visualisasi Interaktif Ter-export

Seluruh figur visualisasi interaktif disimpan dalam format HTML mandiri pada direktori `output/figures/`:

| File Visualisasi | Deskripsi Visual |
|---|---|
| [`01_revisi_per_tahun.html`](output/figures/01_revisi_per_tahun.html) | Grafik garis dan batang interaktif tren revisi tahunan serta persentase revisi minor. |
| [`02_revisi_per_bulan.html`](output/figures/02_revisi_per_bulan.html) | Grafik deret waktu bulanan dengan indikator lonjakan anomali bot. |
| [`03_heatmap_hari_jam_utc.html`](output/figures/03_heatmap_hari_jam_utc.html) | Heatmap interaktif pola aktivitas penyuntingan 7 hari x 24 jam. |
| [`04_heatmap_tahun_bulan.html`](output/figures/04_heatmap_tahun_bulan.html) | Heatmap densitas revisi per bulan dari tahun 2003 sampai 2026. |
| [`05_distribusi_namespace.html`](output/figures/05_distribusi_namespace.html) | Diagram batang horizontal proporsi revisi menurut namespace MediaWiki. |
| [`06_top_halaman.html`](output/figures/06_top_halaman.html) | Peringkat 15 halaman artikel paling banyak disunting beserta rasio kontributor anonim. |
| [`07_top_kontributor.html`](output/figures/07_top_kontributor.html) | Peringkat 15 kontributor teratas dengan pembedaan tipe akun bot vs manusia. |
| [`08_ukuran_teks_per_tahun.html`](output/figures/08_ukuran_teks_per_tahun.html) | Evolusi tahunan ukuran artikel (median dan rata-rata ter-winsorize). |

---

## 6. Panduan Menjalankan Project (Reproducibility)

### A. Persiapan Dataset
1. Unduh file dump mentah dari repositori Wikimedia Dumps:
   ```text
   URL: https://dumps.wikimedia.org/idwiki/20260901/idwiki-20260901-stub-meta-history1.xml.gz
   Tujuan: data/raw/idwiki-20260901-stub-meta-history1.xml.gz
   ```
2. Jalankan konversi XML ke Parquet:
   ```bash
   python src/convert_idwiki_to_parquet.py
   ```
   *File keluaran:* `data/processed/idwiki_revisions.parquet` (1,96 GB).

### B. Menjalankan secara Lokal
1. Pasang dependensi yang tercantum pada `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
2. Buka dan jalankan notebook secara berurutan:
   * `notebooks/01_data_profiling.ipynb`
   * `notebooks/02_data_cleaning.ipynb`
   * `notebooks/03_eda_and_insights.ipynb`

### C. Menjalankan Menggunakan Docker
Container Docker resmi telah disediakan untuk menjamin lingkungan kerja yang terisolasi dan konsisten:

1. Bangun image Docker:
   ```bash
   docker build -t tugas1-bigdata .
   ```
2. Jalankan container:
   ```bash
   docker run --rm -p 8888:8888 -v "$(pwd)":/home/jovyan/work tugas1-bigdata
   ```
3. Buka peramban web pada alamat:
   ```text
   http://localhost:8888/lab
   ```

---

## 7. AI Disclosure Statement

Pernyataan transparansi penggunaan kecerdasan buatan dalam pengerjaan Tugas 1:

* **Alat AI yang Digunakan:** Antigravity (Google DeepMind).
* **Bagian yang Dibantu:**
  1. Konsultasi arsitektur pemrosesan data besar menggunakan Polars Lazy API dan DuckDB in-process SQL agar terhindar dari *Out-of-Memory* (OOM).
  2. Perumusan skrip streaming ETL XML ke Parquet (`iterparse`) serta logika pembersihan outlier berbasis Winsorizing.
  3. Bantuan sintaks perancangan grafik interaktif Plotly dan penyusunan struktur dokumentasi laporan akhir.
* **Verifikasi yang Dilakukan:**
  1. Menjalankan seluruh baris kode dan notebook dari awal secara mandiri serta memverifikasi keluaran data nyata.
  2. Memeriksa validitas angka agregasi antara query DuckDB dan kalkulasi Polars untuk memastikan tidak ada fabrikasi atau halusinasi angka.
  3. Menguji kepatuhan pipeline terhadap pemeriksaan otomatis (*linting* dan autograding GitHub Actions).
