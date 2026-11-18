---
title: "Analisis mendalam unit MAC: HARD vs ARITH vs STRUCT dan rincian per komponen"
type: plan
created: 2026-11-04
updated: 2026-11-04
status: pre-registered
author: mixed
design: "[[analisis-mendalam-mac-design]]"
methodology: quantitative
---

# Analisis mendalam unit MAC — Rencana Kerja

> Dijalankan tugas demi tugas. Tanda **[Laks]** berarti dijalankan Laks di laptop Windows (Quartus). Tanda **[Claude]** berarti dikerjakan Claude lewat VM (Icarus, Python, penyuntingan berkas). Setiap angka harus berasal dari laporan Quartus nyata, dengan nama berkas laporannya.

**Pertanyaan penelitian:** Pada akselerator MLP 196–64–10 (rancangan OS terbaru, 8 lajur, 50 MHz, EP4CE6E22C8), komponen mana di dalam unit MAC dan epilog yang menyumbang selisih LE, delay jalur, dan daya antara HARD, ARITH, dan STRUCT, dan seberapa besar sumbangan masing-masing?

**Hipotesis (pra-registrasi, dibekukan setelah disetujui):**
- **H1:** Seluruh selisih Fmax berasal dari tahap 1 (`mem_d` → pengali → `p_q`).
- **H2:** Seluruh selisih LE per lajur berasal dari pengali (`u_mul`); komponen lain di `mac_unit` setara antarvarian.
- **H3:** Selisih STRUCT terhadap ARITH berasal dari pemetaan carry chain: pengali ARITH memakai lebih banyak LE mode aritmetik daripada STRUCT.
- **H4:** Selisih Fmax ARITH vs STRUCT tidak bermakna dibanding variasi antar-seed fitter.
- **H5:** Epilog memakan kurang dari 5 % LE sistem dan kurang dari 5 % daya dinamis inti; ReLU sendiri mendekati nol.

**Kriteria pembantah (dibekukan):**
- **H1 ditolak** bila (a) jalur terburuk ARITH atau STRUCT tidak melewati `u_mul`, atau (b) delay jalur terburuk tahap 2 (`-from *p_q* -to *acc*`) ARITH atau STRUCT berbeda lebih dari 0,50 ns dari HARD.
- **H2 ditolak** bila LE `mac_unit` dikurangi LE `u_mul` (rata-rata per lajur) pada ARITH atau STRUCT berbeda lebih dari 5 % dari nilai yang sama pada HARD.
- **H3 ditolak** bila proporsi LE mode aritmetik di dalam `u_mul` ARITH tidak lebih besar setidaknya 10 poin persentase daripada di STRUCT.
- **H4 ditolak** bila |rata-rata Fmax ARITH − rata-rata Fmax STRUCT| lebih besar dari 2 × simpangan baku gabungan, pada 5 seed per varian.
- **H5 ditolak** bila LE `epilog_unit` > 5 % LE sistem, atau daya dinamis `epilog_unit` > 5 % daya dinamis inti, atau ReLU (E3) > 1 % LE sistem atau > 1 % daya dinamis inti.

**Kriteria berhenti:** 3 varian × (versi datar + versi terpecah), 5 seed per varian, 1 set kompilasi komponen sendirian. Tidak menambah seed atau varian setelah melihat hasil.

**Metode:** Tiga tingkat pengukuran (komponen sendirian dengan pembungkus register, satu lajur dengan pin maya, sistem utuh dengan rincian per entitas), dibaca dari laporan Quartus `.fit.rpt`, `.sta.rpt`, `.pow.rpt` dengan batasan 20 ns dan model Slow 1200mV 85C. Daya dari Power Analyzer dengan VCD jendela inferensi (metode tim).

**Luaran:** bab hasil dan pembahasan skripsi; slide progres.
**Bahasa:** Indonesia.

---

## Lokasi dan aturan kerja

- Folder kerja: `C:\akselerator-jst-int8-cyclone4\9_Analisis_MAC\` (tidak dilacak git, seperti `8_Varian_Pengali`).
  - `scripts/` skrip; `wrap/` pembungkus pengukuran sendirian; `tb/` testbench tambahan; `hasil/` CSV dan ringkasan; `log.md` catatan penyimpangan.
- Arsip laporan mentah: `8_Varian_Pengali/hasil_mentah/2026-11-xx_analisis_mac_<bagian>/`.
- Perubahan RTL hanya di berkas Student A, di cabang git `studentA/analisis-mac`. `main` tetap versi datar.
- **Gerbang** untuk setiap perubahan RTL:
  - G1: `tb_mac_unit.v` lulus (di `skripsi/Implementasi/rtl/`).
  - G2: `jalankan_sapu.py` di `skripsi/Implementasi/` tetap 48/48 identik. Berkas RTL yang diubah disalin ke `Implementasi/rtl` hanya untuk pengujian, lalu dikembalikan.
  - G3 (tambahan, rancangan OS terbaru): `2_Verilog/jalankan_papan.py` tetap 18/18 identik untuk HARD, ARITH, STRUCT.
- Temuan saat menyusun rencana (4 Nov): `tb_mac_unit.v`, `tb_mult8.v`, `mac_lane_wrap.v`, `mult_timing_wrap.v`, dan `jalankan_sapu.py` tidak ada di repo, hanya di `skripsi/Implementasi/`. Kode `mac_unit.v`, `epilog_unit.v`, dan ketiga `mult_*.v` di kedua tempat identik. `tb_mult8.v` sudah menguji tuntas 65.536 pasangan, jadi Tugas 2 hanya menjalankan ulang dan mengarsipkan.

## Data dan sumber

- Laporan 3 Nov: `8_Varian_Pengali/hasil_mentah/2026-11-03_os_{hard,arith,struct}/` — ada di disk.
- Basis data Quartus 3 Nov: `8_Varian_Pengali/db/`, `output_{hard,arith,struct}/` — ada di disk (untuk `quartus_sta` tanpa kompilasi ulang).
- Pengukuran sendirian lama (pengali, lajur, epilog 272 LE): `skripsi/Implementasi/quartus/hasil_mentah/` — ada di disk.
- Referensi (metadata diverifikasi dulu sebelum dikutip):
  - Intel, *Cyclone IV Device Handbook*, Vol. 1, bab *Embedded Multipliers in Cyclone IV Devices* — perlu diunduh.
  - C. R. Baugh dan B. A. Wooley, "A Two's Complement Parallel Array Multiplication Algorithm", *IEEE Transactions on Computers*, 1973 — perlu diunduh.
  - B. Parhami, *Computer Arithmetic: Algorithms and Hardware Designs*, Oxford University Press — untuk Booth dan Wallace/Dadda sebagai pembanding teoretis.

## Tugas

### Tugas 0: Persiapan [Claude]
**Berkas:** `9_Analisis_MAC/README.md`, `9_Analisis_MAC/log.md`
- [ ] Buat subfolder `scripts/ wrap/ tb/ hasil/ referensi/`
- [ ] Buat cabang `studentA/analisis-mac` dari `main` (belum ada perubahan RTL)
- [ ] Tulis README singkat: tujuan, urutan tugas, cara menjalankan

### Tugas 1: Referensi [Claude + Laks]
**Berkas:** `9_Analisis_MAC/referensi/referensi.bib`, `9_Analisis_MAC/referensi/catatan.md`
- [ ] Verifikasi metadata Baugh & Wooley (1973) dan Parhami lewat Crossref; tulis entri BibTeX
- [ ] [Laks] Unduh Cyclone IV Device Handbook dari situs Intel; simpan PDF di `referensi/`
- [ ] Catat dari handbook: struktur blok (18×18, mode 9×9, register opsional, kendali bertanda), jumlah blok pada EP4CE6, dan kalimat yang bisa dikutip tentang pengali HARD

### Tugas 2: Uji tuntas pengali [Claude]
**Berkas:** `9_Analisis_MAC/hasil/T2_uji_tuntas_mult8.txt`
- [ ] Jalankan `tb_mult8.v` (Icarus 11) untuk ketiga pengali
- [ ] Lulus bila ketiganya 65.536/65.536 benar dan nilai batas OK; arsipkan log

### Tugas 3: Rincian luas dari laporan 3 Nov (versi datar) [Claude]
**Berkas:** `9_Analisis_MAC/scripts/baca_entitas.py`, `hasil/T3_entitas_datar.csv`
- [ ] Parsir *Resource Utilization by Entity* di `.fit.rpt` ketiga varian: LE, register, per entitas
- [ ] Per lajur: `mac_unit` total, `u_mul`, selisih (= komponen non-pengali)
- [ ] Ambil `epilog_unit`, `argmax10`, pengendali, memori (konteks, milik Student B)
- [ ] Uji awal H2 (versi datar), tulis ke CSV

### Tugas 4: Delay per tahap dari basis data 3 Nov [Claude tulis, Laks jalankan]
**Berkas:** `scripts/laporan_tahap.tcl`, `scripts/LAPORAN_TAHAP.bat`, `hasil/T4_tahap_<varian>.rpt`, `hasil/T4_tahap.csv`
- [ ] Skrip `quartus_sta` membuka revisi `daya_<varian>` dan menjalankan `report_timing -detail full_path` untuk:
  - tahap 1: `-from *mem_d*rd_q* -to *p_q*`
  - tahap 2: `-from *p_q* -to *acc*` (termasuk `m_acc`)
  - epilog: `-to *epilog*out_act*`
  - jalur terburuk global
- [ ] Ketiga model timing (Slow 85C, Slow 0C, Fast 0C)
- [ ] [Laks] Jalankan `LAPORAN_TAHAP.bat`; Claude memarsir ke CSV: delay data, delay sel vs interkoneksi, jumlah tingkat logika
- [ ] Uji awal H1 dengan versi datar
- [ ] Arsipkan ke `8_Varian_Pengali/hasil_mentah/2026-11-xx_analisis_mac_timing/`

### Tugas 5: Pecah komponen menjadi submodul [Claude]
**Berkas (cabang `studentA/analisis-mac`):** `2_Verilog/mac_unit.v`, `2_Verilog/epilog_unit.v`
- [ ] Di `mac_unit.v`, submodul internal: `mac_reg_t1` (M2), `mac_mux_init` (M3), `mac_add32` (M4, termasuk `prod_ext`), `mac_reg_acc` (M5), `mac_handshake` (M6). Port, latensi, `PIPE_MULT`, dan `HAS_EPILOG` tidak berubah
- [ ] Di `epilog_unit.v`, submodul: `epi_round` (E1), `epi_shift` (E2), `epi_relu` (E3), `epi_sat` (E4), `epi_reg_out` (E5)
- [ ] Jalankan G1, G2, G3. Gagal salah satu = kembali ke versi sebelumnya, catat di `log.md`

### Tugas 6: Kompilasi versi terpecah ×3 [Claude siapkan, Laks jalankan]
**Berkas:** `scripts/kompilasi_terpecah.py` (turunan `jalankan_varian.py`, sumber RTL dari cabang), `hasil/T6_datar_vs_terpecah.csv`
- [ ] [Laks] Kompilasi HARD, ARITH, STRUCT versi terpecah
- [ ] Bandingkan dengan versi datar: LE total, Fmax
- [ ] Aturan pra-registrasi: bila LE atau Fmax berselisih lebih dari 2 %, angka utama tetap dari versi datar; versi terpecah hanya untuk proporsi antarkomponen. Catat di `log.md`
- [ ] Arsipkan ke `8_Varian_Pengali/hasil_mentah/2026-11-xx_analisis_mac_terpecah_<varian>/`

### Tugas 7: Rincian luas per komponen dan mode LE [Claude + Laks]
**Berkas:** `hasil/T7_komponen_luas.csv`, `hasil/gambar/`
- [ ] Parsir *Resource Utilization by Entity* versi terpecah untuk M1–M6 dan E1–E5
- [ ] Jumlah LE mode normal vs aritmetik di dalam `u_mul` (uji H3). Bila laporan tidak memecah mode per entitas, [Laks] ambil dari Chip Planner atau Resource Property Editor dan catat caranya
- [ ] [Laks] Tangkapan layar Technology Map Viewer: `u_mul` HARD (blok pengali embedded), `u_mul` ARITH dan STRUCT (LE), satu lajur utuh
- [ ] Uji H2 (versi terpecah) dan H3

### Tugas 8: Daya per hierarki [Claude siapkan, Laks jalankan]
**Berkas:** `hasil/T8_daya_hierarki.csv`
- [ ] Alur `TAHAP_DAYA` pada versi terpecah ketiga varian (VCD jendela inferensi, metode tim)
- [ ] Parsir *Thermal Power Dissipation by Hierarchy* dari `.pow.rpt`: daya dinamis M1–M6 per lajur dan E1–E5
- [ ] Catat confidence dan persentase sinyal dari simulasi
- [ ] Uji H5 (bagian daya)

### Tugas 9: Rincian siklus [Claude]
**Berkas:** `9_Analisis_MAC/tb/tb_hitung_siklus.v`, `hasil/T9_siklus.csv`
- [ ] Testbench baru yang meng-instansiasi `top_papan` tanpa mengubahnya dan hanya membaca sinyal internal: siklus aktif MAC per lapisan, siklus `epilog_unit`, siklus argmax, siklus lain
- [ ] Lulus bila jumlahnya 1.708 siklus per citra dan hasil tetap cocok dengan acuan

### Tugas 10: Komponen sendirian [Claude siapkan, Laks jalankan]
**Berkas:** `9_Analisis_MAC/wrap/wrap_komponen.v`, `hasil/T10_sendirian.csv`
- [ ] Pembungkus register (pola `mult_timing_wrap.v`) untuk: pembungkus kosong (dasar), M3, M4, E1, E2, E3, E4. Pengali M1 memakai angka lama (134 / 155 / 0+1 LE; 65,3 / 60,5 / 267,3 MHz) bila laporannya ada di arsip; bila tidak, ukur ulang
- [ ] [Laks] Kompilasi tiap pembungkus dengan `mac_unit.sdc` 20 ns
- [ ] Kurangkan ongkos pembungkus kosong; laporkan LE, delay, Fmax

### Tugas 11: Sapuan seed [Claude siapkan, Laks jalankan]
**Berkas:** `scripts/sapu_seed.py`, `hasil/T11_seed.csv`
- [ ] Versi datar (`main`), seed 1–5 × HARD, ARITH, STRUCT = 15 kompilasi (`set_global_assignment -name SEED <n>`)
- [ ] Catat Fmax, slack, LE tiap kompilasi
- [ ] Rata-rata dan simpangan baku; uji H4

### Tugas 12: Metrik gabungan [Claude]
**Berkas:** `scripts/hitung_metrik.py`, `hasil/T12_metrik.csv`
- [ ] Energi per operasi MAC = daya 8 lajur × 34,16 µs ÷ 13.184 operasi MAC per citra (196×64 + 64×10)
- [ ] Area × delay (LE × periode Fmax) dan energi × delay per varian
- [ ] Label "perkiraan" untuk semua angka dari Power Analyzer

### Tugas 13 (opsional): Daya bergantung data [Claude]
**Berkas:** `9_Analisis_MAC/tb/stimulus/`, `hasil/T13_daya_data.csv`
- [ ] Hanya bila Tugas 0–12 selesai. Stimulus sendiri (acak, nol) di folder sendiri, tanpa menyentuh `mem/` atau `uji/`; jalankan alur daya; bandingkan dengan citra MNIST

### Tugas 14: Rekap hipotesis [Claude]
**Berkas:** `hasil/ringkasan_hipotesis.md`
- [ ] H1–H5: angka yang dipakai, nama berkas laporan, keputusan (bertahan / ditolak / tidak tuntas)
- [ ] Tabel besar per komponen: LE, delay, daya untuk HARD, ARITH, STRUCT

### Tugas 15: Draf naskah [Claude, ditinjau Laks]
**Berkas:** draf skripsi `.docx` berikutnya (hasil dan pembahasan)
- [ ] Subbab hasil "Rincian per komponen unit MAC dan epilog": 2.000–3.000 kata
- [ ] Subbab pembahasan "Penyebab selisih HARD, ARITH, STRUCT": 1.500–2.500 kata, termasuk penjelasan blok pengali embedded menurut handbook
- [ ] Batasan masalah tentang skalabilitas (sudah disepakati)

## Verifikasi

Selesai bila:
- [ ] G1, G2, G3 lulus untuk versi terpecah
- [ ] Semua CSV di `hasil/` terisi dan setiap angka menyebut berkas laporan sumbernya
- [ ] Laporan mentah terarsip di `8_Varian_Pengali/hasil_mentah/2026-11-xx_analisis_mac_*/`
- [ ] H1–H5 masing-masing dinyatakan bertahan, ditolak, atau tidak tuntas di `ringkasan_hipotesis.md`
- [ ] Jumlah siklus rincian = 1.708
- [ ] Draf subbab hasil dan pembahasan masuk ke draf skripsi

## Catatan penyimpangan
Setiap perubahan cakupan, metode, atau data setelah pra-registrasi ditulis di `9_Analisis_MAC/log.md` dengan tanggal dan alasan. Proyek ini tidak memakai wiki pengetahuan; `log.md` menggantikan `knowledge/_meta/log.md`.
