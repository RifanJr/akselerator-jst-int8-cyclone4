#!/usr/bin/env python3
"""Tugas 12 -- metrik gabungan per varian (HARD, ARITH, STRUCT).

Angka utama dari versi DATAR (aturan Tugas 6):
  - luas, daya, energi: 8_Varian_Pengali/hasil_mentah/2026-11-03_os_<v>/{<v>.json, daya_<v>.pow.rpt}
  - Fmax: rata-rata 5 seed, hasil/T11_ringkasan.csv (Slow 1200mV 85C)
Definisi:
  - operasi MAC per citra = 196*64 + 64*10 = 13.184
  - waktu per citra di papan = 1.708 siklus x 20 ns = 34,16 us
  - energi per operasi MAC = daya dinamis 8 lajur mac_unit x 34,16 us / 13.184
    (dua versi: lajur saja, dan lajur + mem_w sendiri = banding setara karena pada HARD
     daya blok pengali embedded dibukukan di mem_w; lihat log 4 Nov)
  - area x delay = LE total x (1 / Fmax rata-rata)
  - energi x delay = energi per citra x waktu per citra (di 50 MHz dan di Fmax rata-rata)
SEMUA angka daya/energi adalah PERKIRAAN Power Analyzer.
"""
import csv, json, re
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
HASIL = AKAR / "9_Analisis_MAC" / "hasil"
OPS = 196 * 64 + 64 * 10
SIKLUS = 1708
T_US = SIKLUS * 20e-3  # 34,16 us
MW = re.compile(r"([\d.]+) mW \(([\d.]+) mW\)")

def hierarki(rpt):
    t = rpt.read_text(errors="replace").splitlines()
    i = next(k for k, b in enumerate(t) if b.startswith("; Thermal Power Dissipation by Hierarchy"))
    out = {}
    for b in t[i + 3:]:
        if b.startswith("+"):
            if out: break
            continue
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if len(sel) < 6 or not sel[0].startswith("|"): continue
        v = [MW.search(x) for x in sel[1:5]]
        g = lambda m, k: float(m.group(k)) if m else 0.0
        out[sel[5]] = {"dinamis": g(v[1], 1) + g(v[3], 1), "dinamis_sendiri": g(v[1], 2) + g(v[3], 2)}
    return out

def main():
    seed = {r["varian"]: r for r in csv.DictReader(open(HASIL / "T11_ringkasan.csv"))}
    rows = []
    for v in ("hard", "arith", "struct"):
        a = AKAR / "3_Quartus" / "hasil_mentah" / f"2026-11-03_os_{v}"
        j = json.loads((a / f"{v}.json").read_text())
        h = hierarki(a / f"daya_{v}.pow.rpt")
        lajur = sum(x["dinamis"] for n, x in h.items() if re.search(r"\|mac_unit:g_lajur\[\d\]\.u_mac$", n))
        memw = sum(x["dinamis_sendiri"] for n, x in h.items() if re.search(r"\|mem_w:g_lajur\[\d\]\.u_mem_w$", n))
        fmax = float(seed[v.upper()]["fmax_rata2"]); le = j["luas"]["le"]
        e_citra = j["daya"]["energi_uj_per_citra"]
        t_fmax_us = SIKLUS / fmax  # us
        rows.append({
            "varian": v.upper(), "LE_total": le, "fmax_rata2_mhz": fmax,
            "daya_total_mw": j["daya"]["total_mw"], "inti_dinamis_mw": j["daya"]["inti_dinamis_mw"],
            "dinamis_8_lajur_mw": round(lajur, 3), "dinamis_mem_w_sendiri_mw": round(memw, 3),
            "energi_per_MAC_pJ_lajur": round(lajur * 1e-3 * T_US * 1e-6 / OPS * 1e12, 3),
            "energi_per_MAC_pJ_setara": round((lajur + memw) * 1e-3 * T_US * 1e-6 / OPS * 1e12, 3),
            "energi_per_citra_uJ": e_citra,
            "area_x_delay_LE_ns": round(le * 1e3 / fmax, 1),
            "waktu_citra_di_fmax_us": round(t_fmax_us, 3),
            "EDP_50MHz_uJ_us": round(e_citra * T_US, 2),
            "keyakinan_daya": j["daya"]["keyakinan"],
            "catatan": "daya/energi = perkiraan Power Analyzer; Fmax rata-rata 5 seed",
            "sumber": f"8_Varian_Pengali/hasil_mentah/2026-11-03_os_{v}/; hasil/T11_ringkasan.csv"})
    hard = rows[0]
    for r in rows:
        for k in ("LE_total", "energi_per_MAC_pJ_setara", "area_x_delay_LE_ns", "EDP_50MHz_uJ_us"):
            r[f"rasio_{k}_vs_HARD"] = round(r[k] / hard[k], 3)
    with open(HASIL / "T12_metrik.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows: print(r)

if __name__ == "__main__":
    main()
