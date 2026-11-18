# 8_Varian_Pengali — ukur ulang tiga varian pengali (Student A)

Mengukur luas, timing, dan daya ketiga varian pengali (`MULT_STYLE` = HARD,
ARITH, STRUCT) pada **rancangan OS terbaru** (`2_Verilog/top_papan.v`, P = 8,
1.708 siklus per citra).

## Cara menjalankan

Klik dua kali `JALANKAN_VARIAN.bat`, atau dari folder akar repo:

```
python 8_Varian_Pengali/jalankan_varian.py               # ketiga varian, sekitar 10-15 menit
python 8_Varian_Pengali/jalankan_varian.py ARITH         # satu varian saja
```

Syarat: Quartus Prime Lite 25.1std di `C:\altera_lite\25.1std`, Icarus Verilog,
Python 3.

### Bila Icarus Verilog tidak terpasang di Windows

Jalankan dalam tiga tahap. Simulasi dapat dijalankan dengan Icarus di Linux
(misalnya VM) yang membaca folder repo yang sama:

1. Windows: `TAHAP_KOMPILASI.bat` (`jalankan_varian.py --kompilasi`)
2. Linux: `IVL_BIN=... IVL_LIB=... python3 8_Varian_Pengali/jalankan_varian.py --simulasi`
   (`IVL_BIN` folder `iverilog`/`vvp`, `IVL_LIB` folder pustaka `ivl` untuk opsi `-B`/`-M`)
3. Windows: `TAHAP_DAYA.bat` (`jalankan_varian.py --daya`)

## Langkah tiap varian

1. **Uji RTL 16 citra** dengan `2_Verilog/tb_papan.v` dan `MULT_STYLE` varian
   (lewat `defparam`): 18 inferensi, kesepuluh akumulator lapisan 2 identik dengan
   `golden_uji.txt`, tepat 1.708 siklus. Bila gagal, pengukuran berhenti.
2. **Kompilasi Quartus** proyek `daya_<varian>`. Proyek dibuat otomatis dari
   `6_Daya_FPGA/daya_os.qsf` dengan tambahan `set_parameter -name MULT_STYLE`.
3. **Analisis daya dengan metode `6_Daya_FPGA` (Student B)**: jendela inferensi
   dari RTL, simulasi netlist (LED cocok pada siklus yang sama dengan RTL), VCD
   hanya selama inferensi, aktivitas register MAC sebagai assignment, lalu
   Power Analyzer.
4. **Arsip** laporan mentah (`map`, `fit`, `sta`, `flow`, `pow`) ke
   `8_Varian_Pengali/hasil_mentah/<tanggal>_os_<varian>/`.

Berkas Student B (`6_Daya_FPGA/`, `2_Verilog/tb_papan.v`, `jalankan_papan.py`)
hanya dipanggil atau dibaca, tidak diubah.

## Hasil

- `hasil/<varian>.json`: angka satu varian beserta nama folder arsipnya.
- `hasil_mentah/`: laporan Quartus yang dirujuk skripsi Student A.
  - `2026-11-03_os_<varian>/`: proyek `daya_<varian>` (angka utama versi datar).
  - `2026-11-04_analisis_mac_pecah_<varian>/`: proyek `pecah_<varian>` (versi terpecah,
    untuk proporsi antarkomponen; RTL dari `9_Analisis_MAC/rtl_terpecah/`).
  - `2026-11-04_analisis_mac_seed/`: ringkasan fitter dan timing lima seed per varian.
  - `2026-11-04_analisis_mac_sendirian/`: komponen unit MAC dan epilog dalam pembungkus register.
  - `2026-09-24_tim/`: pengali dalam pembungkus register dan lajur MAC dengan pin maya
    (pengukuran tim 24 September 2026).
  - Laporan daya disimpan sebagai `*.pow_ringkas.rpt`, yaitu laporan Power Analyzer tanpa
    tabel per sinyal dan per blok (cara yang sama dengan `6_Daya_FPGA`).
- `simulasi_netlist/`: simulasi netlist, skrip VCD, dan skrip akurasi yang menjadi dasar
  alur daya di `6_Daya_FPGA`.

Catatan: daya adalah **perkiraan** Power Analyzer, bukan pengukuran fisik.
