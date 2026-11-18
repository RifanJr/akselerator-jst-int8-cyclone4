#!/usr/bin/env python3
"""
Ukur ulang tiga varian pengali (HARD, ARITH, STRUCT) pada rancangan OS terbaru
(top_papan.v, P = 8, 1.708 siklus per citra).

    python 8_Varian_Pengali/jalankan_varian.py               # ketiga varian
    python 8_Varian_Pengali/jalankan_varian.py ARITH STRUCT  # sebagian saja

Tiap varian:
  1. Uji RTL 16 citra lewat tombol (tb_papan.v) dengan MULT_STYLE varian:
     18 inferensi, 10 akumulator lapisan 2 identik dengan golden_uji.txt,
     tepat 1.708 siklus.
  2. Kompilasi Quartus (luas dan timing), sekaligus menulis netlist .vo.
  3-7. Analisis daya dengan metode 6_Daya_FPGA (Student B): jendela inferensi
     dari RTL, simulasi netlist, VCD hanya selama inferensi, aktivitas
     register MAC sebagai assignment, Power Analyzer.
  8. Arsipkan laporan mentah ke 8_Varian_Pengali/hasil_mentah/<tanggal>_os_<varian>/.

Berkas Student B hanya DIBACA, tidak diubah: proyek Quartus dibuat dari
6_Daya_FPGA/daya_os.qsf dengan tambahan set_parameter MULT_STYLE, dan
testbench serta skrip bantu dipanggil langsung dari folder aslinya.

Syarat: Quartus Prime Lite 25.1std di C:\\altera_lite\\25.1std,
Icarus Verilog di PATH atau di C:\\iverilog\\bin, Python 3.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
AKAR = DI_SINI.parent
DAYA_B = AKAR / "6_Daya_FPGA"
RTL_DIR = AKAR / "2_Verilog"
ARSIP = AKAR / "8_Varian_Pengali" / "hasil_mentah"
QUARTUS = (Path(r"C:\altera_lite\25.1std\quartus") if sys.platform.startswith("win")
           else AKAR.parent / "altera_lite" / "25.1std" / "quartus")
SIM_LIB = QUARTUS / "eda" / "sim_lib"
BUILD = DI_SINI / "build"
HASIL = DI_SINI / "hasil"

PERIODE_PS = 20000                       # 50 MHz
SIKLUS_BARU = 1708
GAYA = ["HARD", "ARITH", "STRUCT"]

RTL = [str(RTL_DIR / f) for f in (
    "top_papan.v", "ctrl_fsm_p8.v", "mem_w.v", "mem_d.v", "mac_unit.v", "epilog_unit.v",
    "argmax10.v", "mult_bw8_arith.v", "mult_bw8_struct.v", "mult_hard8.v",
    "seg7_scan.v", "seg7_dec.v")] + [str(AKAR / "1_Python_PC" / "mem" / "rom_bias8.v")]



# ---------------------------------------------------------------- alat bantu
LOKASI_IVERILOG = [r"C:\iverilog\bin", r"C:\Program Files\iverilog\bin",
                   r"C:\Program Files (x86)\iverilog\bin", r"C:\msys64\mingw64\bin",
                   r"C:\msys64\ucrt64\bin"]


def cari_ivl():
    """kembalikan perintah iverilog dan vvp sebagai daftar (dengan -B/-M bila IVL_LIB diset)"""
    import os
    lib, binp = os.environ.get("IVL_LIB"), os.environ.get("IVL_BIN")
    if binp:
        iv, vv = [str(Path(binp) / "iverilog")], [str(Path(binp) / "vvp")]
    else:
        iv, vv = [cari_alat("iverilog")], [cari_alat("vvp")]
    if lib:
        iv += ["-B", lib]
        vv += ["-M", lib]
    return iv, vv


def cari_alat(nama):
    p = shutil.which(nama)
    for d in LOKASI_IVERILOG:
        p = p or shutil.which(nama, path=d)
    if not p:
        raise SystemExit(f"{nama} tidak ditemukan. Jalankan 'where.exe {nama}' di PowerShell, lalu tambahkan "
                         f"foldernya ke LOKASI_IVERILOG di jalankan_varian.py, atau pasang Icarus Verilog.")
    return p


def jalan(judul, perintah, log, cwd=DI_SINI):
    print(f"--> {judul}", flush=True)
    with open(BUILD / log, "w", encoding="utf-8", errors="replace") as f:
        r = subprocess.run(perintah, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
    teks = (BUILD / log).read_text(encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(teks[-3000:])
        raise SystemExit(f"GAGAL: {judul} (log: 8_Varian_Pengali/build/{log})")
    return teks


def waktu_ps(n):
    return (2 * n - 1) * PERIODE_PS // 2


def baca(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def angka(pola, teks, f=float, flags=0):
    m = re.search(pola, teks, flags)
    return f(m.group(1).replace(",", "")) if m else None


# ---------------------------------------------------------------- pembacaan laporan
def baca_fit(summary, rpt):
    s, r = baca(summary), baca(rpt)
    lajur = [int(x) for x in re.findall(r"^;\s+\|mac_unit:g_lajur\[\d\]\.u_mac\|\s+;\s+(\d+) \(", r, re.M)]
    return {
        "le": angka(r"Total logic elements : ([\d,]+)", s, int),
        "fungsi_kombinasional": angka(r"Total combinational functions : ([\d,]+)", s, int),
        "register": angka(r"Total registers : ([\d,]+)", s, int),
        "pengali_9bit": angka(r"Embedded Multiplier 9-bit elements : (\d+)", s, int),
        "m9k": angka(r"^; M9Ks\s+;\s+(\d+) /", r, int, re.M),
        "bit_memori": angka(r"Total memory bits : ([\d,]+)", s, int),
        "le_lajur": lajur,
        "le_lajur_rerata": round(sum(lajur) / len(lajur), 1) if lajur else None,
    }


def baca_sta(summary, rpt):
    s, r = baca(summary), baca(rpt)
    i = r.find("; Slow 1200mV 85C Model Fmax Summary")
    fmax = angka(r";\s+([\d.]+) MHz\s+;\s+[\d.]+ MHz\s+;\s+clk", r[i:]) if i >= 0 else None
    return {
        "fmax_mhz": fmax,
        "setup_slack_ns": angka(r"Slow 1200mV 85C Model Setup 'clk'\s*\nSlack\s*:\s*([-\d.]+)", s),
        "hold_slack_ns": angka(r"Slow 1200mV 85C Model Hold 'clk'\s*\nSlack\s*:\s*([-\d.]+)", s),
    }


def baca_keyakinan(teks):
    hasil = {}
    for kunci, pola in (("simulasi", "Toggle Rate from Simulation"),
                        ("assignment", "Toggle Rate from Node, entity or clock assignment"),
                        ("vectorless", "Toggle Rate from Vectorless estimation")):
        m = re.search(r"-- Number of signals with " + re.escape(pola) +
                      r"\s*;\s*(\d+) \(([\d.]+)%\)\s*;[^;]*;\s*(\d+) \(([\d.]+)%\)", teks)
        if m:
            hasil[kunci] = {"sinyal_persen": float(m.group(2)), "register_persen": float(m.group(4))}
    return hasil


def baca_pow(summary, rpt, siklus):
    s, r = baca(summary), baca(rpt)

    def mw(label):
        return angka(re.escape(label) + r" : ([\d.]+) mW", s)

    lajur = [float(x) for x in re.findall(r"^;\s+\|mac_unit:g_lajur\[\d\]\.u_mac\s+;\s+([\d.]+) mW", r, re.M)]
    total = mw("Total Thermal Power Dissipation")
    lama_us = siklus * PERIODE_PS / 1e6
    return {
        "total_mw": total,
        "inti_dinamis_mw": mw("Core Dynamic Thermal Power Dissipation"),
        "inti_statis_mw": mw("Core Static Thermal Power Dissipation"),
        "io_mw": mw("I/O Thermal Power Dissipation"),
        "delapan_lajur_mw": round(sum(lajur), 2) if len(lajur) == 8 else None,
        "energi_uj_per_citra": round(total * lama_us / 1000, 3) if total else None,
        "keyakinan": (re.search(r"Power Estimation Confidence : (\w+)", s) or [None, None])[1],
        "sumber_aktivitas": baca_keyakinan(r),
    }


# ---------------------------------------------------------------- satu varian
def tulis_proyek(g):
    proyek = f"daya_{g.lower()}"
    q = baca(DAYA_B / "daya_os.qsf")
    ganti = [
        ("PROJECT_OUTPUT_DIRECTORY output_os", f"PROJECT_OUTPUT_DIRECTORY output_{g.lower()}"),
        ('"build/os_inferensi.vcd" -section_id os_inferensi.vcd',
         f'"build/{g.lower()}_inferensi.vcd" -section_id {g.lower()}_inferensi.vcd'),
        ("POWER_READ_INPUT_FILE os_inferensi.vcd", f"POWER_READ_INPUT_FILE {g.lower()}_inferensi.vcd"),
        ("source build/aktivitas_mac.tcl", f"source build/aktivitas_mac_{g.lower()}.tcl"),
    ]
    for lama, baru in ganti:
        if lama not in q:
            raise SystemExit(f"GAGAL: daya_os.qsf berubah, tidak menemukan '{lama}'")
        q = q.replace(lama, baru)
    kepala = (f"# DIBUAT OTOMATIS oleh 8_Varian_Pengali/jalankan_varian.py dari\n"
              f"# 6_Daya_FPGA/daya_os.qsf (Student B), ditambah MULT_STYLE {g}. Jangan diubah tangan.\n")
    q = kepala + q + f"\nset_parameter -name MULT_STYLE {g}\n"
    (DI_SINI / f"{proyek}.qsf").write_text(q, encoding="utf-8")
    (DI_SINI / f"{proyek}.qpf").write_text(f'QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "{proyek}"\n')
    akt = BUILD / f"aktivitas_mac_{g.lower()}.tcl"
    akt.write_text("# diisi oleh aktivitas_mac.py\n")
    return proyek, akt


def defparam(g, jalur):
    f = BUILD / f"gaya_{g.lower()}_{jalur.split('.')[0]}.v"
    f.write_text(f'module atur_gaya; defparam {jalur}.MULT_STYLE = "{g}"; endmodule\n')
    return str(f)


def uji_rtl(g, iverilog, vvp):
    """tb_papan.v Student B dengan MULT_STYLE varian: 18 inferensi, 10 akumulator, 1.708 siklus"""
    sys.path.insert(0, str(RTL_DIR))
    from jalankan_papan import baca_acuan, SUMBER          # hanya dibaca
    biner = BUILD / f"papan_{g.lower()}.out"
    jalan(f"[{g}] Kompilasi uji RTL 16 citra",
          iverilog + ["-g2012", "-o", str(biner), "-s", "tb_papan", "-s", "atur_gaya"] + SUMBER +
          [defparam(g, "tb_papan.u_top")], f"log_{g.lower()}_rtl_kompilasi.txt", cwd=RTL_DIR)
    teks = jalan(f"[{g}] Uji RTL 16 citra (sekitar 1 menit)", vvp + ["-n", str(biner)],
                 f"log_{g.lower()}_rtl.txt", cwd=RTL_DIR)
    acuan = baca_acuan()
    hasil, aks, per = [], [], []
    for b in teks.splitlines():
        s = b.split()
        if s and s[0] == "AKS" and len(s) == 3:
            aks.append((int(s[1]), int(s[2])))
        elif s and s[0] == "HASIL" and len(s) == 7:
            hasil.append(tuple(int(x) for x in s[1:])); per.append(aks); aks = []
    lulus = 0
    for (idx, h, nilai, siklus, led_cocok, led_beda), ak in zip(hasil, per):
        a = acuan[idx]
        ok = (h == a["prediksi"] and nilai == a["acc"][a["prediksi"]] and len(ak) == 10
              and sorted(d for d, _ in ak) == list(range(10))
              and all(a["acc"][d] == v for d, v in ak)
              and siklus == SIKLUS_BARU and led_cocok == 1 and led_beda == 0)
        lulus += ok
    citra = sorted({r[0] for r in hasil})
    print(f"    {lulus}/{len(hasil)} inferensi identik, {len(citra)} citra berbeda")
    if not (lulus == len(hasil) == 18 and citra == list(range(16))):
        raise SystemExit(f"GAGAL: uji RTL varian {g} tidak lulus")
    return {"inferensi": len(hasil), "identik": lulus, "citra": len(citra), "siklus": SIKLUS_BARU}


def kompilasi(g):
    """tahap Windows: proyek Quartus + kompilasi (luas, timing, netlist .vo)"""
    print("=" * 72); print(f"  KOMPILASI {g}"); print("=" * 72)
    proyek, akt = tulis_proyek(g)
    jalan(f"[{g}] Kompilasi Quartus (1-2 menit)",
          [str(QUARTUS / "bin64" / "quartus_sh.exe"), "--flow", "compile", proyek, "-c", proyek],
          f"log_{g.lower()}_kompilasi.txt")
    fit = baca_fit(DI_SINI / f"output_{g.lower()}" / f"{proyek}.fit.summary",
                   DI_SINI / f"output_{g.lower()}" / f"{proyek}.fit.rpt")
    print(f"    {fit['le']} LE, pengali 9 bit {fit['pengali_9bit']}/30")


def simulasi(g, iverilog, vvp):
    """tahap simulasi (Icarus): uji RTL, jendela inferensi, netlist, VCD, aktivitas MAC"""
    print("=" * 72); print(f"  SIMULASI {g}"); print("=" * 72)
    proyek = f"daya_{g.lower()}"
    akt = BUILD / f"aktivitas_mac_{g.lower()}.tcl"
    uji = uji_rtl(g, iverilog, vvp)

    jvvp = BUILD / f"jendela_{g.lower()}.vvp"
    jalan(f"[{g}] Kompilasi jendela inferensi",
          iverilog + ["-g2012", "-o", str(jvvp), "-s", "tb_jendela_os", "-s", "atur_gaya",
                      str(DAYA_B / "tb_jendela_os.v"), defparam(g, "tb_jendela_os.dut")] + RTL,
          f"log_{g.lower()}_jendela_kompilasi.txt")
    teks = jalan(f"[{g}] Jendela inferensi", vvp + ["-n", str(jvvp)], f"log_{g.lower()}_jendela.txt")
    m = re.search(r"JENDELA mulai=(\d+) selesai=(\d+) siklus=(\d+) led_cocok=(\d+) siklus_papan=(\d+)", teks)
    if not m:
        raise SystemExit("GAGAL: baris JENDELA tidak ditemukan")
    mulai, selesai, siklus, led_cocok, siklus_papan = map(int, m.groups())
    print(f"    siklus {mulai}..{selesai} = {siklus} (penghitung papan {siklus_papan})")
    if siklus != SIKLUS_BARU or siklus_papan != SIKLUS_BARU:
        raise SystemExit(f"GAGAL: harap {SIKLUS_BARU} siklus")

    vo = DI_SINI / "simulation" / "questa" / f"{proyek}.vo"
    if not vo.exists():
        raise SystemExit(f"GAGAL: {vo.name} belum ada, jalankan tahap kompilasi lebih dulu")
    atom = BUILD / f"atoms_{g.lower()}.v"
    jalan(f"[{g}] Ambil atom Cyclone IV E",
          [sys.executable, str(DAYA_B / "ambil_atom.py"), str(SIM_LIB / "cycloneive_atoms.v"), str(vo), str(atom)],
          f"log_{g.lower()}_atom.txt")
    nvvp = BUILD / f"netlist_{g.lower()}.vvp"
    jalan(f"[{g}] Kompilasi simulasi netlist",
          iverilog + ["-g2012", f"-DMULAI={mulai}", f"-DLED_COCOK={led_cocok}", "-o", str(nvvp),
                      str(DAYA_B / "tb_netlist_os.v"), str(vo), str(atom), str(SIM_LIB / "altera_primitives.v")],
          f"log_{g.lower()}_netlist_kompilasi.txt")
    teks = jalan(f"[{g}] Simulasi netlist (rekam VCD)", vvp + ["-n", str(nvvp)], f"log_{g.lower()}_netlist.txt")
    m = re.search(r"NETLIST led_cocok=(-?\d+) harap=(\d+) (\w+)", teks)
    if not m or m.group(3) != "COCOK":
        raise SystemExit(f"GAGAL: netlist {g} tidak sama dengan RTL ({m.group(0) if m else 'tanpa keluaran'})")
    print(f"    LED cocok pada siklus {m.group(1)}, sama dengan RTL")

    mentah, vcd = BUILD / "os_netlist.vcd", BUILD / f"{g.lower()}_inferensi.vcd"
    jalan(f"[{g}] Rapikan VCD", [sys.executable, str(DAYA_B / "siapkan_vcd.py"), str(mentah), str(vcd),
                                 str(waktu_ps(mulai)), str(waktu_ps(selesai))], f"log_{g.lower()}_vcd.txt")
    try:
        mentah.unlink()
    except OSError:
        pass
    jalan(f"[{g}] Aktivitas register MAC", [sys.executable, str(DAYA_B / "aktivitas_mac.py"), str(vcd), str(akt)],
          f"log_{g.lower()}_aktivitas.txt")
    sim = {"uji_rtl": uji, "mulai": mulai, "selesai": selesai, "siklus": siklus,
           "netlist_led_cocok": int(m.group(1)), "simulator": " ".join(iverilog[:1])}
    (BUILD / f"sim_{g.lower()}.json").write_text(json.dumps(sim, indent=1), encoding="utf-8")


def daya(g, tanggal):
    """tahap Windows: Power Analyzer, arsip laporan, ringkasan json"""
    print("=" * 72); print(f"  DAYA {g}"); print("=" * 72)
    proyek = f"daya_{g.lower()}"
    out = DI_SINI / f"output_{g.lower()}"
    akt = BUILD / f"aktivitas_mac_{g.lower()}.tcl"
    simf = BUILD / f"sim_{g.lower()}.json"
    if not simf.exists():
        raise SystemExit(f"GAGAL: {simf.name} belum ada, jalankan tahap simulasi lebih dulu")
    sim = json.loads(baca(simf))
    jalan(f"[{g}] Power Analyzer", [str(QUARTUS / "bin64" / "quartus_pow.exe"), "--read_settings_files=on",
                                     "--write_settings_files=off", proyek, "-c", proyek],
          f"log_{g.lower()}_daya.txt")

    tujuan = ARSIP / f"{tanggal}_os_{g.lower()}"
    tujuan.mkdir(parents=True, exist_ok=True)
    for ek in ("map.rpt", "map.summary", "fit.rpt", "fit.summary", "sta.rpt", "sta.summary",
               "flow.rpt", "pow.rpt", "pow.summary"):
        sumber = out / f"{proyek}.{ek}"
        if sumber.exists():
            shutil.copy(sumber, tujuan)
    shutil.copy(akt, tujuan)
    shutil.copy(DI_SINI / f"{proyek}.qsf", tujuan)
    shutil.copy(simf, tujuan)

    siklus = sim["siklus"]
    hasil = {
        "varian": g, "rancangan": "OS baru (1.708 siklus)", "waktu": datetime.now().isoformat(timespec="seconds"),
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AKAR,
                                 capture_output=True, text=True).stdout.strip(),
        "arsip": str(tujuan.relative_to(AKAR)).replace("\\", "/"),
        "simulasi": sim,
        "siklus": siklus, "waktu_us": siklus * PERIODE_PS / 1e6,
        "luas": baca_fit(out / f"{proyek}.fit.summary", out / f"{proyek}.fit.rpt"),
        "timing": baca_sta(out / f"{proyek}.sta.summary", out / f"{proyek}.sta.rpt"),
        "daya": baca_pow(out / f"{proyek}.pow.summary", out / f"{proyek}.pow.rpt", siklus),
    }
    (HASIL / f"{g.lower()}.json").write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    (tujuan / f"{g.lower()}.json").write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    d = hasil["daya"]
    print(f"    {hasil['luas']['le']} LE, Fmax {hasil['timing']['fmax_mhz']} MHz, "
          f"{d['total_mw']} mW ({d['keyakinan']}), {d['energi_uj_per_citra']} uJ/citra")



def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    BUILD.mkdir(exist_ok=True)
    HASIL.mkdir(exist_ok=True)
    arg = [a.upper() for a in sys.argv[1:]]
    tahap = next((a[2:].lower() for a in arg if a in ("--KOMPILASI", "--SIMULASI", "--DAYA")), "semua")
    pilih = [g for g in GAYA if g in arg] or GAYA
    tanggal = date.today().isoformat()
    if tahap in ("semua", "simulasi"):
        iverilog, vvp = cari_ivl()
    for g in pilih:
        if tahap in ("semua", "kompilasi"):
            kompilasi(g)
        if tahap in ("semua", "simulasi"):
            simulasi(g, iverilog, vvp)
        if tahap in ("semua", "daya"):
            daya(g, tanggal)


if __name__ == "__main__":
    main()
