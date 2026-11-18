#!/usr/bin/env python3
"""Membangkitkan vektor uji tb_mac_unit dari model beku 1_Python_PC.

Keluaran (folder tujuan = argumen pertama, bawaan: folder skrip ini):
  tv_w.hex     12.544 baris  bobot lapisan 1, urutan neuron lalu suku (64 x 196), 8 bit
  tv_x.hex        196 baris  citra uji (input_sample.coe), 8 bit
  tv_init.hex      64 baris  bias Q1.7 digeser 4 ke kiri, 32 bit
  exp_acc.hex      64 baris  akumulator acuan, 32 bit
  exp_act.hex      64 baris  aktivasi acuan (ReLU, geser 8 truncate, saturasi), 8 bit

Aturan bilangan beku: akumulator 32 bit bertanda; geser aritmetika 8 ke kanan
(truncate ke arah minus tak hingga); ReLU sebelum geser; saturasi -128..127.
Hanya memakai pustaka standar Python 3.
"""
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPORT = os.path.join(RAIZ, "1_Python_PC", "Training", "export_final")
N_NEURON, N_SUKU, SHIFT, BIAS_SHIFT = 64, 196, 8, 4


def baca_coe(nama):
    teks = open(os.path.join(EXPORT, nama), encoding="utf-8").read()
    isi = teks.split("memory_initialization_vector=")[1]
    nilai = [int(t, 16) for t in isi.replace(";", ",").replace("\n", ",").split(",") if t.strip()]
    return [v - 256 if v >= 128 else v for v in nilai]


def tulis(folder, nama, nilai, lebar):
    mask = (1 << (4 * lebar)) - 1
    with open(os.path.join(folder, nama), "w", newline="\n") as f:
        for v in nilai:
            f.write(format(v & mask, "0%dx" % lebar) + "\n")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(folder, exist_ok=True)
    w = baca_coe("weights_layer1.coe")
    b = baca_coe("bias_layer1.coe")
    x = baca_coe("input_sample.coe")
    assert len(w) == N_NEURON * N_SUKU and len(b) == N_NEURON and len(x) == N_SUKU

    init = [bi << BIAS_SHIFT for bi in b]
    acc, act = [], []
    for n in range(N_NEURON):
        a = init[n] + sum(x[i] * w[n * N_SUKU + i] for i in range(N_SUKU))
        r = max(a, 0)          # ReLU sebelum geser
        r >>= SHIFT            # geser aritmetika (non-negatif setelah ReLU)
        acc.append(a)
        act.append(max(-128, min(127, r)))

    tulis(folder, "tv_w.hex", w, 2)
    tulis(folder, "tv_x.hex", x, 2)
    tulis(folder, "tv_init.hex", init, 8)
    tulis(folder, "exp_acc.hex", acc, 8)
    tulis(folder, "exp_act.hex", act, 2)
    print("vektor uji ditulis ke", folder)


if __name__ == "__main__":
    main()
