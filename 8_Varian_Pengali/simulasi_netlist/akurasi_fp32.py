# Baca state_dict PyTorch (.pt) tanpa torch: zip + pickle + data float32 mentah
import zipfile, pickle, sys, os, struct, numpy as np, collections
T=sys.argv[1]; pt=os.path.join(T,'export_final','model_mlp_196_64_10.pt')
z=zipfile.ZipFile(pt); names=z.namelist(); root=names[0].split('/')[0]
class Stor:
    def __init__(s,key,dt): s.key=key; s.dt=dt
def rebuild(storage, offset, size, stride, *a):
    raw=np.frombuffer(z.read(f'{root}/data/{storage.key}'),dtype=storage.dt)
    n=int(np.prod(size)) if size else 1
    return np.lib.stride_tricks.as_strided(raw[offset:], shape=size, strides=[s*raw.itemsize for s in stride]).copy() if size else raw[offset:offset+1].copy()
class U(pickle.Unpickler):
    def find_class(s,mod,name):
        if name=='_rebuild_tensor_v2': return rebuild
        if name=='FloatStorage': return 'f4'
        if name=='OrderedDict': return collections.OrderedDict
        if mod=='torch' and name.endswith('Storage'): return 'f4'
        raise pickle.UnpicklingError(f'{mod}.{name}')
    def persistent_load(s,pid):
        _,typ,key,loc,n=pid; return Stor(key,'<f4' if typ in ('f4',) or 'Float' in str(typ) else '<f4')
sd=U(z.open(f'{root}/data.pkl')).load()
print({k:v.shape for k,v in sd.items()})
def idx(p):
    with open(p,'rb') as f:
        m,=struct.unpack('>I',f.read(4)); d=struct.unpack('>'+'I'*(m&0xFF),f.read(4*(m&0xFF)))
        return np.frombuffer(f.read(),dtype=np.uint8).reshape(d)
R=os.path.join(T,'data','MNIST','raw')
X=idx(f'{R}/t10k-images-idx3-ubyte'); y=idx(f'{R}/t10k-labels-idx1-ubyte')
Xf=(X.reshape(-1,14,2,14,2).mean(axis=(2,4)).reshape(-1,196)/255.0).astype(np.float32)
h=np.maximum(Xf@sd['fc1.weight'].T+sd['fc1.bias'],0); o=h@sd['fc2.weight'].T+sd['fc2.bias']
p=o.argmax(1); print(f'akurasi FP32: {(p==y).mean()*100:.2f}%  ({(p==y).sum()}/{len(y)})')
