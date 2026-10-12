# I16 C probe: a small codec in the shape of the generated M0 model (a byte record, a put chain over a
# zeroed buffer, a version dispatch), compiled to C and to a native binary. No `!` (clang 18 cannot
# build it), no escape hatch.
import Base

type H is Data:
  H{v: U32, a0: U32, a1: U32, b0: U32}

def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
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

def enc_at(n: Nat, h: H) -> List<&2, U32>:
  match n:
    case 0n:
      match h:
        case H{+v, +a0, +a1, +b0}:
          m0 = zeros(4n)
          m1 = put(m0, 0n, [v])
          m2 = put(m1, 1n, [a0, a1])
          put(m2, 3n, [b0])
    case 1n+p:
      [57005]

def enc(h: H) -> List<&2, U32>:
  match h:
    case H{+v, +a0, +a1, +b0}:
      enc_at(U32.to_nat(v), H{v, a0, a1, b0})

def show(xs: List<&2, U32>) -> String:
  match xs:
    case Nil{}:
      ""
    case Con{x, t}:
      U32.show(x) ++ " " ++ show(t)

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(show(enc(H{0, 1, 2, 255})))
    IO.print(show(enc(H{3, 1, 2, 255})))
