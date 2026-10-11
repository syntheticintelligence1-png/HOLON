"""Shared Lean prelude: the term-for-term mirror of the Bend models' preludes.

Bend's `List<&2, U32>` byte strings become `List Nat` in Lean (the `&2` scope
annotation and `U32` truncation have no analogue -- values stay `Nat`, with
`UNDEF = 57005` marking undefined memory exactly as in the Bend model). Every
definition here computes identically to its Bend counterpart.
"""

# Mirrors holon/gen/model.py's PRELUDE (codec) and the shared helpers of
# holon/gen/machine.py's PRELUDE (machines). Names are camel-cased only where
# Lean requires; every generated `ex` term calls these exact names.
PRELUDE = '''\
-- Nat comparisons as Bool (mirrors Bend's Nat.is_*).
def natAdd : Nat -> Nat -> Nat
  | 0, b => b
  | a+1, b => Nat.succ (natAdd a b)

def isLt (a b : Nat) : Bool := Nat.ble (a + 1) b
def isLe (a b : Nat) : Bool := Nat.ble a b
def isGt (a b : Nat) : Bool := Nat.ble (b + 1) a
def isGe (a b : Nat) : Bool := Nat.ble b a
def isEq (a b : Nat) : Bool := Nat.beq a b

-- overlay(mem, bs): replace the prefix of mem with bs, keeping the length of mem.
def overlay : List Nat -> List Nat -> List Nat
  | [], _ => []
  | h :: t, [] => h :: t
  | _ :: t, b :: r => b :: overlay t r

-- put(mem, off, bs): write bs at byte offset off (EVM mstore/mstore8, Go copy/PutUint64).
def put : List Nat -> Nat -> List Nat -> List Nat
  | [], _, _ => []
  | h :: t, 0, bs => overlay (h :: t) bs
  | h :: t, n + 1, bs => h :: put t n bs

def zeros : Nat -> List Nat
  | 0 => []
  | n + 1 => 0 :: zeros n

-- slice(b, off, w) = b[off:off+w]
def slice (b : List Nat) (off w : Nat) : List Nat := (b.drop off).take w

-- length tests on the tail t of a non-empty byte string b = h::t (len(b) = 1 + len(t))
def tailLenGe (t : List Nat) (k : Nat) : Bool := Nat.ble k t.length
def tailLenEq (t : List Nat) (k : Nat) : Bool := Nat.beq t.length k

def nthD {a : Type} : List a -> Nat -> a -> a
  | [], _, d => d
  | h :: _, 0, _ => h
  | _ :: t, n + 1, d => nthD t n d

def setD {a : Type} : List a -> Nat -> a -> a -> List a
  | [], 0, v, _ => [v]
  | [], n + 1, v, d => d :: setD [] n v d
  | _ :: t, 0, v, _ => v :: t
  | h :: t, n + 1, v, d => h :: setD t n v d

def tail0 {a : Type} : List a -> List a
  | [] => []
  | _ :: t => t

def lastD {a : Type} : List a -> a -> a
  | [], d => d
  | [h], _ => h
  | _ :: h2 :: t2, d => lastD (h2 :: t2) d

def bNth (xs : List Nat) (i : Nat) : Nat := nthD xs i 0
def bSetNat (xs : List Nat) (i : Nat) (v : Nat) : List Nat := setD xs i v 0

def bMem : Nat -> List Nat -> Bool
  | _, [] => false
  | x, h :: t => x == h || bMem x t

def bRemove : Nat -> List Nat -> List Nat
  | _, [] => []
  | x, h :: t => if x == h then bRemove x t else h :: bRemove x t

def bBlobCount : List Nat -> Nat
  | [] => 0
  | h :: t => if h == 0 then 0 else 1 + bBlobCount t

def bPair (a b : Nat) : Nat := (a + b) * (a + b + 1) / 2 + b

def bEnc : List Nat -> Nat
  | [] => 0
  | h :: t => 1 + bPair h (bEnc t)

def bZerosLike : List Nat -> List Nat
  | [] => []
  | _ :: t => 0 :: bZerosLike t

def eqBool (a b : Bool) : Bool := a == b

def eqListNat : List Nat -> List Nat -> Bool
  | [], [] => true
  | [], _ :: _ => false
  | _ :: _, [] => false
  | x :: xt, y :: yt => x == y && eqListNat xt yt
'''

# Go runtime oracle (facts with Sl/Arr types): mirrors machine.GO_LIB.
GO_LIB = '''\
-- b_go_loop: Go 1.24 runtime/slice.go nextslicecap growth loop, fuel = newlen.
def bGoLoop : Nat -> Bool -> Nat -> Nat -> Nat
  | 0, _, newcap, _ => newcap
  | p + 1, done, newcap, newlen =>
      if done then newcap
      else
        let nc := newcap + (newcap + 768) / 4
        bGoLoop p (Nat.ble newlen nc) nc newlen

def bGoNextcap (newlen oldcap : Nat) : Nat :=
  if isGt newlen (oldcap + oldcap) then newlen
  else if isLt oldcap 256 then oldcap + oldcap
  else bGoLoop newlen false oldcap newlen

def bFirstGe : List Nat -> Nat -> Nat
  | [], n => n
  | h :: t, n => if isGe h n then h else bFirstGe t n

def bZeros : Nat -> List Nat
  | 0 => []
  | n + 1 => 0 :: bZeros n

def bGoRead (heap : List HArr) (s : HSl) : List Nat :=
  ((nthD heap s.b emptyArr).cells.drop s.off).take s.len

-- append(s, xs...): in place when it fits the capacity, else a new backing array.
def bGoAppendSlice (heap : List HArr) (s : HSl) (xs cls : List Nat) : HSl :=
  let n := s.len + xs.length
  if isLe n s.cap then { s with len := n }
  else { b := heap.length, off := 0, len := n,
         cap := bFirstGe cls (bGoNextcap n s.cap) }

def bGoAppendHeap (heap : List HArr) (s : HSl) (xs cls : List Nat) : List HArr :=
  let n := s.len + xs.length
  let nc := bFirstGe cls (bGoNextcap n s.cap)
  let grown := bGoRead heap { b := s.b, off := s.off, len := s.len, cap := s.cap } ++ xs
  if isLe n s.cap then
    setD heap s.b (HArr.mk (put (nthD heap s.b emptyArr).cells (s.off + s.len) xs)) emptyArr
  else
    heap ++ [HArr.mk (grown ++ bZeros (nc - n))]
'''
