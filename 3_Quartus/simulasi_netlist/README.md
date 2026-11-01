# Simulasi netlist, VCD, dan skrip akurasi — 1 November 2026

Dibuat untuk analisis daya PowerPlay rancangan `top_papan` (varian HARD).
Ringkasan angka ada di Project Skripsi: "Hasil Reproduksi dan Daya 2026-11-01".
Laporan mentah dan screenshot: `../hasil_mentah/2026-11-01_papan_hard/`.

## Isi folder
| Berkas | Fungsi |
|---|---|
| `akurasi_int8.py` | Akurasi model integer (dari .coe beku) pada 10.000 citra uji. Hasil: 97,45 % |
| `akurasi_fp32.py` | Akurasi model FP32 (dari .pt beku, dibaca tanpa PyTorch). Hasil: 97,45 % |
| `tb_netlist.v` | Testbench simulasi netlist `../simulation/questa/papan.vo` |
| `ambil_atom.py` | Mengambil modul atom Cyclone IV E yang dibutuhkan dari pustaka Quartus |
| `vcd_scalar.py` | Memecah sinyal vektor di VCD menjadi sinyal 1 bit |
| `papan_netlist.vcd` | Aktivitas sinyal untuk PowerPlay (2.040 siklus: reset, muat citra 00, inferensi). VCD resmi. |
| `jalankan_daya_icarus.bat` | Menjalankan Power Analyzer dengan VCD resmi di atas |
| `jalankan_daya_questa.bat`, `.do` | Percobaan alur Questa (DITOLAK, lihat bawah) |
| `papan.qsf.sebelum_questa` | Cadangan papan.qsf sebelum percobaan Questa |

## Cara mengulang
Akurasi (jalankan dari `1_Python_PC/Training`):
    python ../../3_Quartus/simulasi_netlist/akurasi_int8.py .
    python ../../3_Quartus/simulasi_netlist/akurasi_fp32.py .

VCD (Icarus Verilog 12, dari folder ini, setelah kompilasi Quartus menulis papan.vo):
    python ambil_atom.py C:/altera_lite/25.1std/quartus/eda/sim_lib/cycloneive_atoms.v
    iverilog -g2012 -DVCD -DSIKLUS=2040 -o net.out tb_netlist.v ../simulation/questa/papan.vo atoms_min.v C:/altera_lite/25.1std/quartus/eda/sim_lib/altera_primitives.v
    vvp net.out          (harus mencetak "LED cocok menyala pada siklus 2035")
Lalu, sebelum dipakai Quartus:
1. Hapus scope `tb_netlist` sehingga scope teratas bernama `top_papan`.
2. Hapus blok `$comment ... $dumpall $end` kosong setelah `$enddefinitions` (Quartus gagal membacanya: Error 222007).
3. `python vcd_scalar.py papan_netlist.vcd keluaran.vcd`.

PowerPlay: Processing → Power Analyzer Tool → Add Power Input File(s) → berkas VCD ini, entity `top_papan`, glitch filtering on → Start. Pengaturan ini tersimpan di `../papan.qsf` (6 baris POWER_*).

## Keterbatasan
- Angka daya adalah PERKIRAAN PowerPlay, confidence "Low".
- Hanya 40 % register mendapat aktivitas dari VCD. Register akumulator MAC (acc, m_acc, p_q, init1) memakai estimasi vectorless karena namanya tidak terpetakan. Dua perbaikan nama sudah dicoba, tidak berhasil.
- Simulasi netlist hanya menjalankan citra 00 (tombol butuh 500.000 siklus debounce).
- Jendela VCD memuat sekitar 220 siklus reset dan muat citra, bukan inferensi saja.

## Percobaan Questa (1 November 2026) — ditolak
Tujuan: menaikkan confidence daya dengan alur resmi Quartus (EDA Netlist Writer membuat
`papan_dump_all_vcd_nodes.tcl`, Questa Starter merekam VCD).
- Simulasi Questa benar (LED cocok pada siklus 2.035), tetapi Questa menolak hampir semua nama
  sinyal di skrip Quartus (kesalahan disembunyikan oleh `catch`). Hanya 711 dari sekitar 4.000 sinyal terekam.
- Hasil Power Analyzer: hanya 4,0 % sinyal (11,7 % register) dari simulasi. Tidak sah;
  laporannya di `../hasil_mentah/2026-11-01_TIDAK_SAH_questa_vcd_hanya_4persen/`.
- Dari skrip Quartus diketahui format nama bit register yang diharapkan: `\g_lajur[0].u_mac|acc [31]`
  (nama bus, spasi, nomor bit). VCD Icarus diubah ke format ini, tetapi cakupan register tetap 39,7 %;
  register akumulator MAC (acc, m_acc, p_q, init1) tetap vectorless. Hasil identik dengan sebelumnya
  (`../hasil_mentah/2026-11-01_papan_hard_icarus_v2/`).
- Kesimpulan: angka daya resmi tetap 91,99 mW (perkiraan, confidence Low).
- `papan.qsf` masih berisi EDA_WRITE_NODES_FOR_POWER_ESTIMATION dan EDA_TEST_BENCH_DESIGN_INSTANCE_NAME;
  tidak memengaruhi kompilasi, hanya membuat EDA Netlist Writer menulis skrip VCD.

## Perbandingan tiga varian pengali (1 November 2026)
Revisi Quartus `papan` (HARD), `papan_arith`, `papan_struct`. Varian dipilih lewat `set_parameter -name MULT_STYLE ...`
di `papan_arith.qsf` / `papan_struct.qsf`; berkas RTL tidak diubah.
1. Uji fungsi RTL (salinan tb_papan dengan MULT_STYLE ditimpa, di luar repo): ARITH dan STRUCT LULUS, 18 inferensi identik, 1.816 siklus.
2. `kompilasi_varian.bat`: kompilasi kedua revisi; laporan ke `../hasil_mentah/2026-11-01_papan_arith|struct/`.
3. Simulasi netlist Icarus tiap varian (citra 00, LED cocok pada siklus 2.035), VCD diproses `vcd_quartus.py`
   (satu skrip yang sama untuk ketiga varian, termasuk HARD yang dibuat ulang): `papan_hard|arith|struct_netlist.vcd`.
4. `daya_3_varian.bat`: Power Analyzer untuk ketiga revisi; laporan ke `../hasil_mentah/2026-11-01_daya_papan_hard|arith|struct/`.
Ringkasan angka: Project Skripsi, "Hasil Reproduksi dan Daya 2026-11-01".
