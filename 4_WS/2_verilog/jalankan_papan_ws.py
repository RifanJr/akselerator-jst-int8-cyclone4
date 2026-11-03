#!/usr/bin/env python3
"""
Menguji rancangan WS (top_papan_ws.v) sebelum diprogram ke FPGA.

Mengompilasi dan menjalankan tb_papan_ws.v, lalu memeriksa:
  1. kesepuluh akumulator lapisan 2 setiap citra = 1_Python_PC/uji/golden_uji.txt
  2. prediksi dan nilai maksimum di argmax = acuan
  3. batch kedua (key[2]) identik dengan batch pertama
  4. tampilan dan LED cocok untuk ke-16 citra
  5. jumlah siklus per batch = SIKLUS_HARAP, dan tampilan mode siklus =
     siklus per citra (dibulatkan)

Jalankan dari folder 4_WS/2_verilog:

    python jalankan_papan_ws.py

Syarat: Icarus Verilog (iverilog dan vvp) dapat dipanggil dari baris perintah.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
AKAR = DI_SINI.parent.parent
OS = AKAR / "2_Verilog"
UJI = AKAR / "1_Python_PC" / "uji"
BUILD = DI_SINI / "build"

# Dihitung dari struktur pipa (SPESIFIKASI_WS.md bagian 5), bukan dari simulasi:
#   PRA 3 siklus (isi bobot ubin pertama)
# + 16 x 1648 = 26368 token tanpa jeda
# + 12 siklus: 10 sampai token terakhir tiba di dasar kolom, ditambah 2
#   karena argmax berpipa 3 tahap
UBIN = 32 * 49 + 5 * 16                      # 1648 ubin per batch
SIKLUS_HARAP = 3 + 16 * UBIN + 12            # 26383
SIKLUS_CITRA = (SIKLUS_HARAP + 8) // 16      # 1649, yang ditampilkan papan

SUMBER = [
    "tb_papan_ws.v", "top_papan_ws.v", "ctrl_ws.v", "larik_ws.v",
    "buf_aktivasi_ws.v", "argmax_batch.v",
    # modul bersama rancangan OS, dipakai tanpa diubah
    str(OS / "mac_unit.v"), str(OS / "mult_bw8_arith.v"), str(OS / "mult_bw8_struct.v"),
    str(OS / "mult_hard8.v"), str(OS / "mem_w.v"), str(OS / "epilog_unit.v"),
    str(OS / "seg7_scan.v"), str(OS / "seg7_dec.v"),
    str(AKAR / "1_Python_PC" / "mem" / "rom_bias8.v"),
]


def baca_acuan():
    acuan, kini = {}, None
    for b in (UJI / "golden_uji.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"---\s+citra_(\d+)\.hex\s+MNIST#\d+\s+label\s+\d+\s+prediksi\s+(\d+)", b.strip())
        if m:
            kini = int(m.group(1))
            acuan[kini] = {"prediksi": int(m.group(2)), "acc": [None] * 10}
            continue
        m = re.match(r"digit\s+(\d+)\s*:\s*(-?\d+)", b.strip())
        if m and kini is not None:
            acuan[kini]["acc"][int(m.group(1))] = int(m.group(2))
    return acuan


def bcd(n):
    return f"{n:04d}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for alat in ("iverilog", "vvp"):
        if shutil.which(alat) is None:
            sys.exit(f"perintah '{alat}' tidak ditemukan. Pasang Icarus Verilog lebih dulu.")

    BUILD.mkdir(exist_ok=True)
    biner = BUILD / "papan_ws.out"
    k = subprocess.run(["iverilog", "-g2012", "-o", str(biner)] + SUMBER,
                       cwd=DI_SINI, capture_output=True, text=True)
    if k.returncode != 0:
        sys.exit("kompilasi gagal:\n" + k.stderr)
    j = subprocess.run(["vvp", str(biner)], cwd=DI_SINI, capture_output=True,
                       text=True, timeout=900)

    acuan = baca_acuan()
    aks = {1: {}, 2: {}}            # aks[batch][citra][neuron] = akumulator
    hasil = {1: {}, 2: {}}          # hasil[batch][citra] = (prediksi, nilai, siklus)
    tampil, tampil_siklus, led_siklus = [], None, None
    akses = {}                      # akses[batch] = (baca bobot, baca kata masukan)
    selesai = False
    for b in j.stdout.splitlines():
        s = b.split()
        if not s:
            continue
        if s[0] == "AKS" and len(s) == 5:
            ke, citra, neuron, nilai = map(int, s[1:])
            aks.setdefault(ke, {}).setdefault(citra, {})[neuron] = nilai
        elif s[0] == "HASIL" and len(s) == 6:
            ke, citra, pred, nilai, siklus = map(int, s[1:])
            hasil[ke][citra] = (pred, nilai, siklus)
        elif s[0] == "AKSES" and len(s) == 5:
            ke, bb, mu, bm = map(int, s[1:])
            akses[ke] = (bb, mu, bm)
        elif s[0] == "TAMPIL" and len(s) == 5:
            tampil.append(tuple(map(int, s[1:])))
        elif s[0] == "TAMPIL_SIKLUS":
            tampil_siklus, led_siklus = s[1], s[3]
        elif s[0] == "SELESAI":
            selesai = True
        elif s[0] == "GAGAL:":
            print("  " + b)

    print("=" * 76)
    print("  UJI RANCANGAN WS — top_papan_ws.v (larik 4 x 2, batch 16, varian HARD)")
    print("=" * 76)
    print()
    print("  Citra  Python  Papan  Nilai maks  Acuan  10 aks  Batch 2  Tampilan  Hasil")
    print("  " + "-" * 72)

    salah = 0
    for c in range(16):
        a = acuan[c]
        ak = aks[1].get(c, {})
        sama = sum(1 for d in range(10) if ak.get(d) == a["acc"][d])
        pred, nilai, _ = hasil[1].get(c, (None, None, None))
        nilai_acuan = a["acc"][a["prediksi"]]
        ulang = (aks[2].get(c) == ak and hasil[2].get(c, (0, 0, 0))[:2] == (pred, nilai))
        tp = [x for x in tampil if x[0] == c]
        tampil_ok = len(tp) == 1 and tp[0][1] == a["prediksi"] and tp[0][2] == 1 and tp[0][3] == 0
        benar = (len(ak) == 10 and sama == 10 and pred == a["prediksi"]
                 and nilai == nilai_acuan and ulang and tampil_ok)
        salah += 0 if benar else 1
        print(f"  {c:5d}  {a['prediksi']:6d}  {pred if pred is not None else '-':>5}"
              f"  {nilai if nilai is not None else '-':>10}  {nilai_acuan:5d}  {sama:3d}/10"
              f"  {'sama' if ulang else 'BEDA':>7}  {'cocok' if tampil_ok else 'SALAH':>8}"
              f"  {'cocok' if benar else 'BEDA'}")
    print("  " + "-" * 72)

    siklus = {hasil[ke][0][2] for ke in (1, 2) if 0 in hasil[ke]}
    ok_siklus = siklus == {SIKLUS_HARAP}
    print()
    print(f"  Siklus per batch        : {sorted(siklus)}  (harapan {SIKLUS_HARAP})"
          f"  {'benar' if ok_siklus else 'SALAH'}")
    salah += 0 if ok_siklus else 1

    # Bukti bobot dipakai ulang: setiap ubin dibaca SEKALI dari 8 bank lalu
    # dipakai 16 citra. Blok M9K bobot aktif 2 kali di PRA + 1 kali per ubin
    # (kecuali ubin terakhir) = UBIN + 1; bobot yang dimuat = UBIN ubin;
    # kata masukan = banyak token (16 per ubin).
    harap_akses = (UBIN + 1, UBIN, 16 * UBIN)
    ok_akses = all(akses.get(ke) == harap_akses for ke in (1, 2))
    a1 = akses.get(1, (None, None, None))
    print(f"  Siklus baca M9K bobot   : {a1[0]}  (harapan {UBIN + 1} = {UBIN} kata unik"
          f" + 1 baca ulang)")
    print(f"  Ubin bobot dimuat       : {a1[1]}  (harapan {UBIN}; x 8 bank ="
          f" {8 * UBIN} byte per batch = {8 * UBIN // 16} byte per citra)")
    print(f"  Kata masukan dibaca     : {a1[2]}  (harapan {16 * UBIN})"
          f"  {'benar' if ok_akses else 'SALAH'}")
    salah += 0 if ok_akses else 1

    ok_tampil = (tampil_siklus == bcd(SIKLUS_CITRA) and led_siklus == "1")
    print(f"  Mode siklus menampilkan : {tampil_siklus}  (harapan {bcd(SIKLUS_CITRA)}, "
          f"siklus per citra)  {'benar' if ok_tampil else 'SALAH'}")
    salah += 0 if ok_tampil else 1
    if not selesai:
        print("  Simulasi tidak mencapai akhir testbench")
        salah += 1

    print()
    print("=" * 76)
    if salah == 0:
        print("  HASIL: LULUS — 16 citra dalam satu batch, kesepuluh akumulator tiap citra")
        print("         identik dengan acuan Python, batch ulang identik, dan satu batch")
        print(f"         tepat {SIKLUS_HARAP} siklus ({SIKLUS_CITRA} siklus per citra).")
    else:
        print(f"  HASIL: GAGAL — {salah} masalah")
    print("=" * 76)
    return 0 if salah == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
