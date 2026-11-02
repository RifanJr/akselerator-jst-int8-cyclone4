# 4_daya — Analisis daya rancangan WS

Perkiraan daya dan energi per citra rancangan **WS** (`top_papan_ws.v`, larik
4 × 2, batch 16) dengan **Power Analyzer** Quartus. Metode dan pengaturannya
**sama** dengan analisis rancangan OS di `6_Daya_FPGA/`, supaya kedua rancangan
dibandingkan dengan syarat yang sama.

Perbandingan lengkap OS vs WS ada di [`../PERBANDINGAN_OS_WS.md`](../PERBANDINGAN_OS_WS.md).

## Cara menjalankan

Dari folder `Alur_Utama`:

```
python 4_WS/4_daya/jalankan_daya_ws.py
```

atau klik dua kali `JALANKAN_DAYA_WS.bat`. Waktu yang dibutuhkan sekitar
8 menit, sebagian besar untuk simulasi netlist 26.383 siklus. Tidak
memerlukan papan.

## Isi folder

| Berkas | Isi |
|---|---|
| `daya_ws.qpf`, `daya_ws.qsf` | Proyek Quartus. Rancangan dan pin **sama** dengan `3_quartus/papan_ws.qsf`, ditambah pengaturan Power Analyzer (sama dengan OS). |
| `tb_jendela_ws.v` | Simulasi RTL: mencari siklus mulai dan selesai inferensi batch |
| `tb_netlist_ws.v` | Simulasi netlist pascasintesis, merekam VCD sejak inferensi mulai |
| `ambil_atom.py`, `siapkan_vcd.py` | Sama dengan versi OS (`6_Daya_FPGA/`) |
| `aktivitas_register.py` | Aktivitas register di dalam blok `generate`, dihitung dari VCD yang sama |
| `jalankan_daya_ws.py` | Menjalankan semua langkah dan meringkas hasil |
| `hasil/` | `daya_ws.json`, `daya_ws.pow.summary`, `daya_ws.fit.summary`, `daya_ws.pow_ringkas.rpt` |

## Metode

Metodenya sama dengan OS (lihat `6_Daya_FPGA/README.md`), dengan dua perbedaan:

- **Jendela VCD** berisi satu batch penuh: siklus 19 sampai 26.402, tepat
  **26.383 siklus** (527,66 µs). Energi per citra = daya × 527,66 µs ÷ 16.
- **Register yang tidak terpetakan** lebih banyak, yaitu 960 register MAC
  di larik dan register keluaran bank bobot (`g_bank[k].u_mem_w|q`).
  `aktivitas_register.py` menangani semua bit register di dalam blok
  `generate`, sehingga confidence-nya **High**. Tanpa langkah ini
  confidence-nya *Medium*, dan daya dinamis hanya berbeda 0,02 mW.

Netlist dicek: LED "cocok" menyala pada siklus yang sama dengan RTL
(siklus 26.404).

## Hasil (2 November 2026)

| | Daya | Energi per citra |
|---|---|---|
| **Total chip** | **108,63 mW** | **3,582 µJ** |
| Inti dinamis | 35,57 mW | 1,173 µJ |
| Inti statis | 43,32 mW | 1,429 µJ |
| I/O | 29,73 mW | 0,980 µJ |

- Confidence: **High**. Sumber aktivitas: 85,7 % sinyal dari simulasi, 14,2 %
  dari assignment, dan 0,1 % vectorless (4 sinyal).
- Sumber daya: 3.573 LE, pengali 8/30, sama dengan `3_quartus`.

## Keterbatasan

- Daya adalah **perkiraan model Power Analyzer**, bukan pengukuran fisik.
- Daya I/O mencakup LED dan seven-segment papan.
