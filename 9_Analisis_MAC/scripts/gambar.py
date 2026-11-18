#!/usr/bin/env python3
"""Membuat gambar untuk naskah dari CSV di hasil/ (Tugas 3, 4, 11).
Keluaran: hasil/gambar/G_*.png (300 dpi). Angka ditulis dengan koma desimal (Bahasa Indonesia)."""
import csv
from pathlib import Path
from statistics import mean, stdev
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AKAR = Path(__file__).resolve().parents[1]
H = AKAR / "hasil"; G = H / "gambar"; G.mkdir(parents=True, exist_ok=True)
VAR = ["HARD", "ARITH", "STRUCT"]
WARNA = {"HARD": "#14806f", "ARITH": "#4a5868", "STRUCT": "#8a96a3"}
C_PENGALI, C_LAIN, C_SISA = "#e89b2e", "#c9d1d9", "#4a5868"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})
k = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")

def baca(n): return list(csv.DictReader(open(H / n)))

# ---- G1: rincian delay tahap 1 dan tahap 2 (Slow 85C) -----------------------
t4 = [r for r in baca("T4_tahap.csv") if r["model"] == "slow85"]
fig, ax = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
for i, tahap in enumerate(["tahap1", "tahap2"]):
    a = ax[i]
    for j, v in enumerate(VAR):
        r = next(x for x in t4 if x["varian"] == v and x["laporan"] == tahap)
        lain, pg, mac = float(r["t_lain_ns"]), float(r["t_pengali_ns"]), float(r["t_mac_lain_ns"])
        a.barh(j, lain, color=C_LAIN, edgecolor="white")
        a.barh(j, pg, left=lain, color=C_PENGALI, edgecolor="white")
        a.barh(j, mac, left=lain + pg, color=C_SISA, edgecolor="white")
        tot = float(r["data_delay_ns"])
        a.text(tot + 0.3, j, f"{k(tot,3)} ns ({r['tingkat_logika']} tingkat)", va="center", fontsize=9)
    a.axvline(20, color="#c0392b", lw=1.2, ls="--"); a.text(20, 2.55, "periode 20 ns", color="#c0392b",
                                                          ha="right", fontsize=8)
    a.set_xlim(0, 26); a.set_xlabel("delay jalur data terburuk (ns)")
    a.set_title("Tahap 1: memori → pengali → p_q" if tahap == "tahap1" else "Tahap 2: p_q → penjumlah → akumulator",
                fontsize=10)
ax[0].set_yticks(range(3)); ax[0].set_yticklabels(VAR); ax[0].invert_yaxis()
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=C_LAIN, label="sumber (register memori/p_q)"),
                    Patch(color=C_PENGALI, label="di dalam pengali (u_mul)"),
                    Patch(color=C_SISA, label="bagian lain unit MAC")],
           loc="lower center", ncol=3, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(G / "G_T4_delay_tahap.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- G2: Fmax per seed --------------------------------------------------------
t11 = baca("T11_seed.csv")
fig, a = plt.subplots(figsize=(6, 3.2))
for j, v in enumerate(VAR):
    f = [float(r["fmax_mhz"]) for r in t11 if r["varian"] == v]
    a.scatter([j] * len(f), f, color=WARNA[v], s=28, zorder=3)
    m, s = mean(f), stdev(f)
    a.errorbar(j + 0.18, m, yerr=s, fmt="D", color="black", ms=4, capsize=4, zorder=4)
    a.text(j + 0.28, m, f"{k(m)} ± {k(s)}", va="center", fontsize=8.5)
a.axhline(50, color="#c0392b", lw=1.2, ls="--"); a.text(2.45, 50.8, "syarat 50 MHz", color="#c0392b",
                                                      ha="right", fontsize=8)
a.set_xticks(range(3)); a.set_xticklabels(VAR); a.set_xlim(-0.4, 2.8)
a.set_ylabel("Fmax, Slow 1200mV 85C (MHz)"); a.set_ylim(45, 88)
a.set_title("Fmax lima seed fitter per varian (titik) dan rata-rata ± simpangan baku", fontsize=9.5)
fig.tight_layout(); fig.savefig(G / "G_T11_fmax_seed.png", dpi=300); plt.close(fig)

# ---- G3: LE per lajur MAC -----------------------------------------------------
t3 = {r["varian"]: r for r in baca("T3_ringkasan_lajur.csv")}
fig, a = plt.subplots(figsize=(6, 2.8))
for j, v in enumerate(VAR):
    pg, sisa = float(t3[v]["u_mul_LE_rata2"]), float(t3[v]["non_pengali_LE_rata2"])
    a.barh(j, pg, color=C_PENGALI, edgecolor="white")
    a.barh(j, sisa, left=pg, color=C_SISA, edgecolor="white")
    a.text(pg + sisa + 4, j, f"{k(pg + sisa)} LE", va="center", fontsize=9)
    if pg: a.text(pg / 2, j, k(pg), ha="center", va="center", fontsize=8.5)
    a.text(pg + sisa / 2, j, k(sisa), ha="center", va="center", fontsize=8.5, color="white")
a.set_yticks(range(3)); a.set_yticklabels(["HARD\n(+1 pengali\nembedded)", "ARITH", "STRUCT"]); a.invert_yaxis()
a.set_xlabel("logic element per lajur MAC (rata-rata 8 lajur)"); a.set_xlim(0, 340)
fig.legend(handles=[Patch(color=C_PENGALI, label="pengali (u_mul)"),
                    Patch(color=C_SISA, label="bagian lain unit MAC")],
           loc="lower center", ncol=2, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(G / "G_T3_LE_lajur.png", dpi=300, bbox_inches="tight"); plt.close(fig)
print("ok:", sorted(p.name for p in G.glob("G_*.png")))
