#!/usr/bin/env python3
"""
Model acuan rancangan WS 4x2, batch 16, dalam Python (bilangan bulat).

Menghitung ke-16 citra dengan URUTAN yang sama persis dengan larik WS
(pasangan neuron g -> ubin t -> citra b), membaca bank bobot dan ROM citra
hasil gen_mem_ws.py, lalu mencocokkan kesepuluh akumulator lapisan 2 setiap
citra dengan 1_Python_PC/uji/golden_uji.txt.

Tujuannya memisahkan dua sumber kesalahan: bila model ini cocok, pemetaan
memori dan urutan perhitungan WS sudah benar, sehingga selisih apa pun di
simulasi Verilog nanti pasti berasal dari RTL.

Aritmetika mengikuti rancangan OS:
    bias lapisan 1 digeser kiri 4, lapisan 2 digeser kiri 1 (ke skala akumulator)
    epilog lapisan 1: geser kanan aritmetik 8, ReLU, saturasi 8 bit bertanda
"""
import re
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
PY = DI_SINI.parent.parent / "1_Python_PC"

R, C, B = 4, 2, 16
G1, T1, G2, T2 = 32, 49, 5, 16
OFFSET_L2 = G1 * T1


def bertanda8(v):
    return v - 256 if v > 127 else v


def baca_hex8(berkas):
    return [bertanda8(int(b, 16)) for b in berkas.read_text().split()]


def baca_coe(berkas):
    return [bertanda8(int(b.strip().rstrip(",;"), 16))
            for b in berkas.read_text().splitlines()
            if b.strip() and "=" not in b]


def epilog(acc):
    v = acc >> 8                    # geser kanan aritmetik
    v = max(v, 0)                   # ReLU
    return max(-128, min(127, v))   # saturasi 8 bit bertanda


def baca_acuan():
    acuan, kini = {}, None
    for b in (PY / "uji" / "golden_uji.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"---\s+citra_(\d+)\.hex\s+MNIST#\d+\s+label\s+\d+\s+prediksi\s+(\d+)", b.strip())
        if m:
            kini = int(m.group(1))
            acuan[kini] = {"prediksi": int(m.group(2)), "acc": [None] * 10}
            continue
        m = re.match(r"digit\s+(\d+)\s*:\s*(-?\d+)", b.strip())
        if m and kini is not None:
            acuan[kini]["acc"][int(m.group(1))] = int(m.group(2))
    return acuan


def main():
    bank = [baca_hex8(DI_SINI / f"mem_w_ws_b{k}.hex") for k in range(R * C)]
    rom = [int(b, 16) for b in (DI_SINI / "citra_ws32.hex").read_text().split()]
    bias1 = baca_coe(PY / "Training" / "export_final" / "bias_layer1.coe")
    bias2 = baca_coe(PY / "Training" / "export_final" / "bias_layer2.coe")

    def kata_ke_suku(k):
        return [bertanda8((k >> (8 * r)) & 0xFF) for r in range(R)]

    # ---- lapisan 1: masukan dibaca dari ROM 32 bit ----
    aktivasi = [[0] * 64 for _ in range(B)]          # aktivasi[b][n]
    for g in range(G1):
        psum = [[0] * B for _ in range(C)]
        for t in range(T1):
            w = [[bank[2 * r + c][g * T1 + t] for c in range(C)] for r in range(R)]
            for b in range(B):
                x = kata_ke_suku(rom[t * 16 + b])
                for c in range(C):
                    awal = (bias1[2 * g + c] << 4) if t == 0 else psum[c][b]
                    psum[c][b] = awal + sum(x[r] * w[r][c] for r in range(R))
        for b in range(B):
            for c in range(C):
                aktivasi[b][2 * g + c] = epilog(psum[c][b])

    # ---- lapisan 2: masukan dari buffer aktivasi (kata 32 bit, t*16 + b) ----
    keluaran = [[0] * 10 for _ in range(B)]
    for g in range(G2):
        psum = [[0] * B for _ in range(C)]
        for t in range(T2):
            w = [[bank[2 * r + c][OFFSET_L2 + g * T2 + t] for c in range(C)] for r in range(R)]
            for b in range(B):
                x = [aktivasi[b][4 * t + r] for r in range(R)]
                for c in range(C):
                    awal = (bias2[2 * g + c] << 1) if t == 0 else psum[c][b]
                    psum[c][b] = awal + sum(x[r] * w[r][c] for r in range(R))
        for b in range(B):
            for c in range(C):
                keluaran[b][2 * g + c] = psum[c][b]

    # ---- cocokkan dengan acuan emas ----
    acuan = baca_acuan()
    salah = 0
    for b in range(B):
        prediksi = max(range(10), key=lambda d: (keluaran[b][d], -d))   # seri: indeks kecil
        sama = sum(1 for d in range(10) if keluaran[b][d] == acuan[b]["acc"][d])
        ok = sama == 10 and prediksi == acuan[b]["prediksi"]
        salah += 0 if ok else 1
        print(f"citra {b:2d}: prediksi {prediksi} (acuan {acuan[b]['prediksi']}), "
              f"akumulator cocok {sama}/10  {'cocok' if ok else 'BEDA'}")
    print("HASIL MODEL WS:", "LULUS" if salah == 0 else f"GAGAL ({salah} citra)")
    return 0 if salah == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
