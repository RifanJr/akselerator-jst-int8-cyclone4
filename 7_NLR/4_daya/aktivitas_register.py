#!/usr/bin/env python3
"""
Hitung aktivitas register yang berada di dalam blok generate dari VCD, lalu
tulis sebagai assignment Power Analyzer.

    python aktivitas_register.py nlr_inferensi.vcd aktivitas_register.tcl

Mengapa perlu: Power Analyzer tidak dapat mencocokkan nama bit register yang
berada di dalam blok generate, misalnya
    u_larik|g_baris[3].g_kolom[1].u_mac|acc [31]
    g_bank[7].u_mem_w|q [7]
padahal formatnya sama dengan skrip VCD buatan Quartus sendiri. Register
serupa di luar blok generate terbaca normal. Tanpa langkah ini sekitar 960
register (35 %) memakai perkiraan vectorless dan confidence turun menjadi
Medium.

Nilai yang ditulis berasal dari VCD yang SAMA:
  POWER_TOGGLE_RATE         = jumlah transisi / lama VCD   (transisi per detik)
  POWER_STATIC_PROBABILITY  = bagian waktu bernilai 1
Di laporan, sumber datanya tercatat sebagai "Node assignment".

Salinan 4_WS/4_daya/aktivitas_register.py (WS), versi umum dari
6_Daya_FPGA/aktivitas_mac.py (rancangan OS), yang hanya
menangani register g_lajur[k].u_mac.
"""
import re
import sys

# nama ter-escape yang memuat jalur generate "...[k]." dan merupakan satu bit vektor
POLA = re.compile(r"^\\(.*\]\..*) \[(\d+)\]$")


def main(vcd, keluar):
    nama = {}
    with open(vcd) as f:
        for l in f:
            if l.startswith("$var"):
                p = l.split()
                m = POLA.match(" ".join(p[4:-1]))
                if m:
                    nama[p[3]] = f"{m.group(1)}[{m.group(2)}]"
            elif l.startswith("$enddefinitions"):
                break

        # per sinyal: nilai kini, waktu perubahan terakhir, lama bernilai 1, jumlah transisi
        st = {i: ["x", 0, 0, 0] for i in nama}
        t = t_akhir = 0
        for l in f:
            if l[0] == "#":
                t = t_akhir = int(l[1:])
                continue
            s = st.get(l[1:].rstrip("\n"))
            if s is not None and l[0] in "01xz":
                if s[0] == "1":
                    s[2] += t - s[1]
                if s[0] in "01" and l[0] in "01" and l[0] != s[0]:
                    s[3] += 1
                s[0], s[1] = l[0], t

    lama_s = t_akhir * 1e-12
    out = [f"# Dibuat oleh aktivitas_register.py dari {vcd} (lama {t_akhir / 1e6:.2f} us). Jangan diubah tangan."]
    for i, s in st.items():
        if s[0] == "1":
            s[2] += t_akhir - s[1]
        out.append(f'set_instance_assignment -name POWER_TOGGLE_RATE {round(s[3] / lama_s)} -to "{nama[i]}"')
        out.append(f'set_instance_assignment -name POWER_STATIC_PROBABILITY {s[2] / t_akhir:.4f} -to "{nama[i]}"')
    open(keluar, "w").write("\n".join(out) + "\n")
    print(f"{keluar}: {len(nama)} bit register di dalam blok generate")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
