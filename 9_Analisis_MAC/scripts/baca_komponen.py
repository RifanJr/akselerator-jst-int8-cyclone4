#!/usr/bin/env python3
"""Tugas 6 dan 7 — banding datar vs terpecah, dan luas per komponen versi terpecah.

Sumber:
  datar    : 8_Varian_Pengali/hasil_mentah/2026-11-03_os_<v>/daya_<v>.{fit.summary,fit.rpt,sta.rpt}
  terpecah : 8_Varian_Pengali/output_pecah_<v>/pecah_<v>.{fit.summary,fit.rpt,sta.rpt}
Keluaran:
  hasil/T6_datar_vs_terpecah.csv
  hasil/T7_entitas_terpecah.csv   (semua entitas, semua varian)
  hasil/T7_komponen_luas.csv      (per varian per komponen; rata-rata 8 lajur untuk komponen MAC)
  hasil/T7_mode_LE.csv            (LE mode normal/aritmetik seluruh chip)
"""
import csv, re, sys
from pathlib import Path
from statistics import mean
sys.path.insert(0, str(Path(__file__).resolve().parent))
from baca_entitas import baca, pecah

AKAR = Path(__file__).resolve().parents[2]
HASIL = AKAR / "9_Analisis_MAC" / "hasil"
VAR = ["hard", "arith", "struct"]

def berkas(v, jenis, ek):
    if jenis == "datar":
        return AKAR / "3_Quartus" / "hasil_mentah" / f"2026-11-03_os_{v}" / f"daya_{v}.{ek}"
    return AKAR / "8_Varian_Pengali" / f"output_pecah_{v}" / f"pecah_{v}.{ek}"

def angka(s): return int(s.replace(",", ""))

def ringkas(v, jenis):
    t = berkas(v, jenis, "fit.summary").read_text(errors="replace")
    le = angka(re.search(r"Total logic elements : ([\d,]+)", t).group(1))
    reg = angka(re.search(r"Total registers : ([\d,]+)", t).group(1))
    s = berkas(v, jenis, "sta.rpt").read_text(errors="replace")
    i = s.index("; Slow 1200mV 85C Model Fmax Summary")      # tabel, bukan daftar isi
    fmax = float(re.search(r";\s*([\d.]+) MHz\s*;\s*[\d.]+ MHz\s*;", s[i:]).group(1))
    f = berkas(v, jenis, "fit.rpt").read_text(errors="replace")
    i = f.index("; Logic elements by mode")
    nrm = int(re.search(r"normal mode\s*;\s*(\d+)", f[i:]).group(1))
    ari = int(re.search(r"arithmetic mode\s*;\s*(\d+)", f[i:]).group(1))
    return le, reg, fmax, nrm, ari

def baca_map(rpt):
    """Analysis & Synthesis Resource Utilization by Entity: fungsi kombinasional dan register per
    entitas. Berbeda dengan LE fitter, angka ini aditif (satu LE yang berisi LUT entitas A dan
    register entitas B tidak dihitung dua kali)."""
    t = rpt.read_text(errors="replace").splitlines()
    i = next(k for k, b in enumerate(t) if b.startswith("; Analysis & Synthesis Resource Utilization by Entity"))
    hasil, kepala = {}, None
    for b in t[i + 1:]:
        if b.startswith("+"):
            continue
        if not b.strip() or b.lstrip("; ").startswith("Note"):
            break
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if kepala is None:
            kepala = sel; continue
        r = dict(zip(kepala, sel))
        hasil[r["Full Hierarchy Name"]] = (pecah(r["Combinational ALUTs"])[0], pecah(r["Dedicated Logic Registers"])[0])
    return hasil

KOMP_MAC = [("M1", "u_mul", "pengali"), ("M2", "u_t1", "register tahap 1"), ("M3", "u_mux", "MUX acc_base"),
            ("M4", "u_add", "penjumlah 32 bit"), ("M5", "u_acc", "register akumulator"), ("M6", "u_hs", "handshake"),
            ("M0", "mac_unit", "logika mac_unit di luar submodul")]
KOMP_EPI = [("E1", "u_round", "pembulatan"), ("E2", "u_shift", "penggeser"), ("E3", "u_relu", "ReLU"),
            ("E4", "u_sat", "saturasi"), ("E5", "u_out", "register keluaran"), ("E0", "epilog_unit", "epilog total")]

def main():
    t6, mode, semua, komp = [], [], [], []
    for v in VAR:
        d, p = ringkas(v, "datar"), ringkas(v, "terpecah")
        for k, nama in ((0, "LE total"), (1, "register"), (2, "Fmax Slow 85C (MHz)")):
            sp = 100 * (p[k] - d[k]) / d[k]
            t6.append({"varian": v.upper(), "ukuran": nama, "datar": d[k], "terpecah": p[k],
                       "selisih_persen": round(sp, 2), "lebih_2_persen": abs(sp) > 2})
        mode.append({"varian": v.upper(), "terpecah_LE_normal": p[3], "terpecah_LE_aritmetik": p[4],
                     "datar_LE_normal": d[3], "datar_LE_aritmetik": d[4]})
        rpt = berkas(v, "terpecah", "fit.rpt")
        kel = {}
        for r in baca(rpt):
            nama = r["Full Hierarchy Name"]
            lt, ls = pecah(r["Logic Cells"]); gt, gs = pecah(r["Dedicated Logic Registers"])
            semua.append({"varian": v.upper(), "hierarki": nama, "entitas": r["Entity Name"],
                          "LE_total": lt, "LE_sendiri": ls, "reg_total": gt, "reg_sendiri": gs,
                          "LUT_only": pecah(r["LUT-Only LCs"])[0], "reg_only": pecah(r["Register-Only LCs"])[0],
                          "LUT_reg": pecah(r["LUT/Register LCs"])[0], "pengali_9x9": r["DSP 9x9"],
                          "sumber": str(rpt.relative_to(AKAR)).replace("\\", "/")})
            bag = nama.strip("|").split("|")
            m = re.match(r"mac_unit:g_lajur\[(\d)\]\.u_mac$", bag[1]) if len(bag) > 1 else None
            if m and len(bag) == 2:
                kel.setdefault("mac_unit", []).append((lt, ls, gt, gs))
            elif m and len(bag) == 3:
                inst = bag[2].split(":")[-1]
                inst = "u_mul" if inst.endswith("u_mul") else inst
                kel.setdefault(inst, []).append((lt, ls, gt, gs))
            elif len(bag) > 1 and bag[1] == "epilog_unit:u_epi":
                inst = "epilog_unit" if len(bag) == 2 else bag[2].split(":")[-1]
                kel.setdefault(inst, []).append((lt, ls, gt, gs))
        assert len(kel["mac_unit"]) == 8, v
        # entitas tanpa LE tidak tercantum di laporan -> dihitung 0 agar rata-rata tetap atas 8 lajur
        for inst in ("u_mul", "u_t1", "u_mux", "u_add", "u_acc", "u_hs"):
            kel.setdefault(inst, [])
            kel[inst] += [(0, 0, 0, 0)] * (8 - len(kel[inst]))
        peta = baca_map(berkas(v, "terpecah", "map.rpt"))
        def sintesis(inst, lajur=None):
            for nama, (c, g) in peta.items():
                bag = nama.strip("|").split("|")
                if lajur is not None:
                    if len(bag) < 2 or bag[1] != f"mac_unit:g_lajur[{lajur}].u_mac":
                        continue
                    if (inst == "mac_unit" and len(bag) == 2) or (len(bag) == 3 and (bag[2].endswith(":" + inst) or (inst == "u_mul" and bag[2].endswith("u_mul")))):
                        return c, g
                else:
                    if len(bag) > 1 and bag[1] == "epilog_unit:u_epi" and \
                       ((inst == "epilog_unit" and len(bag) == 2) or (len(bag) == 3 and bag[2].endswith(":" + inst))):
                        return c, g
            return 0, 0
        tot_mac = mean(x[0] for x in kel["mac_unit"])
        for kode, inst, ket in KOMP_MAC:
            xs = kel.get(inst, [(0, 0, 0, 0)])
            ambil = (lambda x: (x[1], x[3])) if inst == "mac_unit" else (lambda x: (x[0], x[2]))
            le = [ambil(x)[0] for x in xs]
            sy = [sintesis(inst, k) for k in range(8)]
            komp.append({"varian": v.upper(), "kode": kode, "komponen": ket, "instans": inst, "n": len(xs),
                         "sint_komb_rata2": round(mean(c for c, _ in sy), 2), "sint_reg_rata2": round(mean(g for _, g in sy), 2),
                         "LE_rata2": round(mean(le), 2), "LE_min": min(le), "LE_maks": max(le),
                         "reg_rata2": round(mean(ambil(x)[1] for x in xs), 2),
                         "persen_mac_unit": round(100 * mean(le) / tot_mac, 1), "persen_epilog": "",
                         "persen_LE_sistem": round(100 * 8 * mean(le) / p[0], 2)})
        # M0 = logika milik mac_unit sendiri (total dikurangi anak), versi sintesis
        anak = [r for r in komp if r["varian"] == v.upper() and r["kode"] in ("M1", "M2", "M3", "M4", "M5", "M6")]
        m0 = next(r for r in komp if r["varian"] == v.upper() and r["kode"] == "M0")
        tot_s = mean(sintesis("mac_unit", k)[0] for k in range(8)), mean(sintesis("mac_unit", k)[1] for k in range(8))
        m0["sint_komb_rata2"] = round(tot_s[0] - sum(r["sint_komb_rata2"] for r in anak), 2)
        m0["sint_reg_rata2"] = round(tot_s[1] - sum(r["sint_reg_rata2"] for r in anak), 2)
        komp.append({"varian": v.upper(), "kode": "MAC", "komponen": "mac_unit total", "instans": "mac_unit", "n": 8,
                     "sint_komb_rata2": round(mean(sintesis("mac_unit", k)[0] for k in range(8)), 2),
                     "sint_reg_rata2": round(mean(sintesis("mac_unit", k)[1] for k in range(8)), 2),
                     "LE_rata2": round(tot_mac, 2), "LE_min": min(x[0] for x in kel["mac_unit"]),
                     "LE_maks": max(x[0] for x in kel["mac_unit"]), "reg_rata2": round(mean(x[2] for x in kel["mac_unit"]), 2),
                     "persen_mac_unit": 100.0, "persen_epilog": "", "persen_LE_sistem": round(100 * 8 * tot_mac / p[0], 2)})
        tot_epi = kel["epilog_unit"][0][0]
        for kode, inst, ket in KOMP_EPI:
            x = kel.get(inst, [(0, 0, 0, 0)])[0]
            le = x[1] if False else x[0]
            c, g = sintesis(inst)
            komp.append({"varian": v.upper(), "kode": kode, "komponen": ket, "instans": inst, "n": 1,
                         "sint_komb_rata2": c, "sint_reg_rata2": g,
                         "LE_rata2": le, "LE_min": le, "LE_maks": le, "reg_rata2": x[2], "persen_mac_unit": "",
                         "persen_epilog": round(100 * le / tot_epi, 1) if tot_epi else "",
                         "persen_LE_sistem": round(100 * le / p[0], 2)})
    for nama, rows in (("T6_datar_vs_terpecah", t6), ("T7_mode_LE", mode),
                       ("T7_entitas_terpecah", semua), ("T7_komponen_luas", komp)):
        kol = list(dict.fromkeys(k for r in rows for k in r))
        with open(HASIL / f"{nama}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=kol); w.writeheader(); w.writerows(rows)
    for r in t6: print(r)
    for r in mode: print(r)
    print("varian kode instans | sintesis komb reg | fitter LE [min-maks] reg %mac %epi %sistem")
    for r in komp:
        print(r["varian"], r["kode"], r["instans"], "|", r["sint_komb_rata2"], r["sint_reg_rata2"], "|", r["LE_rata2"], f"[{r['LE_min']}-{r['LE_maks']}]",
              r["reg_rata2"], r["persen_mac_unit"], r["persen_epilog"], r["persen_LE_sistem"])

if __name__ == "__main__":
    main()
