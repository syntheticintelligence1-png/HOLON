import Base

# Mini header: v (1 byte), a (2 bytes), b (4 bytes), c (2 bytes). 9 bytes on the wire.
type Hdr is Data:
  Hdr{v: U32, a0: U32, a1: U32, b0: U32, b1: U32, b2: U32, b3: U32, c0: U32, c1: U32}

# overlay(mem, bs): replace the prefix of mem with bs, keeping the length of mem.
def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, overlay(t, r)}

# put(mem, off, bs): write bs at byte offset off (an EVM mstore / a Go copy).
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

# "Solidity": dirty memory (57005 = 0xDEAD, outside the byte range), 4-byte words,
# overlapping writes, the c field written as a constant zero, then take 9 bytes.
def enc_sol(h: Hdr) -> List<&2, U32>:
  match h:
    case Hdr{+v, +a0, +a1, +b0, +b1, +b2, +b3, +c0, +c1}:
      m0 = List.replicate(U32, 12n, 57005)
      m1 = put(m0, 0n, [v])
      m2 = put(m1, 1n, [a0, a1, 0, 0])
      m3 = put(m2, 3n, [b0, b1, b2, b3])
      m4 = put(m3, 7n, [0, 0, 0, 0])
      List.take(&2, U32, m4, 9n)

# "Go": zeroed buffer, constant version byte 1, direct writes including c.
def enc_go(h: Hdr) -> List<&2, U32>:
  match h:
    case Hdr{+v, +a0, +a1, +b0, +b1, +b2, +b3, +c0, +c1}:
      m0 = zeros(9n)
      m1 = put(m0, 0n, [1])
      m2 = put(m1, 1n, [a0, a1])
      m3 = put(m2, 3n, [b0, b1, b2, b3])
      put(m3, 7n, [c0, c1])

# Premises of the form field == const are applied by pinning (equivalent to assuming them).
def pin(h: Hdr, k: U32) -> Hdr:
  match h:
    case Hdr{v, a0, a1, b0, b1, b2, b3, c0, c1}:
      Hdr{k, a0, a1, b0, b1, b2, b3, 0, 0}

def list_eq(xs: List<&2, U32>, ys: List<&2, U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(U32.is_eq(x, y), list_eq(xt, yt))

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty

# Generic counter-law with a concrete witness W (the pattern a refuter emits):
#   exs h; {L(h) != R(h)}, proved by (W, e => (%e : is_true(list_eq(_, L(W))); Unit{})).
# The motive at R(W) is is_true(False) = Empty (the goal); at L(W) it is is_true(True) = Unit.
# Here the witness has c = 7, so the claim without the c premise is refuted.
def nopin(h: Hdr) -> Hdr:
  match h:
    case Hdr{v, a0, a1, b0, b1, b2, b3, c0, c1}:
      Hdr{1, a0, a1, b0, b1, b2, b3, c0, c1}

law cl_codec_c:
  exs h: Hdr
  {enc_sol(nopin(h)) != enc_go(nopin(h)) : List<&2, U32>}

def cl_codec_c():
  (Hdr{1, 0, 0, 0, 0, 0, 0, 7, 0}, e => (%e : is_true(list_eq(_, enc_sol(nopin(Hdr{1, 0, 0, 0, 0, 0, 0, 7, 0}))))
  Unit{}))
