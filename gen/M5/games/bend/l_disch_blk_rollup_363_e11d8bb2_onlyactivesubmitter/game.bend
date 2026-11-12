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

type Grp is Data:
  Gr0{}
  Gr1{}
  Gr2{}
  Gr3{}
  Gr4{}
  Gr5{}
  Gr6{}
  Gr7{}
  Gr8{}
  Gr9{}
  Gr10{}
  GrNone{}

type Step is Data:
  Step{g: Grp, d: List<&2, Cp>}

def grp_eq(a: Grp, b: Grp) -> Bool:
  match a b:
    case Gr0{} Gr0{}:
      True{}
    case Gr1{} Gr1{}:
      True{}
    case Gr2{} Gr2{}:
      True{}
    case Gr3{} Gr3{}:
      True{}
    case Gr4{} Gr4{}:
      True{}
    case Gr5{} Gr5{}:
      True{}
    case Gr6{} Gr6{}:
      True{}
    case Gr7{} Gr7{}:
      True{}
    case Gr8{} Gr8{}:
      True{}
    case Gr9{} Gr9{}:
      True{}
    case Gr10{} Gr10{}:
      True{}
    case GrNone{} GrNone{}:
      True{}
    case _ _:
      False{}

def cp_eq(a: Cp, b: Cp) -> Bool:
  match a b:
    case Cp{p1, n1, u1, v1, w1, x1} Cp{p2, n2, u2, v2, w2, x2}:
      Bool.and(Bool.and(Bool.and(Nat.is_eq(p1, p2), Nat.is_eq(n1, n2)), Bool.and(Nat.is_eq(u1, u2), Nat.is_eq(v1, v2))), Bool.and(Nat.is_eq(w1, w2), Nat.is_eq(x1, x2)))

def cps_eq(xs: List<&2, Cp>, ys: List<&2, Cp>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(cp_eq(x, y), cps_eq(xt, yt))
    case _ _:
      False{}

def step_eq(a: Step, b: Step) -> Bool:
  match a b:
    case Step{g1, d1} Step{g2, d2}:
      Bool.and(grp_eq(g1, g2), cps_eq(d1, d2))

def steps_eq(xs: List<&2, Step>, ys: List<&2, Step>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(step_eq(x, y), steps_eq(xt, yt))
    case _ _:
      False{}

def pay(xs: List<&2, Step>, h: List<&2, Cp>) -> List<&2, Cp>:
  match xs:
    case Nil{}:
      h
    case Con{x, t}:
      match x:
        case Step{g, d}:
          pay(t, hadd(h, d))

def witness() -> List<&2, Step>:
  [Step{Gr5{}, [Cp{0n, 0n, 0n, 0n, 0n, 0n}]}, Step{Gr6{}, [Cp{0n, 1n, 0n, 0n, 0n, 0n}]}, Step{Gr5{}, [Cp{1n, 0n, 1n, 1n, 0n, 0n}]}]

def h0() -> List<&2, Cp>:
  [Cp{0n, 0n, 0n, 0n, 0n, 0n}]

def may_0(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      True{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_0(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_0(g), legal_0(t))

def wins_0(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_0(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_0() -> V:
  vpick1(wins_0(witness()))

def may_1(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      True{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_1(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_1(g), legal_1(t))

def wins_1(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_1(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_1() -> V:
  vpick1(wins_1(witness()))

def may_2(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      True{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_2(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_2(g), legal_2(t))

def wins_2(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_2(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_2() -> V:
  vpick1(wins_2(witness()))

def may_3(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      True{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_3(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_3(g), legal_3(t))

def wins_3(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_3(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_3() -> V:
  vpick1(wins_3(witness()))

def may_4(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      True{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_4(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_4(g), legal_4(t))

def wins_4(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_4(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_4() -> V:
  vpick1(wins_4(witness()))

def may_5(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      True{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_5(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_5(g), legal_5(t))

def wins_5(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_5(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_5() -> V:
  vpick1(wins_5(witness()))

def may_6(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      True{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_6(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_6(g), legal_6(t))

def wins_6(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_6(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_6() -> V:
  vpick1(wins_6(witness()))

def may_7(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      True{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_7(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_7(g), legal_7(t))

def wins_7(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_7(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_7() -> V:
  vpick1(wins_7(witness()))

def may_8(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      True{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_8(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_8(g), legal_8(t))

def wins_8(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_8(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_8() -> V:
  vpick1(wins_8(witness()))

def may_9(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      True{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_9(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_9(g), legal_9(t))

def wins_9(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_9(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_9() -> V:
  vpick1(wins_9(witness()))

def may_10(g: Grp) -> Bool:
  match g:
    case Gr0{}:
      False{}
    case Gr1{}:
      False{}
    case Gr2{}:
      False{}
    case Gr3{}:
      False{}
    case Gr4{}:
      False{}
    case Gr5{}:
      False{}
    case Gr6{}:
      False{}
    case Gr7{}:
      False{}
    case Gr8{}:
      False{}
    case Gr9{}:
      False{}
    case Gr10{}:
      True{}
    case GrNone{}:
      False{}

def legal_10(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{x, t}:
      match x:
        case Step{g, d}:
          Bool.and(may_10(g), legal_10(t))

def wins_10(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_10(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_10() -> V:
  vpick1(wins_10(witness()))

def verdicts() -> List<&2, V>:
  [verdict_0(), verdict_1(), verdict_2(), verdict_3(), verdict_4(), verdict_5(), verdict_6(), verdict_7(), verdict_8(), verdict_9(), verdict_10()]
