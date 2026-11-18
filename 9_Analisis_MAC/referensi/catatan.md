# Catatan referensi (Tugas 1)

| Kunci | Status | Yang masih harus dilakukan |
|---|---|---|
| baugh-wooley-1973 | Judul dan jurnal cocok dengan beberapa indeks (scilit, bohrium) | Cek volume/nomor/halaman/DOI di IEEE Xplore (akses kampus) |
| parhami-2010 | Edisi 2, OUP, ISBN 9780195328486 cocok dengan katalog | Cek halaman hak cipta bila bukunya dipinjam |
| intel-cyclone4-hb-v1-ch4 | Halaman unduhan resmi ditemukan (dok. 654776) | [Laks] unduh PDF ke folder ini; catat nomor dokumen dan versi |

## Yang dicari dari handbook bab 4 (untuk pembahasan "algoritma HARD")
- Struktur satu blok: 18×18, dapat dipecah menjadi dua 9×9
- Register masukan dan keluaran opsional; kendali bertanda (signa/signb)
- Jumlah blok untuk EP4CE6 (diharapkan 15 blok 18×18 = 30 pengali 9×9)
- Kalimat yang menyatakan apa yang tidak dipublikasikan tentang struktur internal (bila ada)

Sumber pencarian (4 Nov 2026):
- https://scilit.com/publications/778dc9fed5452b971598bea798425cca
- https://www.tenlong.com.tw/products/9780195328486
- https://www.intel.com/content/www/us/en/content-details/654776/cyclone-iv-device-handbook-volume-1-chapter-4-embedded-multipliers.html

## Isi handbook bab 4 yang dipakai (dibaca 4 Nov 2026 dari `cyclone4-handbook.pdf`)
Bab 4 "Embedded Multipliers in Cyclone IV Devices", nomor dokumen CYIV-51004-1.1, Februari 2010. Halaman 4–1 sampai 4–5.
- Satu blok pengali embedded dapat dikonfigurasi sebagai satu pengali 18 × 18 atau dua pengali 9 × 9 independen (hlm. 4–1, 4–4).
- EP4CE6: 15 blok = 30 pengali 9 × 9 atau 15 pengali 18 × 18 (Tabel 4–1, hlm. 4–2). Cocok dengan laporan Quartus (8/30 terpakai pada HARD).
- Tiap blok terdiri atas tahap pengali, register masukan dan keluaran, serta antarmuka masukan/keluaran (hlm. 4–2, Gambar 4–2). Register bersifat opsional per sinyal.
- Sinyal `signa`/`signb` menentukan operand bertanda atau tidak; hasil bertanda bila salah satu operand bertanda; presisi penuh (hlm. 4–3, 4–4, Tabel 4–2). Dalam mode 9 × 9, dua pengali dalam satu blok berbagi `signa`/`signb`.
- Untuk fungsi multiplier-accumulator, bagian pengali memakai blok embedded dan penjumlah/akumulator dibangun di LE (catatan hlm. 4–4). Ini sama dengan susunan unit MAC varian HARD.
- Handbook TIDAK menjelaskan algoritma atau struktur gerbang di dalam tahap pengali. Jadi skripsi tidak boleh mengklaim Booth/Wallace untuk HARD; yang dapat dikatakan: blok rangkaian khusus berukuran tetap dengan register opsional.
- Tambahan (bukan cakupan saat ini): pengali lunak dapat dibuat memakai M9K sebagai tabel (AN 306) — dapat disebut di saran pengembangan.
