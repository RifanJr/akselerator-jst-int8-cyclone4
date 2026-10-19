# MANIFEST — Model Resmi Akselerator JST INT8

Berkas di folder ini adalah **artefak resmi** hasil pelatihan.
Seluruh citra memori, acuan emas, dan vektor uji di proyek ini
diturunkan dari berkas-berkas ini, bukan dari notebook.

## ATURAN

1. **Folder ini tidak boleh diubah.** Kalau isinya berganti, seluruh
   berkas turunan di `mem/` dan `rtl/` wajib dibangkitkan ulang dan
   seluruh verifikasi wajib dijalankan ulang.
2. **Jangan menjalankan ulang notebook pelatihan** kecuali memang
   berniat mengganti model. Notebook sudah memakai
   `torch.manual_seed`, tetapi hasilnya tetap dapat bergeser bila
   dijalankan di lingkungan berbeda (versi PyTorch, BLAS, perangkat).
   Hal itu sudah pernah terjadi pada 24 September 2026 dan membuat
   14,6 persen bobot berubah.
3. Yang menjadi acuan adalah **berkas di folder ini**, bukan notebook.

Dibekukan : 2026-09-24
Sumber    : Training/export/ hasil menjalankan Training_MLP_PyTorch.ipynb

## Model

| | |
|---|---|
| Arsitektur | 196 - 64 - 10, aktivasi ReLU |
| Praproses | MNIST 28x28 -> 14x14, rerata blok 2x2 |
| Akurasi FP32 | 97,45 % |
| Akurasi INT8 | 97,45 % |
| Degradasi | 0,00 poin persentase |

## Lingkungan pelatihan

Model ini dilatih dengan kombinasi berikut. Untuk mengulang pelatihan dan
memperoleh bobot yang sama persis, versi-versi ini harus dipakai.

| | Versi |
|---|---|
| Python | 3.12.10 |
| PyTorch | 2.12.1+cpu |
| NumPy | 1.26.4 |
| Perangkat | CPU (bukan CUDA) |

Seed: `SEED = 42`, dipasang lewat `torch.manual_seed` dan `np.random.seed`.

**Seed saja tidak menjamin hasil yang sama.** Dua sumber acak dalam notebook
(nilai awal bobot dan `torch.randperm` per epoch) memang dikendalikan seed,
tetapi urutan penjumlahan bilangan pecahan bergantung pada versi PyTorch,
pustaka BLAS, dan jumlah thread. Selisih sekecil 1e-7 per batch, terakumulasi
sepanjang 25 epoch x 469 batch, cukup menggeser bobot akhir secara berarti
meski akurasinya nyaris tidak berubah.

Hal itu sudah terjadi: bobot hasil pelatihan sebelumnya berbeda 14,6 persen
dari bobot di folder ini, dengan akurasi 97,41 persen lawan 97,45 persen.

## Format bilangan

Konvensi Qm.n dengan m termasuk bit tanda, m + n = 8.

| Besaran | Format | Skala |
|---|---|---|
| Masukan | Q2.6 | 2^-6 |
| Bobot lapisan 1 dan 2 | Q3.5 | 2^-5 |
| Bias lapisan 1 dan 2 | Q1.7 | 2^-7 |
| Aktivasi tersembunyi | Q5.3 | 2^-3 |

## Penyelarasan skala

| | Lapisan 1 | Lapisan 2 |
|---|---|---|
| Skala hasil kali | 2^-11 | 2^-8 |
| Bias digeser KIRI | 4 | 1 |
| Akumulator digeser KANAN | 8 | 0 |
| ReLU | ya | tidak |

Rumus geser bias: n_hasilkali - n_bias.
Pembulatan: truncate ke arah minus tak hingga (cfg_round = 0).
Saturasi ke 8 bit bertanda. ReLU dikenakan SEBELUM penggeseran.

## Isi berkas

| Berkas | Isinya | Jumlah nilai |
|---|---|---|
| `weights_layer1.coe` | bobot lapisan 1 | 12544 |
| `weights_layer2.coe` | bobot lapisan 2 | 640 |
| `bias_layer1.coe` | bias lapisan 1 | 64 |
| `bias_layer2.coe` | bias lapisan 2 | 10 |
| `input_sample.coe` | citra uji indeks 0 | 196 |
| `model_mlp_196_64_10.pt` | bobot FP32 asli | - |
| `quant_config.txt` | konfigurasi kuantisasi | - |
| `golden_output.txt` | 10 akumulator keluaran citra uji indeks 0 | 10 |

## Sidik jari SHA-256

Dipakai untuk membuktikan berkas tidak berubah. Periksa dengan
`certutil -hashfile <nama> SHA256` di Windows.

| Berkas | SHA-256 |
|---|---|
| `model_mlp_196_64_10.pt` | `0846c08f8a06d3be848381b588c42c970a7df93c0139a42d3840c91bacc2ed14` |
| `weights_layer1.coe` | `e117144b8e27cf3f8dc9ea06223d7a4e81c88d5ac1566158fb931e0c07bad203` |
| `weights_layer2.coe` | `1a7c59a98e642e7bd500209029312b275d8583be17dc5db576052bf937e78a5b` |
| `bias_layer1.coe` | `a476764d264310e3456408e69ccf6fbaab96862be8e61eaedddc0558e29e3247` |
| `bias_layer2.coe` | `9a7b46082d02bbfbc31af8a5315f93e8c658f30f5bb236d97c16a8ab3979f7de` |
| `input_sample.coe` | `79a087bfeecabe7fe17108c16cb004e993a7507c6302a547aa343ae100e7f088` |
| `quant_config.txt` | `d0b742918fa1f3f78809414cf3fa871a674f93da9d65ba594a45fe4f71575645` |
| `golden_output.txt` | `3784d625a5fd288458ef0c1a478cb2a17b0f48a8f5e5c99b7cbafaf3420fc5b4` |

