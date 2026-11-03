# Spesifikasi Rancangan Weight-Stationary (WS) 4×2, Batch 16

Status: **diimplementasikan**; simulasi RTL LULUS (bit-exact, 16 citra),
kompilasi Quartus berhasil, dan uji papan LULUS (16/16 citra cocok, tampilan
siklus 1649). Rancangan ini
akan dibandingkan dengan rancangan output-stationary (OS) yang sudah ada,
dengan model, MAC, memori, dan clock yang sama.

---

## 1. Dasar teori

Menurut Sze dkk. (2017, §V-B), dataflow WS memiliki tiga ciri:

1. bobot dibaca ke register PE dan *"stays stationary for further accesses"*;
   PE menjalankan sebanyak mungkin MAC dengan bobot yang sama;
2. aktivasi masukan disiarkan ke beberapa PE;
3. jumlah parsial berpindah dan diakumulasi melintasi larik PE.

Pada lapisan terhubung penuh (FC), sebuah bobot hanya dipakai satu kali per
citra. Pemakaian ulang bobot (*filter reuse*) baru ada bila beberapa citra
diproses sekaligus (batch > 1) (Sze dkk., 2017, Gambar 23; Wan dkk., 2023).
Karena itu rancangan ini memproses **16 citra sekaligus**, yaitu seluruh
citra uji yang ada di ROM papan.

Bentuk larik mengikuti larik sistolik WS gaya TPU (Jouppi dkk., 2017;
Kung, 1982): bobot diam di PE, masukan mengalir sepanjang baris, jumlah
parsial mengalir turun sepanjang kolom.

---

## 2. Parameter

| Simbol | Nilai | Arti |
|---|---|---|
| R | 4 | baris larik = banyak suku masukan per ubin |
| C | 2 | kolom larik = banyak neuron yang dihitung bersamaan |
| R·C | 8 | jumlah PE = jumlah MAC (sama dengan rancangan OS) |
| B | 16 | ukuran batch = banyak citra per proses |
| G₁, T₁ | 32, 49 | lapisan 1: 64/2 pasangan neuron, 196/4 ubin masukan |
| G₂, T₂ | 5, 16 | lapisan 2: 10/2 pasangan neuron, 64/4 ubin masukan |

Ukuran 196, 64, dan 10 habis dibagi R = 4 dan C = 2, sehingga **tidak ada PE
yang menganggur** di kedua lapisan.

---

## 3. Loop nest dan pemetaan

```
for lapisan in (1, 2):
  for g = 0..G-1                     // pasangan neuron (n = 2g, 2g+1)    temporal
    for t = 0..T-1                   // ubin 4 suku masukan               temporal
      muat 8 bobot w[2g+c][4t+r] ke register PE(r,c)   ← SEKALI per batch
      for b = 0..B-1                 // 16 citra; bobot DIAM 16 siklus    temporal
        parallel r = 0..3, c = 0..1  // 8 PE                              spasial
          psum[c][b] += Σr  x[b][4t+r] · w[2g+c][4t+r]
```

- **Data yang diam:** bobot, di register PE, selama B = 16 siklus.
- **Masukan:** satu kata 32 bit (4 suku) per siklus; suku ke-r disiarkan ke
  kedua kolom pada baris r.
- **Jumlah parsial:** mengalir turun sepanjang kolom (akumulasi spasial),
  lalu ditahan di FIFO jumlah parsial (register geser) sampai ubin berikutnya.

---

## 4. Arsitektur

```
             ROM citra 32 bit (L1) / buffer aktivasi 32 bit (L2)
                         │ satu kata per siklus
                 ┌───────┴────────┐
                 │ penunda baris  │  byte r ditunda 2r siklus
                 └──┬───┬───┬───┬─┘
     bias ──┐       │   │   │   │
     FIFO   ┴► PE(0,0)──┼───┼───┼──► PE(0,1)
                 │      │   │   │       │
               PE(1,0)◄─┘   │   │     PE(1,1)
                 │          │   │       │
               PE(2,0)◄─────┘   │     PE(2,1)
                 │              │       │
               PE(3,0)◄─────────┘     PE(3,1)
                 │                      │
          FIFO psum (8 reg)      FIFO psum (8 reg)
                 │                      │
          epilog 0 / argmax      epilog 1 / argmax
```

### 4.1 PE

Setiap PE = **register bobot berpenyangga ganda** (aktif + bayangan, 2 × 8 bit)
+ **`mac_unit.v` tanpa modifikasi**, dengan:

- `s_first = s_last = 1` di setiap beat,
- `s_init` = jumlah parsial dari PE di atasnya (PE baris 0: dari FIFO jumlah parsial, atau
  bias pada ubin pertama),
- `m_ready = 1` terus,
- keluaran `m_acc = s_init + x·w`, latensi 2 siklus.

Dengan begitu setiap MAC bekerja sebagai sel larik sistolik: mengalikan, lalu
menjumlahkan hasilnya ke jumlah parsial yang datang dari atas.

### 4.2 Larik 4×2 dan penundaan baris

- Satu kolom terdiri atas 4 MAC berantai, sehingga latensinya 4 × 2 = **8 siklus**.
- Suku masukan baris r harus tiba 2r siklus setelah baris 0, sehingga
  diperlukan penunda 0, 2, 4, 6 siklus × 8 bit = 96 flip-flop.
- Penggantian bobot (bayangan → aktif) di baris r juga ditunda 2r siklus.

### 4.3 FIFO jumlah parsial (register geser)

Jumlah parsial citra b keluar dari dasar kolom 8 siklus setelah masuk, dan
dibutuhkan lagi di puncak kolom tepat **B = 16 siklus** kemudian (ubin
berikutnya, citra yang sama). Karena itu jumlah parsial cukup diedarkan
lewat **FIFO berupa register geser 8 tahap** per kolom:

```
panjang putaran total = 8 (kolom MAC) + 8 (FIFO) = 16 = B
```

- Ubin pertama (t = 0): puncak kolom mengambil **bias** (digeser seperti di
  rancangan OS), bukan isi FIFO.
- Ubin terakhir (t = T−1): yang keluar dari dasar kolom adalah hasil akhir
  neuron dan diteruskan ke epilog (lapisan 1) atau argmax (lapisan 2).

Dasar teorinya:

- Pada WS, jumlah parsial memang harus berpindah ke luar PE: *"the inputs and
  partial sums must move through the spatial array and global buffer"*
  (Sze dkk., 2017, §V-B).
- Kung (1982, hlm. 40, Design B1 *"broadcast inputs, move results, weights
  stay"*): bobot diam di sel, jumlah parsial berpindah dari sel ke sel, dengan
  fungsi sel `y_out ← y_in + w·x_in`, sama dengan PE di rancangan ini.
- Kung (1982, hlm. 41, Design R1): bila beberapa komputasi independen
  diselang-seling dalam satu larik, diperlukan penyimpan tambahan *"to hold a
  temporary result for the other … computation"*. Di rancangan ini, 16 citra
  diselang-seling, dan FIFO inilah penyimpan hasil sementaranya.
- Data yang beredar memutari larik (Kung, 1982, Design B2) dan register tunda
  untuk menahan data selama jumlah siklus tertentu (*"data delay registers to
  keep data around for the required amount of cycles"*, Sze dkk., 2017,
  tentang ShiDianNao) adalah teknik baku larik sistolik.

FIFO dan register geser adalah komponen dasar desain digital. Bentuk ini
dipilih karena urutan akses jumlah parsial selalu tetap (citra 0..15
berulang), sehingga FIFO sederhana tanpa alamat sudah cukup.

Biayanya 2 kolom × 8 × 32 bit = 512 flip-flop, **tanpa akses M9K**.
Sebagai pembanding, kalau jumlah parsial disimpan di M9K, setiap MAC menambah
satu baca dan satu tulis 32 bit (≈211 Kbit per citra). Itu lebih besar
daripada seluruh lalu lintas memori rancangan OS, sehingga manfaat WS hilang.
Ini adalah *psum storage issue* yang disebut Chen dkk. (2016).

### 4.4 Memori bobot

- 8 bank M9K. Bank k = (r, c) berisi `w[2g+c][4t+r]`.
- Alamat = nomor ubin global: `g·T₁ + t` (lapisan 1, 0..1567), lalu
  `1568 + g·T₂ + t` (lapisan 2, 1568..1647). Jadi 1.648 kata per bank.
- **Satu pencacah alamat untuk 8 bank**, naik satu per ubin (setiap 16 siklus)
  dan tidak pernah di-reset, sama seperti sifat rancangan OS.
- Modul `mem_w.v` dipakai tanpa diubah (latensi baca 2 siklus).
- **Bank hanya diaktifkan satu siklus per ubin** (`en_w`), supaya blok M9K
  memang membaca sekali per ubin. Karena `mem_w.v` punya dua tahap register
  dengan satu *clock-enable*, alamat berjalan dua ubin di depan (*prefetch*):
  satu pulsa `en_w` membaca kata baru sekaligus menggeser kata sebelumnya ke
  keluaran. Terukur di simulasi: **1.649 siklus baca per batch** (1.648 kata
  unik + 1 baca ulang kata terakhir).

### 4.5 Memori masukan

- **Lapisan 1:** ROM 16 citra disusun ulang menjadi kata 32 bit
  (4 piksel). Alamat = `t·16 + b`, total 49 × 16 = 784 kata. Citra dibaca
  langsung dari ROM, sehingga tidak perlu fase menyalin citra ke `mem_d`.
- **Lapisan 2:** buffer aktivasi 32 bit, dibagi dua RAM 16 bit
  (lajur 0–1 dan lajur 2–3). Alamat = `t·16 + b` (t = 0..15), 256 kata.
- Aktivasi neuron n citra b ditulis ke kata `(n div 4)·16 + b`, lajur byte
  `n mod 4`. Pasangan neuron (2g, 2g+1) selalu berada di kata yang sama,
  di separuh yang sama (lajur 0–1 bila g genap, 2–3 bila g ganjil), sehingga
  **satu tulis ke satu RAM 16 bit** cukup untuk 2 epilog, tanpa *byte enable*.
- ROM citra dan buffer aktivasi hanya membaca saat ada token.

### 4.6 Bias, epilog, dan argmax

- **Bias:** `rom_bias8.v` dipakai tanpa diubah. Pasangan g memakai
  kelompok `g div 4` (lapisan 1) atau `8 + (2g div 8)` (lapisan 2), lalu
  memilih 2 dari 8 bias keluarannya.
- **Epilog:** 2 instans `epilog_unit.v` (satu per kolom), karena pada ubin
  terakhir kedua kolom mengeluarkan 1 hasil per siklus.
- **Argmax:** 16 pasang register (nilai 32 bit + indeks 4 bit), satu per
  citra. Setiap siklus, citra b diperbarui dengan 2 kandidat (neuron 2g lalu
  2g+1) memakai pembanding `>`. Urutan ini sama dengan `np.argmax`: neuron
  yang lebih dulu menang bila nilainya seri.
  Argmax dibuat **3 tahap pipa** (tangkap, kandidat 2g, kandidat 2g+1 lalu
  tulis). Versi satu tahap sempat menjadi jalur terpanjang seluruh rancangan
  (Fmax ≈ 56 MHz), padahal bukan bagian dataflow WS. Aman karena citra yang
  sama baru diperbarui lagi setelah 256 siklus.

### 4.7 Pengendali

Pencacah bersarang `lapisan → g → t → b` yang maju setiap siklus tanpa jeda.
Pengendali menghasilkan:

- alamat bobot (+1 per ubin) dan pulsa isi bayangan,
- alamat masukan `t·16 + b`,
- pulsa ganti bobot per baris (ditunda 2r),
- pemilih bias atau FIFO jumlah parsial di puncak kolom (t = 0),
- penanda "hasil akhir" di dasar kolom (t = T−1), lengkap dengan nomor neuron
  dan citra, untuk epilog/argmax.

---

## 5. Pewaktuan

Misalkan beat ke-s di baris 0 terjadi pada siklus c₀ + s, dengan
`s = (g·T + t)·16 + b` (ditambah offset lapisan 2).

| Kejadian | Siklus |
|---|---|
| Baca kata masukan untuk beat s | c₀ + s − 2 |
| Baris r memproses beat s | c₀ + s + 2r |
| Hasil beat s keluar dari dasar kolom | c₀ + s + 8 |
| Hasil itu dipakai lagi (ubin t+1, citra b) | c₀ + s + 16 |
| Ganti bobot ubin k di baris r | c₀ + 16k + 2r |
| Isi bayangan untuk ubin k+1 | jendela c₀ + 16k + 7 … c₀ + 16k + 15 |

Syarat jendela isi bayangan: harus setelah baris 3 berganti bobot (+6) dan
sebelum baris 0 berganti lagi (+16). Kedua syarat terpenuhi bila B ≥ 8.
FIFO jumlah parsial membutuhkan B ≥ 8 (latensi kolom). Kedua alasan ini
membuat **B tetap 16** di implementasi.

**Peralihan lapisan 1 → 2:** aktivasi pasangan terakhir lapisan 1
(neuron 62, 63) tertulis paling lambat sekitar 10 siklus setelah lapisan 2
mulai (8 siklus kolom + 1 epilog + 1 tulis), sedangkan lapisan 2 baru membacanya pada ubin t = 15 (≥ 240 siklus).
Karena itu **tidak perlu jeda**.

---

## 6. Persamaan kinerja

Banyak ubin per batch: U = G₁·T₁ + G₂·T₂ = 1.568 + 80 = **1.648**.

| Besaran | Rumus | WS (B = 16) | OS (setelah PR #3) |
|---|---|---|---|
| Siklus per batch (terukur) | 3 + B·U + 12 | **26.383** | 16 × 1.708 = 27.328 |
| Siklus per citra (throughput) | | **1.648,9** (tampilan: 1649) | 1.708 |
| Latensi sampai hasil pertama @ 50 MHz | | **527,7 µs** | 34,2 µs |
| Utilisasi MAC | U·B / siklus | **99,94 %** | 99,3 % |
| Baca bobot per citra (byte) | 8·U / B | **824** | 13.184 |
| Baca masukan per citra | U kata × 4 byte | 6.592 byte | 1.696 byte |
| Akses jumlah parsial ke M9K | | 0 (FIFO register geser) | 0 (akumulator MAC) |
| **Total bit M9K dibaca per citra** | | **≈ 59,3 Kbit** | ≈ 119 Kbit |

Angka OS per batch adalah 16 inferensi berurutan, belum termasuk waktu
memuat citra di papan.

Rincian 26.383 siklus WS: 3 siklus PRA (bobot ubin pertama) + 26.368 token
tanpa jeda + 12 siklus ekor (10 sampai token terakhir tiba di dasar kolom,
2 untuk argmax berpipa). Angka ini dihitung lebih dulu dari struktur pipa,
lalu dicocokkan dengan simulasi.

Akses memori terukur di simulasi per batch: 1.649 siklus baca bank bobot,
1.648 ubin bobot dimuat (13.184 byte, atau 824 byte per citra), dan 26.368
kata masukan.

Untuk B umum (analisis, bukan implementasi), bit M9K per citra adalah
`105.472 / B + 52.736`. Nilainya setara OS pada B ≈ 2, dan lebih baik dari
OS pada B ≥ 3.

---

## 7. Sumber daya terukur (Quartus Prime Lite 25.1std, EP4CE6E22C8)

| | WS 4×2, B = 16 | OS (setelah PR #3) |
|---|---|---|
| Logic element | **3.573 / 6.272 (57 %)** | 2.306 (37 %) |
| Register | 2.613 | 1.420 |
| M9K | **22 / 30** (bobot 16, ROM citra 4, buffer aktivasi 2) | 21 / 30 |
| Bit memori | 138.752 (50 %) | 143.392 (52 %) |
| Pengali 9 bit | 8 / 30 | 8 / 30 |
| Fmax (Slow 1200mV 85C) | **88,55 MHz** (slack 8,707 ns) | 82,46 MHz |

Jalur terpanjang WS kini berada di larik itu sendiri (rantai MAC antarbaris),
bukan di modul pendukung. Tambahan register WS terutama berasal dari FIFO
jumlah parsial (512), register argmax 16 citra (sekitar 600), register bobot
berpenyangga ganda (128), dan penunda baris (96). `AUTO_SHIFT_REGISTER_
RECOGNITION` dimatikan supaya FIFO dan penunda tetap berupa register, tidak
dipindah ke M9K.

---

## 8. Antarmuka papan

- Saat dinyalakan, batch 16 citra dijalankan sekali dan hasilnya disimpan.
- S1/S2: pindah citra dan **menampilkan hasil yang sudah tersimpan**, tanpa
  menghitung ulang.
- S3: menjalankan ulang batch.
- S4 ditahan: menampilkan **siklus per citra** = siklus satu batch ÷ 16
  (dibulatkan), supaya dapat dibandingkan langsung dengan angka 1708 milik
  rancangan OS. Jumlah siklus per batch yang tepat diperiksa di simulasi.
- Tampilan `[nomor citra][.][tebakan Python][tebakan FPGA]` dan LED tetap
  sama dengan rancangan OS.

---

## 9. Verifikasi

1. **Simulasi RTL:** satu batch. Untuk **setiap citra, kesepuluh akumulator
   lapisan 2** harus identik dengan `golden_uji.txt`, begitu juga tebakannya.
2. **Siklus:** jumlah siklus per batch harus sama dengan rumus B·U + c
   (c dihitung dari struktur pipa, bukan dicocokkan setelah simulasi).
3. **Ulang batch (S3):** hasil kedua harus identik dengan hasil pertama.
4. **Quartus:** LE, M9K, pengali, dan Fmax.
5. **Papan:** 16/16 citra cocok.

---

## 10. Struktur folder

Seluruh berkas khusus WS berada di folder `4_WS/`, terpisah dari rancangan OS
(`2_Verilog/`, `3_Quartus/`):

```
Alur_Utama/
├── 1_Python_PC/      bersama: model beku, citra uji, acuan (golden)
├── 2_Verilog/        rancangan OS + modul bersama
├── 3_Quartus/        proyek Quartus OS
└── 4_WS/             rancangan WS
    ├── SPESIFIKASI_WS.md
    ├── 1_mem/        gen_mem_ws.py, 8 bank bobot WS, ROM citra 32 bit
    ├── 2_verilog/    pe_ws, larik_ws, ctrl_ws, buf_aktivasi_ws,
    │                 argmax_batch, top_papan_ws, tb_papan_ws,
    │                 jalankan_papan_ws.py, JALANKAN_SIMULASI_WS.bat
    └── 3_quartus/    papan_ws.qpf/.qsf, JALANKAN_PAPAN_WS.bat, output_papan_ws/
```

| Berkas di `4_WS/` | Isi |
|---|---|
| `1_mem/gen_mem_ws.py` | membuat 8 bank bobot WS dan ROM citra 32 bit dari `1_Python_PC/Training/export_final` dan `1_Python_PC/uji/` |
| `1_mem/mem_w_ws_b0..7.hex` | 8 bank × 1.648 kata |
| `1_mem/citra_ws32.hex` | 784 kata × 32 bit |
| `2_verilog/pe_ws.v` | PE: register bobot ganda + `mac_unit` |
| `2_verilog/larik_ws.v` | larik 4×2, penunda baris, FIFO jumlah parsial |
| `2_verilog/ctrl_ws.v` | pengendali |
| `2_verilog/buf_aktivasi_ws.v` | buffer aktivasi 32 bit dengan byte enable |
| `2_verilog/argmax_batch.v` | argmax 16 citra |
| `2_verilog/top_papan_ws.v` | rancangan teratas papan |
| `2_verilog/tb_papan_ws.v`, `jalankan_papan_ws.py`, `JALANKAN_SIMULASI_WS.bat` | verifikasi |
| `3_quartus/papan_ws.qpf`, `papan_ws.qsf`, `JALANKAN_PAPAN_WS.bat` | proyek Quartus WS |

**Modul bersama, dirujuk dari `2_Verilog/` dan tidak disalin:** `mac_unit.v`,
`mult_*.v`, `mem_w.v`, `epilog_unit.v`, `seg7_*.v`, `papan.sdc`, serta
`1_Python_PC/mem/rom_bias8.v`. Semuanya dipakai **tanpa diubah**. Modul ini
tidak disalin supaya OS dan WS selalu memakai MAC dan memori yang sama
persis; dengan begitu perbandingannya adil, dan MAC tetap satu versi.

Model beku (`export_final/`) dan acuan (`golden_uji.txt`) juga dipakai
bersama tanpa diubah.

---

## 11. Keputusan

| # | Keputusan | Status |
|---|---|---|
| 1 | **B = 16 tetap** di implementasi; nilai B lain dianalisis dengan persamaan di §6 | disetujui |
| 2 | **Jumlah parsial di FIFO register geser**, bukan M9K (§4.3, dasar: Kung 1982; Sze dkk. 2017) | disetujui |
| 3 | **Folder dan proyek Quartus terpisah** (`4_WS/`, §10) | disetujui |
| 4 | **S4 menampilkan siklus per citra** (batch ÷ 16), seperti OS (§8) | disetujui |
| 5 | Konfirmasi ke dosen soal judul dan batch 16 | perlu, bukan prioritas |

---

## Rujukan

- Sze, V., dkk. (2017). Efficient Processing of Deep Neural Networks: A Tutorial and Survey. *Proc. IEEE*, 105(12). doi:10.1109/JPROC.2017.2761740
- Chen, Y.-H., Emer, J., & Sze, V. (2016). Eyeriss. *ISCA 2016*. doi:10.1109/ISCA.2016.40
- Wan, H., dkk. (2023). A Systolic Array with Activation Stationary Dataflow for Deep Fully-Connected Networks. *IEEE AICAS 2023*. doi:10.1109/AICAS57966.2023.10168602
- Jouppi, N. P., dkk. (2017). In-Datacenter Performance Analysis of a Tensor Processing Unit. *ISCA 2017*. doi:10.1145/3079856.3080246
- Kung, H. T. (1982). Why systolic architectures? *Computer*, 15(1). doi:10.1109/MC.1982.1653825
