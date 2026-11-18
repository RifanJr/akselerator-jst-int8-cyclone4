# Ambil hanya modul atom Cyclone IV E yang dipakai papan.vo dari cycloneive_atoms.v,
# karena Icarus menolak modul PLL di berkas aslinya. Hasil: atoms_min.v
import re, sys
src = open(sys.argv[1], errors='replace').read()   # .../quartus/eda/sim_lib/cycloneive_atoms.v
mods = {m.group(1): m.group(0) for m in re.finditer(r'^\s*module\s+(\w+)(.*?)^\s*endmodule', src, re.S | re.M)}
need = ['cycloneive_lcell_comb', 'cycloneive_ram_block', 'cycloneive_io_obuf', 'cycloneive_mac_out',
        'cycloneive_mac_mult', 'cycloneive_io_ibuf', 'cycloneive_clkctrl']
seen, out = set(), []
def add(n):
    if n in seen or n not in mods: return
    seen.add(n)
    for w in set(re.findall(r'\b(cycloneive_\w+)\s+(?:#|\w)', mods[n])): add(w)
    out.append(mods[n])
for n in need: add(n)
defs = sorted(set(l for l in src.split('\n') if l.strip().startswith('`define')))
open('atoms_min.v', 'w').write('\n'.join(defs) + '\n`timescale 1 ps/1 ps\n' + '\n'.join(out))
print('modul diambil:', sorted(seen))
