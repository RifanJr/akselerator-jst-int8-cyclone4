#!/usr/bin/env python3
"""Tugas 10 -- kompilasi pembungkus komponen sendirian dan ringkas hasilnya.

Dijalankan di Windows (JALANKAN_WRAP.bat). Untuk tiap top-level di wrap_komponen.v:
  1. tulis <rev>.qsf/.qpf (EP4CE6E22C8, wrap.sdc 20 ns, semua port data = pin maya)
  2. quartus_sh --flow compile
  3. quartus_sta -t wrap_sta.tcl <rev>  (jalur terburuk, Slow 1200mV 85C)
  4. baca LE/register u_dut (fitter + sintesis), Fmax, data delay
Keluaran: ../hasil/T10_sendirian.csv; arsip laporan ke 8_Varian_Pengali/hasil_mentah/<tgl>_analisis_mac_sendirian/
"""
import csv, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
AKAR = DI_SINI.parents[1]
QUARTUS = Path(r"C:\altera_lite\25.1std\quartus\bin64")
REV = ["wrap_dasar", "wrap_m3_mux", "wrap_m4_add", "wrap_e1_round", "wrap_e2_shift",
       "wrap_e3_relu", "wrap_e4_sat", "wrap_epi_rantai"]
SUMBER = ["../rtl_terpecah/mac_unit.v", "../rtl_terpecah/epilog_unit.v", "../../2_Verilog/mult_bw8_arith.v",
          "../../2_Verilog/mult_bw8_struct.v", "../../2_Verilog/mult_hard8.v", "wrap_komponen.v"]

def tulis(rev):
    q = [f'set_global_assignment -name FAMILY "Cyclone IV E"',
         'set_global_assignment -name DEVICE EP4CE6E22C8',
         f'set_global_assignment -name TOP_LEVEL_ENTITY {rev}',
         f'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_{rev}',
         'set_global_assignment -name SDC_FILE wrap.sdc',
         'set_instance_assignment -name VIRTUAL_PIN ON -to d_i[*]',
         'set_instance_assignment -name VIRTUAL_PIN ON -to q_o[*]']
    q += [f'set_global_assignment -name VERILOG_FILE {s}' for s in SUMBER]
    (DI_SINI / f"{rev}.qsf").write_text("# dibuat jalankan_wrap.py (Tugas 10)\n" + "\n".join(q) + "\n")
    (DI_SINI / f"{rev}.qpf").write_text(f'QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "{rev}"\n')

def jalan(cmd, log):
    with open(DI_SINI / "hasil_sta" / log, "w", encoding="utf-8", errors="replace") as f:
        r = subprocess.run(cmd, cwd=DI_SINI, stdout=f, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        raise SystemExit(f"GAGAL: {' '.join(cmd[:2])} (log: 9_Analisis_MAC/wrap/hasil_sta/{log})")

def entitas(rpt, judul, kolom_le, kolom_reg):
    t = rpt.read_text(errors="replace").splitlines()
    i = next(k for k, b in enumerate(t) if b.startswith("; " + judul))
    kepala, hasil = None, {}
    for b in t[i + 1:]:
        if b.startswith("+"): continue
        if not b.strip() or b.lstrip("; ").startswith("Note"): break
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if kepala is None: kepala = sel; continue
        r = dict(zip(kepala, sel))
        f = lambda s: int(re.match(r"(\d+)", s).group(1))
        hasil[r["Full Hierarchy Name"]] = (f(r[kolom_le]), f(r[kolom_reg]))
    return hasil

def ringkas(rev):
    out = DI_SINI / f"output_{rev}"
    fit = (out / f"{rev}.fit.summary").read_text(errors="replace")
    le = int(re.search(r"Total logic elements : ([\d,]+)", fit).group(1).replace(",", ""))
    sta = (out / f"{rev}.sta.rpt").read_text(errors="replace")
    i = sta.index("; Slow 1200mV 85C Model Fmax Summary")
    m = re.search(r";\s*([\d.]+) MHz\s*;\s*([\d.]+) MHz\s*;", sta[i:])
    tr = (DI_SINI / "hasil_sta" / f"{rev}_slow85.rpt").read_text(errors="replace")
    dd = re.search(r"Data Delay\s*;\s*([\d.]+)", tr)
    sl = re.search(r"Slack\s*;\s*(-?[\d.]+)", tr)
    fe = entitas(out / f"{rev}.fit.rpt", "Fitter Resource Utilization by Entity", "Logic Cells", "Dedicated Logic Registers")
    me = entitas(out / f"{rev}.map.rpt", "Analysis & Synthesis Resource Utilization by Entity", "Combinational ALUTs", "Dedicated Logic Registers")
    dut_f = sum(v[0] for k, v in fe.items() if k.count("|") == 2)      # anak langsung top (u_dut / rantai)
    dut_m = sum(v[0] for k, v in me.items() if k.count("|") == 2)
    return {"revisi": rev, "LE_total": le, "LE_dut_fitter": dut_f, "komb_dut_sintesis": dut_m,
            "fmax_mhz": float(m.group(1)) if m else "", "fmax_terbatas_mhz": float(m.group(2)) if m else "",
            "data_delay_ns": float(dd.group(1)) if dd else "", "slack_ns": float(sl.group(1)) if sl else "",
            "sumber": f"9_Analisis_MAC/wrap/output_{rev}/{rev}.fit.rpt, .sta.rpt; hasil_sta/{rev}_slow85.rpt"}

def main():
    pilih = [r for r in REV if r in sys.argv[1:]] or REV
    (DI_SINI / "hasil_sta").mkdir(exist_ok=True)
    arsip = AKAR / "3_Quartus" / "hasil_mentah" / f"{date.today().isoformat()}_analisis_mac_sendirian"
    arsip.mkdir(parents=True, exist_ok=True)
    baris = []
    for rev in pilih:
        print(f"--> {rev}", flush=True)
        tulis(rev)
        jalan([str(QUARTUS / "quartus_sh.exe"), "--flow", "compile", rev, "-c", rev], f"log_{rev}_kompilasi.txt")
        jalan([str(QUARTUS / "quartus_sta.exe"), "-t", "wrap_sta.tcl", rev], f"log_{rev}_sta.txt")
        r = ringkas(rev); baris.append(r)
        print(f"    LE {r['LE_total']} (dut {r['LE_dut_fitter']}), Fmax {r['fmax_mhz']} MHz, data delay {r['data_delay_ns']} ns", flush=True)
        for ek in ("fit.rpt", "fit.summary", "map.rpt", "sta.rpt", "sta.summary"):
            p = DI_SINI / f"output_{rev}" / f"{rev}.{ek}"
            if p.exists(): shutil.copy(p, arsip)
        shutil.copy(DI_SINI / "hasil_sta" / f"{rev}_slow85.rpt", arsip)
        shutil.copy(DI_SINI / f"{rev}.qsf", arsip)
    with open(AKAR / "9_Analisis_MAC" / "hasil" / "T10_sendirian.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0])); w.writeheader(); w.writerows(baris)
    print(f"\nSelesai. hasil/T10_sendirian.csv; arsip {arsip.relative_to(AKAR)}")

if __name__ == "__main__":
    main()
