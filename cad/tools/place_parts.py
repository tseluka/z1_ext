#!/usr/bin/env python3
# Solve where each part of cad/whole12 sits in 00_full_assembly.stl (24 axis rotations x
# vertex-anchored translations, 0.05 mm tolerance).
# Usage: place_parts.py cad/whole12 out.json 0.05
# NOTE: a match is by vertices only; always confirm with verify_placements.py (triangle level).
from collections import defaultdict,Counter
D=sys.argv[1]; TOL=float(sys.argv[3])
def load(f):
    d=open(os.path.join(D,f),'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    return [tuple(struct.unpack('<3f',d[84+50*i+12+12*v:84+50*i+24+12*v])) for i in range(n) for v in range(3)]
A=load('00_full_assembly.stl')
Au=list(set(A))
G=defaultdict(list); C=0.5
for p in Au: G[(math.floor(p[0]/C),math.floor(p[1]/C),math.floor(p[2]/C))].append(p)
def near(p):
    cx,cy,cz=(math.floor(p[0]/C),math.floor(p[1]/C),math.floor(p[2]/C)); best=1e9;bp=None
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for dz in (-1,0,1):
                for a in G.get((cx+dx,cy+dy,cz+dz),()):
                    d=math.dist(a,p)
                    if d<best: best,bp=d,a
    return best,bp
rots=[]
for perm in itertools.permutations(range(3)):
    for s in itertools.product((1,-1),repeat=3):
        M=[[0]*3 for _ in range(3)]
        for r in range(3): M[r][perm[r]]=s[r]
        det=(M[0][0]*(M[1][1]*M[2][2]-M[1][2]*M[2][1])-M[0][1]*(M[1][0]*M[2][2]-M[1][2]*M[2][0])+M[0][2]*(M[1][0]*M[2][1]-M[1][1]*M[2][0]))
        if det==1: rots.append(M)
I=[[1,0,0],[0,1,0],[0,0,1]]
app=lambda M,p:tuple(sum(M[r][c]*p[c] for c in range(3)) for r in range(3))
res={}; covered=set()
for f in sorted(os.listdir(D)):
    if f.startswith('00') or not f.endswith('.stl'): continue
    P=load(f); Pu=list(set(P)); sols=[]
    for M in rots:
        R=[app(M,p) for p in Pu]
        v0=min(R); samp=R[::max(1,len(R)//30)]
        for a in Au:
            t=tuple(a[k]-v0[k] for k in range(3))
            if all(near(tuple(s[k]+t[k] for k in range(3)))[0]<TOL for s in samp):
                errs=[near(tuple(s[k]+t[k] for k in range(3))) for s in R]
                mx=max(e[0] for e in errs)
                if mx<TOL: sols.append((M,t,mx,frozenset(e[1] for e in errs)))
    inst={}
    for M,t,mx,key in sols: inst.setdefault(key,[]).append((M,t,mx))
    out=[]
    for key,ss in inst.items():
        M,t,mx=sorted(ss,key=lambda x:(x[0]!=I,x[2]))[0]
        covered|=key
        out.append({'R':M,'t_mm':[round(x,4) for x in t],'max_err_mm':mx,'n_sym':len(ss)})
    out.sort(key=lambda o:o['t_mm'])
    res[f]=out
    print(f,len(out))
    for o in out: print('   t=',o['t_mm'],'R=I' if o['R']==I else o['R'],'err=%.4f'%o['max_err_mm'],'sym',o['n_sym'])
print('assembly unique verts',len(Au),'covered',len(covered),'uncovered',len(set(Au)-covered))
json.dump(res,open(sys.argv[2],'w'),indent=1)
