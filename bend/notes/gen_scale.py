import sys
N=int(sys.argv[1])
f=[f"f{i}" for i in range(N)]
out=["import Base","",
"type R is Data:","  R{"+", ".join(f"{x}: U32" for x in f)+"}","",
"""def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, overlay(t, r)}

def put(mem: List<&2, U32>, off: Nat, bs: List<&2, U32>) -> List<&2, U32>:
  match mem off:
    case Nil{} _:
      Nil{}
    case Con{h, t} 0n:
      overlay(Con{h, t}, bs)
    case Con{h, t} 1n+p:
      Con{h, put(t, p, bs)}
"""]
pat="case R{"+", ".join("+"+x for x in f)+"}:"
# enc_a: overlapping 32-byte words with zero tails, overwritten by later ones; dirty memory
lines=["def enc_a(r: R) -> List<&2, U32>:","  match r:","    "+pat,f"      m0 = List.replicate(U32, {N+32}n, 57005)"]
k=0;j=0
for off in range(0,N,8):
    w=f[off:off+8]+["0"]*(32-len(f[off:off+8]))
    lines.append(f"      m{j+1} = put(m{j}, {off}n, [{', '.join(w)}])"); j+=1
lines.append(f"      List.take(&2, U32, m{j}, {N}n)")
out+=lines+[""]
out+=["def enc_b(r: R) -> List<&2, U32>:","  match r:","    "+pat,"      ["+", ".join(f)+"]",""]
out+=["law eq_ab:","  for r: R","  {enc_a(r) == enc_b(r) : List<&2, U32>}","",
"def eq_ab(r):","  match r:","    case R{"+", ".join(f)+"}:","      {==}",""]
open(f"scale_{N}.bend","w").write("\n".join(out))
