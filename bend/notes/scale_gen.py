"""Scale probe used for docs/BEND_NOTES.md section 3.

    python bend/notes/scale_gen.py N   # writes scale_N.bend: an N-field record, two encoders
                                        # (overlapping 32-byte EVM-style writes vs direct writes),
                                        # and their equality proved by match-then-{==}
    bend scale_N.bend [--verdict]
"""
import sys
N=int(sys.argv[1]); W=32
fs=[f"f{i}" for i in range(N)]
L=[]
L.append("import Base\n")
L.append("type R is Data:\n  R{"+", ".join(f"{f}: U32" for f in fs)+"}\n")
L.append("""def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
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

def zeros(n: Nat) -> List<&2, U32>:
  match n:
    case 0n:
      Nil{}
    case 1n+p:
      Con{0, zeros(p)}
""")
pat="case R{"+", ".join("+"+f for f in fs)+"}:"
# sol: chunks of 8 fields written as 32-byte words with 24 zero pad (overlapping)
body=[f"      m0 = List.replicate(U32, {N+W}n, 57005)"]
k=0;i=0
while i<N:
    ch=fs[i:i+8]
    body.append(f"      m{k+1} = put(m{k}, {i}n, [{', '.join(ch)}{', 0'*(W-len(ch))}])")
    k+=1;i+=8
body.append(f"      List.take(&2, U32, m{k}, {N}n)")
L.append("def enc_a(r: R) -> List<&2, U32>:\n  match r:\n    "+pat+"\n"+"\n".join(body)+"\n")
body=[f"      m0 = zeros({N}n)"]
k=0;i=0
while i<N:
    ch=fs[i:i+8]
    body.append(f"      m{k+1} = put(m{k}, {i}n, [{', '.join(ch)}])"); k+=1;i+=8
body.append(f"      m{k}")
L.append("def enc_b(r: R) -> List<&2, U32>:\n  match r:\n    "+pat+"\n"+"\n".join(body)+"\n")
L.append("law eqab:\n  for r: R\n  {enc_a(r) == enc_b(r) : List<&2, U32>}\n")
L.append("def eqab(r):\n  match r:\n    case R{"+", ".join(fs)+"}:\n      {==}\n")
open(f"scale_{N}.bend","w").write("\n".join(L))
