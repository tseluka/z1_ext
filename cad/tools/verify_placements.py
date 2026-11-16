#!/usr/bin/env python3
# Check that the placed parts rebuild 00_full_assembly.stl triangle-for-triangle.
# Usage: verify_placements.py cad/whole12 cad/whole12_placements.json "[]"
# Triangle-level check: placed parts must reproduce the assembly triangle multiset exactly.
import struct,sys,os,json
from collections import Counter
D=sys.argv[1]; pl=json.load(open(sys.argv[2])); drop={(a,tuple(b)) for a,b in json.loads(sys.argv[3])}
def load(f):
    d=open(os.path.join(D,f),'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    return [tuple(struct.unpack('<3f',d[84+50*i+12+12*v:84+50*i+24+12*v])) for i in range(n) for v in range(3)]
q=lambda p:tuple(round(c*20) for c in p)  # 0.05 mm grid
def tris(V): return Counter(frozenset(q(p) for p in V[i:i+3]) for i in range(0,len(V),3))
AV=load('00_full_assembly.stl')
import math
from collections import defaultdict
G=defaultdict(list)
for p in set(AV): G[tuple(math.floor(c) for c in p)].append(p)
def snap(p):
    c0=[math.floor(c) for c in p]; best=(1e9,None)
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for dz in (-1,0,1):
                for a in G.get((c0[0]+dx,c0[1]+dy,c0[2]+dz),()):
                    d=math.dist(a,p)
                    if d<best[0]: best=(d,a)
    return best[1] if best[0]<0.01 else ('MISS',)+tuple(p)
q=lambda p:p
A=tris(AV)
B=Counter()
for f,insts in pl.items():
    P=load(f)
    for o in insts:
        if (f,tuple(o['t_mm'])) in drop: continue
        M,t=o['R'],o['t_mm']
        B+=tris([snap(tuple(sum(M[r][c]*p[c] for c in range(3))+t[r] for r in range(3))) for p in P])
print('assembly',sum(A.values()),'placed',sum(B.values()),'missing',sum((A-B).values()),'extra',sum((B-A).values()))
