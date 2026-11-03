#!/usr/bin/env python3
"""
Model pembanding PC: MLP 196-64-10 yang SAMA dengan akselerator FPGA,
dijalankan di CPU laptop.

Dua versi:
  INT8 (NumPy)   aritmetika bilangan bulat persis seperti FPGA, dari berkas
                 .coe di export_final. Harus identik dengan golden_uji.txt.
  FP32 (PyTorch) cara lazim menjalankan model di PC, dari berkas .pt di
                 export_final (model beku yang sama, sebelum kuantisasi).

Praproses mengikuti notebook Training_MLP_PyTorch.ipynb (Tahap 1 dan 8):
  28x28 -> 14x14 rerata blok 2x2 -> / 255 -> (INT8) kuantisasi Q2.6

Aritmetika INT8 mengikuti Tahap 8 notebook dan rancangan FPGA:
  acc1 = (B1 << 4) + x @ W1^T
  act1 = saturasi_8bit( ReLU(acc1) >> 8 )
  acc2 = (B2 << 1) + act1 @ W2^T          -> argmax

Jalankan sebagai skrip untuk memeriksa kebenaran:
    python 5_PC/model_pc.py
"""
import re
import struct
from pathlib import Path

import numpy as np

DI_SINI = Path(__file__).resolve().parent
PY = DI_SINI.parent / "1_Python_PC"
DIR_MODEL = PY / "Training" / "export_final"
DIR_MNIST = PY / "Training" / "data" / "MNIST" / "raw"
DIR_UJI = PY / "uji"

N_INPUT, N_HIDDEN, N_OUTPUT = 196, 64, 10
N_IN = 6                        # masukan Q2.6
GESER_BIAS_1, GESER_ACC_1 = 4, 8
GESER_BIAS_2 = 1


# ---------------------------------------------------------------------------
#  Data
# ---------------------------------------------------------------------------
def baca_idx(path):
    with open(path, "rb") as f:
        magic, = struct.unpack(">I", f.read(4))
        dims = struct.unpack(">" + "I" * (magic & 0xFF), f.read(4 * (magic & 0xFF)))
        return np.frombuffer(f.read(), dtype=np.uint8).reshape(dims)


def muat_mnist_uji():
    """10.000 citra uji: (X14 float32 untuk FP32, Xq int32 Q2.6 untuk INT8, label)."""
    xraw = baca_idx(DIR_MNIST / "t10k-images-idx3-ubyte")
    y = baca_idx(DIR_MNIST / "t10k-labels-idx1-ubyte").astype(np.int64)
    x14 = (xraw.reshape(-1, 14, 2, 14, 2).mean(axis=(2, 4)).reshape(-1, N_INPUT)
           / 255.0).astype(np.float32)
    xq = np.clip(np.round(x14 * 2.0 ** N_IN), -128, 127).astype(np.int32)
    return x14, xq, y


def muat_citra_uji_fpga():
    """16 citra uji yang sama dengan ROM papan (196 piksel Q2.6 pertama)."""
    hasil = []
    for b in range(16):
        nilai = [int(t, 16) for t in (DIR_UJI / f"citra_{b:02d}.hex").read_text().split()][:N_INPUT]
        hasil.append([v - 256 if v > 127 else v for v in nilai])
    return np.array(hasil, dtype=np.int32)


def baca_acuan():
    """golden_uji.txt -> {citra: (prediksi, [10 akumulator])}"""
    acuan, kini = {}, None
    for b in (DIR_UJI / "golden_uji.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"---\s+citra_(\d+)\.hex\s+MNIST#\d+\s+label\s+\d+\s+prediksi\s+(\d+)", b.strip())
        if m:
            kini = int(m.group(1))
            acuan[kini] = (int(m.group(2)), [None] * 10)
            continue
        m = re.match(r"digit\s+(\d+)\s*:\s*(-?\d+)", b.strip())
        if m and kini is not None:
            acuan[kini][1][int(m.group(1))] = int(m.group(2))
    return acuan


# ---------------------------------------------------------------------------
#  Model INT8 (NumPy), aritmetika sama dengan FPGA
# ---------------------------------------------------------------------------
def baca_coe(path):
    badan = Path(path).read_text().split("memory_initialization_vector=")[1]
    a = np.array([int(t, 16) for t in re.findall(r"\b([0-9A-Fa-f]{2})\b", badan)], dtype=np.int32)
    return np.where(a >= 128, a - 256, a).astype(np.int32)


class ModelINT8:
    def __init__(self):
        w1 = baca_coe(DIR_MODEL / "weights_layer1.coe").reshape(N_HIDDEN, N_INPUT)
        w2 = baca_coe(DIR_MODEL / "weights_layer2.coe").reshape(N_OUTPUT, N_HIDDEN)
        b1 = baca_coe(DIR_MODEL / "bias_layer1.coe")
        b2 = baca_coe(DIR_MODEL / "bias_layer2.coe")
        # disimpan dalam bentuk siap pakai; akumulator 32 bit seperti FPGA
        self.w1t = np.ascontiguousarray(w1.T)                  # 196 x 64
        self.w2t = np.ascontiguousarray(w2.T)                  # 64 x 10
        self.b1 = (b1 << GESER_BIAS_1).astype(np.int32)
        self.b2 = (b2 << GESER_BIAS_2).astype(np.int32)

    def akumulator(self, xq):
        """xq: (n, 196) int32 -> akumulator lapisan 2 (n, 10) int32."""
        acc1 = xq @ self.w1t + self.b1
        act1 = np.clip(np.maximum(acc1, 0) >> GESER_ACC_1, -128, 127).astype(np.int32)
        return act1 @ self.w2t + self.b2

    def prediksi(self, xq):
        return self.akumulator(xq).argmax(axis=1)


# ---------------------------------------------------------------------------
#  Model FP32 (PyTorch), model beku yang sama sebelum kuantisasi
# ---------------------------------------------------------------------------
class ModelFP32:
    def __init__(self):
        import torch
        import torch.nn as nn
        self.torch = torch
        state = torch.load(DIR_MODEL / "model_mlp_196_64_10.pt", map_location="cpu",
                           weights_only=True)
        self.net = nn.Sequential(nn.Linear(N_INPUT, N_HIDDEN), nn.ReLU(),
                                 nn.Linear(N_HIDDEN, N_OUTPUT))
        # kunci state_dict notebook: fc1.*, fc2.*
        self.net[0].weight.data.copy_(state["fc1.weight"])
        self.net[0].bias.data.copy_(state["fc1.bias"])
        self.net[2].weight.data.copy_(state["fc2.weight"])
        self.net[2].bias.data.copy_(state["fc2.bias"])
        self.net.eval()

    def logit(self, x14):
        with self.torch.inference_mode():
            return self.net(self.torch.from_numpy(x14))

    def prediksi(self, x14):
        return self.logit(x14).argmax(dim=1).numpy()


# ---------------------------------------------------------------------------
#  Pemeriksaan kebenaran
# ---------------------------------------------------------------------------
def periksa():
    int8 = ModelINT8()
    fp32 = ModelFP32()

    # 1. INT8 bit-exact terhadap golden_uji.txt (16 citra yang sama dengan FPGA)
    acuan = baca_acuan()
    acc = int8.akumulator(muat_citra_uji_fpga())
    salah = 0
    for b in range(16):
        pred_acuan, acc_acuan = acuan[b]
        cocok = int(acc[b].argmax()) == pred_acuan and list(acc[b]) == acc_acuan
        salah += 0 if cocok else 1
    print(f"INT8 vs golden_uji.txt : {16 - salah}/16 citra, kesepuluh akumulator identik"
          if salah == 0 else f"INT8 vs golden_uji.txt : {salah} citra BEDA")

    # 2. Akurasi 10.000 citra uji
    x14, xq, y = muat_mnist_uji()
    a_int8 = (int8.prediksi(xq) == y).mean() * 100
    a_fp32 = (fp32.prediksi(x14) == y).mean() * 100
    print(f"Akurasi INT8 (NumPy)   : {a_int8:.2f} %  (harapan 97,45 %)")
    print(f"Akurasi FP32 (PyTorch) : {a_fp32:.2f} %  (harapan 97,45 %)")

    ok = salah == 0 and round(a_int8, 2) == 97.45 and round(a_fp32, 2) == 97.45
    print("HASIL:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(periksa())
