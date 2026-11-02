#!/usr/bin/env python3
"""
Siapkan VCD Icarus dari simulasi netlist supaya dapat dibaca Power Analyzer.

    python siapkan_vcd.py masuk.vcd keluar.vcd T_MULAI_PS T_SELESAI_PS

1. Buang scope testbench, ganti nama scope `dut` menjadi `top_papan`.
2. Buang blok $comment/$dumpall kosong setelah $enddefinitions (Quartus
   Error 222007).
3. Pecah sinyal vektor menjadi bit bernama "nama [i]" (format skrip VCD Quartus).
4. Ambil hanya jendela T_MULAI..T_SELESAI dan geser waktunya supaya mulai dari
   0. Keadaan sinyal sebelum T_MULAI ditulis sebagai nilai awal pada waktu 0,
   sehingga jendela boleh berada di tengah rekaman (mis. saat chip diam).

Langkah 1-3 diadaptasi dari 3_Quartus/simulasi_netlist/vcd_quartus.py
(Student A, 1 November 2026); langkah 4 tambahan.
"""
import itertools
import sys


def nama_id():
    a = [chr(c) for c in range(33, 127)]
    for n in itertools.count(1):
        for t in itertools.product(a, repeat=n):
            yield "Z" + "".join(t)


def main(src, dst, t_mulai, t_selesai):
    L = open(src).read().split("\n")
    tb = [l for l in L if l.strip().startswith("$scope module") and l.split()[2] != "dut"][0]
    L = [l for l in L if l != tb]
    L = ["$scope module top_papan $end" if l.strip() == "$scope module dut $end" else l for l in L]
    akhir = L.index("$enddefinitions $end")
    naik = [i for i in range(akhir) if L[i].strip() == "$upscope $end"]
    del L[naik[-1]]
    akhir -= 1
    while L[akhir + 1].startswith(("$comment", "$dumpall")):
        j = akhir + 1
        while not L[j].strip().endswith("$end"):
            j += 1
        del L[akhir + 1:j + 1]

    g, vek, kepala = nama_id(), {}, []
    for l in L[:akhir]:
        p = l.split()
        if l.startswith("$var") and int(p[2]) > 1 and p[-2].startswith("["):
            nama = " ".join(p[4:-2])
            msb, lsb = map(int, p[-2][1:-1].split(":"))
            bit = list(range(msb, lsb - 1, -1)) if msb >= lsb else list(range(msb, lsb + 1))
            ids = [next(g) for _ in bit]
            vek[p[3]] = (ids, ["x"] * len(bit))
            kepala += [f"$var wire 1 {i} {nama} [{b}] $end" for b, i in zip(bit, ids)]
        else:
            kepala.append(l)

    # Perubahan sebelum T_MULAI tidak ditulis; hanya keadaan terakhirnya yang
    # disimpan di `kini`, lalu ditulis sebagai nilai awal pada waktu 0.
    out, t_awal, n_ubah = kepala + [L[akhir]], None, 0
    kini, dalam, t_tulis = {}, False, None

    def ubah(kunci, baris):
        nonlocal n_ubah
        if dalam:
            out.append(baris)
            n_ubah += 1
        else:
            kini[kunci] = baris

    for l in L[akhir + 1:]:
        if l.startswith("#"):
            t = int(l[1:])
            if t_awal is None:
                t_awal = t
                if t_awal > t_mulai:
                    raise SystemExit(f"VCD mulai {t_awal} ps, lebih lambat dari T_MULAI {t_mulai} ps")
            if t > t_selesai:
                break
            if t >= t_mulai and not dalam:
                dalam = True
                if kini:
                    out += ["#0", "$dumpvars"] + list(kini.values()) + ["$end"]
                    t_tulis = 0
            if dalam and t - t_mulai != t_tulis:
                t_tulis = t - t_mulai
                out.append(f"#{t_tulis}")
            continue
        if l.startswith("$"):
            if dalam:
                out.append(l)
            continue
        if l[:1] in "bB" and " " in l:
            val, i = l[1:].split()
            if i in vek:
                ids, lalu = vek[i]
                val = val.rjust(len(ids), "0" if val[0] in "01" else val[0])
                for k, (bi, v) in enumerate(zip(ids, val)):
                    if lalu[k] != v:
                        ubah(bi, v + bi)
                        lalu[k] = v
                continue
            ubah(i, l)
            continue
        if l.strip():
            ubah(l[1:], l)
    out.append(f"#{t_selesai - t_mulai}")
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"{dst}: lama {(t_selesai - t_mulai) / 1e6:.2f} us, vektor dipecah {len(vek)}, "
          f"baris perubahan {n_ubah}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
