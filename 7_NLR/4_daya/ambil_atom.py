#!/usr/bin/env python3
"""
Ambil modul atom Cyclone IV E yang dipakai netlist dari cycloneive_atoms.v,
karena Icarus menolak modul PLL di berkas aslinya.

    python ambil_atom.py cycloneive_atoms.v netlist.vo keluar.v

Diadaptasi dari 3_Quartus/simulasi_netlist/ambil_atom.py (Student A,
1 November 2026); daftar atom kini dibaca dari netlist, bukan ditulis tangan.
"""
import re
import sys

src = open(sys.argv[1], errors="replace").read()
vo = open(sys.argv[2], errors="replace").read()
mods = {m.group(1): m.group(0)
        for m in re.finditer(r"^\s*module\s+(\w+)(.*?)^\s*endmodule", src, re.S | re.M)}
perlu = sorted(set(re.findall(r"^\s*(cycloneive_\w+)\s", vo, re.M)))
seen, out = set(), []


def tambah(n):
    if n in seen or n not in mods:
        return
    seen.add(n)
    for w in set(re.findall(r"\b(cycloneive_\w+)\s+(?:#|\w)", mods[n])):
        tambah(w)
    out.append(mods[n])


for n in perlu:
    tambah(n)
hilang = [n for n in perlu if n not in seen]
if hilang:
    raise SystemExit(f"atom tidak ditemukan: {hilang}")
defs = sorted(set(l for l in src.split("\n") if l.strip().startswith("`define")))
open(sys.argv[3], "w").write("\n".join(defs) + "\n`timescale 1 ps/1 ps\n" + "\n".join(out))
print("atom dipakai netlist:", perlu)
