# 9_Analisis_MAC — analisis per komponen unit MAC (Student A)

Menguraikan selisih luas, delay, dan daya antara pengali HARD, ARITH, dan STRUCT
sampai ke tingkat komponen unit MAC dan epilog, pada rancangan OS akhir
(`2_Verilog/top_papan.v`, 1.708 siklus per citra).

- Desain: `input/ideas/analisis-mendalam-mac-design.md`
- Rencana dan hipotesis H1–H5 beserta kriterianya: `input/ideas/analisis-mendalam-mac-plan.md`
  (ditetapkan 4 November 2026, sebelum pengukuran per komponen)
- Catatan proses dan penyimpangan: `DOKUMENTASI_PROSES.md`, `log.md`

Berkas di `input/ideas/`, `DOKUMENTASI_PROSES.md`, `log.md`, dan `8_Varian_Pengali/simulasi_netlist/README.md` adalah catatan bertanggal yang dibiarkan apa adanya. Sebutan rancangan 1.816 siklus, `jalankan_sapu.py`, folder `skripsi/Implementasi/`, dan cabang `studentA/analisis-mac` di dalamnya menggambarkan keadaan saat itu dan tidak dipakai lagi: rancangan acuan adalah `top_papan.v` (1.708 siklus), dan gerbang uji saat ini ada di `scripts/gerbang.sh`.

## Isi folder

| Folder / berkas | Isi |
|---|---|
| `rtl_terpecah/` | `mac_unit.v` dan `epilog_unit.v` versi terpecah (submodul per komponen) |
| `rtl_uji/` | `tb_mac_unit.v` beserta vektor uji `*.hex`, `tb_mult8.v`, `mac_lane_wrap.v` |
| `tb/` | `tb_hitung_siklus.v`: rincian 1.708 siklus, meng-instansiasi `top_papan` tanpa mengubahnya |
| `wrap/` | proyek pembungkus register untuk mengukur komponen sendirian |
| `kompilasi_pecah/` | pembangkit proyek `pecah_<varian>` dan skrip aktivitas register versi terpecah |
| `scripts/` | skrip pembaca laporan, sapuan seed, laporan per tahap, gerbang uji |
| `hasil/` | CSV dan ringkasan tiap tugas, log gerbang (`gerbang/`), report_timing per tahap (`T4/`), gambar |
| `referensi/` | catatan dan BibTeX |

Laporan Quartus mentah ada di `8_Varian_Pengali/hasil_mentah/`.

## Penting: versi datar dan versi terpecah

`2_Verilog/mac_unit.v` dan `2_Verilog/epilog_unit.v` adalah **versi datar** yang
dipakai OS, WS, dan NLR, dan tidak diubah oleh folder ini. Versi terpecah di
`rtl_terpecah/` memiliki fungsi, port, dan latensi yang sama, tetapi isinya dipecah
menjadi submodul supaya Quartus melaporkan luas, delay, dan daya per komponen.

Kedua versi memakai **nama modul yang sama** (`mac_unit`, `epilog_unit`). Jangan
pernah memasukkan berkas `rtl_terpecah/` ke proyek atau perintah simulasi yang juga
memuat `2_Verilog/mac_unit.v` atau `2_Verilog/epilog_unit.v`. Proyek `pecah_<varian>`
dan `wrap/` sudah diarahkan ke `rtl_terpecah/`.

## Menjalankan gerbang uji

Dari akar repo, dengan Icarus Verilog dan Python 3:

```
bash 9_Analisis_MAC/scripts/gerbang.sh g1 datar      # tb_mac_unit, 3 pengali x PIPE_MULT 0/1
bash 9_Analisis_MAC/scripts/gerbang.sh g1 terpecah
bash 9_Analisis_MAC/scripts/gerbang.sh t2            # tb_mult8, 65.536 pasangan masukan
bash 9_Analisis_MAC/scripts/gerbang.sh g3            # 2_Verilog/jalankan_papan.py, 18/18
```

Semua harus berakhir dengan `HASIL: LULUS`.
