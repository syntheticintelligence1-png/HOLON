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

def head0(xs: List<&2, U32>) -> U32:
  match xs:
    case Nil{}:
      0
    case Con{h, t}:
      h

def disc_b(b: Bool) -> Type:
  match b:
    case True{}:
      Empty
    case False{}:
      Unit

# disc_head(xs, k) is Empty when the head of xs is k, Unit otherwise.
def disc_head(xs: List<&2, U32>, k: U32) -> Type:
  disc_b(U32.is_eq(head0(xs), k))

# A counter-law for a pair that IS equal (version 1): must be rejected.
law cl_codec_v1:
  for h: Hdr
  {enc_sol(pin(h, 1)) != enc_go(pin(h, 1)) : List<&2, U32>}

def cl_codec_v1(h):
  match h:
    case Hdr{v, a0, a1, b0, b1, b2, b3, c0, c1}:
      e => (%e : disc_head(_, 1)
      Unit{})
