# Spesifikasi rancangan No Local Reuse (NLR) (no stationary)

Status: **selesai (10 November 2026).** Simulasi RTL 16/16 citra bit-exact, uji
papan 16/16 cocok, dan analisis daya confidence High. Angka di dokumen ini adalah
hasil simulasi, kompilasi, dan Power Analyzer (ringkasan di bagian 8).

---

## 1. Tujuan

Menyediakan pembanding ketiga sesuai arahan dosen (bimbingan 4 November 2026):
**OS vs WS vs tanpa stationary**, dibandingkan dari sisi daya, energi, dan waktu,
dengan model, chip, clock, dan unit MAC yang sama.

## 2. Definisi dan sumber

Sze dkk. (2017, Proc. IEEE 105(12), hlm. 15, Gbr. 25(c)) menyebut dataflow ini
**no local reuse (NLR)**:

> "no local storage is allocated to the PE … The no local reuse dataflow differs
> from the previous dataflows in that nothing stays stationary inside the PE
> array. As a result, there will be increased traffic on the spatial array and to
> the global buffer for all data types. Specifically, it has to multicast the
> activations, single-cast the filter weights, and then spatially accumulate the
> partial sums across the PE array."

Di dokumen ini NLR juga disebut **no stationary** (istilah dosen: "tanpa
stationary"), karena tidak ada data yang "diam" di MAC seperti pada OS dan WS.

Inti definisinya: **tidak ada data yang ditahan di unit pemroses (MAC) dari satu
operasi ke operasi berikutnya.** Setiap data diambil dari memori (global buffer)
setiap kali dipakai, dan jumlah parsial dikembalikan ke memori.

| | OS (rancangan utama) | WS (larik 4 × 2) | **NLR (rancangan ini)** |
|---|---|---|---|
| Ditahan di MAC | Jumlah parsial (akumulator) | Bobot | **Tidak ada** |
| Bobot | Dari bank, dipakai sekali | Dimuat sekali, dipakai 16 citra | Dari bank, dipakai sekali |
| Masukan | Dari memori, disiarkan ke 8 lajur | Masuk dari kiri, 16 citra | **Dibaca ulang dari memori setiap siklus**, disiarkan ke 8 lajur |
| Jumlah parsial | Tetap di akumulator | Mengalir antar-PE | **Dibaca dari memori, ditambah, ditulis kembali setiap siklus** |

### Penyimpangan dari contoh di Sze (ditulis jujur)

Sze menggambarkan jumlah parsial yang **dijumlahkan antar-PE** (pohon penjumlah)
sebelum kembali ke buffer. Rancangan ini **tidak** memakai pohon penjumlah: setiap
lajur menjumlahkan sendiri melalui memori. Alasannya:

1. **Perbandingan satu variabel.** OS dan NLR hanya berbeda di satu hal, yaitu di
   mana jumlah parsial disimpan (akumulator vs memori M9K). Bank bobot, susunan
   alamat, unit MAC, epilog, dan argmax tetap sama, sehingga selisih yang terukur
   dapat diatribusikan ke dataflow.
2. Pohon penjumlah menuntut susunan bank bobot dan lebar memori masukan yang
   berbeda dari OS (8 masukan per siklus), sehingga OS dan NLR berbeda dalam
   beberapa hal sekaligus.

Prinsip utama NLR, yaitu tidak ada penyimpanan lokal di PE dan semua jenis data
lewat memori, tetap dipenuhi.

## 3. Arsitektur

```
  Memori masukan (mem_d, sama dengan OS)
          │  1 masukan dibaca ULANG setiap siklus, disiarkan ke 8 lajur
          ▼
  ┌──────────┬──────────┬─ ··· ─┬──────────┐
  │ lajur 0  │ lajur 1  │       │ lajur 7  │
  │ bank w0  │ bank w1  │       │ bank w7  │   bobot: sama dengan OS (berkas P8)
  │   MAC    │   MAC    │       │   MAC    │   s_first = s_last = 1 setiap suku
  │ psum M9K │ psum M9K │       │ psum M9K │   memori jumlah parsial per lajur
  └──────────┴──────────┴─ ··· ─┴──────────┘
          │  setelah suku terakhir: epilog (ReLU, geser) → tulis ke mem_d
          ▼
     argmax → hasil (tampilan papan sama dengan OS)
```

Satu operasi pada lajur j, untuk neuron n dan masukan i:

```
psum_baru = psum_lama (dibaca dari memori) + x_i × w[n][i]  → ditulis ke memori
```

Pada suku pertama (i = 0), `psum_lama` diganti bias neuron dari ROM bias (sama
dengan OS), sehingga memori jumlah parsial tidak perlu dikosongkan.

## 4. Urutan pemrosesan dan bahaya baca-setelah-tulis

Memori M9K butuh waktu untuk membaca, dan MAC butuh 2 siklus. Akibatnya nilai
jumlah parsial yang baru ditulis belum bisa langsung dibaca lagi. Kalau satu lajur
mengerjakan neuron yang sama setiap siklus, ia akan membaca nilai lama
(**bahaya baca-setelah-tulis**).

Solusinya: **setiap lajur bergantian mengerjakan K neuron**, sehingga jumlah
parsial suatu neuron baru dibaca lagi K siklus kemudian, setelah nilai barunya
selesai ditulis.

**Lapisan 1** (196 masukan → 64 neuron): lajur j mengerjakan neuron j, j+8, …,
j+56, jadi K = 8, sama dengan pembagian neuron pada OS.

```
untuk i = 0 … 195:            (masukan)
    untuk k = 0 … 7:          (neuron ke-k milik lajur ini, satu per siklus)
        lajur j: psum[k] = psum[k] + x_i × w[j + 8k][i]
```

Total: 196 × 8 = **1.568 siklus**, sama dengan OS.

**Lapisan 2** (64 masukan → 10 neuron): lajur 0–1 punya 2 neuron, lajur 2–7 hanya
1 neuron. K = 2 terlalu kecil untuk menghindari bahaya, jadi setiap masukan diberi
**K₂ = 5 slot** (slot 0–1 terisi, slot 2–4 kosong). Lima adalah jarak aman
terkecil: alamat diberikan pada siklus t, data tiba di MAC pada t + 2, hasil
ditulis pada t + 4, sehingga paling cepat dibaca lagi pada t + 5. Simulasi
memastikan K₂ = 5 menghasilkan keluaran bit-exact.

Total: 64 × 5 = **320 siklus** (OS: 128 siklus). Selisih ini adalah salah satu
biaya NLR.

**Kuras:** setelah tiap lapisan, hasil akhir dibaca dari memori jumlah parsial
satu per siklus: 64 siklus untuk lapisan 1 (lewat epilog, ditulis ke mem_d) dan
10 siklus untuk lapisan 2 (ke argmax).

**Alamat bobot:** memakai berkas bank OS (`1_Python_PC/mem/P8`) **tanpa diubah**.
Alamatnya = (awal lapisan) + k × (jumlah masukan) + i, cukup dihitung dengan
penjumlahan, tanpa pengali.

## 5. Memori jumlah parsial

| | Nilai |
|---|---|
| Jumlah | 8 blok, satu per lajur |
| Lebar × isi | 32 bit × 8 kata (lapisan 1); lapisan 2 memakai kata yang sama |
| Jenis | Simple dual-port: satu port baca dan satu port tulis per siklus |
| Penempatan | Dipaksa ke M9K (`ramstyle = "M9K"`), supaya biaya aksesnya tercatat di Power Analyzer sebagai memori, bukan register |

Pemakaian M9K hasil kompilasi: **21 (sama dengan OS) + 8 = 29 dari 30 blok**.
Laporan Quartus memastikan kedelapan memori jumlah parsial ditempatkan di M9K
(Simple Dual Port), bukan register.

## 6. Siklus dan akses memori per citra

**Siklus** (simulasi RTL, sama dengan penghitung siklus di papan):

| | OS | WS | NLR |
|---|---|---|---|
| Lapisan 1 | 1.568 | – | 1.568 |
| Kuras lapisan 1 | – | – | 64 |
| Lapisan 2 | 128 | – | 320 |
| Kuras lapisan 2 + akhir | – | – | 10 + 3 |
| **Total per citra** | **1.708** | **1.649** | **1.965** |
| Waktu per citra (50 MHz) | 34,16 µs | 32,98 µs | **39,30 µs** |

Waktu per citra = jumlah siklus ÷ 50.000.000 siklus per detik.

**Akses memori** (bit per citra). NLR dari pencacah di testbench
(`tb_papan_nlr.v`, citra 00); OS dan WS dari perhitungan:

| Jenis | OS | WS | NLR |
|---|---|---|---|
| Bobot | ≈ 109 Kbit | ≈ 7 Kbit | 121,1 Kbit (15.136 baca × 8 bit) |
| Masukan | ≈ 14 Kbit | ≈ 53 Kbit | 15,1 Kbit (1.892 baca × 8 bit) |
| Jumlah parsial | 0 | 0 | **843,8 Kbit** (13.184 baca + 13.184 tulis, × 32 bit) |
| Aktivasi lapisan 1 (tulis) | – | – | 0,5 Kbit (64 × 8 bit) |
| **Total** | **≈ 123,5 Kbit** | **≈ 59,8 Kbit** | **980,5 Kbit** |

Bobot NLR sedikit lebih besar dari OS karena bank bobot tetap dibaca pada slot
kosong lapisan 2. Lalu lintas memori NLR sekitar 8× OS dan 16× WS, dan hampir
seluruhnya berasal dari jumlah parsial. Jumlah operasi MAC tetap 13.184, sama
dengan OS.

## 7. Keadilan perbandingan

Sama dengan OS dan WS: chip EP4CE6E22C8, clock 50 MHz, unit MAC (`mac_unit.v`,
varian HARD), 8 MAC, bank bobot berkas P8, ROM bias, epilog, argmax, ROM citra,
tampilan dan tombol papan.

Yang berbeda hanya **pengendali dan memori jumlah parsial**.

## 8. Hasil pengujian

| Tahap | Kriteria lulus | Hasil |
|---|---|---|
| Simulasi RTL (Icarus), 16 citra uji | Kesepuluh akumulator lapisan 2 identik dengan `golden_uji.txt` untuk 16/16 citra | **Lulus**, 18 inferensi lewat tombol, tiap inferensi 1.965 siklus |
| Pencacah di testbench | Jumlah siklus, akses memori, operasi MAC | 13.184 operasi MAC; akses memori di bagian 6 |
| Kompilasi Quartus | Muat di chip, Fmax ≥ 50 MHz | **Lulus**: 2.317 LE (37 %), 1.308 register, M9K 29/30, pengali 9-bit 8/30, Fmax 73,61 MHz (model lambat 85 °C) |
| Uji papan | 16/16 citra cocok; key[3] menampilkan siklus | **Lulus**, 16/16 cocok, tampil 1965 |
| Daya | Alur `6_Daya_FPGA`, confidence High | **Lulus**, confidence High (bekerja dan diam) |

**Sumber daya dibanding OS:** LE hampir sama (2.317 vs 2.306), karena OS dan NLR
hanya berbeda di tempat jumlah parsial disimpan. Fmax lebih rendah (73,61 vs
82,46 MHz) karena jalur dari memori jumlah parsial ke MAC lebih panjang; clock
tetap 50 MHz.

**Daya dan energi** (`4_daya/hasil/daya_nlr.json`). Energi per citra = daya ×
lama satu inferensi (mW × µs = nJ, dibagi 1.000 menjadi µJ):

| | OS | WS | **NLR** |
|---|---|---|---|
| Daya total saat bekerja | 93,91 mW | 108,63 mW | **118,17 mW** |
| Inti dinamis saat bekerja | 21,09 mW | 35,57 mW | **45,14 mW** |
| **Energi per citra** | **3,208 µJ** | **3,582 µJ** | **4,644 µJ** |
| Daya M9K saat bekerja | 9,53 mW | 2,44 mW | **20,34 mW** |
| Daya total saat diam | 89,40 mW | – | 83,96 mW |

Tambahan daya NLR dibanding OS terutama dari M9K (9,53 → 20,34 mW, akibat baca
dan tulis jumlah parsial), sel kombinasional (0,97 → 7,76 mW; penjumlah MAC
menerima jumlah parsial neuron yang berbeda setiap siklus sehingga banyak bit
berganti), dan register (5,38 → 11,50 mW).

Daya saat diam **tidak** dipakai untuk membandingkan dataflow: M9K OS tetap
membaca walau diam (8,71 mW), sedangkan M9K NLR dimatikan saat diam (2,06 mW).
Perbandingan yang adil adalah daya dan energi saat bekerja.

## 9. Struktur folder

```
7_NLR/
  SPESIFIKASI_NLR.md        dokumen ini
  2_verilog/                ctrl_nlr.v, mem_psum.v, top_papan_nlr.v, testbench,
                            skrip simulasi (modul bersama dirujuk dari 2_Verilog)
  3_quartus/                proyek Quartus papan_nlr
  4_daya/                   analisis daya (jalankan_daya_nlr.py, hasil/)
```

## 10. Hal yang perlu dikonfirmasi

1. **Ke dosen:** apakah "tanpa stationary" yang dimaksud adalah *no local reuse*
   seperti di Sze dkk. (2017)?
