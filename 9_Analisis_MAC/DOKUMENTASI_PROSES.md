# Dokumentasi Proses — Analisis Mendalam Unit MAC

Dokumen ini mencatat setiap langkah analisis secara berurutan agar dapat dipakai langsung untuk Bab Metodologi, Hasil, dan Pembahasan skripsi. Setiap angka disertai nama berkas laporan sumbernya. Diperbarui setiap kali satu tugas selesai.

- Pelaksana: Laksana (Student A); pemrosesan data, skrip, dan simulasi dibantu Claude.
- Folder kerja: `C:\akselerator-jst-int8-cyclone4\9_Analisis_MAC\`
- Rencana pra-registrasi: `input/ideas/analisis-mendalam-mac-plan.md`
- Catatan penyimpangan (kronologis, singkat): `log.md`

---

## 1. Latar belakang

Pada pertemuan dengan dosen pembimbing tanggal 4 November 2026, perbandingan tiga gaya pengali (HARD, ARITH, STRUCT) dinilai perlu diperdalam:
1. Bagian mana persisnya yang membuat ARITH dan STRUCT lebih lambat daripada HARD, dan bagaimana membuktikannya; apa sebenarnya pengali HARD.
2. Berat tiap proses di dalam unit MAC perlu diketahui terpisah (misalnya MAC dibanding ReLU).

Diputuskan untuk mengukur setiap komponen unit MAC dan epilog, bukan hanya ReLU, sehingga hasilnya berupa satu tabel perbandingan per komponen.

## 2. Objek dan lingkungan

| Hal | Nilai |
|---|---|
| Perangkat | Intel Cyclone IV EP4CE6E22C8, papan OMDAZZ, osilator 50 MHz |
| Rancangan | `top_papan` (rancangan OS terbaru Student B, 8 lajur MAC, 1.708 siklus per citra) |
| Model | MLP 196–64–10, model beku `Training/export_final` |
| Sintesis dan timing | Quartus Prime Lite 25.1std.0 Build 1129 (21 Okt 2025), batasan clock 20 ns (`2_Verilog/papan.sdc`), model acuan Slow 1200mV 85C |
| Simulasi | Icarus Verilog 11.0 di VM Linux; Python 3.10.12 untuk parsir laporan |
| Varian | dipilih lewat `set_parameter -name MULT_STYLE <HARD/ARITH/STRUCT>` pada revisi `daya_<varian>` di `8_Varian_Pengali/` |

Komponen yang dianalisis (sumber: `2_Verilog/mac_unit.v` dan `2_Verilog/epilog_unit.v`):

| Kode | Komponen | Modul |
|---|---|---|
| M1 | Pengali 8×8 (HARD / ARITH / STRUCT) | `mac_unit`, tahap 1 |
| M2 | Register tahap 1 (`p_q`, `init1`, `f1`, `l1`, `v1`) | `mac_unit` |
| M3 | MUX `acc_base` (bias atau akumulator) | `mac_unit`, tahap 2 |
| M4 | Penjumlah 32 bit `acc_next` (termasuk perluasan tanda) | `mac_unit`, tahap 2 |
| M5 | Register `acc`, `m_acc`, `m_valid` | `mac_unit` |
| M6 | Handshake (`stall`, `s_ready`, `beat`) | `mac_unit` |
| E1–E5 | Pembulatan, penggeser 32 bit, ReLU, saturasi, register keluaran | `epilog_unit` |

## 3. Desain penelitian dan pra-registrasi

Hipotesis dan kriteria pembantah ditetapkan **sebelum** data baru dikumpulkan dan disetujui pada 4 Nov 2026. Hasil yang tidak sesuai tidak boleh dijawab dengan mengubah hipotesis; penyimpangan dicatat.

| | Hipotesis | Ditolak bila |
|---|---|---|
| H1 | Seluruh selisih Fmax berasal dari tahap 1 (memori → pengali → `p_q`) | (a) jalur terburuk ARITH/STRUCT tidak melewati `u_mul`, atau (b) delay tahap 2 ARITH/STRUCT berbeda > 0,50 ns dari HARD |
| H2 | Seluruh selisih LE per lajur berasal dari pengali | LE `mac_unit` − LE `u_mul` (rata-rata per lajur) ARITH/STRUCT berbeda > 5 % dari HARD |
| H3 | Selisih STRUCT vs ARITH berasal dari pemetaan carry chain | proporsi LE mode aritmetik di `u_mul` ARITH tidak ≥ 10 poin persentase lebih besar daripada STRUCT |
| H4 | Selisih Fmax ARITH vs STRUCT tidak bermakna | selisih rata-rata Fmax > 2 × simpangan baku gabungan (5 seed per varian) |
| H5 | Epilog < 5 % LE dan daya dinamis; ReLU mendekati nol | epilog > 5 % LE sistem atau > 5 % daya dinamis inti, atau ReLU > 1 % |

Metode tiga tingkat: (1) komponen sendirian dengan pembungkus register, (2) satu lajur dengan pin maya, (3) sistem utuh dengan rincian per entitas, per tahap timing, dan per hierarki daya.

Gerbang untuk setiap perubahan RTL: `tb_mac_unit.v` lulus, `jalankan_sapu.py` 48/48 identik (keduanya di `skripsi/Implementasi/`), dan `2_Verilog/jalankan_papan.py` 18/18 identik.

---

## 4. Log langkah

### Langkah 0 — Persiapan (4 Nov 2026)
- Dibuat folder `scripts/`, `wrap/`, `tb/`, `hasil/`, `referensi/`, README, dan `log.md`.
- Ditemukan bahwa `tb_mac_unit.v`, `tb_mult8.v`, `mac_lane_wrap.v`, `mult_timing_wrap.v`, dan `jalankan_sapu.py` hanya ada di `skripsi/Implementasi/`, tidak di repo. Isi `mac_unit.v`, `epilog_unit.v`, dan ketiga `mult_*.v` di kedua lokasi diperiksa identik (`diff -w`).
- Cabang git `studentA/analisis-mac` dibuat Laks dari Windows (`git switch -c studentA/analisis-mac`) pada komit `f5eb4f6`. Cabang ini dipakai untuk memecah komponen menjadi submodul (Langkah 5); `main` tetap versi asli.

### Langkah 1 — Referensi (4 Nov 2026, sebagian)
- `referensi/referensi.bib`: Baugh & Wooley (1973), Parhami (2010, edisi 2), Intel Cyclone IV Device Handbook Vol. 1 Bab 4 *Embedded Multipliers*.
- Handbook diunduh Laks ke `referensi/cyclone4-handbook.pdf` dan dibaca: Bab 4 *Embedded Multipliers in Cyclone IV Devices*, nomor dokumen CYIV-51004-1.1, Februari 2010, hlm. 4–1 s.d. 4–5. Isi yang dipakai (rinci di `referensi/catatan.md`):
  - satu blok pengali embedded = satu pengali 18 × 18 atau dua pengali 9 × 9 independen;
  - EP4CE6 memiliki 15 blok = 30 pengali 9 × 9 (Tabel 4–1), cocok dengan laporan Quartus (8 dari 30 terpakai pada HARD);
  - register masukan dan keluaran opsional; sinyal `signa`/`signb` mengatur operand bertanda; hasil presisi penuh;
  - untuk fungsi *multiplier-accumulator*, pengali memakai blok embedded dan akumulator dibangun di LE — sama dengan susunan unit MAC varian HARD;
  - **handbook tidak menjelaskan algoritma atau struktur gerbang di dalam blok pengali.** Karena itu naskah tidak boleh menyebut HARD memakai Booth atau Wallace; yang dapat dinyatakan hanyalah bahwa HARD adalah rangkaian khusus berukuran tetap di silikon, di luar fabric LE, dengan register opsional.
- Status: volume/halaman/DOI Baugh & Wooley masih perlu dicek di IEEE Xplore (akses kampus).

### Langkah 2 — Uji tuntas pengali (4 Nov 2026)
- **Tujuan:** membuktikan ketiga pengali benar untuk seluruh ruang masukan, bukan hanya pada citra uji.
- **Cara:** `skripsi/Implementasi/rtl/tb_mult8.v` menguji seluruh 256 × 256 = 65.536 pasangan masukan bertanda sekaligus untuk tiga pengali, dibandingkan dengan perkalian acuan `i * j`, ditambah tiga nilai batas.
- **Perintah:** `iverilog -g2012 -o sim tb_mult8.v mult_bw8_arith.v mult_bw8_struct.v mult_hard8.v && vvp sim` (RTL dari `2_Verilog/`).
- **Hasil:** ARITH, STRUCT, HARD masing-masing 65.536/65.536 benar; −128×−128 = 16384, −128×127 = −16256, 127×127 = 16129. Log: `hasil/T2_uji_tuntas_mult8.txt`.
- **Catatan:** di simulasi RTL, `mult_hard8.v` adalah `a*b` (atribut `multstyle` diabaikan Icarus). Kebenaran blok pengali embedded sesungguhnya dibuktikan oleh simulasi netlist pascasintesis 3 Nov.

### Langkah 3 — Rincian luas per entitas (4 Nov 2026)
- **Tujuan:** memisahkan LE pengali dari LE komponen lain di tiap lajur MAC (uji awal H2) dan memeriksa pemakaian carry chain (bukti awal H3).
- **Cara:** skrip `scripts/baca_entitas.py` membaca tabel *Fitter Resource Utilization by Entity* dari `8_Varian_Pengali/hasil_mentah/2026-11-03_os_<varian>/daya_<varian>.fit.rpt`. Jumlah LE per mode dibaca dari bagian ringkasan LE di berkas yang sama.
- **Keluaran:** `hasil/T3_entitas_datar.csv` (semua entitas), `hasil/T3_ringkasan_lajur.csv`, `hasil/T3_mode_LE.csv`.

Hasil per lajur MAC (rata-rata 8 lajur):

| | HARD | ARITH | STRUCT |
|---|---|---|---|
| `mac_unit` total | 151,38 LE | 276,75 LE | 289,00 LE |
| `u_mul` (pengali) | 0 LE + 1 pengali embedded 9 bit | 126 LE | 151,25 LE |
| Sisa `mac_unit` (bukan pengali) | 151,38 LE | 150,75 LE | 137,75 LE |
| Register per lajur | 90,25 | 90,25 | 90,25 |

Komponen lain di sistem (sama di ketiga varian): `epilog_unit` 14 LE / 8 register, `argmax10` 71 LE, `ctrl_fsm_p8` 260 LE.

LE per mode seluruh chip:

| | HARD | ARITH | STRUCT |
|---|---|---|---|
| Mode normal | 1.406 | 2.035 | 2.618 |
| Mode aritmetik (carry chain) | 420 | 924 | 420 |
| Tambahan carry chain vs HARD, per lajur | 0 | 63 | 0 |

**Pembacaan:**
- STRUCT tidak memakai carry chain sama sekali di pengalinya; seluruh tambahan LE-nya mode normal. ARITH memakai sekitar 63 LE carry chain per lajur. Ini bukti awal H3 dan bertentangan dengan catatan lama di dokumen "Konteks Skripsi" ("Quartus tetap memetakan full adder eksplisit ke carry chain"), yang berasal dari pengukuran sebelumnya.
- Pada HARD, register keluaran `mem_w` (`q[0..7]`) dikemas Quartus ke register masukan blok pengali embedded (*Register Packing, Timing optimization*; `daya_hard.fit.rpt` baris 198 dst.).
- Sisa `mac_unit` STRUCT 9 % lebih kecil dari HARD. Bila bertahan pada versi terpecah (Langkah 7), H2 ditolak untuk STRUCT. Belum disimpulkan.

### Langkah 4 — Delay per tahap (4 Nov 2026)
- **Tujuan:** menunjukkan di bagian mana waktu jalur habis, untuk menguji H1 dan menjelaskan selisih Fmax.
- **Cara:** skrip Tcl `scripts/laporan_tahap.tcl` dijalankan dengan `quartus_sta` melalui `scripts/LAPORAN_TAHAP.bat` (dijalankan Laks) pada basis data kompilasi 3 Nov, tanpa kompilasi ulang. Untuk tiga model timing (Slow 1200mV 85C, Slow 1200mV 0C, Fast 1200mV 0C) dibuat `report_timing -setup -detail full_path` untuk:
  - tahap 1: `-from [get_registers {*u_mem_d* *u_mem_w*}] -to [get_registers {*u_mac*p_q*}]`
  - tahap 2: `-from [get_registers {*u_mac*p_q* *u_mac*mac_out*}] -to [get_registers {*u_mac*acc*}]`
  - jalur menuju epilog dan argmax, serta 10 jalur terburuk global.
  Laporan dibaca `scripts/baca_tahap.py`: slack, data delay, jumlah tingkat logika, delay sel vs interkoneksi, dan pembagian waktu jalur data menurut tempatnya (di dalam `u_mul`, di bagian lain `u_mac`, di luar).
- **Keluaran:** `hasil/T4/<varian>/*.rpt` (laporan mentah), `hasil/T4_tahap.csv`.

Hasil (Slow 1200mV 85C):

| | HARD | ARITH | STRUCT |
|---|---|---|---|
| Tahap 1: data delay | 8,536 ns | 17,014 ns | 17,571 ns |
| — waktu di dalam pengali | 5,47 ns | 14,34 ns | 17,21 ns |
| — tingkat logika | 2 | 9 | 19 |
| — interkoneksi / sel | 4,54 / 3,66 ns | 6,97 / 9,78 ns | 9,63 / 7,69 ns |
| Tahap 1: slack | 11,064 ns | 2,416 ns | 2,382 ns |
| Tahap 2: data delay | 7,869 ns | 8,568 ns | 8,701 ns |
| Tahap 2: slack | 12,024 ns | 11,364 ns | 11,219 ns |
| Jalur terburuk sistem | `ctrl_fsm_p8` → `argmax10`, 12,050 ns | tahap 1 | tahap 1 |

Fmax per model timing (`hasil/T4/<varian>/fmax_<model>.rpt`):

| | Slow 85C | Slow 0C | Fast 0C |
|---|---|---|---|
| HARD | 82,46 MHz | 88,03 MHz | 187,51 MHz |
| ARITH | 56,87 MHz | 60,97 MHz | 131,61 MHz |
| STRUCT | 56,76 MHz | 59,99 MHz | 126,86 MHz |

**Pembacaan:**
- Pada ARITH dan STRUCT, 14–17 ns dari 20 ns habis di dalam pengali. Pada HARD, blok pengali embedded hanya memakan sekitar 5,5 ns, sehingga jalur terburuk berpindah ke pengendali → argmax.
- Jalur kritis ARITH berjalan melalui rangkaian penjumlah baris yang memakai carry chain (`cout` → `cin` dengan interkoneksi 0 ns), 9 tingkat logika. STRUCT melewati 19 LE terpisah tanpa carry chain. Ini bukti tambahan untuk H3.
- Urutan dan selisih antarvarian konsisten di ketiga model timing.

**Status H1: DITOLAK menurut kriteria pra-registrasi (b).** Bagian (a) terpenuhi (jalur terburuk ARITH/STRUCT melewati `u_mul`), tetapi delay tahap 2 ARITH (+0,699 ns) dan STRUCT (+0,832 ns) melebihi ambang 0,50 ns. Penjelasan berikut berstatus eksploratif: logika tahap 2 identik di ketiga varian (penjumlah 32 bit di carry chain); selisih berasal dari penempatan (interkoneksi menuju penjumlah 1,691 ns pada HARD vs 2,354 ns pada STRUCT) dan dari bit awal jalur (HARD `p_q[2]`, STRUCT `p_q[0]`, sehingga rantai carry lebih panjang). Tahap 2 memiliki slack > 11 ns di semua varian, jadi tidak memengaruhi Fmax.

### Langkah 5 — Memecah komponen menjadi submodul (4 Nov 2026)
- **Tujuan:** agar Quartus melaporkan LE, timing, dan daya untuk setiap komponen M2–M6 dan E1–E5 secara terpisah. Tanpa pemecahan, semuanya tergabung dalam satu baris `mac_unit` / `epilog_unit` di laporan per entitas.
- **Cabang:** `studentA/analisis-mac`. Salinan asli versi datar disimpan di `9_Analisis_MAC/rtl_datar_asli/` (`mac_unit.v`, `epilog_unit.v`). Cabang `main` tidak diubah.
- **Perubahan `2_Verilog/mac_unit.v`:** isi tahap 2 dan pengendali dipindah ke submodul, tanpa mengubah logika:

| Instans | Modul | Komponen |
|---|---|---|
| `u_hs` | `mac_handshake` | M6: `stall`, `s_ready`, `beat` |
| `u_t1` | `mac_reg_t1` | M2: register `p_q`, `init1`, `f1`, `l1`, `v1` |
| `u_mux` | `mac_mux_init` | M3: `acc_base = f_use ? init_use : acc` |
| `u_add` | `mac_add32` | M4: perluasan tanda `prod_ext` dan `acc_next = acc_base + prod_ext` |
| `u_acc` | `mac_reg_acc` | M5: register `acc`, `m_acc`, `m_valid` (logika disalin persis) |

  Instans pengali (`g_hard/g_arith/g_struct.u_mul`), blok `generate` untuk `PIPE_MULT`, dan blok `g_epilog` tidak diubah. Satu-satunya perubahan pada deklarasi port: `m_valid` dan `m_acc` menjadi `output wire` (sebelumnya `output reg`) karena kini digerakkan dari submodul; nama, lebar, protokol, dan latensi port tetap sama sehingga kontrak `mac_unit` tidak berubah.
- **Perubahan `2_Verilog/epilog_unit.v`:** isi dipecah menjadi `u_round` (`epi_round`, E1), `u_shift` (`epi_shift`, E2: `>>> cfg_shift`), `u_relu` (`epi_relu`, E3), `u_sat` (`epi_sat`, E4), `u_out` (`epi_reg_out`, E5). Port `out_*` menjadi `output wire`.
- **Gerbang (skrip `scripts/gerbang.sh`, log di `hasil/gerbang/`):**

| Gerbang | Versi datar (acuan) | Versi terpecah |
|---|---|---|
| G1 `tb_mac_unit.v`, HARD/ARITH/STRUCT × `PIPE_MULT` 0/1 | 6/6 LULUS | 6/6 LULUS |
| G2 `jalankan_sapu.py` | 48/48 identik | 48/48 identik |
| G3 `jalankan_papan.py` (simulasi `top_papan`) | 18/18 identik, 1.708 siklus (HARD) | 18/18 identik, 1.708 siklus (HARD, ARITH, STRUCT) |

- **Kendala yang ditemui:** penyuntingan otomatis pertama meninggalkan beberapa baris `end` berlebih (pencarian teks cocok di tingkat indentasi yang salah) dan mengubah akhir baris CRLF menjadi LF. Keduanya diperbaiki sebelum gerbang dijalankan; berkas akhir kembali ber-CRLF seperti aslinya.
- **Persiapan Langkah 6 dan 8:** folder `kompilasi_pecah/` berisi `jalankan_pecah.py` (salinan `8_Varian_Pengali/jalankan_varian.py` yang membuat revisi `pecah_<varian>`), `aktivitas_mac_pecah.py` (salinan `aktivitas_mac.py` Student B dengan pola nama register yang menyesuaikan hierarki baru; jumlah bit yang diharapkan 8 × (32+32+16+32) = 896, belum diverifikasi), serta `TAHAP_KOMPILASI_PECAH.bat` dan `TAHAP_DAYA_PECAH.bat`. Berkas Student B yang asli tidak diubah.
- **Status:** RTL terpecah siap. Kompilasi Quartus versi terpecah (Langkah 6) menunggu dijalankan Laks.

### Langkah 6 — Kompilasi versi terpecah (4 Nov 2026)
- **Kendala:** kompilasi pertama dari folder `9_Analisis_MAC/kompilasi_pecah/` gagal karena `quartus_map` crash (*Fatal Error: Access Violation*, `HDBX_READER::generate_dependencies`) setelah sintesis selesai. Mematikan assignment masukan daya tidak menolong.
- **Diagnosis** (`kompilasi_pecah/diag_quartus.py`, empat uji Analysis & Synthesis varian HARD):

| Uji | Folder proyek | `mac_unit` | `epilog_unit` | Hasil |
|---|---|---|---|---|
| A | `9_Analisis_MAC/kompilasi_pecah` | datar | datar | crash |
| B | `8_Varian_Pengali` | terpecah | terpecah | lulus |
| C | `9_Analisis_MAC/kompilasi_pecah` | terpecah | datar | crash |
| D | `9_Analisis_MAC/kompilasi_pecah` | datar | terpecah | crash |

- **Kesimpulan:** penyebabnya lokasi proyek, bukan RTL terpecah. Jalur berkas inisialisasi memori di RTL (`../1_Python_PC/mem/...`) relatif terhadap folder proyek, sehingga dari folder dua tingkat berkas hex tidak ditemukan. Proyek `pecah_<varian>` dipindah ke `8_Varian_Pengali/` (keluaran `output_pecah_<varian>/`, berkas antara `build_pecah/`). Selain itu pengaturan proyek identik dengan `daya_<varian>.qsf` (diperiksa dengan `diff`).
- **Hasil kompilasi** (Laks, `8_Varian_Pengali/output_pecah_<varian>/pecah_<varian>.{fit,sta}.rpt`; banding di `hasil/T6_datar_vs_terpecah.csv`, dibuat `scripts/baca_komponen.py`):

| | Datar (3 Nov) | Terpecah | Selisih |
|---|---|---|---|
| HARD — LE total | 2.306 | 2.305 | −0,04 % |
| ARITH — LE total | 3.331 | 3.360 | +0,87 % |
| STRUCT — LE total | 3.413 | 3.439 | +0,76 % |
| HARD — Fmax Slow 85C | 82,46 MHz | 77,98 MHz | **−5,43 %** |
| ARITH — Fmax Slow 85C | 56,87 MHz | 57,71 MHz | +1,48 % |
| STRUCT — Fmax Slow 85C | 56,76 MHz | 56,36 MHz | −0,70 % |

  Register (1.420 / 1.492 / 1.492), pengali embedded (8 / 0 / 0 dari 30), dan jumlah LE mode normal/aritmetik identik dengan versi datar.
- **Keputusan menurut aturan pra-registrasi:** Fmax HARD berselisih lebih dari 2 %, jadi angka utama naskah (LE total, Fmax, daya total) tetap diambil dari versi datar. Versi terpecah hanya dipakai untuk proporsi antarkomponen. Catatan eksploratif: 77,98 MHz masih di dalam rentang 5 seed versi datar HARD (74,15–82,46 MHz, Langkah 11), dan jalur terburuk HARD bukan unit MAC melainkan `ctrl_fsm_p8` → `argmax10`, sehingga selisih ini kemungkinan besar efek penempatan.

### Langkah 7 — Luas per komponen (4 Nov 2026)
- **Cara:** `scripts/baca_komponen.py` membaca dua tabel dari laporan versi terpecah:
  - *Fitter Resource Utilization by Entity* (`pecah_<v>.fit.rpt`): LE per entitas setelah penempatan.
  - *Analysis & Synthesis Resource Utilization by Entity* (`pecah_<v>.map.rpt`): fungsi kombinasional dan register per entitas setelah sintesis.
- **Catatan metode:** LE fitter per entitas tidak dapat dijumlahkan. Bila satu LE berisi LUT milik satu entitas dan register milik entitas lain (*register packing*), LE itu tercantum di kedua entitas. Jumlah LE submodul melebihi total `mac_unit` sebesar 34–48 LE per lajur. Angka sintesis tidak memiliki masalah ini; jumlahnya tepat sama dengan total `mac_unit`. Karena itu proporsi komponen dilaporkan dengan angka sintesis, dan LE fitter ditampilkan sebagai pembanding.
- **Keluaran:** `hasil/T7_komponen_luas.csv`, `hasil/T7_entitas_terpecah.csv`, `hasil/T7_mode_LE.csv`.

Rata-rata per lajur MAC (8 lajur), versi terpecah:

| Komponen | HARD sintesis (komb / reg) | ARITH sintesis | STRUCT sintesis | LE fitter HARD / ARITH / STRUCT |
|---|---|---|---|---|
| M1 Pengali `u_mul` | 0 / 0 (+1 pengali embedded) | 126 / 0 | 151,25 / 0 | 0 / 126 / 151,25 |
| M2 Register tahap 1 `u_t1` | 10,12 / 26,12 | 25,12 / 26,12 | 10,12 / 26,12 | 26,25 / 26,25 / 26,25 |
| M3 MUX `acc_base` `u_mux` | 32 / 0 | 32 / 0 | 32 / 0 | 32 / 32 / 32 |
| M4 Penjumlah 32 bit `u_add` | 64 / 0 | 64 / 0 | 64 / 0 | 64 / 64 / 64 |
| M5 Register akumulator `u_acc` | 0,38 / 64,12 | 0,38 / 64,12 | 0,38 / 64,12 | 64,38 / 64,38 / 64,38 |
| M6 Handshake `u_hs` | 0,25 / 0 | 0,25 / 0 | 0,25 / 0 | 0,25 / 0,25 / 0,25 |
| **`mac_unit` total** | **106,75 / 90,25** | **247,75 / 90,25** | **258,00 / 90,25** | **151,25 / 279,38 / 289,75** |

Epilog (satu instans, sama di ketiga varian): pembulatan 0, penggeser 0, ReLU 0, saturasi 5, register keluaran 9 LE (8 register); total 14 LE = 0,41–0,61 % LE sistem.

**Pembacaan:**
- Logika di luar pengali hampir sama di ketiga varian. Penjumlah dan MUX tahap 2 (96 fungsi kombinasional) adalah bagian terbesar setelah pengali, dan pada HARD menjadi seluruh logika kombinasional unit MAC.
- Handshake (M6) hanya 2 fungsi kombinasional dan muncul di satu lajur. Karena sinyal `m_ready` dari pengendali sama untuk semua lajur, Quartus menggabungkan logika yang identik.
- ARITH memiliki 15 fungsi kombinasional lebih banyak di `u_t1` daripada HARD/STRUCT. Eksploratif: Quartus memindahkan sebagian logika ujung pengali melintasi batas modul ke register `p_q` (seluruh LE `u_t1` ARITH berjenis LUT/register).
- Di sistem, konfigurasi epilog konstan (`ctrl_fsm_p8.v` baris 184–186: shift 8, round 0, relu 1). Karena itu pembulatan hilang, penggeseran menjadi pengawatan, dan ReLU terserap ke logika saturasi, sehingga ketiganya 0 LE. Biaya ReLU dengan konfigurasi variabel diukur sendirian di Langkah 10.

**Uji H2 (kriteria pra-registrasi, LE fitter):** LE `mac_unit` − LE `u_mul` per lajur: HARD 151,25; ARITH 153,38 (+1,4 %); STRUCT 138,50 (−8,4 %). **H2 ditolak** karena STRUCT berselisih lebih dari 5 %. Penjelasan eksploratif: pada tingkat sintesis logika non-pengali STRUCT identik dengan HARD (106,75 fungsi kombinasional). Selisih di tingkat fitter muncul karena register `p_q` STRUCT lebih banyak dikemas ke LE keluaran pengali (rata-rata 23,5 LE LUT/register di `u_mul` STRUCT, dibanding 8 pada ARITH), sehingga LE bersama itu terhitung di `u_mul`.

**Uji H3:** laporan fitter tidak memecah mode LE per entitas, jadi dipakai selisih seluruh chip terhadap HARD. LE mode aritmetik: HARD 420, ARITH 924, STRUCT 420. Tambahan carry chain per lajur: ARITH 63 dari 126 LE pengali (50,0 %), STRUCT 0 dari 151,25 (0 %). Selisih 50 poin persentase ≥ 10 → **H3 bertahan**. Asumsi metode: entitas lain memakai mode aritmetik sama di ketiga varian (didukung `u_add` 64 LE dan logika non-pengali sintesis yang sama). Konfirmasi visual dengan Technology Map Viewer menyusul.

### Langkah 8 — Daya per komponen (4 Nov 2026)
- **Cara:** metode tim (`6_Daya_FPGA`, Student B) diterapkan pada versi terpecah oleh `kompilasi_pecah/jalankan_pecah.py`:
  1. simulasi netlist pascasintesis `pecah_<v>.vo` dengan Icarus Verilog, VCD dipotong hanya pada jendela inferensi;
  2. aktivitas register MAC (`acc`, `m_acc`, `p_q`, `init1`; 8 lajur × 112 bit = 896 bit) dimasukkan sebagai assignment `POWER_TOGGLE_RATE` / `POWER_STATIC_PROBABILITY` (`aktivitas_mac_pecah.py`, salinan `aktivitas_mac.py` dengan pola nama yang mengikuti hierarki baru, misalnya `g_lajur[k].u_mac|u_t1|p_q[i]`);
  3. Power Analyzer dijalankan di Windows (`TAHAP_DAYA_PECAH.bat`).
- **Tahap simulasi (VM, selesai):** ketiga varian lulus uji RTL 18/18 inferensi; jendela inferensi siklus 216–1924 = 1.708 siklus; simulasi netlist cocok dengan RTL (LED pada siklus 1926); 896 bit aktivitas register untuk tiap varian. Berkas di `8_Varian_Pengali/build_pecah/`.
- **Tahap Power Analyzer** (Laks): laporan di `8_Varian_Pengali/output_pecah_<v>/pecah_<v>.pow.rpt`, diarsipkan ke `8_Varian_Pengali/hasil_mentah/2026-11-04_analisis_mac_pecah_<v>/`. Parsir: `scripts/baca_daya.py` → `hasil/T8_daya_hierarki.csv`, `hasil/T8_daya_komponen.csv`.
- **Catatan metode:**
  - Daya dinamis per komponen diambil dari tabel *Thermal Power Dissipation by Hierarchy* (dinamis blok + dinamis routing). Tabel ini lengkap: jumlahnya sama dengan daya inti dinamis ditambah daya dinamis I/O (0,34 mW). Tabel *by Block* tidak dipakai karena tidak memuat semua sel (jumlahnya hanya 80–88 % daya inti dinamis).
  - Daya statis tidak dibagi per komponen; Power Analyzer membukukannya pada tingkat chip.
  - Pada HARD, daya blok pengali embedded (1,41 mW untuk 8 blok, tabel *by Block Type*) dibukukan pada entitas `mem_w`, bukan `u_mul`, karena register keluaran `mem_w` dikemas ke register masukan blok pengali (Langkah 3). Daya `mem_w` sendiri pada HARD tepat 1,41 mW. Pada ARITH/STRUCT, angka `mem_w` sendiri adalah register keluarannya. Karena itu banding pengali yang setara memakai "u_mul + mem_w sendiri".
  - Semua angka daya adalah **perkiraan** Power Analyzer, bukan pengukuran fisik.

Ringkasan seluruh chip (versi terpecah; versi datar 3 Nov dalam kurung):

| | HARD | ARITH | STRUCT |
|---|---|---|---|
| Daya total | 94,24 mW (93,91) | 96,58 mW (96,68) | 98,13 mW (97,47) |
| Inti dinamis | 21,41 mW | 23,64 mW | 25,11 mW |
| Inti statis / I/O | 43,16 / 29,66 mW | 43,27 / 29,67 mW | 43,35 / 29,66 mW |
| Energi per citra | 3,219 µJ (3,208) | 3,299 µJ (3,303) | 3,352 µJ (3,330) |
| Confidence | High | High | Medium |

Confidence dan persentase sumber aktivitas sama dengan versi datar (718 register mendapat aktivitas dari assignment di ketiga varian), jadi nama node aktivitas versi terpecah cocok.

Daya dinamis per komponen (jumlah 8 lajur, mW; persen dari daya inti dinamis):

| Komponen | HARD | ARITH | STRUCT |
|---|---|---|---|
| M1 Pengali `u_mul` | 0,26 (1,2 %) | 1,30 (5,5 %) | 2,63 (10,5 %) |
| M1 + `mem_w` sendiri (banding setara) | 1,67 (7,8 %) | 3,12 (13,2 %) | 4,37 (17,4 %) |
| M2 Register tahap 1 | 1,25 | 1,78 | 1,58 |
| M3 MUX | 0,17 | 0,19 | 0,22 |
| M4 Penjumlah 32 bit | 0,54 | 0,54 | 0,58 |
| M5 Register akumulator | 1,98 | 1,74 | 1,80 |
| M6 Handshake | 0,00 | 0,00 | 0,00 |
| **8 lajur `mac_unit`** | **4,22 (19,7 %)** | **5,48 (23,2 %)** | **6,74 (26,8 %)** |
| Epilog (ReLU 0,00) | 0,01 | 0,01 | 0,02 |
| 8 `mem_w` (bobot, M9K) | 8,75 (40,9 %) | 9,14 (38,7 %) | 9,13 (36,4 %) |
| `ctrl_fsm_p8` | 1,26 | 1,32 | 1,25 |
| ROM citra / `mem_d` | 1,64 / 0,55 | 1,64 / 0,81 | 1,64 / 0,90 |
| `top_papan` sendiri (terutama jaringan clock) | 5,08 | 5,34 | 5,50 |

**Pembacaan:**
- Pengali setara STRUCT memakan daya dinamis 2,6 kali HARD, ARITH 1,9 kali. Selisih daya inti dinamis antarvarian (HARD → ARITH +2,23 mW; HARD → STRUCT +3,70 mW) sebagian besar berasal dari pengali dan register sekitarnya.
- Komponen di luar pengali (penjumlah, MUX, register akumulator) memakan daya yang hampir sama di ketiga varian.
- Pemakan daya dinamis terbesar adalah memori bobot (36–41 %) dan jaringan clock, bukan unit MAC.

**Uji H5 (bagian daya):** epilog 0,01–0,02 mW = 0,04–0,08 % daya inti dinamis (< 5 %); ReLU 0 mW (≤ 1 %). Bersama bagian luas (Langkah 7), **H5 bertahan**. Batasan: di sistem konfigurasi epilog konstan, sehingga ReLU terserap ke saturasi.

### Langkah 9 — Rincian siklus (4 Nov 2026)
- **Cara:** testbench baru `tb/tb_hitung_siklus.v` meng-instansiasi `top_papan` tanpa mengubahnya dan membaca sinyal pengendali `dut.u_ctrl` di tepi turun clock. Jendela inferensi sama dengan `6_Daya_FPGA/tb_jendela_os.v` (siklus saat `sibuk = 1`). Simulasi Icarus Verilog di VM. Keluaran: `hasil/T9_siklus.csv`.
- **Hasil:** total 1.708 siklus, sama dengan penghitung papan (`siklus_r`), dan keluaran cocok dengan acuan (LED cocok).

| Bagian | Siklus | Persen |
|---|---|---|
| Isi pipa awal (latensi baca memori sebelum beat pertama) | 2 | 0,12 % |
| Beat MAC lapisan 1 (8 kelompok × 196 suku) | 1.568 | 91,80 % |
| Beat MAC lapisan 2 (2 kelompok × 64 suku) | 128 | 7,49 % |
| Ekor: 2 siklus pipa MAC + 8 siklus pengurasan kelompok terakhir | 10 | 0,59 % |
| **Total** | **1.708** | **100 %** |

  Berjalan sejajar (tidak menambah siklus): pengurasan akumulator 80 siklus (10 kelompok × 8 lajur), epilog 64, tulis aktivasi 64, argmax 10.
- **Pembacaan:** 99,30 % siklus berisi beat MAC. Epilog, argmax, dan pengurasan tersembunyi di balik aliran data, kecuali pengurasan kelompok terakhir. Catatan: penanda `lapisan2` berganti 2 siklus lebih awal karena berada di tahap alamat; pembagian per lapisan memakai urutan beat.

### Langkah 10 — Komponen sendirian (4 Nov 2026)
- **Cara:** pembungkus register (pola `mult_timing_wrap.v`) di `wrap/wrap_komponen.v` untuk pembungkus kosong, M3, M4, E1–E4, dan rantai epilog utuh; konfigurasi epilog variabel. Semua port data pin maya; batasan clock 20 ns (`wrap/wrap.sdc`). Kompilasi dan pembacaan hasil oleh `wrap/jalankan_wrap.py` (`JALANKAN_WRAP.bat`); jalur terburuk dibaca `wrap_sta.tcl` (Slow 1200mV 85C).
- **Pengali (M1)** memakai angka pembungkus lama di arsip `skripsi/Implementasi/quartus/hasil_mentah/wrap_*`: ARITH 134 LE, 65,32 MHz; STRUCT 155 LE, 60,48 MHz; HARD 0 LE + 1 pengali embedded, 267,31 MHz (dibatasi 250 MHz oleh laju toggle I/O minimum).
- **Hasil** (Laks menjalankan `JALANKAN_WRAP.bat`; arsip `8_Varian_Pengali/hasil_mentah/2026-11-04_analisis_mac_sendirian/`; `hasil/T10_sendirian.csv`, `hasil/T10_komponen_bersih.csv`). Delay komponen = data delay jalur terburuk dikurangi data delay pembungkus kosong (1,289 ns).

| Komponen | LE | Delay komponen | Fmax pembungkus |
|---|---|---|---|
| M1 pengali ARITH / STRUCT / HARD (arsip) | 134 / 155 / 0 + 1 pengali embedded | ≈ 14,0 / 15,2 / 2,5 ns (perkiraan: 1/Fmax − 1,289 ns) | 65,3 / 60,5 / 267,3 MHz |
| M3 MUX `acc_base` | 32 | 1,21 ns | 390,5 MHz |
| M4 penjumlah 32 bit | 32 (31 mode aritmetik) | 3,64 ns | 199,8 MHz |
| E1 pembulatan | 38 | 6,94 ns | 120,0 MHz |
| E2 penggeser 32 bit variabel | 115 | 7,39 ns | 114,1 MHz |
| E3 ReLU | 32 | 1,31 ns | 374,7 MHz |
| E4 saturasi | 24 | 4,96 ns | 157,9 MHz |
| E1–E4 berurutan (epilog kombinasional utuh) | 264 | 16,03 ns | 57,5 MHz |

- **Pembacaan:**
  - Pengali lunak adalah komponen paling lambat dan paling besar di jalur MAC; MUX dan penjumlah bersama hanya sekitar 4,9 ns.
  - Dengan konfigurasi variabel, epilog sendirian berukuran 264 LE dan 16 ns. Di sistem hanya 14 LE karena `ctrl_fsm_p8` memberi konfigurasi konstan (Langkah 7). Bagian terbesar adalah penggeser variabel (115 LE).
  - ReLU sendirian 32 LE (satu LUT per bit) dan 1,31 ns, yaitu 12 % LE epilog variabel. Inilah biaya ReLU bila konfigurasinya tidak tetap.
  - Penjumlah sendirian 32 LE, sedangkan di sistem `u_add` tercatat 64 LE. Penyebabnya belum diperiksa (eksploratif: `acc_next` menggerakkan dua register dengan enable berbeda).

### Langkah 12 — Metrik gabungan (4 Nov 2026)
- **Cara:** `scripts/hitung_metrik.py` → `hasil/T12_metrik.csv`. Angka utama dari versi datar (aturan Langkah 6) dan Fmax rata-rata 5 seed (Langkah 11). Operasi MAC per citra 196 × 64 + 64 × 10 = 13.184; waktu per citra 1.708 × 20 ns = 34,16 µs. Daya dan energi adalah **perkiraan** Power Analyzer.

| | HARD | ARITH | STRUCT |
|---|---|---|---|
| Energi per operasi MAC, 8 lajur + `mem_w` sendiri (setara) | 15,03 pJ | 20,03 pJ (× 1,33) | 21,66 pJ (× 1,44) |
| Energi per operasi MAC, lajur saja | 11,38 pJ | 14,72 pJ | 17,15 pJ |
| Area × delay (LE ÷ Fmax rata-rata) | 29.100 LE·ns | 58.279 LE·ns (× 2,00) | 60.592 LE·ns (× 2,08) |
| Waktu per citra bila dijalankan di Fmax rata-rata | 21,55 µs | 29,88 µs | 30,32 µs |
| Energi × delay per citra (50 MHz) | 109,6 µJ·µs | 112,8 µJ·µs | 113,8 µJ·µs |

- **Pembacaan:** pada tingkat unit MAC, HARD jauh lebih efisien (energi per MAC 25–31 % lebih rendah, area × delay setengahnya). Pada tingkat sistem utuh selisih energi per citra hanya 3–4 %, karena daya total didominasi daya statis (43 mW) dan I/O (30 mW) yang sama di ketiga varian.

### Langkah 11 — Sapuan seed (4 Nov 2026)
- **Tujuan:** mengetahui apakah selisih Fmax ARITH vs STRUCT (0,11 MHz) lebih besar daripada variasi acak fitter (H4).
- **Cara:** `scripts/sapu_seed.py` (melalui `SAPU_SEED.bat`, dijalankan Laks) membuat revisi `seed_<varian>_s<n>` dari `daya_<varian>.qsf` tanpa pengaturan daya/EDA, menambahkan `SEED <n>` (n = 1–5), mengompilasi penuh, lalu membaca Fmax Slow 85C, setup slack, dan total LE. Pembaca angka diuji terhadap laporan 3 Nov (82,46 / 56,87 / 56,76 MHz cocok). Seed 1 adalah bawaan Quartus.
- **Keluaran:** `hasil/T11_seed.csv` (per kompilasi), `hasil/T11_ringkasan.csv`, `hasil/T11_uji_H4.txt`, laporan mentah di `8_Varian_Pengali/hasil_mentah/2026-11-04_analisis_mac_seed/`. Seed 1 mereproduksi angka 3 Nov persis (82,46 / 56,87 / 56,76 MHz).

Hasil Fmax Slow 1200mV 85C (MHz):

| Seed | HARD | ARITH | STRUCT |
|---|---|---|---|
| 1 | 82,46 | 56,87 | 56,76 |
| 2 | 81,41 | 57,52 | 55,41 |
| 3 | 78,46 | 57,25 | 56,46 |
| 4 | 74,15 | 57,40 | 56,25 |
| 5 | 79,74 | 56,74 | 56,76 |
| **Rata-rata ± SD** | **79,24 ± 3,23** | **57,16 ± 0,34** | **56,33 ± 0,56** |
| Total LE rata-rata | 2.297,4 | 3.329,8 | 3.415,0 |

Uji H4 (kriteria pra-registrasi):
- Selisih rata-rata ARITH − STRUCT = 0,828 MHz.
- SD gabungan √((0,338² + 0,557²)/2) = 0,460 MHz → ambang 2 × SD = 0,921 MHz.
- 0,828 < 0,921 → **H4 bertahan** (selisih ARITH vs STRUCT tidak bermakna), dengan margin tipis 0,093 MHz.

**Pembacaan:**
- Terhadap rata-rata HARD, Fmax rata-rata turun 27,9 % (ARITH) dan 28,9 % (STRUCT). Angka −31 % pada slide lama berasal dari satu seed; untuk naskah dipakai angka rata-rata 5 seed.
- Sebaran HARD jauh lebih lebar (SD 3,23 MHz) daripada ARITH/STRUCT. Penjelasan eksploratif: jalur terburuk HARD bukan unit MAC, melainkan `ctrl_fsm_p8` → `argmax10` (Langkah 4), jalur yang didominasi interkoneksi sehingga peka terhadap penempatan. Pada ARITH/STRUCT, Fmax dipatok oleh logika pengali yang strukturnya tetap, sehingga sebarannya kecil.
- Dalam semua seed, HARD tetap jauh di atas ARITH/STRUCT (seed terburuk HARD 74,15 MHz > seed terbaik ARITH 57,52 MHz), dan ketiganya melampaui 50 MHz.

---

## 5. Ringkasan status hipotesis

| | Status | Dasar |
|---|---|---|
| H1 | Ditolak (kriteria b) | Langkah 4 |
| H2 | Ditolak (STRUCT −8,4 %); eksploratif: efek pengemasan register | Langkah 3 dan 7 |
| H3 | Bertahan (selisih 50 poin persentase) | Langkah 3, 4, dan 7 |
| H4 | Bertahan (margin 0,093 MHz) | Langkah 11 |
| H5 | Bertahan (epilog < 0,7 % LE dan < 0,1 % daya dinamis; ReLU 0) | Langkah 7 dan 8 |

## 6. Gambar

Grafik yang sudah dibuat (skrip `scripts/gambar.py`, 300 dpi, desimal koma, di `hasil/gambar/`):

| Berkas | Isi | Sumber data |
|---|---|---|
| `G_T4_delay_tahap.png` | Delay tahap 1 dan 2 per varian, tahap 1 dipecah menjadi waktu di pengali dan di luar pengali; garis periode 20 ns | `hasil/T4_tahap.csv` |
| `G_T11_fmax_seed.png` | Fmax 5 seed per varian dengan rata-rata ± SD; garis 50 MHz | `hasil/T11_seed.csv` |
| `G_T3_LE_lajur.png` | LE per lajur MAC: pengali vs bukan pengali | `hasil/T3_ringkasan_lajur.csv` |

Tangkapan layar Quartus yang sudah diambil Laks: `T4_hard_tahap1.png`, `T4_arith_tahap1.png`, `T4_struct_tahap1.png` (Timing Analyzer, jalur tahap 1, Slow 85C).

Gambar Quartus Langkah 7 (diambil Claude dengan mengendalikan Quartus, 4 Nov 2026):

| Berkas | Isi |
|---|---|
| `T7_techmap_hard_umul.pdf/.png` | Technology Map Viewer pascafitting, `u_mul` lajur 0 HARD: satu blok `mac_mult1` (DSP_MULT 9 × 9, SIGNA/SIGNB, register masukan CLK/ENA) dan `mac_out2`, tanpa LE |
| `T7_techmap_arith_umul.pdf/.png` | `u_mul` ARITH: LE yang tersambung `cout → cin` (56 sambungan carry chain) |
| `T7_techmap_struct_umul.pdf/.png` | `u_mul` STRUCT: LE terpisah di dalam instans `full_adder`, tanpa sambungan `cin` |
| `T7_techmap_<v>_lajur.pdf/.png` | satu lajur MAC utuh: submodul `u_mul`, `u_t1`, `u_mux`, `u_add`, `u_acc`, `u_hs` |
| `T7_chipplanner_<v>.png` | Chip Planner, LE lajur 0 disorot (HARD 240, ARITH 379, STRUCT 389 node) |

PDF diekspor lewat File → Export (vektor, dapat diperbesar); PNG dibuat dengan `pdftoppm -r 200`. Hitungan `cout`/`cin` dibaca dari teks PDF (`pdftotext`) dan menjadi konfirmasi visual H3.

Rencana awal (arsip):

Tangkapan layar dari Quartus (simpan di `hasil/gambar/`, nama berkas disarankan):
1. ~~`T4_*_tahap1.png`~~ — selesai.
2. `T7_techmap_hard_umul.png` — Technology Map Viewer, `u_mul` lajur 0 HARD (menunjukkan blok pengali embedded).
3. `T7_techmap_arith_umul.png`, `T7_techmap_struct_umul.png` — Technology Map Viewer, `u_mul` lajur 0 ARITH dan STRUCT.
4. `T7_chipplanner_<varian>.png` — Chip Planner, letak satu lajur MAC.
5. `T3_fitter_entity_<varian>.png` — Compilation Report → Fitter → Resource Section → Resource Utilization by Entity.

Langkah pengambilan rinci diberikan saat tugas terkait dikerjakan.
