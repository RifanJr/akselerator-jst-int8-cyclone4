#!/usr/bin/env python3
"""
Menguji rancangan papan (top_papan.v) sebelum diprogram ke FPGA.

Mengompilasi dan menjalankan tb_papan.v, yang meniru orang menekan tombol
untuk menjalankan ke-16 citra uji, lalu mencocokkan setiap hasil ke
1_Python_PC/uji/golden_uji.txt: digit terpilih DAN nilai akumulator pemenangnya harus sama
persis. Jumlah siklus tiap inferensi harus 1816, sama dengan top_akselerator_p8.

Jalankan dari folder 2_Verilog:

    python jalankan_papan.py

Syarat: Icarus Verilog (iverilog dan vvp) dapat dipanggil dari baris perintah.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent
RTL = AKAR
UJI = AKAR.parent / "1_Python_PC" / "uji"
BUILD = AKAR / "build_sapu"
SIKLUS_HARAP = 1816

SUMBER = ["tb_papan.v", "top_papan.v", "ctrl_fsm_p8.v", "mem_w.v", "mem_d.v",
          "mac_unit.v", "epilog_unit.v", "argmax10.v", "mult_bw8_arith.v",
          "mult_bw8_struct.v", "mult_hard8.v", "seg7_scan.v", "seg7_dec.v",
          "../1_Python_PC/mem/rom_bias8.v"]


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


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for alat in ("iverilog", "vvp"):
        if shutil.which(alat) is None:
            sys.exit(f"perintah '{alat}' tidak ditemukan. Pasang Icarus Verilog lebih dulu.")

    BUILD.mkdir(exist_ok=True)
    biner = BUILD / "papan.out"
    k = subprocess.run(["iverilog", "-g2012", "-o", str(biner)] + SUMBER,
                       cwd=RTL, capture_output=True, text=True)
    if k.returncode != 0:
        sys.exit("kompilasi gagal:\n" + k.stderr)
    j = subprocess.run(["vvp", str(biner)], cwd=RTL, capture_output=True, text=True, timeout=600)

    acuan = baca_acuan()
    hasil, tampil_siklus, led_siklus = [], None, None
    for b in j.stdout.splitlines():
        s = b.split()
        if s and s[0] == "HASIL" and len(s) == 7:
            hasil.append(tuple(int(x) for x in s[1:]))
        elif s and s[0] == "TAMPIL_SIKLUS":
            tampil_siklus, led_siklus = s[1], s[3]

    print("=" * 72)
    print("  UJI RANCANGAN PAPAN — top_papan.v (P = 8, varian HARD)")
    print("=" * 72)
    print()
    print("  Citra  Python  Papan  Akumulator  Acuan  Siklus  LED cocok  Hasil")
    print("  " + "-" * 66)

    salah = 0
    for idx, h, nilai, siklus, led_cocok, led_beda in hasil:
        a = acuan[idx]
        nilai_acuan = a["acc"][a["prediksi"]]
        benar = (h == a["prediksi"] and nilai == nilai_acuan
                 and siklus == SIKLUS_HARAP and led_cocok == 1 and led_beda == 0)
        salah += 0 if benar else 1
        print(f"  {idx:5d}  {a['prediksi']:6d}  {h:5d}  {nilai:10d}  {nilai_acuan:5d}"
              f"  {siklus:6d}  {'nyala' if led_cocok else 'mati':>9}  {'cocok' if benar else 'BEDA'}")
    print("  " + "-" * 66)

    terlihat = sorted({r[0] for r in hasil})
    if terlihat != list(range(16)):
        print(f"  Citra yang terjangkau tombol tidak lengkap: {terlihat}")
        salah += 1
    if len(hasil) != 18:
        print(f"  Jumlah inferensi {len(hasil)}, seharusnya 18")
        salah += 1

    print()
    ok_tampil = (tampil_siklus == "1816" and led_siklus == "1")
    print(f"  Mode siklus (key[3] ditahan) menampilkan : {tampil_siklus}  "
          f"{'benar' if ok_tampil else 'SALAH'}")
    salah += 0 if ok_tampil else 1
    print()
    print("=" * 72)
    if salah == 0:
        print(f"  HASIL: LULUS — {len(hasil)} inferensi lewat tombol, seluruhnya identik")
        print("         dengan acuan Python, dan tiap inferensi tepat 1816 siklus.")
    else:
        print(f"  HASIL: GAGAL — {salah} masalah")
    print("=" * 72)
    return 0 if salah == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
