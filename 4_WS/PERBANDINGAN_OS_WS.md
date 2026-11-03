# Perbandingan OS vs WS

Dua rancangan akselerator MLP 196–64–10 INT8 pada chip yang sama
(EP4CE6E22C8, 50 MHz, 8 pengali HARD), dengan modul bersama yang sama:

- **OS** (*output stationary*): `2_Verilog/top_papan.v`, 8 lajur, satu citra
  per inferensi.
- **WS** (*weight stationary*): `4_WS/2_verilog/top_papan_ws.v`, larik
  sistolik 4 × 2, batch 16 citra.

Semua angka **terukur** dari simulasi RTL, laporan Quartus, dan Power
Analyzer (2 November 2026).

## Ringkasan

| | OS | WS | Unggul |
|---|---|---|---|
| Siklus per citra | 1.708 | 1.649 | WS (sedikit) |
| Latensi sampai hasil pertama | **34,16 µs** | 527,66 µs (16 citra sekaligus) | **OS** |
| Bit memori M9K dibaca/ditulis per citra | 123,5 Kbit | **59,8 Kbit** | **WS (2,1× lebih sedikit)** |
| Energi M9K per citra | 325 nJ | **80 nJ** | **WS (4,0× lebih hemat)** |
| Energi register + logika per citra | 217 nJ | 902 nJ | OS |
| **Energi total chip per citra** | **3,208 µJ** | 3,582 µJ | **OS (11,7 % lebih hemat)** |
| Energi inti dinamis per citra | **0,720 µJ** | 1,173 µJ | OS |
| Logic element | **2.306** | 3.573 | OS |
| Blok M9K | 21 | 22 | sama |
| Fmax | 82,46 MHz | **88,55 MHz** | WS |

**Kesimpulan:** WS terbukti mengurangi akses memori. Bit M9K per citra turun
separuh dan energi M9K turun 4×, sesuai tujuan dataflow WS. Namun pada MLP
kecil di FPGA ini, penghematan itu **kalah besar** dibanding biaya tambahannya,
yaitu jumlah parsial yang berpindah antar-PE setiap siklus dan argmax untuk 16
citra. Akibatnya energi total per citra WS sekitar 12 % lebih besar, dan
latensinya 15× lebih panjang karena harus menunggu satu batch.

## A. Kinerja

| | OS | WS (B = 16) |
|---|---|---|
| Siklus per citra | 1.708 | 1.648,9 (26.383 ÷ 16) |
| Latensi sampai hasil pertama | 34,16 µs | 527,66 µs |
| Beat MAC berguna | 13.184 dari 13.568 (99,3 %) | 13.184 dari 13.184 (99,94 %) |

Pada OS, 384 beat terbuang karena lapisan 2 hanya memakai 10 dari 16 lajur
dalam dua putaran.

## B. Akses memori per citra

| Jenis data | OS | WS |
|---|---|---|
| Bobot | 13.664 byte (bank dibaca setiap siklus) | 824,5 byte (dibaca sekali per ubin, dipakai 16 citra) |
| Masukan | 1.708 byte | 6.592 byte |
| Tulis aktivasi | 64 byte | 64 byte |
| Jumlah parsial | 0 (tetap di akumulator MAC) | 0 (FIFO register, tidak ke M9K) |
| **Total bit M9K** | **≈123,5 Kbit** | **≈59,8 Kbit** |

Catatan: pada OS, bank bobot tetap membaca walaupun akselerator diam, karena
`mem_en` terhubung ke sinyal "semua lajur siap". Hal ini **tidak memengaruhi**
angka daya di bawah, karena VCD hanya merekam selama inferensi.

## C. Sumber daya (LE)

| Bagian | OS | WS |
|---|---|---|
| 8 MAC | ≈1.211 | ≈1.390 |
| Struktur larik (bobot ganda, penunda baris, FIFO) | – | 607 |
| Pengendali | 260 | 288 |
| Argmax | 71 | 918 (16 citra) |
| Epilog | 14 | 2 × 13 |
| *Top* (tombol, tampilan, ROM citra, penangkap) | 621 | 283 |
| **Total** | **2.306** | **3.573** |

## D. Daya dan energi per citra

Metodenya sama untuk keduanya: Power Analyzer dengan VCD dari simulasi netlist
selama inferensi saja, dengan confidence **High** (`6_Daya_FPGA/` dan
`4_WS/4_daya/`).

| | OS | WS |
|---|---|---|
| Lama per citra | 34,16 µs | 32,98 µs |
| Daya total | 93,91 mW | 108,63 mW |
| Daya inti dinamis | 21,09 mW | 35,57 mW |
| **Energi total per citra** | **3,208 µJ** | **3,582 µJ** |
| Energi inti dinamis per citra | 0,720 µJ | 1,173 µJ |

Rincian per jenis blok (daya × lama per citra):

| Jenis blok | OS | WS |
|---|---|---|
| M9K (memori) | 9,53 mW → **325 nJ** | 2,44 mW → **80 nJ** |
| Register | 5,38 mW → 184 nJ | 18,07 mW → 596 nJ |
| Logika kombinasional | 0,97 mW → 33 nJ | 9,27 mW → 306 nJ |
| Pengali | 1,64 mW → 56 nJ | 0,88 mW → 29 nJ |
| Jaringan clock | 3,56 mW → 122 nJ | 4,91 mW → 162 nJ |

Di WS, larik memakan 19,75 mW, dan sekitar 15 mW di antaranya berasal dari
8 MAC. Akumulator berubah setiap siklus karena jumlah parsial berpindah ke PE
di bawahnya. Pada OS, kedelapan MAC hanya memakan 4,39 mW. Argmax
16 citra memakan 5,78 mW.

## Pembahasan

- Hasil ini sesuai kompromi yang dijelaskan Sze dkk. (2017): WS meminimalkan
  pembacaan bobot, tetapi jumlah parsial harus dipindahkan antar-PE.
- Keuntungan WS biasanya besar bila membaca memori jauh lebih mahal daripada
  memindahkan data antar-register, misalnya bila bobot diambil dari DRAM.
  Di rancangan ini semua bobot ada di M9K di dalam chip, sehingga selisih
  biaya itu kecil. **Kemungkinan** inilah sebabnya penghematan memori WS
  tidak cukup menutup biaya register tambahannya. Dugaan ini belum diuji
  secara terpisah.
- WS membutuhkan batch (B = 16) untuk memakai ulang bobot pada lapisan FC.
  Untuk aplikasi yang memproses satu citra sekaligus, OS lebih cocok.

## Dibandingkan dengan PC

Angka PC berasal dari `5_PC/` (INT8 NumPy, satu inti Ryzen 5 7535HS).
Energi total per citra PC adalah 399,5 µJ, sehingga OS sekitar 125× lebih
hemat dan WS sekitar 112× lebih hemat. Kedua rancangan FPGA jauh lebih hemat
daripada PC, dan selisih antara OS dan WS kecil dibanding selisih FPGA–PC.
