# Laporan Student A: Perbandingan Pengali dan Analisis Daya (1 November 2026)

Penulis: Laks (Student A, Compute Engine). Versi daring yang dapat dikomentari: https://claude.ai/artifact/GeLEpfeMZoEpxpCicyHzSX

## Ringkasan

Pada 1 November 2026 Student A mereproduksi seluruh angka repo `akselerator-jst-int8-cyclone4` (rancangan papan `top_papan`, P = 8) dan menambahkan perbandingan tiga varian pengali beserta analisis daya. Ketiga varian identik bit demi bit dan sama cepatnya; HARD paling hemat luas dan daya.

| | HARD | ARITH | STRUCT |
| --- | --- | --- | --- |
| Logic element | 2.129 (34 %) | 3.171 (51 %) | 3.237 (52 %) |
| Pengali embedded 9 bit | 8/30 | 0/30 | 0/30 |
| M9K | 21/30 | 21/30 | 21/30 |
| Fmax (Slow 1200mV 85C) | 70,58 MHz | 57,68 MHz | 57,39 MHz |
| Waktu per citra @ 50 MHz | 36,3 µs | 36,3 µs | 36,3 µs |
| Daya total (perkiraan) | 91,99 mW | 94,96 mW | 95,21 mW |
| Energi per citra (perkiraan) | 3,34 µJ | 3,45 µJ | 3,46 µJ |
| Akurasi (10.000 citra) | 97,45 % | 97,45 % | 97,45 % |

Semua angka luas dan timing berasal dari laporan Quartus Prime Lite 25.1std. Angka daya adalah perkiraan PowerPlay dengan confidence Low (lihat Keterbatasan). Tidak ada berkas RTL yang diubah.

## Hasil rinci

Setiap angka di bawah dapat dilacak ke berkas laporan di `3_Quartus/hasil_mentah/`.

**Akurasi (10.000 citra uji MNIST, model beku `export_final`)**

- Sidik jari SHA-256 seluruh berkas `export_final` cocok dengan `MANIFEST.md`.
- INT8 (model integer dari berkas .coe): 97,45 % (9.745/10.000); citra 0 cocok dengan `golden_output.txt`. Skrip: `simulasi_netlist/akurasi_int8.py`.
- FP32 (berkas `.pt`): 97,45 % (9.745/10.000). Skrip: `simulasi_netlist/akurasi_fp32.py`.

**Simulasi**

- RTL (`jalankan_papan.py`, Icarus 12): LULUS untuk HARD, ARITH, STRUCT; 18 inferensi identik dengan acuan, tepat 1.816 siklus per inferensi. ARITH/STRUCT diuji memakai salinan `tb_papan.v` dengan MULT_STYLE ditimpa, di luar repo.
- Netlist pascasintesis ketiga varian (`.vo` + pustaka atom Cyclone IV E): citra 00 berjalan otomatis setelah reset, LED cocok menyala pada siklus ke-2.035.

**Luas dan timing**

| | HARD | ARITH | STRUCT |
| --- | --- | --- | --- |
| Register | 1.185 | 1.257 | 1.257 |
| LE satu lajur `mac_unit` (g_lajur[0]) | 158 | 288 | 297 |
| Setup slack @ 20 ns | +5,832 ns | +2,664 ns | +2,575 ns |
| Hold slack | +0,430 ns | +0,448 ns | +0,398 ns |
| Folder laporan | `2026-11-01_papan_hard` | `2026-11-01_papan_arith` | `2026-11-01_papan_struct` |

Berkas sumber per varian: `.fit.summary`, `.fit.rpt` (LE, M9K, pengali), `.sta.rpt`, `.sta.summary` (Fmax, slack), `.map.rpt` (bukti nilai MULT_STYLE).

**Daya (perkiraan PowerPlay)**

| | HARD | ARITH | STRUCT |
| --- | --- | --- | --- |
| Core dinamis | 19,17 mW | 22,03 mW | 22,19 mW |
| Core statis | 43,15 mW | 43,25 mW | 43,35 mW |
| I/O | 29,67 mW | 29,67 mW | 29,67 mW |
| 8 lajur `mac_unit` | 3,30 mW | 4,93 mW | 5,20 mW |
| Sinyal dari simulasi / register dari simulasi | 82,0 % / 39,8 % | 85,4 % / 37,8 % | 77,7 % / 37,8 % |
| Folder laporan | `2026-11-01_daya_papan_hard` | `2026-11-01_daya_papan_arith` | `2026-11-01_daya_papan_struct` |

Energi per citra = daya total × 36,32 µs. Untuk core dinamis saja: 0,70 / 0,80 / 0,81 µJ.

**Pembacaan**

- Pengali dari logika menambah sekitar 1.040 LE (ARITH) dan 1.110 LE (STRUCT), sekitar 130–140 LE per lajur.
- STRUCT sekitar 66 LE lebih besar dari ARITH untuk algoritma Baugh-Wooley yang sama: gaya penulisan RTL memengaruhi luas.
- Fmax turun sekitar 18 %, tetapi ketiga varian tetap lolos 50 MHz, jadi waktu per citra sama.
- Selisih daya sekitar 3 mW antara HARD dan dua varian lain sebaiknya ditulis sebagai kecenderungan, bukan selisih pasti.
- Register ARITH/STRUCT 72 lebih banyak; dugaan (belum dicek): register pipa yang pada HARD diserap ke blok pengali.

## Metode dan cara mengulang

Varian dipilih lewat revisi Quartus, bukan dengan mengubah RTL; seluruh langkah dapat diulang dari folder `3_Quartus/simulasi_netlist/` (lihat `README.md` di sana).

1. **Lingkungan.** Quartus Prime Lite 25.1std Build 1129 dengan Cyclone IV E device support, di `C:\altera_lite\25.1std`. Icarus Verilog 12 untuk simulasi. Perangkat EP4CE6E22C8, batasan clock 20 ns (`2_Verilog/papan.sdc`), model timing Slow 1200mV 85C.
2. **Revisi Quartus.** `papan` (HARD, bawaan), `papan_arith`, `papan_struct`. Dua revisi baru adalah salinan `papan.qsf` dengan satu baris tambahan `set_parameter -name MULT_STYLE ARITH` atau `STRUCT`, dan folder keluaran sendiri (`output_arith`, `output_struct`). Nilai parameter dibuktikan di `.map.rpt` masing-masing.
3. **Kompilasi.** `simulasi_netlist/kompilasi_varian.bat` (atau Ctrl+L di Quartus untuk revisi `papan`). Laporan disalin ke `hasil_mentah/2026-11-01_papan_<varian>/`.
4. **Simulasi netlist untuk VCD.** `tb_netlist.v` menyimulasikan netlist `.vo` hasil EDA Netlist Writer selama 2.040 siklus (reset 16 siklus, muat citra 00, satu inferensi). Pustaka atom diambil dari instalasi Quartus dengan `ambil_atom.py`, karena Icarus menolak modul PLL di berkas aslinya.
5. **Olah VCD.** `vcd_quartus.py` (satu skrip untuk ketiga varian): membuang scope testbench, membuang blok `$dumpall` kosong yang membuat Quartus gagal (Error 222007), dan memecah vektor menjadi sinyal 1 bit dengan format nama yang dipakai Quartus, misalnya `\g_lajur[0].u_mac|acc [31]`. Hasil: `papan_hard|arith|struct_netlist.vcd`.
6. **Power Analyzer.** `simulasi_netlist/daya_3_varian.bat` menjalankan `quartus_pow` untuk ketiga revisi. Tiap revisi membaca VCD-nya sendiri (assignment `POWER_INPUT_FILE_NAME` di `.qsf`), glitch filtering aktif, suhu sambungan dihitung otomatis. Laporan disalin ke `hasil_mentah/2026-11-01_daya_papan_<varian>/`.
7. **Akurasi.** Dari folder `1_Python_PC/Training`: `python ../../3_Quartus/simulasi_netlist/akurasi_int8.py .` dan `akurasi_fp32.py`. Kedua skrip hanya membaca `export_final` dan data uji MNIST; model tidak dilatih ulang.

Berkas VCD tidak masuk git (`*.vcd` diabaikan) karena dapat dibuat ulang dengan langkah 4–5.

## Keterbatasan

Angka luas, timing, dan akurasi kuat; angka daya adalah perkiraan dengan confidence Low dan perlu ditulis apa adanya.

- **Confidence daya Low.** Sekitar 80 % sinyal mendapat aktivitas dari simulasi, tetapi register akumulator MAC (`acc`, `m_acc`, `p_q`, `init1`, sekitar 718 register) tidak terpetakan dari VCD dan memakai estimasi vectorless. Daya statis (sekitar 43 mW) dan I/O (29,67 mW) tidak bergantung pada VCD, jadi ketidakpastian hanya ada di bagian dinamis (19–22 mW).
- **Upaya menaikkan confidence sudah dicoba dan gagal.** (1) Nama register per bit `acc[31]` dan akhiran `~q`. (2) Alur resmi Quartus + Questa Starter 2025.2 memakai `papan_dump_all_vcd_nodes.tcl`: Questa menolak hampir semua nama sinyal, hanya 4,0 % sinyal terekam. Hasil ini tidak sah dan sengaja tidak masuk git. (3) Format nama dari skrip Quartus diterapkan ke VCD Icarus: hasil identik dengan semula.
- **Simulasi netlist hanya satu citra.** Tombol papan butuh debounce 500.000 siklus, terlalu lambat untuk simulasi tingkat gerbang. Kebenaran 16 citra dibuktikan di simulasi RTL, bukan di netlist.
- **Jendela VCD memuat reset dan muat citra** (sekitar 220 dari 2.040 siklus), bukan inferensi saja.
- **Angka `top_papan` tidak boleh dicampur dengan angka `sys8_*`** (2.153 / 3.177 / 3.252 LE). Top-level berbeda: `top_papan` memuat ROM citra, penampil seven-segment, dan tombol.
- **Waktu FPGA adalah hitungan siklus simulasi** (1.816 ÷ 50 MHz), belum diukur di papan dengan mode `key[3]`.
- **Akurasi FPGA 97,45 % bersandar pada kesetaraan bit-exact**, bukan pada 10.000 citra yang dijalankan di perangkat keras.

## Perubahan di repo dan branch git

Semua perubahan diajukan lewat branch `studentA/varian-pengali-daya` dan pull request; tidak ada berkas RTL, `mem/`, `uji/`, atau `export_final` yang diubah.

| Berkas | Status | Keterangan |
| --- | --- | --- |
| `3_Quartus/papan.qsf` | diubah | Ditambah 6 assignment Power Analyzer (VCD `simulasi_netlist/papan_hard_netlist.vcd`, path relatif). Spasi ganda di baris pin dirapikan otomatis oleh Quartus. |
| `3_Quartus/papan.qpf` | diubah | Quartus menambahkan revisi `papan_arith` dan `papan_struct` serta menulis ulang komentar kepala. |
| `3_Quartus/papan_arith.qsf`, `papan_struct.qsf` | baru | Revisi varian pengali (`set_parameter -name MULT_STYLE`). |
| `3_Quartus/simulasi_netlist/` | baru | Skrip, testbench netlist, README cara mengulang. |
| `3_Quartus/hasil_mentah/2026-11-01_*` | baru | Laporan Quartus mentah, screenshot, diagram RTL (PDF). |
| `.gitignore` | diubah | Mengabaikan `output_arith/`, `output_struct/`, `output_papan_asli/`, run daya yang tidak sah, log, dan skrip percobaan lama. |
| `3_Quartus/output_papan/papan.sof`, `papan.fit.summary` | jangan di-commit | Hanya cap waktu yang berubah; kembalikan ke versi asli. |

Perhatian:

- `git status` di Windows dapat menandai hampir semua berkas sebagai berubah karena akhir baris (CRLF). Isinya identik; atasi dengan `git config core.autocrlf true`.
- Skrip `.bat` memakai path Quartus `C:\altera_lite\25.1std`. Di laptop lain, sesuaikan baris `set "Q=..."`.
- Path VCD di ketiga `.qsf` baru diubah menjadi relatif. Jalankan `daya_3_varian.bat` sekali sebelum commit untuk memastikan angka daya tetap 91,99 / 94,96 / 95,21 mW.

Perintah (PowerShell, dari `C:\akselerator-jst-int8-cyclone4`):

```powershell
git config core.autocrlf true
git restore 3_Quartus/output_papan/papan.sof 3_Quartus/output_papan/papan.fit.summary
git switch -c studentA/varian-pengali-daya
git add .gitignore 3_Quartus
git status
git commit -m "Student A: perbandingan HARD/ARITH/STRUCT, analisis daya, dokumentasi"
git push -u origin studentA/varian-pengali-daya
```

Periksa keluaran `git status` sebelum commit: tidak boleh ada `output_arith/`, `output_struct/`, berkas `.vcd`, atau folder `TIDAK_SAH`. Bila tidak punya hak tulis ke repo Rifan, fork repo lalu buka pull request dari fork.

## Untuk Student B: pembanding PC

Pembanding PC dijalankan di laptop Student B; angka FPGA yang menjadi lawan bandingnya adalah varian HARD di bawah.

| Besaran | FPGA (HARD) | Yang perlu diukur di PC |
| --- | --- | --- |
| Akurasi | 97,45 % (bit-exact dengan acuan) | 10.000 citra uji, model INT8 dan FP32 |
| Waktu per citra | 36,3 µs (1.816 siklus @ 50 MHz, hitungan simulasi) | latensi satu citra (batch = 1) |
| Daya | 91,99 mW total, perkiraan PowerPlay | daya CPU saat inferensi |
| Energi per citra | 3,34 µJ (perkiraan) | (daya beban − daya idle) × waktu per citra |

Metode yang disarankan agar perbandingannya adil:

1. **Model sama.** Baca `export_final` saja; jangan melatih ulang. `akurasi_int8.py` dan `akurasi_fp32.py` di `3_Quartus/simulasi_netlist/` sudah memuat model dan data uji, dan dapat dipakai sebagai dasar skrip pengukur waktu.
2. **Dua pembanding.** INT8 (aritmetika sama dengan perangkat keras, keluaran harus cocok dengan `golden_uji.txt`) dan FP32 (cara lazim menjalankan model di PC).
3. **Waktu.** Ukur dari vektor 196 masukan sampai argmax, tanpa memuat citra. Pemanasan beberapa ratus inferensi, lalu ukur minimal 10.000 inferensi dengan `time.perf_counter_ns()`. Laporkan median, persentil 95, dan simpangan baku. Ulangi dengan satu thread dan pengaturan bawaan.
4. **Daya.** Paling baik dengan watt meter di colokan dinding (idle dan saat loop inferensi). Pembacaan perangkat lunak (misalnya HWiNFO) hanya pelengkap dan diberi label perkiraan.
5. **Catat lingkungan.** Tipe CPU, jumlah inti, RAM, OS, versi Python/NumPy/PyTorch, charger terpasang, mode daya.

Catatan kejujuran: daya FPGA adalah perkiraan chip saja, sedangkan watt meter mengukur seluruh sistem PC. Keterbatasan ini perlu ditulis di naskah.

## Hal terbuka untuk pertemuan dosen

Empat keputusan berikut memengaruhi cara angka di laporan ini ditulis di naskah.

- [ ] Apakah perkiraan PowerPlay dengan confidence Low cukup, atau perlu pengukuran arus fisik di papan?
- [ ] CPU dan metode pembanding PC mana yang dianggap adil (satu citra atau batch; INT8 atau FP32; watt meter atau pembacaan perangkat lunak)?
- [ ] Apakah bukti kebenaran 16 citra di simulasi RTL dan 1 citra di simulasi netlist sudah cukup?
- [ ] Pembanding pengali diganti dari DSP48E1 ke pengali embedded 9 bit (keputusan 8.1), dan judul serta rumusan masalah perlu diselaraskan karena varian final adalah HARD.

Pekerjaan teknis yang tersisa: uji papan fisik dengan mode `key[3]` (konfirmasi 1.816 siklus) dan pembanding PC oleh Student B.
