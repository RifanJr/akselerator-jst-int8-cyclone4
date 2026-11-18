---
title: "Komponen mana di dalam unit MAC yang menentukan selisih luas, Fmax, dan daya antara pengali HARD, ARITH, dan STRUCT?"
type: design
created: 2026-11-04
updated: 2026-11-04
tags: [fpga, cyclone-iv, mac-unit, baugh-wooley, pengali-embedded, analisis-komponen]
status: approved
author: mixed
---

# Analisis mendalam unit MAC: perbandingan HARD, ARITH, STRUCT dan rincian per komponen

## Latar (masukan dosen, 4 Nov 2026)
1. Perbandingan HARD, ARITH, dan STRUCT harus lebih dalam: bagian mana persisnya yang membuat ARITH dan STRUCT lebih lambat, bagaimana membuktikannya, dan apa sebenarnya pengali HARD itu.
2. Berat tiap proses harus bisa diketahui terpisah, misalnya waktu dan ongkos MAC dibanding ReLU.
Keputusan bersama: tidak hanya ReLU yang diukur, tetapi setiap komponen di dalam unit MAC dan epilog, sehingga hasilnya menjadi satu tabel perbandingan besar.

## Pertanyaan penelitian
Pada akselerator MLP 196–64–10 di Cyclone IV EP4CE6E22C8 (rancangan OS terbaru, 8 lajur, 50 MHz), komponen mana di dalam unit MAC dan epilog yang menyumbang selisih logic element, delay jalur, dan daya antara varian pengali HARD, ARITH, dan STRUCT, dan seberapa besar sumbangan masing-masing?

Hipotesis yang dapat dibantah:
- **H1 (lokasi selisih Fmax).** Seluruh selisih Fmax berasal dari tahap 1 (memori data → pengali → `p_q`). Delay tahap 2 (`p_q` → MUX → penjumlah 32 bit → `acc`) berselisih kurang dari 0,5 ns antarvarian. Dibantah bila delay tahap 2 berbeda lebih dari 0,5 ns atau jalur terburuk ARITH/STRUCT tidak melewati pengali.
- **H2 (lokasi selisih luas).** Selisih LE per lajur (sekitar 125–140 LE) sepenuhnya berasal dari pengali. LE komponen selain pengali (register tahap 1, MUX, penjumlah, register akumulator, handshake) berselisih kurang dari 5 % antarvarian.
- **H3 (penyebab STRUCT ≠ ARITH).** Selisih STRUCT terhadap ARITH berasal dari cara Quartus memetakan penjumlahnya. Diuji dengan jumlah LE mode aritmetik (carry chain) di dalam pengali. Catatan: dokumen konteks menyebut Quartus "tetap memetakan full adder eksplisit ke carry chain", sedangkan komentar `mult_bw8_struct.v` menduga sebaliknya. Pengukuran ini yang memutuskan.
- **H4 (kebermaknaan).** Selisih Fmax ARITH vs STRUCT (0,11 MHz pada 3 Nov) lebih kecil daripada variasi antar-seed fitter, jadi tidak bermakna. Dibantah bila selisih rata-rata lebih besar dari dua kali simpangan baku antar-seed.
- **H5 (berat epilog).** Epilog (pembulatan, geser, ReLU, saturasi) memakan kurang dari 5 % LE dan daya dinamis sistem, dan ReLU sendiri mendekati nol. Dibantah bila salah satu melewati 5 %.

## Posisi terhadap literatur (singkat)
Pengali bertanda berbasis logika pada FPGA umumnya dibandingkan dengan blok DSP atau pengali embedded dari sisi luas dan kecepatan, sedangkan penguraian ongkos per komponen di dalam MAC jarang dilaporkan untuk FPGA kelas pemula. Rujukan inti yang perlu dicari dan diverifikasi: makalah asli Baugh & Wooley (1973) tentang perkalian komplemen dua, buku aritmetika komputer (misalnya Parhami) untuk Booth dan Wallace/Dadda sebagai pembanding teoretis, dan Cyclone IV Device Handbook bab *Embedded Multipliers* untuk struktur blok HARD. Pencarian literatur lengkap dikerjakan terpisah.

## Komponen yang diukur
Sumber: `2_Verilog/mac_unit.v` (HAS_EPILOG = 0, PIPE_MULT = 0 di dalam sistem) dan `2_Verilog/epilog_unit.v` (dipakai bersama 8 lajur).

| Kode | Komponen | Letak |
|---|---|---|
| M1 | Pengali 8×8 (HARD / ARITH / STRUCT) | `mac_unit`, tahap 1 |
| M2 | Register tahap 1: `p_q`, `init1`, `f1`, `l1`, `v1` | `mac_unit` |
| M3 | MUX `acc_base` (bias atau akumulator) | `mac_unit`, tahap 2 |
| M4 | Penjumlah 32 bit `acc_next` (termasuk perluasan tanda `prod_ext`) | `mac_unit`, tahap 2 |
| M5 | Register `acc`, `m_acc`, `m_valid` | `mac_unit` |
| M6 | Handshake (`stall`, `s_ready`, `beat`) | `mac_unit` |
| E1 | Pembulatan (`rnd_add` dan penjumlahnya) | `epilog_unit` |
| E2 | Penggeser aritmetik 32 bit, 5 tingkat | `epilog_unit` |
| E3 | ReLU | `epilog_unit` |
| E4 | Saturasi 8 bit (dua pembanding dan pemilih) | `epilog_unit` |
| E5 | Register keluaran epilog | `epilog_unit` |

Argmax, pengendali, dan memori milik Student B. Angkanya boleh ditampilkan dalam tabel sistem sebagai konteks, tetapi tidak diklaim sebagai rancangan Student A.

## Metode
Tiga tingkat pengukuran, karena Quartus menggabungkan logika lintas batas modul sehingga satu sudut pandang saja bisa menyesatkan.

**Tingkat 1: komponen sendirian.** Tiap komponen dibungkus register (metode `mac_lane_wrap.v`) dan dikompilasi terpisah. Hasil: LE, register, delay, Fmax, dan daya dengan vektor uji yang sama. Ongkos pembungkus diukur sekali (pembungkus kosong) lalu dikurangkan.

**Tingkat 2: satu lajur MAC.** Metode pin maya yang sudah dipakai. Hasil: LE per komponen di dalam satu lajur.

**Tingkat 3: sistem utuh** (`top_papan`, alur `8_Varian_Pengali/jalankan_varian.py`).
- Isi `mac_unit.v` dan `epilog_unit.v` dipecah menjadi submodul sesuai tabel komponen, tanpa mengubah port, protokol, latensi, atau `PIPE_MULT`. Versi datar sekarang dipertahankan sebagai acuan, dan selisih LE serta Fmax antara versi datar dan versi terpecah dilaporkan.
- Luas: Fitter → *Resource Utilization by Entity*, termasuk jumlah LE per mode (normal dan aritmetik).
- Delay: `report_timing` per tahap, misalnya `-from *mem_d*rd_q* -to *p_q*` (tahap 1) dan `-from *p_q* -to *acc*` (tahap 2), dengan rincian delay sel vs delay interkoneksi dan jumlah tingkat logika. Diambil untuk ketiga varian, termasuk jalur tahap 1 pada HARD yang tidak kritis.
- Daya: Power Analyzer → *Thermal Power Dissipation by Hierarchy*, dengan VCD jendela inferensi seperti metode tim.
- Bukti visual: Technology Map Viewer (pengali HARD terpeta ke satu blok pengali embedded; ARITH/STRUCT ke LE) dan Chip Planner.
- Waktu dalam siklus: penghitung di testbench untuk tahap MAC, epilog, argmax, dan overhead. Total harus tetap 1.708 siklus.

**Penguat ketelitian.**
- Sapuan seed fitter: 5 seed × 3 varian, dilaporkan rata-rata ± simpangan baku (untuk H4).
- Tiga model timing: Slow 1200mV 85C (acuan), Slow 1200mV 0C, Fast 1200mV 0C.
- Uji tuntas pengali: seluruh 65.536 pasangan masukan di `tb_mult8.v`.
- Metrik gabungan: energi per operasi MAC (pJ/MAC), area × delay, energi × delay.
- Daya bergantung data (opsional): VCD dari citra MNIST, masukan acak, dan masukan nol.

**Tentang "algoritma HARD".** Struktur gerbang di dalam blok pengali embedded tidak dipublikasikan Intel. Yang dilaporkan: struktur blok menurut handbook (18×18 yang dapat dipecah menjadi dua 9×9, register masukan/keluaran opsional, kendali bertanda), bukti pemetaan dari Technology Map Viewer, dan delay terukur saat sendirian (3,74 ns, dari pengukuran pembungkus register yang tercatat di dokumen konteks). Tidak ada klaim tentang Booth atau Wallace di dalam blok tersebut.

## Data dan bahan
- Laporan 3 Nov di `8_Varian_Pengali/hasil_mentah/2026-11-03_os_{hard,arith,struct}/` sebagai titik awal dan pembanding.
- Kompilasi baru: versi terpecah ×3 varian, sapuan seed (15 kompilasi), tiga model timing, kompilasi komponen sendirian.
- Simulasi: Icarus Verilog 11 di VM (RTL dan netlist pascasintesis), skrip `aktivitas_mac.py` milik tim untuk VCD.
- Arsip laporan mentah: `8_Varian_Pengali/hasil_mentah/2026-11-xx_analisis_mac_*/`.

## Luaran
☑ Bab hasil dan pembahasan skripsi (tabel rincian komponen, grafik delay per tahap, grafik daya per hierarki)
☑ Slide progres berikutnya
☐ Artikel (kemungkinan, setelah skripsi)

## Hasil yang diharapkan
- **Positif:** H1, H2, H5 bertahan. Narasinya menjadi "ongkos Baugh-Wooley terkonsentrasi di pengali: +X LE dan +Y ns di tahap 1; komponen lain identik; epilog dan ReLU hampir gratis karena dipakai bersama."
- **Temuan lain yang tetap bernilai:** bila H1 gugur (misalnya penempatan ARITH ikut memperlambat tahap 2 karena kepadatan routing), itu temuan tentang efek tidak langsung pengali logika. Bila H4 bertahan, kesimpulan "STRUCT lebih lambat" harus diganti menjadi "ARITH dan STRUCT setara dalam Fmax; berbeda pada LE".

## Risiko metodologis
- Memecah modul dapat mengubah optimasi Quartus. Mitigasi: bandingkan versi datar dan terpecah; angka utama tetap dari versi datar bila selisihnya bermakna.
- Komponen yang dilebur Quartus (misalnya MUX ke dalam LE penjumlah) bisa tercatat mendekati nol. Ini dilaporkan sebagai temuan, bukan galat.
- Daya komponen kecil bisa di bawah resolusi Power Analyzer. Laporkan sebagai "perkiraan", sertakan confidence, dan bandingkan secara relatif.
- Semua angka daya adalah perkiraan, bukan ukuran fisik di papan (menunggu keputusan dosen).
- Setiap perubahan pada berkas Student A wajib lolos dua gerbang: `tb_mac_unit.v` lulus dan sapuan 48/48 identik.

## Kelayakan
- Semua perubahan di berkas milik Student A (`mac_unit.v`, `epilog_unit.v`, `mult_*.v`, `mac_lane_wrap.v`, `tb_*`). Berkas Student B tidak disentuh; `top_papan.v` tetap.
- Perangkat: Quartus Prime Lite 25.1std di laptop, Icarus 11 di VM, skrip yang ada di `8_Varian_Pengali/`.
- Perkiraan waktu: sekitar 1,5–2 minggu kerja, terutama untuk kompilasi dan simulasi daya (perkiraan, bukan hasil ukur).

## Batas cakupan (tidak diteliti di sini)
- Algoritma pengali baru (Booth radix-4, Wallace/Dadda): hanya pembanding teoretis, implementasinya opsional bila waktu tersisa.
- Perubahan kontrak `mac_unit` atau `PIPE_MULT` di dalam sistem. `PIPE_MULT = 1` hanya boleh diuji pada pengukuran sendirian.
- Jumlah lajur (8 vs 4/16): desain terpisah.
- Skalabilitas (lapisan tambahan): saran pengembangan dan batasan masalah.
- Pengukuran daya fisik di papan.

## Langkah berikutnya
Setelah disetujui, susun rencana kerja di `input/ideas/analisis-mendalam-mac-plan.md` (writing-research-plan).
