#!/usr/bin/env python3
"""Tugas 4 — parsir laporan report_timing (hasil/T4/<varian>/*.rpt) ke hasil/T4_tahap.csv.

Untuk jalur terburuk (Path #1) tiap laporan diambil: slack, simpul asal/tujuan,
clock skew, data delay, jumlah tingkat logika, total delay interkoneksi (IC) dan
sel (Cell) pada jalur data, serta pembagian waktu jalur data menurut tempatnya:
  t_pengali  : elemen di dalam u_mul (termasuk blok mac_mult/mac_out pada HARD)
  t_mac_lain : elemen di u_mac di luar u_mul (mis. LE p_q, MUX, penjumlah)
  t_lain     : selain itu (memori, pengendali, epilog, argmax)
Pembagian dihitung dari kolom Incr pada "Data Arrival Path" setelah baris "data path".
"""
import csv, re
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
T4 = AKAR / "hasil" / "T4"

def angka(s):
    try: return float(s)
    except ValueError: return None

def parsir(p):
    t = p.read_text(errors="replace")
    if "TIDAK ADA REGISTER" in t or "GALAT" in t[:200]:
        return {"catatan": t.strip()[:150]}
    if "Path #1" not in t:
        return {"catatan": "tidak ada jalur"}
    blok = t[t.index("Path #1"):]
    nxt = blok.find("Path #2")
    blok = blok[: nxt if nxt > 0 else None]
    def prop(nama):
        m = re.search(r";\s*" + re.escape(nama) + r"\s*;\s*([^;]*?)\s*;", blok)
        return m.group(1) if m else ""
    r = {"slack_ns": angka(prop("Slack")), "dari": prop("From Node"), "ke": prop("To Node"),
         "data_delay_ns": angka(prop("Data Delay")), "clock_skew_ns": angka(prop("Clock Skew"))}
    m = re.search(r";\s*Number of Logic Levels\s*;\s*;\s*(\d+)", blok)
    r["tingkat_logika"] = int(m.group(1)) if m else None
    data = blok[blok.index(";   Data "):] if ";   Data " in blok else ""
    for jenis in ("IC", "Cell"):
        m = re.search(r";\s*" + jenis + r"\s*;\s*;\s*(\d+)\s*;\s*([\d.]+)\s*;\s*(\d+)", data)
        if m:
            r[f"{jenis}_jumlah"] = int(m.group(1)); r[f"{jenis}_ns"] = float(m.group(2)); r[f"{jenis}_pct"] = int(m.group(3))
    arr = blok[blok.index("; Data Arrival Path"):]
    arr = arr[arr.index("data path"):]
    tp = tm = tl = 0.0
    for b in arr.splitlines()[1:]:
        if b.startswith("+"): break
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if len(sel) < 7: continue
        inc = angka(sel[1]); el = sel[6]
        if inc is None: continue
        if "u_mul" in el or "mac_mult" in el or "mac_out" in el: tp += inc
        elif "u_mac" in el: tm += inc
        else: tl += inc
    r.update(t_pengali_ns=round(tp, 3), t_mac_lain_ns=round(tm, 3), t_lain_ns=round(tl, 3))
    return r

def main():
    baris = []
    for v in ("hard", "arith", "struct"):
        for p in sorted((T4 / v).glob("*.rpt")):
            if p.stem.startswith("fmax"): continue
            jenis, model = p.stem.rsplit("_", 1)
            r = {"varian": v.upper(), "laporan": jenis, "model": model}
            r.update(parsir(p))
            r["sumber"] = f"9_Analisis_MAC/hasil/T4/{v}/{p.name}"
            baris.append(r)
    kolom = ["varian", "laporan", "model", "slack_ns", "data_delay_ns", "clock_skew_ns", "tingkat_logika",
             "IC_jumlah", "IC_ns", "IC_pct", "Cell_jumlah", "Cell_ns", "Cell_pct",
             "t_pengali_ns", "t_mac_lain_ns", "t_lain_ns", "dari", "ke", "catatan", "sumber"]
    with open(AKAR / "hasil" / "T4_tahap.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=kolom, extrasaction="ignore"); w.writeheader(); w.writerows(baris)
    for r in baris:
        if r["model"] == "slow85":
            print(f'{r["varian"]:6} {r["laporan"]:12} slack={r.get("slack_ns")} dd={r.get("data_delay_ns")} '
                  f'lv={r.get("tingkat_logika")} IC={r.get("IC_ns")}({r.get("IC_pct")}%) Cell={r.get("Cell_ns")}({r.get("Cell_pct")}%) '
                  f'pengali={r.get("t_pengali_ns")} maclain={r.get("t_mac_lain_ns")} lain={r.get("t_lain_ns")} '
                  f'| {r.get("dari","")} -> {r.get("ke","")} {r.get("catatan","")}')

if __name__ == "__main__":
    main()
