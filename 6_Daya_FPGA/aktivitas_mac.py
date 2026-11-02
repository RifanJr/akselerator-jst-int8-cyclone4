#!/usr/bin/env python3
"""
Hitung aktivitas register akumulator MAC dari VCD, lalu tulis sebagai
assignment Power Analyzer.

    python aktivitas_mac.py os_inferensi.vcd aktivitas_mac.tcl

Mengapa perlu: Power Analyzer tidak dapat mencocokkan nama bit register yang
berada di dalam blok generate (g_lajur[k].u_mac|acc [i], m_acc, p_q, init1),
padahal formatnya sama dengan skrip VCD buatan Quartus sendiri. Register
serupa di luar g_lajur (misalnya u_ctrl|cnt_w [3]) terbaca normal. Tanpa
langkah ini sekitar 718 register (50 %) memakai perkiraan vectorless dan
confidence turun menjadi Medium.

Nilai yang ditulis berasal dari VCD yang SAMA:
  POWER_TOGGLE_RATE         = jumlah transisi / lama VCD   (transisi per detik)
  POWER_STATIC_PROBABILITY  = bagian waktu bernilai 1
Di laporan, sumber datanya tercatat sebagai "Node assignment".
"""
import re
import sys

POLA = re.compile(r"^.g_lajur\[(\d+)\]\.u_mac\|(acc|m_acc|p_q|init1) \[(\d+)\]$")


def main(vcd, keluar):
    baris = open(vcd).read().split("\n")
    nama = {}
    for l in baris:
        if l.startswith("$var"):
            p = l.split()
            m = POLA.match(" ".join(p[4:-1]))
            if m:
                nama[p[3]] = f"g_lajur[{m.group(1)}].u_mac|{m.group(2)}[{m.group(3)}]"
        if l.startswith("$enddefinitions"):
            break

    # per sinyal: nilai kini, waktu perubahan terakhir, lama bernilai 1, jumlah transisi
    st = {i: ["x", 0, 0, 0] for i in nama}
    t = t_akhir = 0
    for l in baris:
        if l.startswith("#"):
            t = t_akhir = int(l[1:])
            continue
        if l[:1] in "01xz" and l[1:] in st:
            s = st[l[1:]]
            if s[0] == "1":
                s[2] += t - s[1]
            if s[0] in "01" and l[0] in "01" and l[0] != s[0]:
                s[3] += 1
            s[0], s[1] = l[0], t

    lama_s = t_akhir * 1e-12
    out = [f"# Dibuat oleh aktivitas_mac.py dari {vcd} (lama {t_akhir / 1e6:.2f} us). Jangan diubah tangan."]
    for i, s in st.items():
        if s[0] == "1":
            s[2] += t_akhir - s[1]
        out.append(f'set_instance_assignment -name POWER_TOGGLE_RATE {round(s[3] / lama_s)} -to "{nama[i]}"')
        out.append(f'set_instance_assignment -name POWER_STATIC_PROBABILITY {s[2] / t_akhir:.4f} -to "{nama[i]}"')
    open(keluar, "w").write("\n".join(out) + "\n")
    print(f"{keluar}: {len(nama)} bit register akumulator MAC")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
