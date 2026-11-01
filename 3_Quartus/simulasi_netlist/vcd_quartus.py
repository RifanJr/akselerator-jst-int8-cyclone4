# Siapkan VCD Icarus untuk Quartus: buang scope testbench, buang blok $dumpall kosong,
# pecah vektor menjadi bit bernama "nama [i]" (format yang dipakai skrip VCD buatan Quartus)
import sys, itertools, re
src, dst = sys.argv[1], sys.argv[2]
L = open(src).read().split('\n')
L = [l for l in L if l.strip() != '$scope module tb_netlist $end']
L = ['$scope module top_papan $end' if l.strip() == '$scope module dut $end' else l for l in L]
end = L.index('$enddefinitions $end')
ups = [i for i in range(end) if L[i].strip() == '$upscope $end']; del L[ups[-1]]; end -= 1
if L[end+1].startswith('$comment'): del L[end+1:end+4]
def gen():
    a = [chr(c) for c in range(33, 127)]
    for n in itertools.count(1):
        for t in itertools.product(a, repeat=n): yield 'Z' + ''.join(t)
g = gen(); vec = {}; hdr = []
for l in L[:end]:
    p = l.split()
    if l.startswith('$var') and int(p[2]) > 1 and p[-2].startswith('['):
        name = ' '.join(p[4:-2]); msb, lsb = map(int, p[-2][1:-1].split(':'))
        bits = list(range(msb, lsb-1, -1)) if msb >= lsb else list(range(msb, lsb+1))
        ids = [next(g) for _ in bits]; vec[p[3]] = (ids, ['x']*len(bits))
        hdr += [f'$var wire 1 {i} {name} [{b}] $end' for b, i in zip(bits, ids)]
    else: hdr.append(l)
out = hdr + [L[end]]
for l in L[end+1:]:
    if l[:1] in 'bB' and ' ' in l:
        val, i = l[1:].split()
        if i in vec:
            ids, last = vec[i]; val = val.rjust(len(ids), '0' if val[0] in '01' else val[0])
            for k, (bi, v) in enumerate(zip(ids, val)):
                if last[k] != v: out.append(v + bi); last[k] = v
            continue
    out.append(l)
open(dst, 'w').write('\n'.join(out)); print(dst, 'vektor dipecah:', len(vec))
