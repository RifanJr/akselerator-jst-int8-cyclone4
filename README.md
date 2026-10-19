# Alur Utama — dari MNIST sampai papan menebak angka

Folder ini hanya berisi berkas yang dipakai pada alur utama. Uji papan
(`uji_papan`), pembanding naif, simulasi pascasintesis, analisis daya, dan
pengukuran unit MAC tetap ada di folder `Implementasi`, tidak disalin ke sini.

Folder `Implementasi` tidak diubah sama sekali. Folder ini salinan yang
jalurnya sudah disesuaikan, jadi bisa dijalankan sendiri.

```
Alur_Utama/
├── 1_Python_PC/     langkah 1–4  model, bobot .hex, citra uji, golden
├── 2_Verilog/       langkah 5–6  rancangan akselerator + simulasi
└── 3_Quartus/       langkah 7–9  kompilasi, program papan
```

---

## 1_Python_PC

| Langkah | Berkas | Hasil |
|---|---|---|
| 1–3 Training dan kuantisasi INT8 | `Training/Training_MLP_PyTorch.ipynb`, Tahap 1–6 | `Training/export_final/` (model beku, akurasi 97,45 %) |
| 4a Bobot ke format memori FPGA | `Training/Training_MLP_PyTorch.ipynb`, Tahap 7 | `mem/P8/mem_w_b0..b7.hex` (8 bank), `mem/mem_d.hex`, `mem/rom_bias8.v` |
| 4b 16 citra uji, golden, dan ROM citra | `Training/Training_MLP_PyTorch.ipynb`, Tahap 8 | `uji/citra_00..15.hex`, `uji/golden_uji.txt`, `uji/daftar_uji.txt`, `uji/citra_papan.hex` |

`Training/data/MNIST/raw/` hanya berisi test set (10.000 citra), dipakai Tahap 8.

**Semua hasil sudah tersedia dan tidak perlu dibuat ulang.** Tahap 1–6 notebook
sengaja tidak dijalankan lagi: hasil pelatihan ulang tidak akan sama persis,
sehingga seluruh pengujian harus diulang. Tahap 7 dan Tahap 8 notebook
aman dijalankan; keluarannya identik dengan berkas yang ada (sudah diuji).

`rom_bias8.v` berbentuk Verilog, tetapi tempatnya di sini karena dibuat oleh
Tahap 7 notebook dari bias model.

---

## 2_Verilog

| Berkas | Fungsi |
|---|---|
| `top_papan.v` | **rancangan teratas**: akselerator + ROM 16 citra + tombol + seven-segment + LED |
| `ctrl_fsm_p8.v` | pengendali orkestrasi memori, 8 lajur |
| `mem_w.v`, `mem_d.v` | memori bobot dan memori data (M9K) |
| `mac_unit.v` | unit MAC (spesifikasi Student A) |
| `mult_hard8.v` | pengali 9 bit bawaan chip, **yang dipakai** |
| `mult_bw8_arith.v`, `mult_bw8_struct.v` | varian pengali lain; tetap disertakan karena dirujuk `mac_unit.v` |
| `epilog_unit.v` | geser bit, ReLU |
| `argmax10.v` | memilih angka dengan nilai terbesar |
| `seg7_scan.v`, `seg7_dec.v` | penggerak seven-segment |
| `papan.sdc` | batasan clock 50 MHz |
| `tb_papan.v` + `jalankan_papan.py` | simulasi sebelum masuk chip |

Simulasi (butuh Icarus Verilog), dari folder `2_Verilog`:

```
python jalankan_papan.py
```

Harus berakhir dengan `HASIL: LULUS — 18 inferensi`.

---

## 3_Quartus

| Berkas | Fungsi |
|---|---|
| `papan.qpf`, `papan.qsf` | proyek Quartus: chip EP4CE6E22C8, daftar berkas, pin papan |
| `JALANKAN_PAPAN.bat` | langkah 1 kompilasi, langkah 2 program papan lewat USB-Blaster |
| `output_papan/papan.sof` | hasil kompilasi yang siap diprogram |
| `output_papan/papan.fit.summary` | pemakaian LE, M9K, pengali |
| `output_papan/papan.sta.summary` | hasil analisis timing (Fmax) |

Klik dua kali `JALANKAN_PAPAN.bat` (tutup Quartus GUI dulu). Kalau hanya
ingin memprogram tanpa kompilasi ulang: Quartus Programmer → Add File →
`output_papan/papan.sof` → Start.

Di papan, layar menampilkan `[nomor citra][.][tebakan Python][tebakan FPGA]`,
misalnya `00.77`. LED1 menyala bila keduanya cocok. S1 citra berikutnya,
S2 sebelumnya, S3 ulang, S4 ditahan menampilkan jumlah siklus (1816).
