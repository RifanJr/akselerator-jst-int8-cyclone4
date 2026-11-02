#!/usr/bin/env python3
"""
Metrik klasifikasi pada 10.000 citra uji MNIST: accuracy, precision, recall,
F1 (per digit dan rata-rata makro), serta matriks kebingungan.

    python 5_PC/metrik_akurasi.py

Model INT8 identik bit per bit dengan FPGA (lihat model_pc.py), sehingga
angka INT8 di sini juga berlaku untuk akselerator FPGA. FP32 ditampilkan
sebagai pembanding.

Rumus, untuk tiap digit d (0-9):
  precision = tebakan d yang benar / semua tebakan d
  recall    = citra d yang tertebak benar / semua citra d sebenarnya
  F1        = 2 x precision x recall / (precision + recall)
Rata-rata makro = rata-rata biasa ke-10 digit (setiap digit berbobot sama).
"""
import json
from pathlib import Path

import numpy as np

from model_pc import ModelFP32, ModelINT8, muat_mnist_uji

HASIL = Path(__file__).resolve().parent / "hasil"
N_KELAS = 10


def metrik(prediksi, label):
    mk = np.zeros((N_KELAS, N_KELAS), dtype=np.int64)       # baris = label, kolom = tebakan
    np.add.at(mk, (label, prediksi), 1)
    benar = np.diag(mk).astype(float)
    tebakan = mk.sum(axis=0).astype(float)
    sebenarnya = mk.sum(axis=1).astype(float)
    precision = np.divide(benar, tebakan, out=np.zeros(N_KELAS), where=tebakan > 0)
    recall = np.divide(benar, sebenarnya, out=np.zeros(N_KELAS), where=sebenarnya > 0)
    pr = precision + recall
    f1 = np.divide(2 * precision * recall, pr, out=np.zeros(N_KELAS), where=pr > 0)
    return {
        "accuracy": float(benar.sum() / mk.sum()),
        "precision_makro": float(precision.mean()),
        "recall_makro": float(recall.mean()),
        "f1_makro": float(f1.mean()),
        "per_digit": [{"digit": d, "jumlah": int(sebenarnya[d]), "precision": float(precision[d]),
                       "recall": float(recall[d]), "f1": float(f1[d])} for d in range(N_KELAS)],
        "matriks_kebingungan": mk.tolist(),
    }


def cetak(nama, m):
    print(f"\n{nama}")
    print(f"  Accuracy {m['accuracy'] * 100:6.2f} %   Precision {m['precision_makro'] * 100:6.2f} %   "
          f"Recall {m['recall_makro'] * 100:6.2f} %   F1 {m['f1_makro'] * 100:6.2f} %   (rata-rata makro)")
    print(f"  {'Digit':>5} {'Jumlah':>7} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    for d in m["per_digit"]:
        print(f"  {d['digit']:>5} {d['jumlah']:>7} {d['precision'] * 100:9.2f}% {d['recall'] * 100:7.2f}% "
              f"{d['f1'] * 100:7.2f}%")


def main():
    x14, xq, y = muat_mnist_uji()
    p_int8 = ModelINT8().prediksi(xq)
    p_fp32 = ModelFP32().prediksi(x14)
    hasil = {"data": "MNIST uji, 10.000 citra (14x14)",
             "INT8 (sama dengan FPGA)": metrik(p_int8, y),
             "FP32 (PyTorch)": metrik(p_fp32, y),
             "tebakan_INT8_berbeda_dengan_FP32": int((p_int8 != p_fp32).sum())}
    for nama in ("INT8 (sama dengan FPGA)", "FP32 (PyTorch)"):
        cetak(nama, hasil[nama])
    print(f"\nCitra yang tebakan INT8 dan FP32-nya berbeda: {hasil['tebakan_INT8_berbeda_dengan_FP32']} dari 10.000")
    HASIL.mkdir(exist_ok=True)
    keluar = HASIL / "metrik_akurasi.json"
    keluar.write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Hasil: {keluar}")


if __name__ == "__main__":
    main()
