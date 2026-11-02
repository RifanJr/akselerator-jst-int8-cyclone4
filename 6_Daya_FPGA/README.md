# 6_Daya_FPGA — Analisis daya akselerator di FPGA

Perkiraan daya dan energi per citra rancangan **OS** (`2_Verilog/top_papan.v`,
P = 8, pengali HARD, 1.708 siklus per citra) dengan **Power Analyzer** Quartus,
memakai aktivitas sinyal dari simulasi netlist **selama inferensi saja**.

---

## Cara menjalankan

Dari folder `Alur_Utama`:

```
python 6_Daya_FPGA/jalankan_daya_os.py
```

atau klik dua kali `JALANKAN_DAYA_OS.bat`. Selesai dalam sekitar 1 menit dan
tidak memerlukan papan.

Syarat: Quartus Prime Lite 25.1std di `C:\altera_lite\25.1std`, Icarus Verilog
di PATH atau di `C:\iverilog\bin`.

## Isi folder

| Berkas | Isi |
|---|---|
| `daya_os.qpf`, `daya_os.qsf` | Proyek Quartus. Rancangan dan pin **sama** dengan `3_Quartus/papan.qsf`, ditambah pengaturan Power Analyzer. Dipisah supaya `3_Quartus/output_papan` tidak berubah. |
| `tb_jendela_os.v` | Simulasi RTL: mencari siklus mulai dan selesai inferensi citra 00 |
| `tb_netlist_os.v` | Simulasi netlist pascasintesis, merekam VCD sejak inferensi mulai |
| `ambil_atom.py` | Mengambil modul atom Cyclone IV E yang dipakai netlist |
| `siapkan_vcd.py` | Merapikan VCD untuk Quartus dan memotongnya tepat pada jendela inferensi |
| `aktivitas_mac.py` | Menghitung aktivitas register akumulator MAC dari VCD yang sama (lihat Metode) |
| `jalankan_daya_os.py` | Menjalankan semua langkah dan meringkas hasil |
| `hasil/` | `daya_os.json` (ringkasan), `daya_os.pow.summary`, `daya_os.fit.summary`, `daya_os.pow_ringkas.rpt` (laporan daya tanpa tabel per sinyal) |

## Metode

1. **Kompilasi** Quartus, sekaligus menulis netlist tingkat gerbang (`.vo`).
2. **Jendela inferensi** dari simulasi RTL: siklus 216 sampai 1.924, tepat
   **1.708 siklus**, sama dengan penghitung siklus di papan.
3. **Simulasi netlist** dengan Icarus. Netlist dianggap benar bila LED "cocok"
   menyala pada siklus yang sama dengan RTL (siklus 1.926).
4. **VCD** hanya berisi jendela inferensi (34,16 µs). Reset dan muat citra
   tidak ikut terekam.
5. **Aktivitas register akumulator MAC.** Power Analyzer tidak dapat
   mencocokkan nama bit register di dalam blok `generate`
   (`g_lajur[k].u_mac|acc`, `m_acc`, `p_q`, `init1`; 718 register), walaupun
   formatnya sama dengan skrip VCD buatan Quartus sendiri. Register serupa di
   luar `g_lajur` terbaca normal. `aktivitas_mac.py` menghitung laju toggle dan
   probabilitas statis register itu dari **VCD yang sama**, lalu memberikannya
   sebagai assignment. Tanpa langkah ini confidence-nya *Medium*, dan daya
   dinamis hanya berbeda 0,02 mW (21,07 vs 21,09 mW).
6. **Power Analyzer**, dengan pendinginan dan laju toggle masukan sama seperti
   analisis Student A (1 November 2026).

Energi per citra = daya × 34,16 µs.

Langkah 1, 3, dan 4 diadaptasi dari `3_Quartus/simulasi_netlist/` milik
Student A. Bagian yang baru adalah jendela inferensi, aktivitas register MAC,
dan pengendali otomatis.

## Hasil (2 November 2026)

| | Daya | Energi per citra |
|---|---|---|
| **Total chip** | **93,91 mW** | **3,208 µJ** |
| Inti dinamis | 21,09 mW | 0,720 µJ |
| Inti statis | 43,16 mW | 1,474 µJ |
| I/O | 29,66 mW | 1,013 µJ |

- Confidence: **High** ("user provided sufficient toggle rate data").
- Sumber aktivitas: 83,4 % sinyal dari simulasi, 16,5 % dari assignment
  (register MAC), 0,1 % vectorless (4 sinyal: 2 pin konfigurasi dan 2 sinyal
  kombinasional).
- Sumber daya: 2.306 LE, pengali 8/30, sama dengan `3_Quartus`.

Sebagai pembanding, hasil Student A (rancangan OS lama 1.816 siklus, VCD
memuat reset dan muat citra) adalah 91,99 mW total, 19,17 mW dinamis, dengan
confidence *Low*.

## Perbandingan dengan PC

Angka PC berasal dari `5_PC/` (AMD Ryzen 5 7535HS, model INT8 NumPy, satu inti,
2 November 2026).

| | FPGA (OS, 50 MHz) | PC (INT8, satu inti) | |
|---|---|---|---|
| Latensi per citra | 34,16 µs, selalu sama | median 15,6 µs, p99 22,5 µs | PC ≈2× lebih cepat |
| Throughput | 29.274 citra/s | 62.058 citra/s | PC ≈2× lebih cepat |
| Daya saat bekerja | 93,91 mW (chip) | 24,79 W (paket CPU) | FPGA ≈264× lebih kecil |
| **Energi per citra, total chip** | **3,208 µJ** | **399,5 µJ** (paket CPU) | **FPGA ≈125× lebih hemat** |
| Energi per citra, bagian yang bekerja | 0,720 µJ (inti dinamis) | 171,5 µJ (tambahan di inti) | FPGA ≈238× lebih hemat |

**Kesimpulan:** FPGA jauh lebih hemat energi, tetapi pada 50 MHz dengan 8 MAC
ia sekitar dua kali lebih lambat dari satu inti CPU laptop. Keunggulan lain
FPGA adalah latensinya tetap, sedangkan di PC latensinya bervariasi.

## Keterbatasan

- Daya FPGA adalah **perkiraan model Power Analyzer**, dan daya PC adalah
  **telemetri CPU**. Keduanya bukan pengukuran fisik. Pengukuran fisik dengan
  sensor arus masih berupa rencana.
- Simulasi netlist hanya menjalankan **citra 00**. Tombol papan memerlukan
  debounce 500.000 siklus, terlalu lambat untuk simulasi tingkat gerbang.
  Kebenaran 16 citra dibuktikan di simulasi RTL dan uji papan.
- Daya I/O mencakup LED dan seven-segment papan, yang tetap menyala walau
  akselerator diam.
- "Inti dinamis" FPGA dan "tambahan di inti" PC tidak persis sama: daya
  dinamis FPGA juga mencakup clock dan penampil yang tetap aktif saat diam.
