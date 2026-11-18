# Ringkasan hipotesis — analisis mendalam unit MAC (Tugas 14)

Rencana pra-registrasi: `input/ideas/analisis-mendalam-mac-plan.md` (disetujui 4 Nov 2026). Rincian langkah: `DOKUMENTASI_PROSES.md`; penyimpangan: `log.md`. Daya dan energi adalah perkiraan Power Analyzer.

## Keputusan

| | Hipotesis | Kriteria tolak | Angka | Keputusan | Sumber |
|---|---|---|---|---|---|
| H1 | Seluruh selisih Fmax berasal dari tahap 1 | (a) jalur terburuk ARITH/STRUCT tidak lewat `u_mul`; (b) delay tahap 2 berbeda > 0,50 ns dari HARD | (a) terpenuhi: jalur terburuk lewat `u_mul` (14,34 / 17,21 ns di pengali). (b) tahap 2: HARD 7,869; ARITH 8,568 (+0,699); STRUCT 8,701 (+0,832) ns | **Ditolak** (kriteria b). Selisih tahap 2 tidak memengaruhi Fmax (slack > 11 ns); eksploratif: penempatan dan bit awal jalur | `hasil/T4_tahap.csv`, `hasil/T4/<v>/*.rpt` |
| H2 | Seluruh selisih LE per lajur berasal dari pengali | LE non-pengali per lajur berbeda > 5 % dari HARD | Fitter: HARD 151,25; ARITH 153,38 (+1,4 %); STRUCT 138,50 (−8,4 %) | **Ditolak** (STRUCT). Eksploratif: tingkat sintesis non-pengali HARD = STRUCT = 106,75; selisih dari pengemasan register `p_q` ke LE pengali | `hasil/T7_komponen_luas.csv`, `pecah_<v>.fit.rpt`, `.map.rpt` |
| H3 | Selisih STRUCT vs ARITH dari pemetaan carry chain | proporsi LE aritmetik di `u_mul` ARITH tidak ≥ 10 poin lebih besar | ARITH 63/126 = 50,0 %; STRUCT 0/151,25 = 0 % (selisih chip vs HARD); Technology Map Viewer: ARITH 56 sambungan `cout→cin`, STRUCT 0 `cin` | **Bertahan** | `hasil/T7_mode_LE.csv`, `hasil/gambar/T7_techmap_*_umul.pdf` |
| H4 | Selisih Fmax ARITH vs STRUCT tidak bermakna | selisih rata-rata > 2 × SD gabungan (5 seed) | 0,828 MHz < 0,921 MHz | **Bertahan** (margin 0,093 MHz) | `hasil/T11_uji_H4.txt`, `hasil/T11_seed.csv` |
| H5 | Epilog < 5 % LE dan daya dinamis; ReLU mendekati nol | epilog > 5 % LE sistem atau > 5 % daya dinamis inti, atau ReLU > 1 % | Epilog 14 LE = 0,41–0,61 % LE; 0,01–0,02 mW = 0,04–0,08 % daya inti dinamis; ReLU 0 LE, 0 mW | **Bertahan**. Batasan: konfigurasi epilog di sistem konstan; dengan konfigurasi variabel ReLU 32 LE (Tugas 10) | `hasil/T7_komponen_luas.csv`, `hasil/T8_daya_komponen.csv`, `hasil/T10_komponen_bersih.csv` |

Aturan Tugas 6 terpicu (Fmax HARD versi terpecah −5,43 %): angka utama (LE total, Fmax, daya total) dari versi datar; versi terpecah hanya untuk proporsi komponen.

## Tabel besar per komponen

Luas: per lajur MAC, rata-rata 8 lajur, versi terpecah. Sintesis = fungsi kombinasional / register (aditif). Daya: dinamis, jumlah 8 lajur, versi terpecah. Delay sendirian: pembungkus register (Tugas 10).

| Komponen | Sintesis HARD | Sintesis ARITH | Sintesis STRUCT | Daya HARD (mW) | Daya ARITH | Daya STRUCT | Sendirian: LE / delay |
|---|---|---|---|---|---|---|---|
| M1 Pengali | 0 / 0 (+1 pengali embedded) | 126 / 0 | 151,25 / 0 | 1,67* | 3,12* | 4,37* | ARITH 134 / ≈14,0 ns; STRUCT 155 / ≈15,2 ns; HARD 0+1 / ≈2,5 ns |
| M2 Register tahap 1 | 10,12 / 26,12 | 25,12 / 26,12 | 10,12 / 26,12 | 1,25 | 1,78 | 1,58 | — |
| M3 MUX `acc_base` | 32 / 0 | 32 / 0 | 32 / 0 | 0,17 | 0,19 | 0,22 | 32 / 1,21 ns |
| M4 Penjumlah 32 bit | 64 / 0 | 64 / 0 | 64 / 0 | 0,54 | 0,54 | 0,58 | 32 / 3,64 ns |
| M5 Register akumulator | 0,38 / 64,12 | 0,38 / 64,12 | 0,38 / 64,12 | 1,98 | 1,74 | 1,80 | — |
| M6 Handshake | 0,25 / 0 | 0,25 / 0 | 0,25 / 0 | 0,00 | 0,00 | 0,00 | — |
| **`mac_unit` (per lajur)** | **106,75 / 90,25** | **247,75 / 90,25** | **258,00 / 90,25** | 4,22 (8 lajur) | 5,48 | 6,74 | — |
| E1 Pembulatan | 0 | 0 | 0 | 0 | 0 | 0 | 38 / 6,94 ns |
| E2 Penggeser | 0 | 0 | 0 | 0 | 0 | 0 | 115 / 7,39 ns |
| E3 ReLU | 0 | 0 | 0 | 0 | 0 | 0 | 32 / 1,31 ns |
| E4 Saturasi | 5 / 0 | 5 / 0 | 5 / 0 | 0,00 | 0,00 | 0,00 | 24 / 4,96 ns |
| E5 Register keluaran | 9 / 8 | 9 / 8 | 9 / 8 | 0,01 | 0,01 | 0,02 | — |

\* banding setara: `u_mul` + daya `mem_w` sendiri (pada HARD daya blok pengali embedded dibukukan di `mem_w`).

Delay tahap (sistem, Slow 85C, versi datar): tahap 1 HARD 8,536 / ARITH 17,014 / STRUCT 17,571 ns, dengan waktu di pengali 5,47 / 14,34 / 17,21 ns; tahap 2 7,869 / 8,568 / 8,701 ns. Fmax rata-rata 5 seed: 79,24 / 57,16 / 56,33 MHz.

Metrik gabungan (versi datar): energi per operasi MAC 15,03 / 20,03 / 21,66 pJ; area × delay 29.100 / 58.279 / 60.592 LE·ns; energi per citra 3,208 / 3,303 / 3,330 µJ. Siklus: 1.708 = 2 isi pipa + 1.696 beat MAC + 10 ekor.
