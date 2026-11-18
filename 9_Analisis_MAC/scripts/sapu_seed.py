#!/usr/bin/env python3
"""Tugas 11 — sapuan seed fitter (versi datar, cabang main).

Untuk tiap varian (HARD, ARITH, STRUCT) dan seed 1..5, skrip ini:
  1. membuat revisi seed_<varian>_s<n> di 8_Varian_Pengali dari daya_<varian>.qsf
     (pengaturan daya/EDA dibuang; SEED <n> ditambahkan),
  2. menjalankan  quartus_sh --flow compile,
  3. membaca Fmax (Slow 1200mV 85C), setup slack, dan LE dari laporan,
  4. menyalin laporan mentah ke 8_Varian_Pengali/hasil_mentah/<tgl>_analisis_mac_seed/,
  5. menulis 9_Analisis_MAC/hasil/T11_seed.csv dan ringkasan rata-rata ± simpangan baku.

Seed 1 adalah bawaan Quartus, jadi seharusnya mengulang hasil 3 Nov.
Jalankan lewat SAPU_SEED.bat (Windows). Kompilasi yang sudah ada dilewati,
jadi skrip aman dijalankan ulang bila terputus.
"""
import csv, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path
from statistics import mean, stdev

REPO = Path(__file__).resolve().parents[2]
KERJA = REPO / "8_Varian_Pengali"
HASIL = REPO / "9_Analisis_MAC" / "hasil"
ARSIP = REPO / "3_Quartus" / "hasil_mentah" / f"{date.today():%Y-%m-%d}_analisis_mac_seed"
QSH = Path(r"C:\altera_lite\25.1std\quartus\bin64\quartus_sh.exe")
VARIAN = ["hard", "arith", "struct"]
SEED = [1, 2, 3, 4, 5]
BUANG = ("POWER_", "EDA_", "VCD", "PROJECT_OUTPUT_DIRECTORY", "SEED")

def buat_revisi(v, s):
    rev = f"seed_{v}_s{s}"
    asal = (KERJA / f"daya_{v}.qsf").read_text().splitlines()
    isi = [b for b in asal if not any(k in b for k in BUANG)]
    isi += [f"set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_seed/{rev}",
            f"set_global_assignment -name SEED {s}"]
    (KERJA / f"{rev}.qsf").write_text("\n".join(isi) + "\n")
    (KERJA / f"{rev}.qpf").write_text(f'QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "{rev}"\n')
    return rev

def baca(rev):
    d = KERJA / "output_seed" / rev
    sta = (d / f"{rev}.sta.rpt").read_text(errors="replace")
    fit = (d / f"{rev}.fit.summary").read_text(errors="replace")
    blok = sta[sta.index("Slow 1200mV 85C Model Fmax Summary"):]
    fmax = float(re.search(r";\s*([\d.]+)\s*MHz\s*;\s*([\d.]+)\s*MHz\s*;\s*clk", blok).group(1))
    blok = sta[sta.index("Slow 1200mV 85C Model Setup Summary"):]
    slack = float(re.search(r";\s*clk\s*;\s*(-?[\d.]+)\s*;", blok).group(1))
    le = int(re.search(r"Total logic elements\s*:\s*([\d,]+)", fit).group(1).replace(",", ""))
    return fmax, slack, le, d

def main():
    if not QSH.exists():
        sys.exit(f"quartus_sh tidak ditemukan: {QSH}")
    ARSIP.mkdir(parents=True, exist_ok=True)
    HASIL.mkdir(parents=True, exist_ok=True)
    baris = []
    for v in VARIAN:
        for s in SEED:
            rev = buat_revisi(v, s)
            sudah = (KERJA / "output_seed" / rev / f"{rev}.sta.rpt").exists()
            if not sudah:
                print(f"\n=== kompilasi {rev} ===", flush=True)
                r = subprocess.run([str(QSH), "--flow", "compile", rev, "-c", rev], cwd=KERJA)
                if r.returncode != 0:
                    print(f"GAGAL: {rev}"); continue
            fmax, slack, le, d = baca(rev)
            tujuan = ARSIP / rev
            tujuan.mkdir(exist_ok=True)
            for f in d.glob(f"{rev}.*"):
                if f.suffix in (".rpt", ".summary"):
                    shutil.copy2(f, tujuan / f.name)
            baris.append(dict(varian=v.upper(), seed=s, fmax_mhz=fmax, setup_slack_ns=slack,
                              LE=le, sumber=f"8_Varian_Pengali/hasil_mentah/{ARSIP.name}/{rev}/{rev}.sta.rpt"))
            print(baris[-1], flush=True)
    with open(HASIL / "T11_seed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0])); w.writeheader(); w.writerows(baris)
    with open(HASIL / "T11_ringkasan.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["varian", "n", "fmax_rata2", "fmax_sd", "fmax_min", "fmax_maks", "LE_rata2", "LE_sd"])
        for v in VARIAN:
            f = [b["fmax_mhz"] for b in baris if b["varian"] == v.upper()]
            l = [b["LE"] for b in baris if b["varian"] == v.upper()]
            if len(f) >= 2:
                w.writerow([v.upper(), len(f), round(mean(f), 3), round(stdev(f), 3), min(f), max(f),
                            round(mean(l), 1), round(stdev(l), 1)])
    print("\nSelesai. Lihat 9_Analisis_MAC/hasil/T11_seed.csv dan T11_ringkasan.csv")

if __name__ == "__main__":
    main()
