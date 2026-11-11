import Base

type Cp is Data:
  Cp{pos: Nat, neg: Nat, up: Nat, un: Nat, upp: Nat, unp: Nat}

type Pay is Data:
  Nonneg{}
  Negative{}
  Incomparable{}
  Undetermined{}

type V is Data:
  Rat{}
  Irr{}
  IrrB{}
  Unk{}

def cadd(a: Cp, b: Cp) -> Cp:
  match a b:
    case Cp{p1, n1, u1, v1, w1, x1} Cp{p2, n2, u2, v2, w2, x2}:
      Cp{Nat.add(p1, p2), Nat.add(n1, n2), Nat.add(u1, u2), Nat.add(v1, v2), Nat.add(w1, w2), Nat.add(x1, x2)}

def hadd(xs: List<&2, Cp>, ys: List<&2, Cp>) -> List<&2, Cp>:
  match xs ys:
    case Nil{} _:
      ys
    case Con{x, xt} Nil{}:
      Con{x, xt}
    case Con{x, xt} Con{y, yt}:
      Con{cadd(x, y), hadd(xt, yt)}

def c_ge(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, u, +v, w, +x}:
      Bool.and(Nat.is_eq(Nat.add(v, x), 0n), Nat.is_le(n, p))

def c_le(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, +u, v, +w, x}:
      Bool.and(Nat.is_eq(Nat.add(u, w), 0n), Nat.is_le(p, n))

def c_lt(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, +u, v, +w, +x}:
      Bool.and(Bool.and(Nat.is_eq(Nat.add(u, w), 0n), Nat.is_le(p, n)), Bool.or(Nat.is_lt(p, n), Nat.is_gt(x, 0n)))

def c_gt(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, u, +v, +w, +x}:
      Bool.and(Bool.and(Nat.is_eq(Nat.add(v, x), 0n), Nat.is_le(n, p)), Bool.or(Nat.is_lt(n, p), Nat.is_gt(w, 0n)))

def all_ge(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{+x, t}:
      Bool.and(c_ge(x), all_ge(t))

def all_le(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{+x, t}:
      Bool.and(c_le(x), all_le(t))

def any_lt(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{+x, t}:
      Bool.or(c_lt(x), any_lt(t))

def any_gt(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{+x, t}:
      Bool.or(c_gt(x), any_gt(t))

def pick(ge: Bool, le: Bool, lt: Bool, gt: Bool) -> Pay:
  match ge le lt gt:
    case True{} _ _ _:
      Nonneg{}
    case False{} True{} True{} _:
      Negative{}
    case False{} _ True{} True{}:
      Incomparable{}
    case _ _ _ _:
      Undetermined{}

def classify(+h: List<&2, Cp>) -> Pay:
  pick(all_ge(h), all_le(h), any_lt(h), any_gt(h))

def is_nonneg(p: Pay) -> Bool:
  match p:
    case Nonneg{}:
      True{}
    case _:
      False{}

def is_neg(p: Pay) -> Bool:
  match p:
    case Negative{}:
      True{}
    case _:
      False{}

def vpick(w: Bool, l: Bool) -> V:
  match w l:
    case True{} _:
      Rat{}
    case False{} True{}:
      Irr{}
    case False{} False{}:
      Unk{}

def vpick1(w: Bool) -> V:
  match w:
    case True{}:
      Rat{}
    case False{}:
      Unk{}

def step(+mv: Nat) -> List<&2, Cp>:
  [Cp{0n, mv, 0n, 0n, 0n, 0n}]

def zero() -> List<&2, Cp>:
  [Cp{0n, 0n, 0n, 0n, 0n, 0n}]

def pay(k: Nat, +mv: Nat) -> List<&2, Cp>:
  match k:
    case 0n:
      zero()
    case 1n+p:
      hadd(step(mv), pay(p, mv))
