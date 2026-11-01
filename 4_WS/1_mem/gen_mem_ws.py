#!/usr/bin/env python3
"""
Pemetaan memori rancangan weight-stationary (WS) 4x2, batch 16.

Membaca model beku dan citra uji yang SAMA dengan rancangan OS, lalu
menyusunnya ulang untuk larik WS. Isi bobot tidak berubah, hanya susunannya.

Masukan (hanya dibaca, tidak diubah):
    1_Python_PC/Training/export_final/weights_layer1.coe   64 x 196, per neuron
    1_Python_PC/Training/export_final/weights_layer2.coe   10 x 64,  per neuron
    1_Python_PC/uji/citra_00.hex .. citra_15.hex             196 piksel pertama
    1_Python_PC/mem/P8/mem_w_b0..7.hex                       hanya untuk cek silang

Keluaran (di folder ini):
    mem_w_ws_b0..7.hex   8 bank x 1648 kata x 8 bit
    citra_ws32.hex       784 kata x 32 bit

Pemetaan (lihat SPESIFIKASI_WS.md, bagian 4.4 dan 4.5):
    PE(r, c), r = 0..3 baris, c = 0..1 kolom, bank k = 2r + c
    lapisan 1: alamat g*49 + t        isi w1[2g+c][4t+r]   g = 0..31, t = 0..48
    lapisan 2: alamat 1568 + g*16 + t isi w2[2g+c][4t+r]   g = 0..4,  t = 0..15
    citra    : alamat t*16 + b        isi {x_b[4t+3], x_b[4t+2], x_b[4t+1], x_b[4t]}

Jalankan dari mana saja:
    python 4_WS/1_mem/gen_mem_ws.py
"""
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
AKAR = DI_SINI.parent.parent
PY = AKAR / "1_Python_PC"

R, C, B = 4, 2, 16
N_IN, N_HID, N_OUT = 196, 64, 10
G1, T1 = N_HID // C, N_IN // R      # 32, 49
G2, T2 = N_OUT // C, N_HID // R     # 5, 16
OFFSET_L2 = G1 * T1                 # 1568
KATA_BANK = G1 * T1 + G2 * T2       # 1648


def baca_coe(berkas):
    """Nilai coe heksadesimal 8 bit, dikembalikan sebagai bilangan bertanda."""
    nilai = []
    for b in berkas.read_text().splitlines():
        b = b.strip().rstrip(",;")
        if not b or "=" in b:
            continue
        v = int(b, 16)
        nilai.append(v - 256 if v > 127 else v)
    return nilai


def baca_hex(berkas):
    nilai = []
    for b in berkas.read_text().splitlines():
        b = b.strip()
        if not b or b.startswith("//") or b.startswith("@"):
            continue
        v = int(b, 16)
        nilai.append(v - 256 if v > 127 else v)
    return nilai


def main():
    w1_rata = baca_coe(PY / "Training" / "export_final" / "weights_layer1.coe")
    w2_rata = baca_coe(PY / "Training" / "export_final" / "weights_layer2.coe")
    assert len(w1_rata) == N_HID * N_IN, len(w1_rata)
    assert len(w2_rata) == N_OUT * N_HID, len(w2_rata)
    w1 = [w1_rata[n * N_IN:(n + 1) * N_IN] for n in range(N_HID)]
    w2 = [w2_rata[n * N_HID:(n + 1) * N_HID] for n in range(N_OUT)]

    # ---- cek silang: bank OS (P = 8) harus berisi bobot yang sama ----
    # bank j OS: neuron j, j+8, ... (196 bobot berurutan), lalu lapisan 2
    # mulai alamat 1568: neuron j dan j+8 (64 bobot), bila neuron itu ada.
    for j in range(8):
        os_bank = baca_hex(PY / "mem" / "P8" / f"mem_w_b{j}.hex")
        for kel in range(N_HID // 8):
            n = 8 * kel + j
            assert os_bank[kel * N_IN:(kel + 1) * N_IN] == w1[n], f"L1 bank {j} neuron {n}"
        for kel in range(2):
            n = 8 * kel + j
            awal = OFFSET_L2 + kel * N_HID
            harap = w2[n] if n < N_OUT else [0] * N_HID
            assert os_bank[awal:awal + N_HID] == harap, f"L2 bank {j} neuron {n}"
    print("cek silang dengan bank OS: cocok (bobot identik)")

    # ---- bank bobot WS ----
    for r in range(R):
        for c in range(C):
            k = 2 * r + c
            isi = []
            for g in range(G1):
                for t in range(T1):
                    isi.append(w1[2 * g + c][4 * t + r])
            for g in range(G2):
                for t in range(T2):
                    isi.append(w2[2 * g + c][4 * t + r])
            assert len(isi) == KATA_BANK
            (DI_SINI / f"mem_w_ws_b{k}.hex").write_text(
                "".join(f"{v & 0xFF:02x}\n" for v in isi))
    print(f"8 bank bobot WS ditulis: {KATA_BANK} kata per bank")

    # ---- ROM citra 32 bit ----
    citra = []
    for b in range(B):
        piksel = baca_hex(PY / "uji" / f"citra_{b:02d}.hex")[:N_IN]
        assert len(piksel) == N_IN
        citra.append(piksel)
    kata = []
    for t in range(T1):
        for b in range(B):
            k = 0
            for r in range(R):
                k |= (citra[b][4 * t + r] & 0xFF) << (8 * r)
            kata.append(k)
    (DI_SINI / "citra_ws32.hex").write_text("".join(f"{k:08x}\n" for k in kata))
    print(f"ROM citra 32 bit ditulis: {len(kata)} kata")

    # ---- cek: hitung ulang seluruh susunan dari berkas yang ditulis ----
    bank = [baca_hex(DI_SINI / f"mem_w_ws_b{k}.hex") for k in range(R * C)]
    for g in range(G1):
        for t in range(T1):
            for r in range(R):
                for c in range(C):
                    assert bank[2 * r + c][g * T1 + t] == w1[2 * g + c][4 * t + r]
    for g in range(G2):
        for t in range(T2):
            for r in range(R):
                for c in range(C):
                    assert bank[2 * r + c][OFFSET_L2 + g * T2 + t] == w2[2 * g + c][4 * t + r]
    terpakai = sorted(abs(v) for bk in bank for v in bk)
    assert len(terpakai) == N_HID * N_IN + N_OUT * N_HID   # tanpa kata pengisi
    print("cek ulang susunan: cocok; total", len(terpakai), "bobot, tanpa pengisi")


if __name__ == "__main__":
    main()
