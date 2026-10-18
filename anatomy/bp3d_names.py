import collections
m=collections.defaultdict(list); fma={}
with open(r"C:\AnatomyFactory\anatomy\bp3d\isa_element_parts.txt",encoding="utf-8",errors="replace") as f:
    next(f)
    for line in f:
        p=line.rstrip("\n").split("\t")
        if len(p)>=3:
            m[p[1]].append(p[2]); fma[p[1]]=p[0]
print("UNIQUE_NAMES",len(m),"TOTAL_ELEMENTS",sum(len(v) for v in m.values()))
targets=["deltoid","biceps brachii","triceps brachii","brachialis","pectoralis major","humerus","radius","ulna","scapula","clavicle","skull","masseter","heart"]
for t in targets:
    hits=[(n,len(m[n])) for n in m if t==n.lower() or t in n.lower()]
    print(f"[{t}] ->", hits[:4])
