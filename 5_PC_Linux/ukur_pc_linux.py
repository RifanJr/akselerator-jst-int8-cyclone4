#!/usr/bin/env python3
"""
Pengukuran kinerja model pembanding PC di LINUX (Ubuntu) pada inti terisolasi.

Model diambil dari model_pc.py di folder yang sama (INT8 NumPy, bit-exact dengan
FPGA; FP32 PyTorch). Ciri pengukuran:
  - inti uji diisolasi kernel (isolcpus, nohz_full, rcu_nocbs, irqaffinity;
    dipasang lewat GRUB, lihat README), sehingga hanya inferensi yang berjalan;
  - BUKTI isolasi direkam: ftrace peristiwa sched_switch (siapa saja yang
    berjalan di CPU uji dan berapa lama), sela paksa (nonvoluntary context
    switch) proses inferensi, dan selisih interupsi per CPU;
  - daya dan energi dibaca langsung dari penghitung energi CPU (RAPL AMD):
    paket (seluruh chip) dan inti uji.

Yang diukur hanya INFERENSI: dari vektor 196 masukan yang sudah ada di memori
sampai argmax, sama dengan sisi FPGA yang hanya menghitung siklus akselerator.

Perintah (dari folder Alur_Utama; bukti dan daya butuh root):
    sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py waktu --inti 2
    sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py beban --model int8 --detik 60 --inti 2
    sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py ulang --kali 5 --detik 60 --inti 2

--inti K: proses dikunci ke inti fisik K (prosesor logis 2K) dengan
        os.sched_setaffinity, prioritas normal (nice 0). Thread kembar SMT inti
        K (prosesor logis 2K+1) dibiarkan kosong. Penomoran dicek dari
        thread_siblings_list sebelum mengunci. Pengukuran resmi: K = 2.

waktu:  latensi: pemanasan 1.000 kali, lalu 10.000 inferensi satu citra, tiap
        inferensi diukur sendiri dengan perf_counter_ns. Throughput: batch 1,
        16 (sama dengan batch WS), dan 10.000. Dengan --inti, bukti ftrace
        mencakup seluruh jendela pengukuran.

beban:  diam N detik -> inferensi satu citra berulang N detik -> diam N detik.
        Energi dibaca 5 detik setelah awal dan 5 detik sebelum akhir tiap fase
        (tepi dibuang supaya transisi antarfase tidak ikut terhitung). Rumus:
          daya fase (W)        = selisih energi (J) / selisih waktu (s)
          daya diam            = rata-rata fase diam sebelum dan sesudah
          selisih daya         = daya beban - daya diam
          energi total/citra   = daya beban / laju (citra per detik)
          energi tambahan/citra= selisih daya / laju
          (W / (citra/s) = J per citra; x 1e6 = uJ per citra)
          frekuensi efektif    = selisih APERF (siklus) / selisih waktu
        Bukti ftrace mencakup seluruh fase beban.

Hasil ditulis ke 5_PC_Linux/hasil/; rekaman ftrace mentah ke hasil/ftrace/.
"""
import argparse
import gc
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
MODEL_PC = DI_SINI                           # folder berisi model_pc.py
HASIL = DI_SINI / "hasil"
HASIL_FTRACE = HASIL / "ftrace"
TRACE = Path("/sys/kernel/tracing")

LATENSI_PEMANASAN = 1000
LATENSI_N = 10000
BATCH = (1, 16, 10000)
DURASI_THROUGHPUT = 3.0          # detik per ukuran batch
TEPI_DETIK = 5.0                 # dibuang di awal dan akhir tiap fase

# MSR AMD (Family 19h): satuan energi, energi inti, energi paket, siklus aktual
MSR_SATUAN_RAPL = 0xC0010299
MSR_ENERGI_INTI = 0xC001029A
MSR_ENERGI_PAKET = 0xC001029B
MSR_APERF = 0xE8


# ---------------------------------------------------------------------------
#  Utilitas
# ---------------------------------------------------------------------------
def jalankan(perintah):
    try:
        return subprocess.run(perintah, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def baca(jalur):
    """Isi berkas teks (mis. /sys/...), atau "" bila tidak ada / tidak boleh dibaca."""
    try:
        return Path(jalur).read_text().strip()
    except Exception:
        return ""


def tulis(jalur, isi):
    with open(jalur, "w") as f:
        f.write(isi)


def root():
    return os.geteuid() == 0


def milik_pengguna(jalur):
    """Saat dijalankan dengan sudo, kembalikan kepemilikan berkas ke pengguna asli."""
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if root() and uid and gid:
        try:
            os.chown(jalur, int(uid), int(gid))
        except OSError:
            pass


def siapkan_folder(folder):
    folder.mkdir(parents=True, exist_ok=True)
    milik_pengguna(folder.parent if folder == HASIL_FTRACE else folder)
    milik_pengguna(folder)


def simpan_json(berkas, data):
    berkas.write_text(json.dumps(data, indent=2), encoding="utf-8")
    milik_pengguna(berkas)


def daftar_cpu(teks):
    """'4-5' atau '4,5' atau '' -> {4, 5}."""
    hasil = set()
    for bagian in teks.split(","):
        bagian = bagian.strip()
        if not bagian:
            continue
        a, _, b = bagian.partition("-")
        hasil |= set(range(int(a), int(b or a) + 1))
    return hasil


def suhu_cpu():
    """Suhu Tctl CPU (k10temp) dalam derajat Celsius, atau None."""
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        if baca(h / "name") == "k10temp":
            nilai = baca(h / "temp1_input")
            return int(nilai) / 1000 if nilai else None
    return None


# ---------------------------------------------------------------------------
#  Lingkungan
# ---------------------------------------------------------------------------
def info_lingkungan():
    import numpy as np
    import torch
    cpu = ""
    for baris in baca("/proc/cpuinfo").splitlines():
        if baris.startswith("model name"):
            cpu = baris.split(":", 1)[1].strip()
            break
    baterai, listrik = [], []
    for d in sorted(Path("/sys/class/power_supply").glob("*")):
        jenis = baca(d / "type")
        if jenis == "Battery":
            baterai.append(f"{d.name} {baca(d / 'capacity')}% status={baca(d / 'status')}")
        elif jenis == "Mains":
            listrik.append(f"{d.name} online={baca(d / 'online')}")
    cpufreq = "/sys/devices/system/cpu/cpu0/cpufreq/"
    mode = {
        "power_profiles_daemon": jalankan(["powerprofilesctl", "get"]),
        "platform_profile": baca("/sys/firmware/acpi/platform_profile"),
        "driver": baca(cpufreq + "scaling_driver"),
        "amd_pstate": baca("/sys/devices/system/cpu/amd_pstate/status"),
        "governor": baca(cpufreq + "scaling_governor"),
        "epp": baca(cpufreq + "energy_performance_preference"),
    }
    return {
        "waktu": datetime.now().isoformat(timespec="seconds"),
        "cpu": cpu or platform.processor(),
        "cpu_logis": os.cpu_count(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "skema_daya": ", ".join(f"{k}={v}" for k, v in mode.items() if v),
        "baterai": "; ".join(baterai + listrik) or "tidak ada",
        "desktop": jalankan(["systemctl", "is-active", "graphical.target"]),
        "root": root(),
        "isolasi": {
            "cmdline": baca("/proc/cmdline"),
            "isolated": baca("/sys/devices/system/cpu/isolated"),
            "nohz_full": baca("/sys/devices/system/cpu/nohz_full"),
        },
    }


def atur_thread(mode):
    """Harus dipanggil SEBELUM numpy/torch dimuat."""
    if mode == "1":
        for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[v] = "1"


def kunci_inti(k):
    """Kunci proses ini ke inti fisik k (prosesor logis 2k), prioritas normal.

    Sebelum mengunci, dicek bahwa prosesor logis 2k memang thread pertama inti
    fisik k (thread_siblings_list harus "2k-2k+1" atau "2k,2k+1").
    """
    if k is None:
        return {"inti_fisik": None}
    logis = 2 * k
    saudara = baca(f"/sys/devices/system/cpu/cpu{logis}/topology/thread_siblings_list")
    if saudara not in (f"{logis}-{logis + 1}", f"{logis},{logis + 1}"):
        sys.exit(f"prosesor logis {logis} bukan thread pertama inti fisik {k} "
                 f"(thread_siblings_list = {saudara!r})")
    try:
        os.sched_setaffinity(0, {logis})
    except OSError as e:
        sys.exit(f"gagal mengunci proses ke prosesor logis {logis}: {e}")
    ok_affinity = os.sched_getaffinity(0) == {logis}
    if not ok_affinity:
        sys.exit(f"gagal mengunci proses ke prosesor logis {logis}")
    terisolasi = {logis, logis + 1} <= daftar_cpu(baca("/sys/devices/system/cpu/isolated"))
    return {"inti_fisik": k, "prosesor_logis": logis, "affinity_ok": ok_affinity,
            "thread_siblings": saudara, "terisolasi": terisolasi,
            "prioritas": f"normal (nice {os.nice(0)})"}


def peringatan_isolasi(inti):
    if inti is None:
        return
    if not root():
        print("PERINGATAN: tidak dijalankan sebagai root -> bukti ftrace dan daya TIDAK direkam.\n"
              "           Jalankan dengan: sudo ~/skripsi/.venv/bin/python ...", flush=True)
    if not {2 * inti, 2 * inti + 1} <= daftar_cpu(baca("/sys/devices/system/cpu/isolated")):
        print(f"PERINGATAN: CPU {2 * inti}-{2 * inti + 1} tidak terisolasi (isolcpus belum aktif).",
              flush=True)


# ---------------------------------------------------------------------------
#  Bukti: sela paksa, interupsi, ftrace
# ---------------------------------------------------------------------------
def tid_proses():
    return sorted(int(t) for t in os.listdir("/proc/self/task"))


def sela_proses():
    """Jumlah context switch semua thread proses ini: (sukarela, paksa)."""
    sukarela = paksa = 0
    for t in os.listdir("/proc/self/task"):
        for baris in baca(f"/proc/self/task/{t}/status").splitlines():
            if baris.startswith("voluntary_ctxt_switches"):
                sukarela += int(baris.split()[1])
            elif baris.startswith("nonvoluntary_ctxt_switches"):
                paksa += int(baris.split()[1])
    return sukarela, paksa


def potret_interupsi(cpus):
    """{nama: {cpu: jumlah}} dari /proc/interrupts dan /proc/softirqs untuk CPU tertentu."""
    hasil = {}
    for berkas, awalan in (("/proc/interrupts", ""), ("/proc/softirqs", "softirq ")):
        baris = baca(berkas).splitlines()
        if not baris:
            continue
        kolom = {nama: i for i, nama in enumerate(baris[0].split())}
        for b in baris[1:]:
            bagian = b.split()
            if not bagian:
                continue
            nama = awalan + bagian[0].rstrip(":")
            nilai = bagian[1:]
            isi = {}
            for c in cpus:
                i = kolom.get(f"CPU{c}")
                if i is not None and i < len(nilai) and nilai[i].isdigit():
                    isi[c] = int(nilai[i])
            if isi:
                hasil[nama] = isi
    return hasil


KOLOM_STAT = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal")


def potret_stat(cpus):
    """Waktu per CPU dari /proc/stat (satuan tick kernel, USER_HZ)."""
    hasil = {}
    for baris in baca("/proc/stat").splitlines():
        bagian = baris.split()
        if bagian and bagian[0].startswith("cpu") and bagian[0][3:].isdigit() \
                and int(bagian[0][3:]) in cpus:
            hasil[int(bagian[0][3:])] = dict(zip(KOLOM_STAT, map(int, bagian[1:1 + len(KOLOM_STAT)])))
    return hasil


def selisih_stat(awal, akhir):
    """Porsi waktu tiap CPU selama jendela: user/system/idle/... dalam detik dan persen."""
    tick = os.sysconf("SC_CLK_TCK")
    hasil = {}
    for c, b in akhir.items():
        a = awal.get(c, b)
        d = {k: (b[k] - a[k]) / tick for k in KOLOM_STAT}
        total = sum(d.values())
        hasil[f"cpu{c}"] = {"detik": d, "total_detik": total,
                            "persen": {k: (v / total * 100 if total else 0.0) for k, v in d.items()}}
    return hasil


def selisih_interupsi(awal, akhir, cpus):
    hasil = {f"cpu{c}": {} for c in cpus}
    for nama, isi in akhir.items():
        for c, v in isi.items():
            d = v - awal.get(nama, {}).get(c, v)
            if d:
                hasil[f"cpu{c}"][nama] = d
    return hasil


class Ftrace:
    """Merekam peristiwa sched_switch di CPU tertentu lewat tracefs.

    Jam rekaman = "mono" (CLOCK_MONOTONIC), sama dengan time.monotonic(),
    sehingga jendela pengukuran bisa dicocokkan. Pengaturan tracefs dikembalikan
    seperti semula setelah selesai.
    """
    BERKAS = ("tracing_on", "tracing_cpumask", "events/sched/sched_switch/enable")

    def __init__(self, cpus):
        self.cpus = sorted(cpus)
        self.awal = {}
        self.penanda = None

    def mulai(self):
        for b in self.BERKAS:
            self.awal[b] = baca(TRACE / b)
        jam = re.search(r"\[(\S+)\]", baca(TRACE / "trace_clock"))
        self.awal["trace_clock"] = jam.group(1) if jam else "local"
        tulis(TRACE / "tracing_on", "0")
        tulis(TRACE / "trace_clock", "mono")
        tulis(TRACE / "tracing_cpumask", format(sum(1 << c for c in self.cpus), "x"))
        tulis(TRACE / "events/sched/sched_switch/enable", "1")
        tulis(TRACE / "trace", "")                       # kosongkan buffer
        self.penanda = open(TRACE / "trace_marker", "w")
        tulis(TRACE / "tracing_on", "1")

    def tandai(self, teks):
        """Penanda fase di rekaman (memudahkan membaca berkas mentah)."""
        if self.penanda:
            try:
                self.penanda.write(teks + "\n")
                self.penanda.flush()
            except OSError:
                pass

    def selesai(self):
        """Hentikan, ambil teks rekaman per CPU, kembalikan pengaturan."""
        tulis(TRACE / "tracing_on", "0")
        teks = {c: baca(TRACE / f"per_cpu/cpu{c}/trace") for c in self.cpus}
        statistik = {}
        for c in self.cpus:
            st = {}
            for baris in baca(TRACE / f"per_cpu/cpu{c}/stats").splitlines():
                k, _, v = baris.partition(":")
                if k.strip() in ("entries", "overrun"):
                    st[k.strip()] = int(v.split()[0])
            statistik[c] = st
        if self.penanda:
            self.penanda.close()
            self.penanda = None
        self.pulihkan()
        return teks, statistik

    def pulihkan(self):
        try:
            tulis(TRACE / "tracing_on", "0")
            tulis(TRACE / "events/sched/sched_switch/enable",
                  self.awal.get("events/sched/sched_switch/enable", "0"))
            if self.awal.get("tracing_cpumask"):
                tulis(TRACE / "tracing_cpumask", self.awal["tracing_cpumask"])
            tulis(TRACE / "trace_clock", self.awal.get("trace_clock", "local"))
            tulis(TRACE / "tracing_on", self.awal.get("tracing_on", "1") or "1")
        except OSError:
            pass


POLA_SWITCH = re.compile(
    r"\[(\d+)\]\s+(?:\S+\s+)?(\d+\.\d+):\s+sched_switch:\s+"
    r"prev_comm=(.*?) prev_pid=(-?\d+) .*?==> next_comm=(.*?) next_pid=(-?\d+)")


def ringkas_ftrace(teks, a, b, pid_inferensi):
    """Siapa saja yang berjalan di satu CPU selama jendela [a, b] (detik, jam mono)."""
    ev = []
    for baris in teks.splitlines():
        m = POLA_SWITCH.search(baris)
        if m:
            ev.append((float(m.group(2)), m.group(3), int(m.group(4)), m.group(5), int(m.group(6))))
    ev.sort()
    jendela = b - a
    if not ev:
        # Tidak ada satu pun pergantian tugas di CPU ini selama rekaman: siapa yang
        # berjalan tidak bisa disimpulkan dari ftrace saja -> lihat bukti /proc/stat.
        return {"jendela_detik": jendela, "pergantian_tugas": 0, "tanpa_pergantian": True,
                "inferensi_detik": 0.0, "inferensi_persen": 0.0, "diam_detik": None,
                "diam_persen": None, "lain_us_total": 0.0, "lain": [],
                "catatan": "tidak ada pergantian tugas selama rekaman; status dari /proc/stat"}
    berjalan = None
    for ts, _, _, nc, np_ in ev:
        if ts <= a:
            berjalan = (nc, np_)
        else:
            break
    if berjalan is None:
        sesudah = [e for e in ev if e[0] > a]
        berjalan = (sesudah[0][1], sesudah[0][2]) if sesudah else ("tidak_diketahui", -1)

    durasi, kali = {}, {}
    t, ganti = a, 0
    for ts, _, _, nc, np_ in ev:
        if ts <= a or ts > b:
            continue
        durasi[berjalan] = durasi.get(berjalan, 0.0) + ts - t
        t, berjalan, ganti = ts, (nc, np_), ganti + 1
        kali[berjalan] = kali.get(berjalan, 0) + 1
    durasi[berjalan] = durasi.get(berjalan, 0.0) + b - t

    inferensi = sum(d for (c, p), d in durasi.items() if p in pid_inferensi)
    diam = sum(d for (c, p), d in durasi.items() if p == 0)
    lain = sorted(({"comm": c, "pid": p, "us": d * 1e6, "kali": kali.get((c, p), 0)}
                   for (c, p), d in durasi.items() if p not in pid_inferensi and p != 0),
                  key=lambda x: -x["us"])
    return {
        "jendela_detik": jendela,
        "pergantian_tugas": ganti,
        "inferensi_detik": inferensi,
        "inferensi_persen": inferensi / jendela * 100 if jendela > 0 else 0.0,
        "diam_detik": diam,
        "diam_persen": diam / jendela * 100 if jendela > 0 else 0.0,
        "lain_us_total": sum(x["us"] for x in lain),
        "lain": lain,
    }


def simpan_ftrace(nama, teks):
    siapkan_folder(HASIL_FTRACE)
    berkas = {}
    for c, isi in teks.items():
        p = HASIL_FTRACE / f"{nama}_cpu{c}.txt"
        p.write_text(isi, encoding="utf-8")
        milik_pengguna(p)
        berkas[f"cpu{c}"] = str(p.relative_to(DI_SINI))
    return berkas


def bukti_ftrace(ft_teks, ft_stat, a, b, pid_inferensi, nama):
    hasil = {"berkas": simpan_ftrace(nama, ft_teks), "per_cpu": {}}
    for c, isi in ft_teks.items():
        r = ringkas_ftrace(isi, a, b, set(pid_inferensi))
        r["buffer"] = ft_stat.get(c, {})
        hasil["per_cpu"][f"cpu{c}"] = r
    return hasil


def cetak_bukti(bukti, cpu_uji):
    ft = bukti.get("ftrace")
    if ft:
        for nama, r in ft["per_cpu"].items():
            peran = "uji" if nama == f"cpu{cpu_uji}" else "kembar"
            if r.get("tanpa_pergantian"):
                print(f"  ftrace {nama} ({peran}): tidak ada pergantian tugas sama sekali, "
                      f"buffer hilang {r['buffer'].get('overrun', '?')} (status: lihat /proc/stat)")
                continue
            lain =", ".join(f"{x['comm']} {x['us']:.1f} µs" for x in r["lain"][:5]) or "tidak ada"
            print(f"  ftrace {nama} ({peran}): inferensi {r['inferensi_persen']:.4f} %, "
                  f"diam {r['diam_persen']:.4f} %, lain {r['lain_us_total']:.1f} µs [{lain}], "
                  f"buffer hilang {r['buffer'].get('overrun', '?')}")
    s = bukti.get("sela_paksa")
    if s is not None:
        print(f"  sela paksa proses inferensi: {s}  (sukarela: {bukti.get('sela_sukarela')})")
    for nama, st in bukti.get("proc_stat", {}).items():
        p = st["persen"]
        print(f"  /proc/stat {nama}: user {p['user']:.1f} %, system {p['system']:.1f} %, "
              f"idle {p['idle']:.1f} %, irq+softirq {p['irq'] + p['softirq']:.1f} % "
              f"(dari {st['total_detik']:.2f} detik)")
    for nama, irq in bukti.get("interupsi", {}).items():
        print(f"  interupsi {nama}: {json.dumps(irq) if irq else 'tidak ada'}")


# ---------------------------------------------------------------------------
#  Energi (RAPL AMD lewat MSR, dibaca lokal dari CPU uji)
# ---------------------------------------------------------------------------
class PembacaEnergi:
    """Membaca penghitung energi paket dan inti dari /dev/cpu/<cpu>/msr.

    Dipanggil dari proses yang SUDAH dikunci ke CPU itu, sehingga pembacaan MSR
    dijalankan di CPU itu sendiri (tanpa interupsi antar-inti).
    Penghitung energi 32 bit; satuan = 1/2^ESU joule (MSR 0xC0010299 bit 12:8).
    """

    def __init__(self, cpu):
        if os.sched_getaffinity(0) != {cpu}:
            raise RuntimeError(f"proses harus dikunci ke CPU {cpu} sebelum membaca energi")
        jalur = f"/dev/cpu/{cpu}/msr"
        if not os.path.exists(jalur):
            subprocess.run(["modprobe", "msr"], capture_output=True)
        self.fd = os.open(jalur, os.O_RDONLY)
        esu = (self._msr(MSR_SATUAN_RAPL) >> 8) & 0x1F
        self.joule_per_satuan = 1.0 / (1 << esu)

    def _msr(self, alamat):
        return int.from_bytes(os.pread(self.fd, 8, alamat), "little")

    def baca(self):
        return {"t": time.monotonic(),
                "paket": self._msr(MSR_ENERGI_PAKET) & 0xFFFFFFFF,
                "inti": self._msr(MSR_ENERGI_INTI) & 0xFFFFFFFF,
                "aperf": self._msr(MSR_APERF)}

    def selisih(self, a, b):
        dt = b["t"] - a["t"]
        paket = ((b["paket"] - a["paket"]) & 0xFFFFFFFF) * self.joule_per_satuan
        inti = ((b["inti"] - a["inti"]) & 0xFFFFFFFF) * self.joule_per_satuan
        return {"detik": dt, "energi_paket_j": paket, "energi_inti_j": inti,
                "daya_paket_w": paket / dt, "daya_inti_w": inti / dt,
                "frekuensi_efektif_mhz": (b["aperf"] - a["aperf"]) / dt / 1e6}

    def tutup(self):
        os.close(self.fd)


# ---------------------------------------------------------------------------
#  Pengukuran waktu (dijalankan di proses anak)
# ---------------------------------------------------------------------------
def statistik(ns):
    import numpy as np
    us = np.asarray(ns, dtype=np.float64) / 1000.0
    return {
        "n": int(us.size),
        "median_us": float(np.median(us)),
        "rata_us": float(us.mean()),
        "simpangan_us": float(us.std()),
        "p95_us": float(np.percentile(us, 95)),
        "p99_us": float(np.percentile(us, 99)),
        "min_us": float(us.min()),
        "maks_us": float(us.max()),
    }


def ukur_latensi(fungsi, data):
    """fungsi(satu_citra) diukur satu per satu; data: daftar citra (1, 196)."""
    n = len(data)
    for i in range(LATENSI_PEMANASAN):
        fungsi(data[i % n])
    waktu = []
    gc.disable()
    try:
        for i in range(LATENSI_N):
            x = data[i % n]
            t0 = time.perf_counter_ns()
            fungsi(x)
            waktu.append(time.perf_counter_ns() - t0)
    finally:
        gc.enable()
    return statistik(waktu)


def ukur_throughput(fungsi, kumpulan, ukuran):
    """Citra per detik untuk satu ukuran batch, dijalankan berulang selama DURASI_THROUGHPUT."""
    batch = [kumpulan[i:i + ukuran] for i in range(0, len(kumpulan) - ukuran + 1, ukuran)]
    for b in batch[:3]:
        fungsi(b)
    n_citra, i = 0, 0
    gc.disable()
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < DURASI_THROUGHPUT:
            fungsi(batch[i % len(batch)])
            n_citra += ukuran
            i += 1
    finally:
        gc.enable()
    dt = time.perf_counter() - t0
    return {"batch": ukuran, "citra_per_detik": n_citra / dt,
            "us_per_citra": dt / n_citra * 1e6}


def anak_waktu(mode, inti):
    atur_thread(mode)
    kunci = kunci_inti(inti)
    sys.path.insert(0, str(MODEL_PC))
    import torch
    from model_pc import ModelFP32, ModelINT8, muat_mnist_uji
    if mode == "1":
        torch.set_num_threads(1)

    x14, xq, _ = muat_mnist_uji()
    int8, fp32 = ModelINT8(), ModelFP32()
    satu_q = [xq[i:i + 1] for i in range(len(xq))]
    satu_f = [x14[i:i + 1] for i in range(len(x14))]

    # Pra-pemanasan di LUAR jendela ukur: setiap jalur kode (kedua model, semua
    # ukuran batch) dijalankan sekali supaya potongan pustaka yang belum ada di
    # memori sudah dibaca dari disk sebelum pengukuran dimulai.
    for fungsi, semua in ((int8.prediksi, xq), (fp32.prediksi, x14)):
        for ukuran in BATCH:
            fungsi(semua[:ukuran])

    cpus = [2 * inti, 2 * inti + 1] if inti is not None else []
    irq0 = potret_interupsi(cpus)
    stat0 = potret_stat(cpus)
    sela0 = sela_proses()
    tid = tid_proses()
    t_mulai = time.monotonic()

    hasil = {"mode_thread": mode, "torch_thread": torch.get_num_threads(),
             "kunci_inti": kunci, "model": {}}
    for nama, fungsi, satu, semua in (("INT8 (NumPy)", int8.prediksi, satu_q, xq),
                                      ("FP32 (PyTorch)", fp32.prediksi, satu_f, x14)):
        hasil["model"][nama] = {
            "latensi_satu_citra": ukur_latensi(fungsi, satu),
            "throughput": [ukur_throughput(fungsi, semua, b) for b in BATCH],
        }

    t_selesai = time.monotonic()
    sela1 = sela_proses()
    stat1 = potret_stat(cpus)
    irq1 = potret_interupsi(cpus)
    hasil["jendela_mono"] = [t_mulai, t_selesai]
    hasil["tid"] = sorted(set(tid) | set(tid_proses()))
    hasil["bukti"] = {"sela_sukarela": sela1[0] - sela0[0], "sela_paksa": sela1[1] - sela0[1],
                      "proc_stat": selisih_stat(stat0, stat1),
                      "interupsi": selisih_interupsi(irq0, irq1, cpus)}
    print(json.dumps(hasil))


# ---------------------------------------------------------------------------
#  Perintah "waktu"
# ---------------------------------------------------------------------------
def perintah_waktu(inti):
    peringatan_isolasi(inti)
    siapkan_folder(HASIL)
    laporan = {"lingkungan": info_lingkungan(), "jalan": []}
    cap = datetime.now().strftime("%Y%m%d_%H%M%S")
    akhiran = f"_inti{inti}" if inti is not None else ""
    # Bila dikunci ke satu inti, hanya mode 1 thread yang bermakna.
    for mode in (("1",) if inti is not None else ("1", "bawaan")):
        print(f"mengukur, mode thread = {mode}"
              + (f", inti fisik {inti}" if inti is not None else "") + " ...", flush=True)
        ft = Ftrace([2 * inti, 2 * inti + 1]) if (inti is not None and root()) else None
        try:
            if ft:
                ft.mulai()
            p = subprocess.run([sys.executable, "-I", str(Path(__file__)), "_anak_waktu", mode,
                                "-" if inti is None else str(inti)],
                               capture_output=True, text=True)
        finally:
            ft_hasil = ft.selesai() if ft else None
        if p.returncode != 0:
            sys.exit(p.stderr)
        jalan = json.loads(p.stdout.strip().splitlines()[-1])
        if ft_hasil:
            a, b = jalan["jendela_mono"]
            jalan["bukti"]["ftrace"] = bukti_ftrace(*ft_hasil, a, b, jalan["tid"],
                                                    f"waktu{akhiran}_{cap}")
        laporan["jalan"].append(jalan)

    berkas = HASIL / f"waktu{akhiran}_{cap}.json"
    simpan_json(berkas, laporan)

    ling = laporan["lingkungan"]
    print()
    print(f"CPU       : {ling['cpu']} ({ling['cpu_logis']} thread logis)")
    print(f"Pustaka   : Python {ling['python']}, NumPy {ling['numpy']}, PyTorch {ling['torch']}")
    print(f"Baterai   : {ling['baterai']}")
    print(f"Mode daya : {ling['skema_daya']}")
    print(f"Isolasi   : isolated={ling['isolasi']['isolated'] or '-'}, "
          f"nohz_full={ling['isolasi']['nohz_full'] or '-'}, desktop={ling['desktop']}")
    print()
    print(f"{'Model':16} {'Thread':7} {'Median':>9} {'Rata':>9} {'p95':>9} {'p99':>9} {'Simp':>8}"
          f"   {'b=1':>10} {'b=16':>10} {'b=10000':>10}")
    print(f"{'':16} {'':7} {'(µs)':>9} {'(µs)':>9} {'(µs)':>9} {'(µs)':>9} {'(µs)':>8}"
          f"   {'citra/s':>10} {'citra/s':>10} {'citra/s':>10}")
    for j in laporan["jalan"]:
        for nama, m in j["model"].items():
            L = m["latensi_satu_citra"]
            T = {t["batch"]: t["citra_per_detik"] for t in m["throughput"]}
            print(f"{nama:16} {j['mode_thread']:7} {L['median_us']:9.2f} {L['rata_us']:9.2f}"
                  f" {L['p95_us']:9.2f} {L['p99_us']:9.2f} {L['simpangan_us']:8.2f}"
                  f"   {T[1]:10.0f} {T[16]:10.0f} {T[10000]:10.0f}")
    if inti is not None:
        print("\nBukti selama jendela pengukuran:")
        cetak_bukti(laporan["jalan"][0]["bukti"], 2 * inti)
    print()
    print(f"hasil lengkap: {berkas}")


# ---------------------------------------------------------------------------
#  Perintah "beban" (pola diam-beban-diam, dengan daya dan bukti)
# ---------------------------------------------------------------------------
def perintah_beban(model, detik, mode, inti):
    if detik <= 2 * TEPI_DETIK:
        sys.exit(f"--detik harus lebih dari {2 * TEPI_DETIK:.0f} (tepi {TEPI_DETIK:.0f} detik dibuang)")
    peringatan_isolasi(inti)
    atur_thread(mode)
    kunci = kunci_inti(inti)
    sys.path.insert(0, str(MODEL_PC))
    import torch
    from model_pc import ModelFP32, ModelINT8, muat_mnist_uji
    if mode == "1":
        torch.set_num_threads(1)

    x14, xq, _ = muat_mnist_uji()
    if model == "int8":
        fungsi, satu = ModelINT8().prediksi, [xq[i:i + 1] for i in range(len(xq))]
    else:
        fungsi, satu = ModelFP32().prediksi, [x14[i:i + 1] for i in range(len(x14))]
    # Pra-pemanasan sebelum fase diam pertama (lihat anak_waktu)
    for i in range(100):
        fungsi(satu[i % len(satu)])

    siapkan_folder(HASIL)
    cap =datetime.now().strftime("%Y%m%d_%H%M%S")
    akhiran = f"_inti{inti}" if inti is not None else ""
    nama = f"beban_{model}_{mode}{akhiran}_{cap}"
    rekam = inti is not None and root()
    cpus = [2 * inti, 2 * inti + 1] if inti is not None else []
    energi = PembacaEnergi(2 * inti) if rekam else None
    ft = Ftrace(cpus) if rekam else None

    fase, baca_e, mono, suhu = [], {}, {}, {}

    def catat(nama_fase):
        mono[nama_fase] = time.monotonic()
        suhu[nama_fase] = suhu_cpu()
        if ft:
            ft.tandai(nama_fase)
        fase.append({"fase": nama_fase, "waktu": datetime.now().isoformat(timespec="milliseconds")})
        print(f"{fase[-1]['waktu']}  {nama_fase}", flush=True)

    def diam(kunci_a, kunci_b):
        time.sleep(TEPI_DETIK)
        if energi:
            baca_e[kunci_a] = energi.baca()
        time.sleep(detik - 2 * TEPI_DETIK)
        if energi:
            baca_e[kunci_b] = energi.baca()
        time.sleep(TEPI_DETIK)

    try:
        if ft:
            ft.mulai()
        catat("diam_mulai")
        diam("d1a", "d1b")
        catat("beban_mulai")
        irq0, stat0, sela0, tid = potret_interupsi(cpus), potret_stat(cpus), sela_proses(), tid_proses()
        n, cpu0 = 0, time.process_time()
        sudah_a = sudah_b = energi is None
        t0 = time.perf_counter()
        while True:
            lewat = time.perf_counter() - t0
            if lewat >= detik:
                break
            if not sudah_a and lewat >= TEPI_DETIK:
                baca_e["ba"], sudah_a = energi.baca(), True
            if not sudah_b and lewat >= detik - TEPI_DETIK:
                baca_e["bb"], sudah_b = energi.baca(), True
            fungsi(satu[n % len(satu)])
            n += 1
        dt = time.perf_counter() - t0
        waktu_cpu = time.process_time() - cpu0      # waktu CPU proses ini, semua thread
        catat("beban_selesai")
        sela1, stat1, irq1 = sela_proses(), potret_stat(cpus), potret_interupsi(cpus)
        tid = sorted(set(tid) | set(tid_proses()))
        diam("d2a", "d2b")
        catat("diam_selesai")
    finally:
        ft_hasil = ft.selesai() if ft else None
        if energi:
            energi.tutup()

    laju = n / dt
    hasil = {"lingkungan": info_lingkungan(), "model": model, "mode_thread": mode,
             "kunci_inti": kunci, "detik_per_fase": detik, "tepi_dibuang_detik": TEPI_DETIK,
             "inferensi": n, "detik_beban": dt, "citra_per_detik": laju,
             "detik_cpu_proses": waktu_cpu,
             # 100 % = proses ini memakai satu prosesor logis penuh selama fase beban
             "pemakaian_cpu_persen": waktu_cpu / dt * 100,
             "suhu_c": suhu, "fase": fase,
             "jendela_beban_mono": [mono["beban_mulai"], mono["beban_selesai"]]}
    if inti is not None:
        hasil["bukti"] = {"sela_sukarela": sela1[0] - sela0[0], "sela_paksa": sela1[1] - sela0[1],
                          "proc_stat": selisih_stat(stat0, stat1),
                          "interupsi": selisih_interupsi(irq0, irq1, cpus)}
    if ft_hasil:
        hasil["bukti"]["ftrace"] = bukti_ftrace(*ft_hasil, mono["beban_mulai"], mono["beban_selesai"],
                                                tid, nama)
    if energi:
        d1 = energi.selisih(baca_e["d1a"], baca_e["d1b"])
        bb = energi.selisih(baca_e["ba"], baca_e["bb"])
        d2 = energi.selisih(baca_e["d2a"], baca_e["d2b"])
        daya = {}
        for lingkup in ("paket", "inti"):
            k = f"daya_{lingkup}_w"
            p_diam = (d1[k] + d2[k]) / 2
            daya[lingkup] = {
                "diam_sebelum_w": d1[k], "beban_w": bb[k], "diam_sesudah_w": d2[k],
                "diam_w": p_diam, "selisih_w": bb[k] - p_diam,
                "energi_total_uj_per_citra": bb[k] / laju * 1e6,
                "energi_tambahan_uj_per_citra": (bb[k] - p_diam) / laju * 1e6,
            }
        hasil["daya"] = daya
        hasil["frekuensi_efektif_mhz"] = {"diam_sebelum": d1["frekuensi_efektif_mhz"],
                                          "beban": bb["frekuensi_efektif_mhz"],
                                          "diam_sesudah": d2["frekuensi_efektif_mhz"]}
        hasil["energi_mentah"] = {"joule_per_satuan": energi.joule_per_satuan, "fase": {"diam_sebelum": d1,
                                                                    "beban": bb, "diam_sesudah": d2}}

    berkas = HASIL / f"{nama}.json"
    simpan_json(berkas, hasil)
    print(f"\n{n} inferensi dalam {dt:.1f} detik ({laju:.0f} citra/detik)")
    print(f"waktu CPU proses: {waktu_cpu:.1f} detik = {waktu_cpu / dt * 100:.1f} % satu prosesor logis")
    if inti is not None:
        print(f"dikunci ke inti fisik {inti} (prosesor logis {2 * inti}), prioritas normal")
        print("Bukti selama fase beban:")
        cetak_bukti(hasil["bukti"], 2 * inti)
    if energi:
        for lingkup, label in (("paket", "paket CPU"), ("inti", f"inti {inti}")):
            d = hasil["daya"][lingkup]
            print(f"  daya {label:9}: diam {d['diam_w']:.3f} W, beban {d['beban_w']:.3f} W, "
                  f"selisih {d['selisih_w']:.3f} W -> energi total {d['energi_total_uj_per_citra']:.2f} µJ/citra, "
                  f"tambahan {d['energi_tambahan_uj_per_citra']:.2f} µJ/citra")
        print(f"  frekuensi efektif saat beban: {hasil['frekuensi_efektif_mhz']['beban']:.0f} MHz, "
              f"suhu {suhu.get('beban_mulai')} -> {suhu.get('beban_selesai')} °C")
    print(f"cap waktu fase: {berkas}")


# ---------------------------------------------------------------------------
#  Perintah "ulang": satu sesi pengukuran daya penuh
# ---------------------------------------------------------------------------
def rerata_simpangan(nilai):
    return [statistics.mean(nilai), statistics.stdev(nilai) if len(nilai) > 1 else 0.0]


def rangkum_sesi(berkas_beban):
    """Rata-rata ± simpangan antarulangan per model."""
    per_model = {}
    for b in berkas_beban:
        d = json.loads(Path(b).read_text(encoding="utf-8"))
        per_model.setdefault(d["model"], []).append(d)
    rangkuman = {}
    for model, daftar in per_model.items():
        r = {"ulangan": len(daftar),
             "citra_per_detik": rerata_simpangan([d["citra_per_detik"] for d in daftar]),
             "pemakaian_cpu_persen": rerata_simpangan([d["pemakaian_cpu_persen"] for d in daftar])}
        if all("daya" in d for d in daftar):
            for lingkup in ("paket", "inti"):
                r[lingkup] = {k: rerata_simpangan([d["daya"][lingkup][k] for d in daftar])
                              for k in ("diam_w", "beban_w", "selisih_w",
                                        "energi_total_uj_per_citra", "energi_tambahan_uj_per_citra")}
        cpu_uji = [d["bukti"]["ftrace"]["per_cpu"].get(f"cpu{d['kunci_inti']['prosesor_logis']}")
                   for d in daftar if d.get("bukti", {}).get("ftrace")]
        if cpu_uji:
            r["ftrace_inferensi_persen_min"] = min(c["inferensi_persen"] for c in cpu_uji)
            r["ftrace_lain_us_maks"] = max(c["lain_us_total"] for c in cpu_uji)
            r["sela_paksa_maks"] = max(d["bukti"]["sela_paksa"] for d in daftar)
        rangkuman[model] = r
    return rangkuman


def perintah_ulang(kali, detik, inti, model, tunggu):
    """Menjalankan "beban" berulang, model bergantian, tiap pengukuran di proses baru.

    Proses baru dipakai supaya setiap pengukuran mulai dari keadaan yang sama
    (pustaka dimuat ulang, pengaturan thread dan inti diterapkan ulang).
    """
    daftar = [m.strip() for m in model.split(",") if m.strip()]
    for m in daftar:
        if m not in ("int8", "fp32"):
            sys.exit(f"model tidak dikenal: {m}")
    peringatan_isolasi(inti)
    n_total = kali * len(daftar)
    menit = (tunggu + n_total * 3 * detik) / 60
    mulai = datetime.now()
    print(f"Sesi: {kali} ulangan x {len(daftar)} model ({', '.join(daftar)}) = {n_total} pengukuran,"
          f" {detik:.0f} detik per fase" + (f", inti fisik {inti}" if inti is not None else ""))
    selesai = datetime.fromtimestamp(mulai.timestamp() + menit * 60)
    print(f"Perkiraan lama: {menit:.0f} menit, selesai sekitar pukul {selesai.strftime('%H:%M')}")
    print("Jangan memakai laptop sampai selesai.\n", flush=True)

    if tunggu > 0:
        print(f"{datetime.now().strftime('%H:%M:%S')}  menunggu {tunggu:.0f} detik supaya sistem tenang ...", flush=True)
        time.sleep(tunggu)

    berkas = []
    nomor = 0
    for ke in range(1, kali + 1):
        for m in daftar:
            nomor += 1
            print(f"\n=== pengukuran {nomor}/{n_total}: {m.upper()}, ulangan {ke} ===", flush=True)
            perintah = [sys.executable, "-I", str(Path(__file__)), "beban", "--model", m,
                        "--detik", str(detik), "--thread", "1"]
            if inti is not None:
                perintah += ["--inti", str(inti)]
            p = subprocess.run(perintah, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(p.stdout.rstrip(), flush=True)
            if p.returncode != 0:
                print(p.stderr)
                sys.exit(f"pengukuran {nomor} gagal; sesi dihentikan")
            for b in p.stdout.splitlines():
                if b.startswith("cap waktu fase:"):
                    berkas.append(b.split(":", 1)[1].strip())

    siapkan_folder(HASIL)
    rangkuman = rangkum_sesi(berkas)
    catatan = {"mulai": mulai.isoformat(timespec="seconds"),
               "selesai": datetime.now().isoformat(timespec="seconds"),
               "kali": kali, "detik_per_fase": detik, "inti": inti, "model": daftar,
               "pengukuran": berkas, "rangkuman": rangkuman}
    sesi = HASIL / f"sesi_{mulai.strftime('%Y%m%d_%H%M%S')}.json"
    simpan_json(sesi, catatan)

    print(f"\nSESI SELESAI pada {datetime.now().strftime('%H:%M:%S')}: {len(berkas)} pengukuran.")
    for m, r in rangkuman.items():
        print(f"\n{m.upper()} ({r['ulangan']} ulangan), rata-rata ± simpangan:")
        print(f"  laju {r['citra_per_detik'][0]:.0f} ± {r['citra_per_detik'][1]:.0f} citra/s")
        for lingkup in ("paket", "inti"):
            if lingkup in r:
                x = r[lingkup]
                print(f"  {lingkup:5}: diam {x['diam_w'][0]:.3f} W, beban {x['beban_w'][0]:.3f} ± "
                      f"{x['beban_w'][1]:.3f} W, energi total {x['energi_total_uj_per_citra'][0]:.2f} ± "
                      f"{x['energi_total_uj_per_citra'][1]:.2f} µJ/citra")
        if "ftrace_inferensi_persen_min" in r:
            print(f"  bukti: inferensi minimal {r['ftrace_inferensi_persen_min']:.4f} % inti uji, "
                  f"lain maksimal {r['ftrace_lain_us_maks']:.1f} µs, sela paksa maksimal {r['sela_paksa_maks']}")
    print(f"\nDaftar dan rangkuman sesi ini: {sesi}")


# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "_anak_waktu":
        anak_waktu(sys.argv[2], None if sys.argv[3] == "-" else int(sys.argv[3]))
        return
    if not sys.platform.startswith("linux"):
        sys.exit("ukur_pc_linux.py khusus Linux (memakai isolcpus, ftrace, dan MSR).")
    if len(sys.argv) == 1:
        # dijalankan tanpa perintah, misalnya lewat tombol Run di VS Code
        print("ukur_pc_linux.py perlu diberi perintah. Jalankan dari terminal, di folder Alur_Utama:\n")
        print("  sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py ulang --kali 5 --detik 60 --inti 2")
        print("  sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py beban --model int8 --detik 60 --inti 2")
        print("  sudo ~/skripsi/.venv/bin/python 5_PC_Linux/ukur_pc_linux.py waktu --inti 2\n")
        print("ulang : satu sesi pengukuran daya penuh (INT8 dan FP32 bergantian, berulang)")
        print("beban : satu pengukuran diam - beban - diam, dengan daya dan bukti isolasi")
        print("waktu : latensi per citra dan throughput, dengan bukti isolasi")
        print("Penjelasan lengkap: python 5_PC_Linux/ukur_pc_linux.py -h")
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="perintah", required=True)
    w = sub.add_parser("waktu", help="latensi per citra dan throughput")
    w.add_argument("--inti", type=int, default=None, help="kunci ke inti fisik K")
    b = sub.add_parser("beban", help="pola diam-beban-diam dengan daya dan bukti isolasi")
    b.add_argument("--model", choices=("int8", "fp32"), default="int8")
    b.add_argument("--detik", type=float, default=60.0)
    b.add_argument("--thread", choices=("1", "bawaan"), default="1")
    b.add_argument("--inti", type=int, default=None, help="kunci ke inti fisik K")
    u = sub.add_parser("ulang", help="satu sesi penuh: beban INT8 dan FP32 bergantian, berulang")
    u.add_argument("--kali", type=int, default=5, help="ulangan per model (bawaan 5)")
    u.add_argument("--detik", type=float, default=60.0, help="lama tiap fase (bawaan 60)")
    u.add_argument("--inti", type=int, default=None, help="kunci ke inti fisik K")
    u.add_argument("--model", default="int8,fp32", help="urutan model, dipisah koma")
    u.add_argument("--tunggu", type=float, default=60.0,
                   help="detik menunggu sebelum pengukuran pertama (bawaan 60)")
    a = ap.parse_args()
    if a.perintah == "waktu":
        perintah_waktu(a.inti)
    elif a.perintah == "ulang":
        perintah_ulang(a.kali, a.detik, a.inti, a.model, a.tunggu)
    else:
        if a.inti is not None and a.thread != "1":
            sys.exit("--inti hanya bermakna dengan --thread 1")
        perintah_beban(a.model, a.detik, a.thread, a.inti)


if __name__ == "__main__":
    main()
