set_option autoImplicit false
set_option maxRecDepth 20000
set_option maxHeartbeats 2000000

namespace Model

inductive Obs where
  | ok
  | rev (code : Nat)
deriving DecidableEq

structure T_Sl where
  f_b : Nat
  f_off : Nat
  f_len : Nat
  f_cap : Nat
deriving DecidableEq

structure T_Arr where
  f_cells : List Nat
deriving DecidableEq

structure St where
  f_heap : List T_Arr
  f_ctx : T_Sl
  f_txp : T_Sl
  f_view : T_Sl
  f_snap : List Nat
  f_live : Bool
  f_classes : List Nat
  f_log : List Obs
deriving DecidableEq

inductive Act where
  | a_append (i_bctx : List Nat) (i_payload : List Nat)
  | a_txsPayloadV2
deriving DecidableEq

def hl_nthD {α : Type} : List α → Nat → α → α
  | [], _, d => d
  | h :: _, 0, _ => h
  | _ :: t, i + 1, d => hl_nthD t i d

def hl_setD {α : Type} : List α → Nat → α → α → List α
  | [], 0, v, _ => [v]
  | [], i + 1, v, d => d :: hl_setD [] i v d
  | _ :: t, 0, v, _ => v :: t
  | h :: t, i + 1, v, d => h :: hl_setD t i v d

def hl_lastD {α : Type} : List α → α → α
  | [], d => d
  | [h], _ => h
  | _ :: t, d => hl_lastD t d

def hl_mem (x : Nat) : List Nat → Bool
  | [] => false
  | h :: t => Nat.beq x h || hl_mem x t

def hl_remove (x : Nat) : List Nat → List Nat
  | [] => []
  | h :: t => bif Nat.beq x h then hl_remove x t else h :: hl_remove x t

def hl_zeros : List Nat → List Nat
  | [] => []
  | _ :: t => 0 :: hl_zeros t

def hl_eqNats : List Nat → List Nat → Bool
  | [], [] => true
  | x :: xs, y :: ys => Nat.beq x y && hl_eqNats xs ys
  | _, _ => false

def hl_pair (x y : Nat) : Nat := (x + y) * (x + y + 1) / 2 + y

def hl_enc : List Nat → Nat
  | [] => 0
  | h :: t => 1 + hl_pair h (hl_enc t)

def hl_okHead : List Obs → Bool
  | Obs.ok :: _ => true
  | _ => false

def hl_allOk : List Obs → Bool
  | [] => true
  | Obs.ok :: t => hl_allOk t
  | Obs.rev _ :: _ => false

def hz_Sl : T_Sl := { f_b := 0, f_off := 0, f_len := 0, f_cap := 0 }

def hz_Arr : T_Arr := { f_cells := ([] : List Nat) }

def tw_blobCount : List Nat → Nat
  | [] => 0
  | h :: t => bif Nat.beq h 0 then 0 else 1 + tw_blobCount t

def tw_goLoop : Nat → Bool → Nat → Nat → Nat
  | 0, _, nc, _ => nc
  | _ + 1, true, nc, _ => nc
  | p + 1, false, nc, nl => tw_goLoop p (Nat.ble nl (nc + (nc + 768) / 4)) (nc + (nc + 768) / 4) nl

def tw_goNextcap (nl oc : Nat) : Nat :=
  bif Nat.blt (oc + oc) nl then nl else bif Nat.blt oc 256 then oc + oc else tw_goLoop nl false oc nl

def tw_firstGe : List Nat → Nat → Nat
  | [], n => n
  | h :: t, n => bif Nat.ble n h then h else tw_firstGe t n

def tw_overlay : List Nat → List Nat → List Nat
  | [], _ => []
  | h :: t, [] => h :: t
  | _ :: t, b :: r => b :: tw_overlay t r

def tw_put : List Nat → Nat → List Nat → List Nat
  | [], _, _ => []
  | h :: t, 0, bs => tw_overlay (h :: t) bs
  | h :: t, p + 1, bs => h :: tw_put t p bs

def tw_zeros : Nat → List Nat
  | 0 => []
  | p + 1 => 0 :: tw_zeros p

def tw_goRead (hp : List T_Arr) (sl : T_Sl) : List Nat :=
  List.take sl.f_len (List.drop sl.f_off (hl_nthD hp sl.f_b hz_Arr).f_cells)

def tw_goAppendSlice (hp : List T_Arr) (sl : T_Sl) (xs : List Nat) (cls : List Nat) : T_Sl :=
  bif Nat.ble (sl.f_len + xs.length) sl.f_cap then { sl with f_len := sl.f_len + xs.length }
  else { f_b := hp.length, f_off := 0, f_len := sl.f_len + xs.length, f_cap := tw_firstGe cls (tw_goNextcap (sl.f_len + xs.length) sl.f_cap) }

def tw_goAppendHeap (hp : List T_Arr) (sl : T_Sl) (xs : List Nat) (cls : List Nat) : List T_Arr :=
  bif Nat.ble (sl.f_len + xs.length) sl.f_cap then hl_setD hp sl.f_b { f_cells := tw_put (hl_nthD hp sl.f_b hz_Arr).f_cells (sl.f_off + sl.f_len) xs } hz_Arr
  else hp ++ [{ f_cells := (tw_goRead hp sl ++ xs) ++ tw_zeros (tw_firstGe cls (tw_goNextcap (sl.f_len + xs.length) sl.f_cap) - (sl.f_len + xs.length)) }]

inductive Dc_append where
  | rev (code : Nat)
  | ok (l_c1 : T_Sl) (l_h2 : List T_Arr) (l_t1 : T_Sl)

def dec_append (r_heap : List T_Arr) (r_ctx : T_Sl) (r_txp : T_Sl) (r_classes : List Nat) (i_bctx : List Nat) (i_payload : List Nat) : Dc_append :=
  let l_h1 := (tw_goAppendHeap r_heap r_ctx i_bctx r_classes)
  let l_c1 := (tw_goAppendSlice r_heap r_ctx i_bctx r_classes)
  let l_h2 := (tw_goAppendHeap l_h1 r_txp i_payload r_classes)
  let l_t1 := (tw_goAppendSlice l_h1 r_txp i_payload r_classes)
  Dc_append.ok l_c1 l_h2 l_t1

def exe_append (d : Dc_append) (s : St) : St :=
  match d with
  | Dc_append.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_append.ok l_c1 l_h2 l_t1 => { s with f_heap := l_h2, f_ctx := l_c1, f_txp := l_t1, f_log := Obs.ok :: s.f_log }

def stp_append (s : St) (i_bctx : List Nat) (i_payload : List Nat) : St :=
  exe_append (dec_append s.f_heap s.f_ctx s.f_txp s.f_classes i_bctx i_payload) s

inductive Dc_txsPayloadV2 where
  | rev (code : Nat)
  | ok (l_h1 : List T_Arr) (l_v : T_Sl)

def dec_txsPayloadV2 (r_heap : List T_Arr) (r_ctx : T_Sl) (r_txp : T_Sl) (r_classes : List Nat) : Dc_txsPayloadV2 :=
  let l_pb := (tw_goRead r_heap r_txp)
  let l_h1 := (tw_goAppendHeap r_heap r_ctx l_pb r_classes)
  let l_v := (tw_goAppendSlice r_heap r_ctx l_pb r_classes)
  Dc_txsPayloadV2.ok l_h1 l_v

def exe_txsPayloadV2 (d : Dc_txsPayloadV2) (s : St) : St :=
  match d with
  | Dc_txsPayloadV2.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_txsPayloadV2.ok l_h1 l_v => { s with f_heap := l_h1, f_view := l_v, f_snap := (tw_goRead l_h1 l_v), f_live := true, f_log := Obs.ok :: s.f_log }

def stp_txsPayloadV2 (s : St) : St :=
  exe_txsPayloadV2 (dec_txsPayloadV2 s.f_heap s.f_ctx s.f_txp s.f_classes) s

def step (a : Act) (s : St) : St :=
  match a with
  | Act.a_append i_bctx i_payload => stp_append s i_bctx i_payload
  | Act.a_txsPayloadV2 => stp_txsPayloadV2 s

def run : List Act → St → St
  | [], s => s
  | a :: r, s => run r (step a s)

def s0 : St := { f_heap := [({ f_cells := ([] : List Nat) } : T_Arr)], f_ctx := ({ f_b := 0, f_off := 0, f_len := 0, f_cap := 0 } : T_Sl), f_txp := ({ f_b := 0, f_off := 0, f_len := 0, f_cap := 0 } : T_Sl), f_view := ({ f_b := 0, f_off := 0, f_len := 0, f_cap := 0 } : T_Sl), f_snap := ([] : List Nat), f_live := false, f_classes := [0, 8, 16, 24, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256, 288, 320, 352, 384, 416, 448, 480, 512], f_log := ([] : List Obs) }

def obs (tr : List Act) (s : St) : List Obs :=
  (run tr { s with f_log := [] }).f_log

def fn_runs_ok (tr : List Act) (s : St) : Bool := hl_allOk (obs tr s)

def fn_last_ok (s : St) : Bool := hl_okHead s.f_log

def fn_no_code : List Obs → Nat → Bool
  | [], _ => true
  | Obs.ok :: t, k => fn_no_code t k
  | Obs.rev c :: t, k => !(Nat.beq c k) && fn_no_code t k

def fn_perm : Act → Bool
  | Act.a_append _ _ => true
  | Act.a_txsPayloadV2 => true

def fn_is_append : Act → Bool
  | Act.a_append _ _ => true
  | _ => false

def fn_is_txsPayloadV2 : Act → Bool
  | Act.a_txsPayloadV2 => true
  | _ => false

def ob_view_intact (s : St) : Bool :=
  ((!s.f_live) || (hl_eqNats (tw_goRead s.f_heap s.f_view) s.f_snap))

end Model
