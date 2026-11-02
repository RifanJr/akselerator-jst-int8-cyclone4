#!/usr/bin/env python3
"""
Pengukuran kinerja model pembanding PC (lihat model_pc.py).

Yang diukur hanya INFERENSI: dari vektor 196 masukan yang sudah ada di memori
sampai argmax. Memuat citra, praproses, dan tampilan tidak dihitung, sama
dengan sisi FPGA yang hanya menghitung siklus akselerator.

Perintah:
    python 5_PC/ukur_pc.py waktu [--inti K]  latensi per citra + throughput
    python 5_PC/ukur_pc.py beban --model int8 --detik 60 [--inti K]
                                             pola diam-beban-diam untuk HWiNFO
    python 5_PC/ukur_pc.py ulang --kali 5 --detik 60 --inti 2
                                             satu sesi penuh: "beban" untuk INT8
                                             dan FP32 bergantian, diulang --kali
                                             kali, berurutan tanpa jeda

--inti K: proses dikunci ke inti fisik K (prosesor logis 2K, karena pada
        Ryzen di Windows dua thread SMT satu inti bernomor 2K dan 2K+1), dengan
        prioritas normal. Dengan begitu daya "Core K Power" di HWiNFO
        dapat dipakai sebagai daya inti yang mengerjakan inferensi. Periksa di
        Task Manager atau HWiNFO bahwa beban memang jatuh di inti itu.
        Saran: K = 2 (inti 0 paling sering dipakai interupsi sistem).

waktu:  setiap ukuran dijalankan dua kali di proses terpisah, mode thread
        "1" (satu thread) dan "bawaan", karena jumlah thread NumPy/PyTorch
        harus ditetapkan sebelum pustakanya dimuat.
        Latensi: pemanasan 1.000 kali, lalu 10.000 inferensi satu citra,
        tiap inferensi diukur sendiri dengan perf_counter_ns.
        Throughput: batch 1, 16 (sama dengan batch WS), dan 10.000.

beban:  diam N detik -> inferensi satu citra berulang N detik -> diam N detik.
        Cap waktu tiap fase ditulis ke berkas, untuk dicocokkan dengan log
        CSV HWiNFO (CPU Package Power).

Hasil ditulis ke 5_PC/hasil/.
"""
import argparse
import gc
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
HASIL = DI_SINI / "hasil"

LATENSI_PEMANASAN = 1000
LATENSI_N = 10000
BATCH = (1, 16, 10000)
DURASI_THROUGHPUT = 3.0          # detik per ukuran batch


# ---------------------------------------------------------------------------
#  Lingkungan
# ---------------------------------------------------------------------------
def jalankan(perintah):
    try:
        return subprocess.run(perintah, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def info_lingkungan():
    import numpy as np
    import torch
    ps = ["powershell", "-NoProfile", "-Command"]
    cpu = jalankan(ps + ["(Get-CimInstance Win32_Processor).Name"])
    baterai = jalankan(ps + ["$b = Get-CimInstance Win32_Battery; if ($b) "
                             "{ \"$($b.EstimatedChargeRemaining)% status=$($b.BatteryStatus)\" } else { 'tidak ada' }"])
    return {
        "waktu": datetime.now().isoformat(timespec="seconds"),
        "cpu": cpu or platform.processor(),
        "cpu_logis": os.cpu_count(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "skema_daya": jalankan(["powercfg", "/getactivescheme"]),
        # BatteryStatus 2 = tersambung ke listrik (Win32_Battery)
        "baterai": baterai,
    }


def atur_thread(mode):
    """Harus dipanggil SEBELUM numpy/torch dimuat."""
    if mode == "1":
        for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[v] = "1"


def kunci_inti(k):
    """Kunci proses ini ke inti fisik k (prosesor logis 2k), prioritas NORMAL.

    Memakai fungsi Windows SetProcessAffinityMask lewat ctypes. Mengembalikan
    catatan yang disimpan ke berkas hasil.

    Prioritas sengaja dibiarkan normal. Versi awal memakai prioritas tinggi,
    dan itu membuat HWiNFO tertahan saat membaca sensor inti yang sedang
    dipakai: nilai sensor CPU membeku sampai sekitar 20 detik selama fase beban
    (terlihat pada log 2 November 2026). Dengan prioritas normal, HWiNFO tetap
    mendapat giliran sebentar di inti itu, dan pengaruhnya ke inferensi dapat
    diabaikan.
    """
    if k is None:
        return {"inti_fisik": None}
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    proses = k32.GetCurrentProcess()
    logis = 2 * k
    ok_affinity = bool(k32.SetProcessAffinityMask(proses, 1 << logis))
    if not ok_affinity:
        sys.exit(f"gagal mengunci proses ke prosesor logis {logis}")
    return {"inti_fisik": k, "prosesor_logis": logis,
            "affinity_ok": ok_affinity, "prioritas": "normal"}


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
    sys.path.insert(0, str(DI_SINI))
    import torch
    from model_pc import ModelFP32, ModelINT8, muat_mnist_uji
    if mode == "1":
        torch.set_num_threads(1)

    x14, xq, _ = muat_mnist_uji()
    int8, fp32 = ModelINT8(), ModelFP32()
    satu_q = [xq[i:i + 1] for i in range(len(xq))]
    satu_f = [x14[i:i + 1] for i in range(len(x14))]

    hasil = {"mode_thread": mode, "torch_thread": torch.get_num_threads(),
             "kunci_inti": kunci, "model": {}}
    for nama, fungsi, satu, semua in (("INT8 (NumPy)", int8.prediksi, satu_q, xq),
                                      ("FP32 (PyTorch)", fp32.prediksi, satu_f, x14)):
        hasil["model"][nama] = {
            "latensi_satu_citra": ukur_latensi(fungsi, satu),
            "throughput": [ukur_throughput(fungsi, semua, b) for b in BATCH],
        }
    print(json.dumps(hasil))


# ---------------------------------------------------------------------------
#  Perintah "waktu"
# ---------------------------------------------------------------------------
def perintah_waktu(inti):
    HASIL.mkdir(exist_ok=True)
    laporan = {"lingkungan": info_lingkungan(), "jalan": []}
    # Bila dikunci ke satu inti, hanya mode 1 thread yang bermakna.
    for mode in (("1",) if inti is not None else ("1", "bawaan")):
        print(f"mengukur, mode thread = {mode}"
              + (f", inti fisik {inti}" if inti is not None else "") + " ...", flush=True)
        p = subprocess.run([sys.executable, "-I", str(Path(__file__)), "_anak_waktu", mode,
                            "-" if inti is None else str(inti)],
                           capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(p.stderr)
        laporan["jalan"].append(json.loads(p.stdout.strip().splitlines()[-1]))

    cap = datetime.now().strftime("%Y%m%d_%H%M%S")
    akhiran = f"_inti{inti}" if inti is not None else ""
    berkas = HASIL / f"waktu{akhiran}_{cap}.json"
    berkas.write_text(json.dumps(laporan, indent=2), encoding="utf-8")

    ling = laporan["lingkungan"]
    print()
    print(f"CPU     : {ling['cpu']} ({ling['cpu_logis']} thread logis)")
    print(f"Pustaka : Python {ling['python']}, NumPy {ling['numpy']}, PyTorch {ling['torch']}")
    print(f"Baterai : {ling['baterai']}")
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
    print()
    print(f"hasil lengkap: {berkas}")


# ---------------------------------------------------------------------------
#  Perintah "beban" (untuk HWiNFO)
# ---------------------------------------------------------------------------
def perintah_beban(model, detik, mode, inti):
    atur_thread(mode)
    kunci = kunci_inti(inti)
    sys.path.insert(0, str(DI_SINI))
    import torch
    from model_pc import ModelFP32, ModelINT8, muat_mnist_uji
    if mode == "1":
        torch.set_num_threads(1)

    x14, xq, _ = muat_mnist_uji()
    if model == "int8":
        fungsi, satu = ModelINT8().prediksi, [xq[i:i + 1] for i in range(len(xq))]
    else:
        fungsi, satu = ModelFP32().prediksi, [x14[i:i + 1] for i in range(len(x14))]

    HASIL.mkdir(exist_ok=True)
    fase = []

    def catat(nama):
        fase.append({"fase": nama, "waktu": datetime.now().isoformat(timespec="milliseconds")})
        print(f"{fase[-1]['waktu']}  {nama}", flush=True)

    catat("diam_mulai")
    time.sleep(detik)
    catat("beban_mulai")
    n, t0, cpu0 = 0, time.perf_counter(), time.process_time()
    while time.perf_counter() - t0 < detik:
        fungsi(satu[n % len(satu)])
        n += 1
    dt = time.perf_counter() - t0
    waktu_cpu = time.process_time() - cpu0      # waktu CPU proses ini, semua thread
    catat("beban_selesai")
    time.sleep(detik)
    catat("diam_selesai")

    hasil = {"lingkungan": info_lingkungan(), "model": model, "mode_thread": mode,
             "kunci_inti": kunci, "detik_per_fase": detik, "inferensi": n,
             "detik_beban": dt, "citra_per_detik": n / dt,
             "detik_cpu_proses": waktu_cpu,
             # 100 % = proses ini memakai satu prosesor logis penuh selama fase beban
             "pemakaian_cpu_persen": waktu_cpu / dt * 100,
             "fase": fase}
    cap = datetime.now().strftime("%Y%m%d_%H%M%S")
    akhiran = f"_inti{inti}" if inti is not None else ""
    berkas = HASIL / f"beban_{model}_{mode}{akhiran}_{cap}.json"
    berkas.write_text(json.dumps(hasil, indent=2), encoding="utf-8")
    print(f"\n{n} inferensi dalam {dt:.1f} detik ({n / dt:.0f} citra/detik)")
    print(f"waktu CPU proses: {waktu_cpu:.1f} detik = {waktu_cpu / dt * 100:.1f} % satu prosesor logis")
    if inti is not None:
        print(f"dikunci ke inti fisik {inti} (prosesor logis {2 * inti}), prioritas normal")
    print(f"cap waktu fase: {berkas}")


# ---------------------------------------------------------------------------
#  Perintah "ulang": satu sesi pengukuran daya penuh
# ---------------------------------------------------------------------------
def perintah_ulang(kali, detik, inti, model, tunggu):
    """Menjalankan "beban" berulang, model bergantian, tiap pengukuran di proses baru.

    Proses baru dipakai supaya setiap pengukuran mulai dari keadaan yang sama
    (pustaka dimuat ulang, pengaturan thread dan inti diterapkan ulang).
    """
    daftar = [m.strip() for m in model.split(",") if m.strip()]
    for m in daftar:
        if m not in ("int8", "fp32"):
            sys.exit(f"model tidak dikenal: {m}")
    n_total = kali * len(daftar)
    menit = (tunggu + n_total * 3 * detik) / 60
    mulai = datetime.now()
    print(f"Sesi: {kali} ulangan x {len(daftar)} model ({', '.join(daftar)}) = {n_total} pengukuran,"
          f" {detik:.0f} detik per fase" + (f", inti fisik {inti}" if inti is not None else ""))
    selesai = datetime.fromtimestamp(mulai.timestamp() + menit * 60)
    print(f"Perkiraan lama: {menit:.0f} menit, selesai sekitar pukul {selesai.strftime('%H:%M')}")
    print("Pastikan logging HWiNFO SUDAH berjalan. Jangan memakai laptop sampai selesai.\n", flush=True)

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

    HASIL.mkdir(exist_ok=True)
    catatan = {"mulai": mulai.isoformat(timespec="seconds"),
               "selesai": datetime.now().isoformat(timespec="seconds"),
               "kali": kali, "detik_per_fase": detik, "inti": inti, "model": daftar,
               "pengukuran": berkas}
    sesi = HASIL / f"sesi_{mulai.strftime('%Y%m%d_%H%M%S')}.json"
    sesi.write_text(json.dumps(catatan, indent=2), encoding="utf-8")
    print(f"\nSESI SELESAI pada {datetime.now().strftime('%H:%M:%S')}: {len(berkas)} pengukuran.")
    print("Sekarang HENTIKAN logging HWiNFO, lalu simpan CSV-nya di 5_PC\\hasil\\.")
    print(f"Daftar pengukuran sesi ini: {sesi}")


# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "_anak_waktu":
        anak_waktu(sys.argv[2], None if sys.argv[3] == "-" else int(sys.argv[3]))
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) == 1:
        # dijalankan tanpa perintah, misalnya lewat tombol Run di VS Code
        print("ukur_pc.py perlu diberi perintah. Jalankan dari terminal, di folder Alur_Utama:\n")
        print("  python 5_PC/ukur_pc.py ulang --kali 5 --detik 60 --inti 2")
        print("  python 5_PC/ukur_pc.py beban --model int8 --detik 60 --inti 2")
        print("  python 5_PC/ukur_pc.py waktu --inti 2\n")
        print("ulang : satu sesi pengukuran daya penuh (INT8 dan FP32 bergantian, berulang)")
        print("beban : satu pengukuran diam - beban - diam")
        print("waktu : latensi per citra dan throughput")
        print("Penjelasan lengkap: python 5_PC/ukur_pc.py -h")
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="perintah", required=True)
    w = sub.add_parser("waktu", help="latensi per citra dan throughput")
    w.add_argument("--inti", type=int, default=None, help="kunci ke inti fisik K")
    b = sub.add_parser("beban", help="pola diam-beban-diam untuk pengukuran daya HWiNFO")
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
