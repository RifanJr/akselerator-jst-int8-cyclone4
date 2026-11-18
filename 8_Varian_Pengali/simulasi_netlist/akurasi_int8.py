import re, struct, sys, os, numpy as np
T = sys.argv[1]  # folder Training
def idx(p):
    with open(p,'rb') as f:
        m,=struct.unpack('>I',f.read(4)); d=struct.unpack('>'+'I'*(m&0xFF),f.read(4*(m&0xFF)))
        return np.frombuffer(f.read(),dtype=np.uint8).reshape(d)
def coe(p):
    b=open(p).read().split('memory_initialization_vector=')[1]
    a=np.array([int(t,16) for t in re.findall(r'\b([0-9A-Fa-f]{2})\b',b)],dtype=np.int64)
    return np.where(a>=128,a-256,a)
E=os.path.join(T,'export_final'); R=os.path.join(T,'data','MNIST','raw')
W1=coe(f'{E}/weights_layer1.coe').reshape(64,196); W2=coe(f'{E}/weights_layer2.coe').reshape(10,64)
B1=coe(f'{E}/bias_layer1.coe'); B2=coe(f'{E}/bias_layer2.coe')
X=idx(f'{R}/t10k-images-idx3-ubyte'); y=idx(f'{R}/t10k-labels-idx1-ubyte')
Xf=(X.reshape(-1,14,2,14,2).mean(axis=(2,4)).reshape(-1,196)/255.0).astype(np.float32)
Xq=np.clip(np.round(Xf*64),-128,127).astype(np.int64)
a1=Xq@W1.T+(B1<<4); a1=np.maximum(a1,0); H=np.clip(a1>>8,-128,127)
a2=H@W2.T+(B2<<1)
pred=a2.argmax(1); acc=(pred==y).mean()
print(f'citra uji: {len(y)}  benar: {(pred==y).sum()}  akurasi INT8: {acc*100:.2f}%')
print(f'akumulator maks |L1| {np.abs(Xq@W1.T+(B1<<4)).max()}  |L2| {np.abs(a2).max()}')
# cek citra uji 0 terhadap golden_output.txt
g=[int(l.split(':')[1]) for l in open(f'{E}/golden_output.txt') if 'digit' in l]
print('citra 0 cocok dengan golden_output.txt:', list(a2[0])==g)
