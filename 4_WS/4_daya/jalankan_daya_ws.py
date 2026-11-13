#!/usr/bin/env python3
"""
Analisis daya akselerator WS (top_papan_ws.v, larik 4 x 2, batch 16) dengan
Power Analyzer Quartus, memakai aktivitas sinyal dari simulasi netlist
SELAMA INFERENSI SAJA (satu batch 16 citra).

    python 4_WS/4_daya/jalankan_daya_ws.py

Langkah dan pengaturan sama dengan 6_Daya_FPGA/jalankan_daya_os.py
(rancangan OS), supaya kedua rancangan dibandingkan dengan syarat yang sama:
  1. Kompilasi Quartus (proyek daya_ws), sekaligus menulis netlist .vo
  2. Simulasi RTL: cari siklus mulai dan selesai inferensi batch
  3. Simulasi netlist (Icarus + atom Cyclone IV E), rekam VCD; LED "cocok"
     harus menyala pada siklus yang sama dengan RTL (sekitar 6 menit)
  4. Rapikan VCD: hanya jendela inferensi, waktu digeser ke 0
  5. Aktivitas register di dalam blok generate (aktivitas_register.py)
  6. Power Analyzer, lalu ringkas hasil ke hasil/daya_ws.json

Energi per citra = daya x lama batch / 16.

Syarat: Quartus Prime Lite 25.1std di C:\\altera_lite\\25.1std,
Icarus Verilog di PATH atau di C:\\iverilog\\bin.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
QUARTUS = Path(r"C:\altera_lite\25.1std\quartus")
SIM_LIB = QUARTUS / "eda" / "sim_lib"
PROYEK = "daya_ws"
PERIODE_PS = 20000                              # 50 MHz
BATCH = 16
SIKLUS_HARAP = 3 + BATCH * 1648 + 12            # 26.383, sama dengan jalankan_papan_ws.py

RTL = ["../2_verilog/" + f for f in (
    "top_papan_ws.v", "ctrl_ws.v", "larik_ws.v", "buf_aktivasi_ws.v", "argmax_batch.v")] + \
      ["../../2_Verilog/" + f for f in (
    "mac_unit.v", "mult_bw8_arith.v", "mult_bw8_struct.v", "mult_hard8.v", "mem_w.v",
    "epilog_unit.v", "seg7_scan.v", "seg7_dec.v")] + ["../../1_Python_PC/mem/rom_bias8.v"]

BUILD = DI_SINI / "build"
OUT = DI_SINI / "output_ws"
HASIL = DI_SINI / "hasil"


def cari_alat(nama):
    p = shutil.which(nama) or shutil.which(nama, path=r"C:\iverilog\bin")
    if not p:
        raise SystemExit(f"{nama} tidak ditemukan (pasang Icarus Verilog)")
    return p


def jalan(judul, perintah, log):
    print(f"--> {judul}", flush=True)
    with open(BUILD / log, "w", encoding="utf-8", errors="replace") as f:
        r = subprocess.run(perintah, cwd=DI_SINI, stdout=f, stderr=subprocess.STDOUT, text=True)
    teks = (BUILD / log).read_text(encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(teks[-3000:])
        raise SystemExit(f"GAGAL: {judul} (log: build/{log})")
    return teks


def waktu_ps(n):
    """waktu tepi naik ke-n (clock mulai 0, tepi naik pertama pada setengah periode)"""
    return (2 * n - 1) * PERIODE_PS // 2


def ringkas_laporan(rpt, keluar):
    """salin laporan daya tanpa tabel per sinyal dan per blok (berukuran megabita)"""
    buang = {"Signal Activities", "Thermal Power Dissipation by Block"}
    simpan = []
    for blok in rpt.read_text(encoding="utf-8", errors="replace").split("\n\n"):
        baris = blok.strip("\n").split("\n")
        if len(baris) > 1 and baris[0].startswith("+") and baris[1].strip("; ") in buang:
            simpan.append(f"; {baris[1].strip('; ')} ; (tabel dihapus dari salinan ringkas)")
            continue
        simpan.append(blok)
    keluar.write_text("\n\n".join(simpan), encoding="utf-8")


def baca_keyakinan(rpt):
    """baris Confidence Metric Details: jumlah dan persen sinyal serta register per sumber"""
    teks = rpt.read_text(encoding="utf-8", errors="replace")
    hasil = {}
    for kunci, pola in (("simulasi", "Toggle Rate from Simulation"),
                        ("assignment", "Toggle Rate from Node, entity or clock assignment"),
                        ("vectorless", "Toggle Rate from Vectorless estimation")):
        m = re.search(r"-- Number of signals with " + re.escape(pola) +
                      r"\s*;\s*(\d+) \(([\d.]+)%\)\s*;[^;]*;\s*(\d+) \(([\d.]+)%\)", teks)
        if m:
            hasil[kunci] = {"sinyal": int(m.group(1)), "sinyal_persen": float(m.group(2)),
                            "register": int(m.group(3)), "register_persen": float(m.group(4))}
    return hasil


def baca_jenis_blok(rpt):
    """tabel Thermal Power Dissipation by Block Type: {jenis: daya total mW}"""
    teks = rpt.read_text(encoding="utf-8", errors="replace")
    bagian = teks.split("; Thermal Power Dissipation by Block Type")[1].split("\n\n")[0]
    hasil = {}
    for b in bagian.split("\n"):
        m = re.match(r"; ([^;]+?)\s*; ([\d.]+) mW", b)
        if m:
            hasil[m.group(1)] = float(m.group(2))
    return hasil


def main():
    BUILD.mkdir(exist_ok=True)
    HASIL.mkdir(exist_ok=True)
    iverilog, vvp = cari_alat("iverilog"), cari_alat("vvp")
    bin64 = QUARTUS / "bin64"
    akt = BUILD / "aktivitas_register.tcl"
    if not akt.exists():
        akt.write_text("# diisi oleh aktivitas_register.py\n")   # daya_ws.qsf me-source berkas ini

    # 1. kompilasi
    jalan("Kompilasi Quartus (sekitar 1 menit)",
          [str(bin64 / "quartus_sh.exe"), "--flow", "compile", PROYEK, "-c", PROYEK], "log_kompilasi.txt")
    fit = (OUT / f"{PROYEK}.fit.summary").read_text()
    le = re.search(r"Total logic elements : ([\d,]+)", fit).group(1)
    print(f"    {le} LE")

    # 2. jendela inferensi dari RTL
    jalan("Kompilasi simulasi RTL", [iverilog, "-g2012", "-o", "build/jendela.vvp", "tb_jendela_ws.v"] + RTL,
          "log_rtl_kompilasi.txt")
    teks = jalan("Simulasi RTL: cari jendela inferensi", [vvp, "-n", "build/jendela.vvp"], "log_rtl.txt")
    m = re.search(r"JENDELA mulai=(\d+) selesai=(\d+) siklus=(\d+) led_cocok=(\d+) siklus_papan=(\d+)", teks)
    if not m:
        raise SystemExit("GAGAL: baris JENDELA tidak ditemukan")
    mulai, selesai, siklus, led_cocok, siklus_papan = map(int, m.groups())
    print(f"    siklus {mulai}..{selesai} = {siklus} siklus (penghitung papan {siklus_papan})")
    if siklus != SIKLUS_HARAP or siklus_papan != SIKLUS_HARAP:
        raise SystemExit(f"GAGAL: harap {SIKLUS_HARAP} siklus")

    # 3. simulasi netlist
    vo = DI_SINI / "simulation" / "questa" / f"{PROYEK}.vo"
    jalan("Ambil atom Cyclone IV E", [sys.executable, "ambil_atom.py", str(SIM_LIB / "cycloneive_atoms.v"),
                                     str(vo), "build/atoms_min.v"], "log_atom.txt")
    jalan("Kompilasi simulasi netlist",
          [iverilog, "-g2012", f"-DMULAI={mulai}", f"-DLED_COCOK={led_cocok}", "-o", "build/netlist.vvp",
           "tb_netlist_ws.v", str(vo), "build/atoms_min.v", str(SIM_LIB / "altera_primitives.v")],
          "log_netlist_kompilasi.txt")
    teks = jalan("Simulasi netlist, rekam VCD (sekitar 6 menit)", [vvp, "-n", "build/netlist.vvp"],
                 "log_netlist.txt")
    m = re.search(r"NETLIST led_cocok=(-?\d+) harap=(\d+) (\w+)", teks)
    if not m or m.group(3) != "COCOK":
        raise SystemExit(f"GAGAL: netlist tidak sama dengan RTL ({m.group(0) if m else 'tanpa keluaran'})")
    print(f"    LED cocok pada siklus {m.group(1)}, sama dengan RTL")

    # 4-5. VCD jendela inferensi dan aktivitas register di blok generate
    t0, t1 = waktu_ps(mulai), waktu_ps(selesai)
    jalan("Rapikan VCD", [sys.executable, "siapkan_vcd.py", "build/ws_netlist.vcd", "build/ws_inferensi.vcd",
                          str(t0), str(t1)], "log_vcd.txt")
    jalan("Aktivitas register di blok generate", [sys.executable, "aktivitas_register.py",
                                                   "build/ws_inferensi.vcd", str(akt)], "log_aktivitas.txt")

    # 6. Power Analyzer
    jalan("Power Analyzer", [str(bin64 / "quartus_pow.exe"), "--read_settings_files=on",
                             "--write_settings_files=off", PROYEK, "-c", PROYEK], "log_daya.txt")
    ringkas = (OUT / f"{PROYEK}.pow.summary").read_text()

    def mw(label):
        return float(re.search(re.escape(label) + r" : ([\d.]+) mW", ringkas).group(1))

    daya = {"total_mw": mw("Total Thermal Power Dissipation"),
            "inti_dinamis_mw": mw("Core Dynamic Thermal Power Dissipation"),
            "inti_statis_mw": mw("Core Static Thermal Power Dissipation"),
            "io_mw": mw("I/O Thermal Power Dissipation")}
    keyakinan = re.search(r"Power Estimation Confidence : (.+)", ringkas).group(1).strip()
    lama_batch_us = siklus * PERIODE_PS / 1e6
    lama_citra_us = lama_batch_us / BATCH
    energi = {k.replace("_mw", "_uj_per_citra"): round(v * lama_citra_us / 1000, 6) for k, v in daya.items()}

    hasil = {
        "waktu": datetime.now().isoformat(timespec="seconds"),
        "rancangan": "WS, top_papan_ws.v (larik 4 x 2, batch 16, pengali HARD)",
        "branch_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=DI_SINI,
                                        capture_output=True, text=True).stdout.strip(),
        "perangkat": "EP4CE6E22C8",
        "logic_elements": le,
        "clock_mhz": 1e6 / PERIODE_PS,
        "jendela_vcd": {"siklus_mulai": mulai, "siklus_selesai": selesai, "siklus": siklus,
                        "lama_us": lama_batch_us, "citra": f"batch {BATCH} citra uji"},
        "lama_per_citra_us": lama_citra_us,
        "daya": daya,
        "energi": energi,
        "daya_per_jenis_blok_mw": baca_jenis_blok(OUT / f"{PROYEK}.pow.rpt"),
        "keyakinan": keyakinan,
        "sumber_aktivitas": baca_keyakinan(OUT / f"{PROYEK}.pow.rpt"),
    }
    (HASIL / "daya_ws.json").write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copy(OUT / f"{PROYEK}.pow.summary", HASIL)
    shutil.copy(OUT / f"{PROYEK}.fit.summary", HASIL)
    ringkas_laporan(OUT / f"{PROYEK}.pow.rpt", HASIL / f"{PROYEK}.pow_ringkas.rpt")

    print()
    print(f"Daya total     {daya['total_mw']:7.2f} mW  -> {energi['total_uj_per_citra']:.3f} uJ per citra")
    print(f"  inti dinamis {daya['inti_dinamis_mw']:7.2f} mW  -> {energi['inti_dinamis_uj_per_citra']:.3f} uJ")
    print(f"  inti statis  {daya['inti_statis_mw']:7.2f} mW  -> {energi['inti_statis_uj_per_citra']:.3f} uJ")
    print(f"  I/O          {daya['io_mw']:7.2f} mW  -> {energi['io_uj_per_citra']:.3f} uJ")
    print(f"Lama batch     {lama_batch_us:.2f} us ({siklus} siklus), {lama_citra_us:.2f} us per citra")
    print(f"Confidence     {keyakinan}")
    for k, v in hasil["sumber_aktivitas"].items():
        print(f"  dari {k:10s}: {v['sinyal_persen']:5.1f} % sinyal, {v['register_persen']:5.1f} % register")
    print("Hasil: 4_WS/4_daya/hasil/daya_ws.json")


if __name__ == "__main__":
    main()
