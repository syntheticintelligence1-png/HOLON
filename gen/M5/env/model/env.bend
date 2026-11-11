import Base

def serve(ok: Bool, x: U32) -> Maybe<&2, U32>:
  match ok:
    case True{}:
      Some{x}
    case False{}:
      None{}

def le(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n _:
      True{}
    case 1n+p 0n:
      False{}
    case 1n+p 1n+q:
      le(p, q)

def lt(k: Nat, j: Nat) -> Bool:
  match k j:
    case 0n _:
      False{}
    case 1n+p 0n:
      True{}
    case 1n+p 1n+q:
      lt(p, q)

def is_none(m: Maybe<&2, U32>) -> Type:
  match m:
    case None{}:
      Unit
    case Some{v}:
      Empty

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty

def is_false(b: Bool) -> Type:
  match b:
    case False{}:
      Unit
    case True{}:
      Empty

# env-da-retention: window family, W = 131072 (a premise)
def W() -> U32:
  131072

def da_within(age: U32) -> Bool:
  U32.is_le(age, W())

def da_deliver(age: U32, x: U32) -> Maybe<&2, U32>:
  serve(da_within(age), x)

# env-fetch-archive: availability family (no parameter)
def fetch_deliver(committed: Bool, x: U32) -> Maybe<&2, U32>:
  serve(committed, x)

# env-l1-confirmations: finality_depth family, d = 10 (a premise)
def D() -> Nat:
  10n

def removed(k: Nat, j: Nat) -> Bool:
  lt(k, j)

def consumed_depth(e: Nat) -> Nat:
  Nat.add(D(), e)
