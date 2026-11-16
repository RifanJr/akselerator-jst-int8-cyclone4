# 5_PC_Linux — Pembanding PC di Linux dengan inti terisolasi

Model MLP 196–64–10 yang **sama** dengan akselerator FPGA dijalankan di CPU
laptop (Ubuntu) untuk membandingkan kecepatan, kestabilan waktu, daya, dan
energi per citra. Inti uji **diisolasi oleh kernel**, sehingga selama
pengukuran **hanya program inferensi yang berjalan** di inti itu, dan hal ini
**dibuktikan** dengan rekaman penjadwal kernel (ftrace).

---

## Isi folder

| Berkas | Isi |
|---|---|
| `model_pc.py` | Dua versi model dari `1_Python_PC/Training/export_final`: **INT8 (NumPy)** dengan aritmetika persis seperti FPGA, dan **FP32 (PyTorch)** sebagai cara lazim di PC. Jalankan langsung untuk memeriksa kebenaran. |
| `ukur_pc_linux.py` | Pengukuran: `waktu` (latensi per citra dan throughput), `beban` (pola diam–beban–diam dengan daya, energi, dan bukti isolasi), `ulang` (satu sesi daya penuh, INT8 dan FP32 bergantian, beserta rangkumannya) |
| `jalankan_resmi.sh` | Satu perintah untuk seluruh pengukuran resmi (cek kondisi → `waktu --inti 2` → `waktu` → `ulang`) |
| `metrik_akurasi.py` | Accuracy, precision, recall, F1 per digit dan rata-rata, untuk INT8 dan FP32 |
| `hasil/` | Data resmi: JSON per pengukuran, rangkuman sesi, log layar, rekaman ftrace mentah (`hasil/ftrace/`) |
| `hasil/uji_coba/` | Uji coba saat menyiapkan metode (desktop masih aktif); **bukan** data resmi |

## Kebenaran model

```
python 5_PC_Linux/model_pc.py
```

- INT8: kesepuluh akumulator lapisan 2 untuk 16/16 citra **identik** dengan
  `1_Python_PC/uji/golden_uji.txt`, sama dengan FPGA.
- Akurasi 10.000 citra uji: INT8 97,45 %, FP32 97,45 %.

## Lingkungan

| | |
|---|---|
| Laptop | Lenovo IdeaPad Gaming 3 15ARH7 (82SB) |
| CPU | AMD Ryzen 5 7535HS (6 inti fisik / 12 thread) |
| RAM | 24 GB terpasang (Linux melaporkan 18,7 GiB dapat dipakai) |
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-43-generic |
| Python / NumPy / PyTorch | 3.12.10 / 1.26.4 / 2.12.1+cpu |
| Mode daya | Balanced (`power-profiles-daemon`; amd-pstate-epp, EPP `balance_performance`) |
| Inti uji | inti fisik 2 = CPU 4 (CPU 5, thread kembarnya, dibiarkan kosong) |
| Kondisi | charger tersambung, **mode teks (desktop dimatikan)**, WiFi/Bluetooth mati |

Penomoran inti: inti fisik K = CPU 2K dan 2K+1
(dicek dari `/sys/devices/system/cpu/cpu4/topology/thread_siblings_list` = `4-5`).

## Isolasi inti

Parameter kernel, dipasang lewat berkas tambahan GRUB
`/etc/default/grub.d/isolasi-uji.cfg` (berkas utama `/etc/default/grub` tidak diubah):

```
isolcpus=domain,managed_irq,4,5 nohz_full=4,5 rcu_nocbs=4,5 irqaffinity=0-3,6-11
```

| Parameter | Fungsi |
|---|---|
| `isolcpus=domain,managed_irq,4,5` | CPU 4–5 dikeluarkan dari penjadwal umum: proses lain tidak ditaruh di sana; interupsi yang dikelola driver dijauhkan |
| `nohz_full=4,5` | detak timer kernel (1.000 Hz) dimatikan selama hanya satu program berjalan |
| `rcu_nocbs=4,5` | pekerjaan pembersihan kernel (RCU callback) dipindah ke inti lain |
| `irqaffinity=0-3,6-11` | interupsi perangkat secara bawaan diarahkan ke CPU selain 4–5 |

Program inferensi masuk ke CPU 4 lewat `os.sched_setaffinity` (prioritas
normal). `irqbalance` tidak terpasang, jadi tidak ada yang memindahkan
interupsi kembali.

Memasang (sekali, lalu reboot):
```
echo 'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT isolcpus=domain,managed_irq,4,5 nohz_full=4,5 rcu_nocbs=4,5 irqaffinity=0-3,6-11"' | sudo tee /etc/default/grub.d/isolasi-uji.cfg
sudo update-grub
```
Mencabut: `sudo rm /etc/default/grub.d/isolasi-uji.cfg && sudo update-grub`, lalu reboot.
Cek aktif: `cat /sys/devices/system/cpu/isolated` harus `4-5`.

## Metode

### Bukti bahwa hanya inferensi yang berjalan

Direkam selama jendela pengukuran (`waktu`) dan selama fase beban (`beban`):

| Bukti | Sumber | Yang ditunjukkan |
|---|---|---|
| **Siapa saja yang berjalan di CPU 4 dan 5** | ftrace, peristiwa `sched_switch` (jam `mono`) | daftar semua tugas yang pernah dijadwalkan beserta lamanya |
| Persen inti untuk inferensi | dari ftrace | waktu inferensi di CPU 4 ÷ lama jendela × 100 % |
| Sela paksa | `nonvoluntary_ctxt_switches` proses inferensi | berapa kali inferensi diusir dari inti |
| Porsi waktu per CPU | `/proc/stat` | user / system / idle / interupsi per CPU |
| Interupsi | selisih `/proc/interrupts` dan `/proc/softirqs` | gangguan perangkat dan timer yang masuk ke CPU 4–5 |
| Kelengkapan rekaman | `per_cpu/cpuN/stats` (overrun) | tidak ada peristiwa yang hilang |

### Daya dan energi

Dibaca langsung dari penghitung energi CPU (RAPL AMD, lewat MSR), **oleh proses
inferensi di CPU 4 sendiri** (pembacaan lokal, tanpa interupsi ke inti lain),
untuk dua lingkup:

- **paket**: seluruh chip CPU (keenam inti, cache L3, pengendali memori, dll.);
- **inti 2**: hanya inti yang mengerjakan inferensi.

Penghitung energi bertambah terus (satuan joule). Energi dibaca 5 detik
setelah awal dan 5 detik sebelum akhir tiap fase (tepi dibuang supaya
transisi antarfase tidak ikut terhitung):

- daya fase (W) = selisih energi (J) ÷ selisih waktu (s), karena 1 W = 1 J/s;
- daya diam = rata-rata fase diam sebelum dan sesudah beban;
- selisih daya = daya beban − daya diam;
- **energi total per citra** = daya beban ÷ laju (citra/s);
- energi tambahan per citra = selisih daya ÷ laju
  (W ÷ citra/s = J per citra; × 10⁶ = µJ per citra);
- frekuensi efektif = selisih penghitung siklus APERF ÷ selisih waktu (untuk
  memastikan tidak ada penurunan frekuensi karena panas).

### Waktu

Yang diukur hanya **inferensi**: dari vektor 196 masukan di memori sampai
argmax; memuat citra dan praproses tidak dihitung, sama dengan sisi FPGA.
Pemanasan 1.000 kali, lalu 10.000 inferensi satu citra, tiap inferensi diukur
sendiri (`perf_counter_ns`; termasuk overhead pemanggilan Python, yang
merupakan bagian dari cara lazim menjalankan model di PC); throughput untuk
batch 1, 16 (sama dengan batch WS), dan 10.000. Sebelum jendela ukur, setiap jalur kode dijalankan sekali
(pra-pemanasan) supaya pustaka sudah termuat dari disk.

## Cara mengulang

Kondisi: charger tersambung, mode daya Balanced, semua aplikasi ditutup,
WiFi/Bluetooth mati. Pindah ke mode teks (`Ctrl+Alt+F3`), login, lalu:

```
sudo systemctl isolate multi-user.target
cd ~/skripsi/Alur_Utama
sudo bash 5_PC_Linux/jalankan_resmi.sh
sudo systemctl isolate graphical.target
```

`jalankan_resmi.sh` berhenti bila: tidak dijalankan sebagai root, isolasi
CPU 4–5 atau `nohz_full` tidak aktif, charger tidak tersambung, atau mode daya
bukan Balanced. Lama ±33 menit. Perintah satuan:

```
sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py waktu --inti 2
sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py ulang --kali 5 --detik 60 --inti 2
```

## Hasil resmi (16–17 November 2026, mode teks)

Log: `hasil/log_resmi_20261116_235042.txt`.

### Bukti isolasi

Sepuluh pengukuran beban (5 × INT8, 5 × FP32, masing-masing fase 60 detik):

| Bukti | Hasil |
|---|---|
| Inferensi di CPU 4 (ftrace) | **99,99998–99,99999 %** dari fase beban |
| Tugas lain di CPU 4 | hanya `kworker/4:1` (thread kernel milik CPU 4), **8–11 µs** per 60 detik |
| Sela paksa | 1 per pengukuran (sama dengan yang terlihat di ftrace) |
| CPU 5 (kembar) | tidak ada pergantian tugas; `/proc/stat` idle 100 % |
| `/proc/stat` CPU 4 | user 100 % |
| Interupsi CPU 4 | ±36–41 per 60 detik (timer ±16, CAL ±11, softirq timer ±10) |
| Rekaman hilang | 0 |
| Pemakaian CPU proses | 100,00 % satu prosesor logis |
| Frekuensi efektif saat beban | 4.413–4.461 MHz (tanpa penurunan karena panas) |
| Suhu maksimum | 86,3 °C (INT8), 78,8 °C (FP32) |

`waktu --inti 2`: inferensi 99,9968 % dari jendela ukur (sisanya proses yang
sama menunggu disk saat menghitung statistik, bukan saat inferensi diukur;
tugas lain hanya `kworker/4:1` 10 µs).

### Latensi dan throughput (`hasil/waktu_inti2_20261116_235044.json`)

Satu thread, dikunci ke inti 2 yang terisolasi:

| Model | Median | p95 | p99 | Simpangan | Throughput 1 citra | Batch 16 | Batch 10.000 |
|---|---|---|---|---|---|---|---|
| INT8 (NumPy) | **15,79 µs** | 16,18 µs | 17,24 µs | 0,32 µs | 61.809 citra/s | 130.413 citra/s | 140.940 citra/s |
| FP32 (PyTorch) | 20,41 µs | 20,89 µs | 24,72 µs | 0,79 µs | 48.826 citra/s | 560.871 citra/s | 3.095.786 citra/s |

Tanpa kunci inti, thread bawaan (`hasil/waktu_20261116_235105.json`): INT8
median 15,80 µs; FP32 batch 10.000 mencapai 7.729.600 citra/s.

### Daya dan energi (`hasil/sesi_20261116_235145.json`, 5 ulangan, rata-rata ± simpangan)

| | INT8 (NumPy) | FP32 (PyTorch) |
|---|---|---|
| Laju selama beban | 62.101 ± 220 citra/s | 48.057 ± 783 citra/s |
| Daya paket: diam / beban | 5,79 / 21,75 ± 0,18 W | 5,79 / 20,96 ± 0,20 W |
| Daya inti 2: diam / beban | 0,000 / 10,77 ± 0,03 W | 0,000 / 10,93 ± 0,12 W |
| Selisih daya paket | 15,96 ± 0,15 W | 15,18 ± 0,18 W |
| Selisih daya inti 2 | 10,77 ± 0,03 W | 10,93 ± 0,12 W |
| **Energi total per citra (paket)** | **350,2 ± 2,3 µJ** | **436,2 ± 4,6 µJ** |
| **Energi total per citra (inti 2)** | **173,3 ± 0,9 µJ** | **227,4 ± 4,3 µJ** |
| Energi tambahan per citra (paket) | 257,0 ± 2,1 µJ | 315,8 ± 2,8 µJ |

Daya inti 2 saat diam 0,000 W karena inti terisolasi tidur penuh; akibatnya
energi total inti = energi tambahan inti.

### Akurasi (`hasil/metrik_akurasi.json`)

```
python 5_PC_Linux/metrik_akurasi.py
```

10.000 citra uji MNIST. Untuk setiap digit: precision = tebakan digit itu yang
benar ÷ semua tebakan digit itu; recall = citra digit itu yang tertebak benar ÷
semua citra digit itu; F1 = 2 × precision × recall ÷ (precision + recall).
Rata-rata makro = rata-rata biasa ke-10 digit:

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| INT8 (= FPGA) | 97,45 % | 97,43 % | 97,43 % | 97,43 % |
| FP32 (PyTorch) | 97,45 % | 97,43 % | 97,43 % | 97,43 % |

- Hasil INT8 berlaku juga untuk FPGA, karena keduanya identik bit per bit.
- INT8 dan FP32 menebak berbeda pada 35 dari 10.000 citra; jumlah tebakan
  benarnya kebetulan sama.
- F1 terendah pada digit 8 dan 9 (±96,6 %), tertinggi pada digit 1 dan 0
  (±98,5 %). Rincian per digit dan matriks kebingungan: `hasil/metrik_akurasi.json`.

## Catatan

- Daya berasal dari penghitung energi di dalam CPU (RAPL), bukan pengukuran
  arus fisik, sama halnya dengan daya FPGA yang merupakan perkiraan Power
  Analyzer.
- Isolasi tidak menghapus seluruh aktivitas kernel: thread kernel milik inti itu
  sendiri dan sedikit interupsi timer tetap ada. Semuanya tercatat dan terukur
  (lihat Bukti isolasi).
