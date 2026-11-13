# 5_PC — Pembanding PC

Model MLP 196–64–10 yang **sama** dengan akselerator FPGA, dijalankan di CPU
laptop untuk membandingkan kecepatan, kestabilan waktu, dan energi per citra.

---

## Isi folder

| Berkas | Isi |
|---|---|
| `model_pc.py` | Dua versi model dari `1_Python_PC/Training/export_final`: **INT8 (NumPy)** dengan aritmetika persis seperti FPGA, dan **FP32 (PyTorch)** sebagai cara lazim di PC. Jalankan langsung untuk memeriksa kebenaran. |
| `ukur_pc.py` | Pengukuran: `waktu` (latensi per citra dan throughput), `beban` (pola diam–beban–diam untuk HWiNFO), `ulang` (satu sesi daya penuh, INT8 dan FP32 bergantian) |
| `metrik_akurasi.py` | Accuracy, precision, recall, F1 per digit dan rata-rata, untuk INT8 dan FP32 |
| `olah_daya_pc.py` | Mengolah log CSV HWiNFO: daya diam, daya beban, selisihnya, energi per citra, dan rangkuman per model |
| `hasil/` | Data mentah dan rangkuman pengukuran (lihat bagian Hasil) |

## Kebenaran model

```
python 5_PC/model_pc.py
```

- INT8: kesepuluh akumulator lapisan 2 untuk 16/16 citra **identik** dengan
  `1_Python_PC/uji/golden_uji.txt`, sama dengan FPGA.
- Akurasi 10.000 citra uji: INT8 97,45 %, FP32 97,45 %.

### Precision, recall, F1

```
python 5_PC/metrik_akurasi.py
```

Untuk setiap digit dihitung:
- precision = tebakan digit itu yang benar ÷ semua tebakan digit itu;
- recall = citra digit itu yang tertebak benar ÷ semua citra digit itu;
- F1 = 2 × precision × recall ÷ (precision + recall).

Rata-rata makro adalah rata-rata biasa dari ke-10 digit. Hasil INT8 berlaku
juga untuk FPGA, karena keduanya identik bit per bit.

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| INT8 (= FPGA) | 97,45 % | 97,43 % | 97,43 % | 97,43 % |
| FP32 (PyTorch) | 97,45 % | 97,43 % | 97,43 % | 97,43 % |

- F1 terendah ada pada digit 8 dan 9 (sekitar 96,6 %), tertinggi pada
  digit 1 dan 0 (sekitar 98,5 %).
- INT8 dan FP32 menebak berbeda pada **35 dari 10.000** citra. Jumlah tebakan
  benarnya kebetulan sama, tetapi citra yang salah tidak persis sama.
- Rincian per digit dan matriks kebingungan: `hasil/metrik_akurasi.json`.

## Cara mengulang pengukuran

**Kondisi:** laptop dicolok ke listrik, semua aplikasi lain ditutup (termasuk
VS Code), jalankan dari Windows PowerShell di folder `Alur_Utama`.

1. **Latensi dan throughput** (HWiNFO tidak diperlukan, sebaiknya ditutup):
   ```
   python 5_PC/ukur_pc.py waktu --inti 2
   python 5_PC/ukur_pc.py waktu
   ```
2. **Daya** dengan HWiNFO64 (mode *Sensors-only*):
   1. Mulai logging CSV (ikon *Start Logging*).
   2. Jalankan satu sesi penuh (±31 menit, jangan memakai laptop):
      ```
      python 5_PC/ukur_pc.py ulang --kali 5 --detik 60 --inti 2
      ```
   3. Setelah muncul `SESI SELESAI`, hentikan logging dan simpan CSV di `5_PC/hasil/`.
   4. Olah:
      ```
      python 5_PC/olah_daya_pc.py 5_PC/hasil/<nama log>.CSV
      ```

`--inti 2` mengunci proses ke inti fisik 2 (prosesor logis 4) dengan
prioritas normal, sehingga daya "Core 2 Power" di HWiNFO dapat dipakai sebagai
daya inti yang mengerjakan inferensi.

## Metode

- Yang diukur hanya **inferensi**: dari vektor 196 masukan di memori sampai
  argmax. Memuat citra dan praproses tidak dihitung, sama dengan sisi FPGA.
- Latensi: pemanasan 1.000 kali, lalu 10.000 inferensi satu citra, masing-masing
  diukur dengan `perf_counter_ns`. Waktu ini termasuk overhead pemanggilan Python,
  yang merupakan bagian dari cara lazim menjalankan model di PC.
- Daya: **metode selisih**, yaitu daya beban dikurangi rata-rata daya diam
  sebelum dan sesudahnya. Lima detik di tepi tiap fase dibuang, dan hanya
  cuplikan HWiNFO yang benar-benar diperbarui yang dipakai.
- Energi per citra: *tambahan* = selisih daya ÷ citra per detik;
  *total* = daya beban ÷ citra per detik.
- Tiga tingkat daya: **inti** yang dikunci, **paket CPU**, dan **GPU** sebagai
  kontrol (harus tidak berubah, karena model hanya berjalan di CPU).

## Lingkungan

| | |
|---|---|
| Laptop | Lenovo IdeaPad Gaming 3 15ARH7 (82SB), Windows 11 |
| CPU | AMD Ryzen 5 7535HS, 6 inti / 12 thread |
| RAM | 24 GB |
| Pustaka | Python 3.12.10, NumPy 1.26.4, PyTorch 2.12.1 (CPU) |
| Alat ukur daya | HWiNFO64 v8.48, interval cuplikan 2 detik |
| Kondisi | Laptop dicolok, semua aplikasi latar ditutup (hanya Notepad terbuka) |

## Hasil (2 November 2026)

### Latensi dan throughput (`hasil/waktu_inti2_20261102_200234.json`)

Dikunci ke inti fisik 2, satu thread.

| Model | Median | p95 | p99 | Simpangan | Throughput 1 citra | Throughput batch 10.000 |
|---|---|---|---|---|---|---|
| INT8 (NumPy) | 15,6 µs | 15,9 µs | 22,5 µs | 2,1 µs | 62.420 citra/s | 150.084 citra/s |
| FP32 (PyTorch) | 39,6 µs | 46,9 µs | 59,6 µs | 4,4 µs | 24.501 citra/s | 2.579.971 citra/s |

Tanpa penguncian inti dan dengan thread bawaan, FP32 batch 10.000 mencapai
6.411.422 citra/s (`hasil/waktu_20261102_200429.json`).

### Daya dan energi (`hasil/hwinfo_resmi_20261102.CSV`, 5 ulangan per model)

| | INT8 (NumPy) | FP32 (PyTorch) |
|---|---|---|
| Throughput selama beban | 62.058 ± 462 citra/s | 24.907 ± 141 citra/s |
| Selisih daya inti | 10,64 ± 0,08 W | 10,49 ± 0,16 W |
| Selisih daya paket CPU | 16,36 ± 0,07 W | 15,04 ± 0,14 W |
| **Energi tambahan per citra (inti)** | **171,5 ± 1,0 µJ** | **421,3 ± 6,0 µJ** |
| Energi tambahan per citra (paket) | 263,7 ± 2,1 µJ | 603,7 ± 7,8 µJ |
| Energi total per citra (paket) | 399,5 ± 4,9 µJ | 941,6 ± 5,6 µJ |
| Selisih daya GPU (kontrol) | −0,09 W | −0,08 W |

### Catatan metode: prioritas proses dan HWiNFO

Sesi pertama (`hasil/hwinfonew.CSV`) memakai prioritas proses **tinggi**.
Akibatnya HWiNFO tertahan saat membaca sensor inti yang sedang penuh dipakai:
nilai sensor CPU membeku sampai sekitar 22 detik selama fase beban (saat diam
selalu diperbarui tiap 2 detik), sehingga satu ulangan INT8 tidak dapat dipakai.
Setelah prioritas diubah menjadi normal, jeda pembaruan saat beban paling lama
4 detik dan simpangan antarulangan turun di bawah 2 %. Data sesi pertama
disimpan sebagai bukti.

## Keterbatasan

- Daya dari HWiNFO adalah **telemetri CPU** (perkiraan dari prosesor), bukan
  pengukuran fisik. Pengukuran fisik dengan wattmeter atau sensor arus masih
  berupa rencana.
- Latensi PC termasuk overhead Python. Implementasi native (misalnya C) dapat
  lebih cepat dan tidak diukur di sini.
- Hasil berlaku untuk laptop dan pengaturan di atas.
