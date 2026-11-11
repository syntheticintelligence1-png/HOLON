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

type St is Data:
  St{v0: Nat}

type Act is Data:
  A0{}

def guard(a: Act, s: St) -> Bool:
  match a s:
    case A0{} St{+v0}:
      True{}

def eff(a: Act, s: St) -> St:
  match a s:
    case A0{} St{+v0}:
      St{Nat.add(v0, 2n)}

def bad(s: St) -> Bool:
  match s:
    case St{+v0}:
      Bool.and(True{}, Nat.is_ge(v0, 1n))

def act_eq(a: Act, b: Act) -> Bool:
  match a b:
    case A0{} A0{}:
      True{}
    case _ _:
      False{}

def mem(+a: Act, xs: List<&2, Act>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{h, t}:
      Bool.or(act_eq(a, h), mem(a, t))

def all_acts() -> List<&2, Act>:
  [A0{}]

def s0() -> St:
  St{0n}

def h0() -> List<&2, Cp>:
  [Cp{0n, 0n, 0n, 0n, 0n, 0n}]

def by_0(a: Act) -> Bool:
  match a:
    case A0{}:
      False{}

def fl_0(a: Act, h: List<&2, Cp>) -> List<&2, Cp>:
  match a:
    case A0{}:
      hadd(h, [Cp{0n, 0n, 0n, 0n, 0n, 0n}])

# every legal schedule of distinct actions of class 0 that triggers ends negative (or none triggers)
def lose_0(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      True{}
    case 1n+(+p):
      match xs:
        case Nil{}:
          True{}
        case Con{+a, t}:
          +s2 = eff(a, s)
          +h2 = fl_0(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_0(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.or(Bool.not(t2), is_neg(classify(h2)))
          Bool.and(Bool.or(Bool.not(ok), Bool.and(here, lose_0(p, all_acts(), s2, h2, Con{a, used}, t2))), lose_0(1n+p, t, s, h, used, trig))

# some legal schedule of distinct actions of class 0 triggers and ends nonneg
def win_0(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      False{}
    case 1n+(+p):
      match xs:
        case Nil{}:
          False{}
        case Con{+a, t}:
          +s2 = eff(a, s)
          +h2 = fl_0(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_0(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.and(t2, is_nonneg(classify(h2)))
          Bool.or(Bool.and(ok, Bool.or(here, win_0(p, all_acts(), s2, h2, Con{a, used}, t2))), win_0(1n+p, t, s, h, used, trig))

# a strategy of class 0 (a list of its actions): legal, distinct, triggers, nonneg at its end
def wins_0(xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool, +n: Nat) -> Bool:
  match xs:
    case Nil{}:
      Bool.and(Bool.and(trig, Nat.is_gt(n, 0n)), is_nonneg(classify(h)))
    case Con{+a, t}:
      +s2 = eff(a, s)
      Bool.and(Bool.and(Bool.and(by_0(a), guard(a, s)), Bool.not(mem(a, used))), wins_0(t, s2, fl_0(a, h), Con{a, used}, Bool.or(trig, bad(s2)), Nat.add(n, 1n)))

def verdict_0() -> V:
  vpick(win_0(2n, all_acts(), s0(), h0(), Nil{}, False{}), lose_0(2n, all_acts(), s0(), h0(), Nil{}, False{}))

def by_1(a: Act) -> Bool:
  match a:
    case A0{}:
      True{}

def fl_1(a: Act, h: List<&2, Cp>) -> List<&2, Cp>:
  match a:
    case A0{}:
      hadd(h, [Cp{0n, 0n, 0n, 0n, 0n, 0n}])

# every legal schedule of distinct actions of class 1 that triggers ends negative (or none triggers)
def lose_1(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      True{}
    case 1n+(+p):
      match xs:
        case Nil{}:
          True{}
        case Con{+a, t}:
          +s2 = eff(a, s)
          +h2 = fl_1(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_1(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.or(Bool.not(t2), is_neg(classify(h2)))
          Bool.and(Bool.or(Bool.not(ok), Bool.and(here, lose_1(p, all_acts(), s2, h2, Con{a, used}, t2))), lose_1(1n+p, t, s, h, used, trig))

# some legal schedule of distinct actions of class 1 triggers and ends nonneg
def win_1(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      False{}
    case 1n+(+p):
      match xs:
        case Nil{}:
          False{}
        case Con{+a, t}:
          +s2 = eff(a, s)
          +h2 = fl_1(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_1(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.and(t2, is_nonneg(classify(h2)))
          Bool.or(Bool.and(ok, Bool.or(here, win_1(p, all_acts(), s2, h2, Con{a, used}, t2))), win_1(1n+p, t, s, h, used, trig))

# a strategy of class 1 (a list of its actions): legal, distinct, triggers, nonneg at its end
def wins_1(xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool, +n: Nat) -> Bool:
  match xs:
    case Nil{}:
      Bool.and(Bool.and(trig, Nat.is_gt(n, 0n)), is_nonneg(classify(h)))
    case Con{+a, t}:
      +s2 = eff(a, s)
      Bool.and(Bool.and(Bool.and(by_1(a), guard(a, s)), Bool.not(mem(a, used))), wins_1(t, s2, fl_1(a, h), Con{a, used}, Bool.or(trig, bad(s2)), Nat.add(n, 1n)))

def verdict_1() -> V:
  vpick(win_1(2n, all_acts(), s0(), h0(), Nil{}, False{}), lose_1(2n, all_acts(), s0(), h0(), Nil{}, False{}))

def verdicts() -> List<&2, V>:
  [verdict_0(), verdict_1()]
