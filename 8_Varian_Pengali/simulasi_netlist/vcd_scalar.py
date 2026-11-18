# Pecah variabel vektor VCD menjadi sinyal 1 bit bernama "nama[i]" agar cocok dengan nama sel di netlist Quartus
import sys, itertools
src, dst = sys.argv[1], sys.argv[2]
L = open(src).read().split('\n')
end = L.index('$enddefinitions $end')
def gen_ids():
    alpha=[chr(c) for c in range(33,127)]
    for n in itertools.count(1):
        for t in itertools.product(alpha, repeat=n):
            yield 'Z'+''.join(t)
newid = gen_ids()
vec = {}
hdr = []
for l in L[:end]:
    p = l.split()
    if l.startswith('$var') and int(p[2]) > 1 and len(p) >= 7 and p[-2].startswith('['):
        name = ' '.join(p[4:-2]); msb, lsb = map(int, p[-2][1:-1].split(':'))
        bits = list(range(msb, lsb-1, -1)) if msb >= lsb else list(range(msb, lsb+1))
        ids = [next(newid) for _ in bits]
        vec[p[3]] = (bits, ids, ['x']*len(bits))
        for b, i in zip(bits, ids):
            hdr.append(f'$var wire 1 {i} {name}[{b}] $end')
    else:
        hdr.append(l)
out = hdr + [L[end]]
for l in L[end+1:]:
    if l[:1] in 'bB' and ' ' in l:
        val, i = l[1:].split()
        if i in vec:
            bits, ids, last = vec[i]
            val = val.rjust(len(bits), '0' if val[0] in '01' else val[0])
            for k, (bi, v) in enumerate(zip(ids, val)):
                if last[k] != v:
                    out.append(v + bi); last[k] = v
            continue
    out.append(l)
open(dst, 'w').write('\n'.join(out))
print('vektor dipecah:', len(vec))
