# Spesifikasi rancangan tanpa stationary (No Local Reuse, NLR)

Status: **draf untuk disetujui sebelum menulis kode.** Angka siklus dan akses
memori di dokumen ini masih **perkiraan dari perhitungan**, belum hasil simulasi.

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
**K₂ slot** (sebagian slot kosong). K₂ adalah jarak aman terkecil, diperkirakan
**5 siklus**, dan dipastikan dari simulasi.

Total: 64 × K₂ ≈ **320 siklus** (OS: 128 siklus). Selisih ini adalah salah satu
biaya NLR.

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

Pemakaian M9K diperkirakan **21 (sama dengan OS) + 8 = 29 dari 30 blok**. Ini
sudah ketat. Kalau tidak muat, alternatifnya akan dibahas sebelum diubah.

## 6. Perkiraan siklus dan akses memori per citra

**Siklus** (dihitung dari urutan di bagian 4, belum simulasi):

| | OS | WS | NLR (perkiraan) |
|---|---|---|---|
| Lapisan 1 | 1.568 | – | 1.568 |
| Lapisan 2 | 128 | – | ≈ 320 |
| Total per citra | 1.708 | 1.649 | **≈ 1.900** |

**Akses memori** (bit per citra):

| Jenis | OS | WS | NLR (perkiraan) |
|---|---|---|---|
| Bobot | ≈ 109 Kbit | ≈ 7 Kbit | ≈ 109 Kbit |
| Masukan | ≈ 14 Kbit | ≈ 53 Kbit | ≈ 15 Kbit |
| Jumlah parsial | 0 | 0 | **≈ 840 Kbit** (13.184 operasi × (32 bit baca + 32 bit tulis)) |
| **Total** | **≈ 123,5 Kbit** | **≈ 59,8 Kbit** | **≈ 965 Kbit** |

Perkiraan ini menunjukkan biaya NLR: lalu lintas memorinya sekitar 8× OS dan 16×
WS. Angka resminya diambil dari pencacah di simulasi.

## 7. Keadilan perbandingan

Sama dengan OS dan WS: chip EP4CE6E22C8, clock 50 MHz, unit MAC (`mac_unit.v`,
varian HARD), 8 MAC, bank bobot berkas P8, ROM bias, epilog, argmax, ROM citra,
tampilan dan tombol papan.

Yang berbeda hanya **pengendali dan memori jumlah parsial**.

## 8. Rencana pengujian

| Tahap | Kriteria lulus |
|---|---|
| Simulasi RTL (Icarus), 16 citra uji | Kesepuluh akumulator lapisan 2 identik dengan `golden_uji.txt` untuk 16/16 citra |
| Pencacah di testbench | Jumlah siklus, baca/tulis memori jumlah parsial, baca bobot, baca masukan |
| Kompilasi Quartus | Muat di chip, Fmax ≥ 50 MHz; catat LE, register, M9K, pengali |
| Uji papan | 16/16 citra cocok; tombol S4 menampilkan siklus per citra |
| Daya | Alur `6_Daya_FPGA` (jendela bekerja dan diam, VCD netlist, confidence High) |

## 9. Struktur folder

```
7_NLR/
  SPESIFIKASI_NLR.md        dokumen ini
  2_verilog/                ctrl_nlr.v, mem_psum.v, top_papan_nlr.v, testbench,
                            skrip simulasi (modul bersama dirujuk dari 2_Verilog)
  3_quartus/                proyek Quartus papan_nlr
  4_daya/                   analisis daya (setelah RTL lulus)
```

## 10. Hal yang perlu dikonfirmasi

1. **Ke dosen:** apakah "tanpa stationary" yang dimaksud adalah *no local reuse*
   seperti di Sze dkk. (2017)?
2. **K₂ untuk lapisan 2:** dipastikan dari simulasi (perkiraan 5).
3. **M9K 29/30:** kalau tidak muat, dibahas dulu sebelum mengubah rancangan.
