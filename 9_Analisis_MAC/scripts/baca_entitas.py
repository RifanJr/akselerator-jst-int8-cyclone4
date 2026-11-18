#!/usr/bin/env python3
"""Tugas 3 — rincian luas per entitas dari laporan fitter Quartus.

Membaca bagian "Fitter Resource Utilization by Entity" di <revisi>.fit.rpt,
lalu menulis:
  hasil/T3_entitas_datar.csv   : satu baris per entitas per varian
  hasil/T3_ringkasan_lajur.csv : per varian, rata-rata 8 lajur:
                                 mac_unit total, u_mul, non-pengali (= total - u_mul)

Angka "Logic Cells" Quartus berformat "total (sendiri)". Kolom *_sendiri
adalah LE yang dimiliki entitas itu tanpa anak-anaknya.

Pakai:  python3 baca_entitas.py <folder_hasil_mentah_hard> <..._arith> <..._struct>
"""
import csv, re, sys
from pathlib import Path
from statistics import mean

AKAR = Path(__file__).resolve().parents[1]
HASIL = AKAR / "hasil"
POLA = re.compile(r"^(\d+)\s*\((\d+)\)$")

def pecah(s):
    m = POLA.match(s.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def baca(rpt):
    teks = rpt.read_text(errors="replace").splitlines()
    i = next(k for k, b in enumerate(teks) if b.startswith("; Fitter Resource Utilization by Entity"))
    kepala, baris = None, []
    for b in teks[i + 1:]:
        if b.startswith("+") or not b.strip():
            if baris and not b.strip():
                break
            continue
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if kepala is None:
            kepala = sel
            continue
        if b.lstrip("; ").startswith("Note"):
            break
        baris.append(dict(zip(kepala, sel)))
    return baris

def main(folders):
    semua, ringkas = [], []
    for f in (Path(x).resolve() for x in folders):
        rpt = next(f.glob("*.fit.rpt"))
        varian = rpt.stem.replace("daya_", "").replace(".fit", "").upper()
        mac, mul = {}, {}
        for r in baca(rpt):
            lc_t, lc_s = pecah(r["Logic Cells"])
            rg_t, rg_s = pecah(r["Dedicated Logic Registers"])
            nama = r["Full Hierarchy Name"]
            semua.append({
                "varian": varian, "entitas": r["Entity Name"] or "top_papan",
                "hierarki": nama, "LE_total": lc_t, "LE_sendiri": lc_s,
                "reg_total": rg_t, "reg_sendiri": rg_s,
                "M9K": r["M9Ks"], "pengali_9x9": r["DSP 9x9"],
                "pengali_embedded_total": r["DSP Elements"],
                "LUT_only": pecah(r["LUT-Only LCs"])[0],
                "reg_only": pecah(r["Register-Only LCs"])[0],
                "LUT_reg": pecah(r["LUT/Register LCs"])[0],
                "sumber": str(rpt.relative_to(AKAR.parent)),
            })
            m = re.search(r"g_lajur\[(\d)\]\.u_mac", nama)
            if m and nama.endswith("u_mac"):
                mac[m.group(1)] = (lc_t, rg_t)
            elif m and "u_mul" in nama.split("|")[-1]:
                mul[m.group(1)] = (lc_t, rg_t)
        assert len(mac) == 8, f"{varian}: lajur MAC ditemukan {len(mac)}"
        mul_le = [mul.get(k, (0, 0))[0] for k in mac]
        mac_le = [mac[k][0] for k in mac]
        ringkas.append({
            "varian": varian,
            "mac_unit_LE_rata2": round(mean(mac_le), 2),
            "mac_unit_LE_min": min(mac_le), "mac_unit_LE_maks": max(mac_le),
            "u_mul_LE_rata2": round(mean(mul_le), 2),
            "non_pengali_LE_rata2": round(mean(a - b for a, b in zip(mac_le, mul_le)), 2),
            "mac_unit_reg_rata2": round(mean(mac[k][1] for k in mac), 2),
            "catatan_u_mul": "tidak muncul sebagai entitas" if not mul else "",
            "sumber": str(rpt.relative_to(AKAR.parent)),
        })
    HASIL.mkdir(exist_ok=True)
    with open(HASIL / "T3_entitas_datar.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(semua[0]))
        w.writeheader(); w.writerows(semua)
    with open(HASIL / "T3_ringkasan_lajur.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ringkas[0]))
        w.writeheader(); w.writerows(ringkas)
    for r in ringkas:
        print(r)

if __name__ == "__main__":
    main(sys.argv[1:])
