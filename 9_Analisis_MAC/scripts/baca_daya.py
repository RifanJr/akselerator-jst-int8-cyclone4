#!/usr/bin/env python3
"""Tugas 8 — daya dinamis per komponen dari Thermal Power Dissipation by Hierarchy.

Sumber: 8_Varian_Pengali/output_pecah_<v>/pecah_<v>.pow.{rpt,summary} (versi terpecah, 4 Nov 2026)
Daya dinamis entitas = Block Thermal Dynamic + Routing Thermal Dynamic (kolom total, termasuk anak).
Daya statis tidak dibagi per komponen (sebagian besar hanya tercatat di top_papan).
Keluaran: hasil/T8_daya_hierarki.csv (semua baris), hasil/T8_daya_komponen.csv (ringkasan)
Catatan: tabel "by Block" tidak dipakai karena tidak lengkap (jumlahnya hanya 80-88 % daya inti dinamis).
Jumlah tabel per hierarki = daya inti dinamis + daya dinamis I/O (diperiksa).
Semua angka daya adalah PERKIRAAN Power Analyzer, bukan pengukuran fisik.
"""
import csv, re
from pathlib import Path
from statistics import mean

AKAR = Path(__file__).resolve().parents[2]
HASIL = AKAR / "9_Analisis_MAC" / "hasil"
MW = re.compile(r"([\d.]+) mW \(([\d.]+) mW\)")

def nilai(s):
    m = MW.search(s)
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)

def baca(v):
    rpt = AKAR / "8_Varian_Pengali" / f"output_pecah_{v}" / f"pecah_{v}.pow.rpt"
    t = rpt.read_text(errors="replace").splitlines()
    i = next(k for k, b in enumerate(t) if b.startswith("; Thermal Power Dissipation by Hierarchy"))
    baris = {}
    for b in t[i + 3:]:
        if b.startswith("+"):
            if baris: break
            continue
        sel = [c.strip() for c in b.strip().strip(";").split(";")]
        if len(sel) < 6 or not sel[0].startswith("|"):
            continue
        tot, blk, sta, rut = (nilai(x) for x in sel[1:5])
        baris[sel[5]] = {"total": tot[0], "statis": sta[0], "dinamis": round(blk[0] + rut[0], 4),
                         "dinamis_sendiri": round(blk[1] + rut[1], 4)}
    s = (AKAR / "8_Varian_Pengali" / f"output_pecah_{v}" / f"pecah_{v}.pow.summary").read_text(errors="replace")
    ring = {k: float(re.search(pola + r" : ([\d.]+) mW", s).group(1)) for k, pola in
            (("total", "Total Thermal Power Dissipation"), ("inti_dinamis", "Core Dynamic Thermal Power Dissipation"),
             ("inti_statis", "Core Static Thermal Power Dissipation"), ("io", "I/O Thermal Power Dissipation"))}
    ring["keyakinan"] = re.search(r"Power Estimation Confidence : (\w+)", s).group(1)
    return rpt, baris, ring

KOMP = [("M1", "u_mul"), ("M2", "u_t1"), ("M3", "u_mux"), ("M4", "u_add"), ("M5", "u_acc"), ("M6", "u_hs")]
EPI = [("E1", "u_round"), ("E2", "u_shift"), ("E3", "u_relu"), ("E4", "u_sat"), ("E5", "u_out")]

def main():
    semua, ring_rows = [], []
    for v in ("hard", "arith", "struct"):
        rpt, b, r = baca(v)
        for nama, x in b.items():
            semua.append({"varian": v.upper(), "hierarki": nama, **x})
        def cari(pola):
            return [x for n, x in b.items() if re.search(pola, n)]
        lajur = cari(r"\|mac_unit:g_lajur\[\d\]\.u_mac$")
        assert len(lajur) == 8
        tambah = lambda kode, ket, mw, n: ring_rows.append({
            "varian": v.upper(), "kode": kode, "komponen": ket, "n": n,
            "dinamis_mw_total": round(mw, 3), "dinamis_mw_per_lajur": round(mw / 8, 4) if n == 8 else "",
            "persen_inti_dinamis": round(100 * mw / r["inti_dinamis"], 2), "keyakinan": r["keyakinan"],
            "sumber": str(rpt.relative_to(AKAR)).replace("\\", "/")})
        mac8 = sum(x["dinamis"] for x in lajur)
        for kode, inst in KOMP:
            xs = cari(r"\|mac_unit:g_lajur\[\d\]\.u_mac\|[^|]*" + (r"u_mul$" if inst == "u_mul" else ":" + inst + "$"))
            tambah(kode, inst, sum(x["dinamis"] for x in xs), 8)
        tambah("M0", "mac_unit sendiri", sum(x["dinamis_sendiri"] for x in lajur), 8)
        # Pada HARD, register keluaran mem_w dikemas ke register masukan blok pengali embedded, dan
        # Power Analyzer membukukan daya blok pengali embedded (mac_mult) pada entitas mem_w, bukan u_mul.
        # Untuk banding setara: pengali + logika milik mem_w sendiri (register q / blok pengali).
        memw_sendiri = sum(x["dinamis_sendiri"] for x in cari(r"\|mem_w:g_lajur\[\d\]\.u_mem_w$"))
        mul = sum(x["dinamis"] for x in cari(r"\|mac_unit:g_lajur\[\d\]\.u_mac\|[^|]*u_mul$"))
        tambah("M1W", "u_mul + mem_w sendiri (banding setara)", mul + memw_sendiri, 8)
        tambah("WS", "mem_w sendiri (HARD: blok pengali embedded; lain: register q)", memw_sendiri, 8)
        tambah("MAC", "8 lajur mac_unit", mac8, 8)
        epi = cari(r"\|epilog_unit:u_epi$")[0]
        for kode, inst in EPI:
            xs = cari(r"\|epilog_unit:u_epi\|[^|]*:" + inst + "$")
            tambah(kode, inst, sum(x["dinamis"] for x in xs), 1)
        tambah("EPI", "epilog total", epi["dinamis"], 1)
        for kode, pola, ket in (("W", r"\|mem_w:g_lajur\[\d\]\.u_mem_w$", "8 mem_w (M9K bobot)"),
                                ("D", r"\|mem_d:u_mem_d$", "mem_d"), ("C", r"\|ctrl_fsm_p8:u_ctrl$", "ctrl_fsm_p8"),
                                ("A", r"\|argmax10:u_amax$", "argmax10"), ("CI", r"\|altsyncram:citra_rtl_0$", "ROM citra"),
                                ("S", r"\|seg7_scan:u_scan$", "seg7_scan")):
            tambah(kode, ket, sum(x["dinamis"] for x in cari(pola)), len(cari(pola)))
        top = b["|top_papan"]
        tambah("T", "top_papan sendiri", top["dinamis_sendiri"], 1)
        tambah("SUM", "jumlah hierarki (dinamis)", top["dinamis"], 1)
        ring_rows.append({"varian": v.upper(), "kode": "RING", "komponen":
                          f"total {r['total']} mW; inti dinamis {r['inti_dinamis']}; inti statis {r['inti_statis']}; I/O {r['io']}",
                          "keyakinan": r["keyakinan"]})
    for nama, rows in (("T8_daya_hierarki", semua), ("T8_daya_komponen", ring_rows)):
        kol = list(dict.fromkeys(k for x in rows for k in x))
        with open(HASIL / f"{nama}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=kol); w.writeheader(); w.writerows(rows)
    for x in ring_rows:
        print(x["varian"], x["kode"], x["komponen"], x.get("dinamis_mw_total", ""), x.get("dinamis_mw_per_lajur", ""), x.get("persen_inti_dinamis", ""))

if __name__ == "__main__":
    main()
