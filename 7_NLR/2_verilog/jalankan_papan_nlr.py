#!/usr/bin/env python3
"""
Menguji rancangan papan (top_papan.v) sebelum diprogram ke FPGA.

Mengompilasi dan menjalankan tb_papan.v, yang meniru orang menekan tombol
untuk menjalankan ke-16 citra uji, lalu mencocokkan setiap hasil ke
1_Python_PC/uji/golden_uji.txt: digit terpilih, nilai akumulator pemenangnya, DAN
kesepuluh akumulator lapisan 2 harus sama persis. Jumlah siklus tiap inferensi harus
SIKLUS_HARAP.

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
OS = AKAR.parent.parent / "2_Verilog"          # modul bersama rancangan OS
UJI = AKAR.parent.parent / "1_Python_PC" / "uji"
BUILD = AKAR / "build"
# Siklus per inferensi NLR (dihitung dari urutan di ctrl_nlr.v):
#   lapisan 1 : 196 masukan x 8 slot           = 1568
#   kuras 1   : 64 hasil akhir, satu per siklus =   64
#   lapisan 2 : 64 masukan x 5 slot (K2)        =  320
#   kuras 2   : 10 hasil akhir                  =   10
#   akhir     : tunggu argmax menerima hasil    =    3
SIKLUS_HARAP = 1568 + 64 + 320 + 10 + 3        # 1965

SUMBER = ["tb_papan_nlr.v", "top_papan_nlr.v", "ctrl_nlr.v", "mem_psum.v",
          str(OS / "mem_w.v"), str(OS / "mem_d.v"), str(OS / "mac_unit.v"),
          str(OS / "epilog_unit.v"), str(OS / "argmax10.v"),
          str(OS / "mult_bw8_arith.v"), str(OS / "mult_bw8_struct.v"),
          str(OS / "mult_hard8.v"), str(OS / "seg7_scan.v"), str(OS / "seg7_dec.v"),
          str(AKAR.parent.parent / "1_Python_PC" / "mem" / "rom_bias8.v")]


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
    biner = BUILD / "papan_nlr.out"
    k = subprocess.run(["iverilog", "-g2012", "-o", str(biner)] + SUMBER,
                       cwd=RTL, capture_output=True, text=True)
    if k.returncode != 0:
        sys.exit("kompilasi gagal:\n" + k.stderr)
    j = subprocess.run(["vvp", str(biner)], cwd=RTL, capture_output=True, text=True, timeout=600)

    acuan = baca_acuan()
    hasil, tampil_siklus, led_siklus, akses = [], None, None, None
    aks, aks_per_hasil = [], []          # keluaran lapisan 2 tiap inferensi
    for b in j.stdout.splitlines():
        s = b.split()
        if s and s[0] == "AKS" and len(s) == 3:
            aks.append((int(s[1]), int(s[2])))
        elif s and s[0] == "HASIL" and len(s) == 7:
            hasil.append(tuple(int(x) for x in s[1:]))
            aks_per_hasil.append(aks)
            aks = []
        elif s and s[0] == "AKSES" and len(s) == 8:
            akses = [int(x) for x in s[1:]]
        elif s and s[0] == "TAMPIL_SIKLUS":
            tampil_siklus, led_siklus = s[1], s[3]

    print("=" * 72)
    print("  UJI RANCANGAN PAPAN — top_papan_nlr.v (tanpa stationary, 8 lajur, HARD)")
    print("=" * 72)
    print()
    print("  Citra  Python  Papan  Akumulator  Acuan  10 aks  Siklus  LED cocok  Hasil")
    print("  " + "-" * 74)

    salah = 0
    for (idx, h, nilai, siklus, led_cocok, led_beda), ak in zip(hasil, aks_per_hasil):
        a = acuan[idx]
        nilai_acuan = a["acc"][a["prediksi"]]
        # kesepuluh akumulator lapisan 2, tiap digit tepat sekali
        sama = sum(1 for d, v in ak if a["acc"][d] == v)
        aks_benar = (len(ak) == 10 and sorted(d for d, _ in ak) == list(range(10))
                     and sama == 10)
        benar = (h == a["prediksi"] and nilai == nilai_acuan and aks_benar
                 and siklus == SIKLUS_HARAP and led_cocok == 1 and led_beda == 0)
        salah += 0 if benar else 1
        print(f"  {idx:5d}  {a['prediksi']:6d}  {h:5d}  {nilai:10d}  {nilai_acuan:5d}"
              f"  {sama:3d}/10  {siklus:6d}  {'nyala' if led_cocok else 'mati':>9}"
              f"  {'cocok' if benar else 'BEDA'}")
    print("  " + "-" * 74)

    terlihat = sorted({r[0] for r in hasil})
    if terlihat != list(range(16)):
        print(f"  Citra yang terjangkau tombol tidak lengkap: {terlihat}")
        salah += 1
    if len(hasil) != 18:
        print(f"  Jumlah inferensi {len(hasil)}, seharusnya 18")
        salah += 1

    print()
    ok_tampil = (tampil_siklus == str(SIKLUS_HARAP) and led_siklus == "1")
    print(f"  Mode siklus (key[3] ditahan) menampilkan : {tampil_siklus}  "
          f"{'benar' if ok_tampil else 'SALAH'}")
    salah += 0 if ok_tampil else 1
    print()
    if akses:
        siklus, bank, masuk, ps_baca, ps_tulis, mac, akt = akses
        bit = bank * 8 + masuk * 8 + (ps_baca + ps_tulis) * 32 + akt * 8
        print("  Akses memori, inferensi pertama (citra 00):")
        print(f"    siklus sibuk                : {siklus}")
        print(f"    operasi MAC                 : {mac}  (harus 13.184 = 64x196 + 10x64)")
        print(f"    baca bank bobot (8 bit)     : {bank}")
        print(f"    baca masukan (8 bit)        : {masuk}")
        print(f"    baca jumlah parsial (32 bit): {ps_baca}")
        print(f"    tulis jumlah parsial (32bit): {ps_tulis}")
        print(f"    tulis aktivasi (8 bit)      : {akt}")
        print(f"    total bit memori            : {bit:,}".replace(",", "."))
        if mac != 13184:
            print("    JUMLAH OPERASI MAC SALAH")
            salah += 1
    else:
        print("  Baris AKSES tidak ditemukan")
        salah += 1
    print()
    print("=" * 72)
    if salah == 0:
        print(f"  HASIL: LULUS — {len(hasil)} inferensi lewat tombol, seluruhnya identik")
        print(f"         dengan acuan Python (10 akumulator tiap citra), dan tiap")
        print(f"         inferensi tepat {SIKLUS_HARAP} siklus.")
    else:
        print(f"  HASIL: GAGAL — {salah} masalah")
    print("=" * 72)
    return 0 if salah == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
