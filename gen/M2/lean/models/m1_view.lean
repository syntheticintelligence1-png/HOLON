set_option autoImplicit false
set_option maxRecDepth 20000
set_option maxHeartbeats 2000000

namespace Model

inductive Obs where
  | ok
  | rev (code : Nat)
deriving DecidableEq

structure T_BD where
  f_o : Nat
  f_f : Nat
  f_n : Nat
  f_s : Nat
deriving DecidableEq

structure T_Ch where
  f_c : Nat
  f_d : Nat
  f_s : Nat
  f_w : Bool
  f_f : Bool
deriving DecidableEq

structure T_Entry where
  f_ver : Nat
  f_tot : Nat
  f_n : Nat
  f_hb : Nat
  f_prev : Nat
  f_post : Nat
  f_lbn : Nat
  f_csr : Nat
  f_bvh : Nat
  f_tag : Nat
  f_bdo : Nat
  f_bdf : Nat
  f_bdn : Nat
  f_bds : Nat
deriving DecidableEq

structure St where
  f_t : Nat
  f_lfi : Nat
  f_inch : Bool
  f_bc : Nat
  f_rri : Nat
  f_paused : Bool
  f_W : Nat
  f_F : Nat
  f_D : Nat
  f_qlen : Nat
  f_qpend : Nat
  f_enq : List Nat
  f_active : List Nat
  f_chals : List Nat
  f_fsr : List Nat
  f_chs : List T_Ch
  f_win : List T_Entry
  f_s_csr : List Nat
  f_s_bd : List T_BD
  f_s_bvh : List Nat
  f_s_tag : List Nat
  f_log : List Obs
deriving DecidableEq

inductive Act where
  | a_commitBatch (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat)
  | a_commitState (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat)
  | a_commitBatchWithProof (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) (i_proof : Nat)
  | a_revertBatch (i_who : Nat) (i_idx : Nat) (i_count : Nat)
  | a_challengeState (i_who : Nat) (i_idx : Nat) (i_value : Nat)
  | a_proveState (i_who : Nat) (i_idx : Nat) (i_proof : Nat)
  | a_finalizeBatch (i_who : Nat) (i_idx : Nat)
  | a_setPause (i_who : Nat) (i_status : Bool)
  | a_sendMessage (i_who : Nat)
  | a_wait (i_dt : Nat)
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

def hz_BD : T_BD := { f_o := 0, f_f := 0, f_n := 0, f_s := 0 }

def hz_Ch : T_Ch := { f_c := 0, f_d := 0, f_s := 0, f_w := false, f_f := false }

def hz_Entry : T_Entry := { f_ver := 0, f_tot := 0, f_n := 0, f_hb := 0, f_prev := 0, f_post := 0, f_lbn := 0, f_csr := 0, f_bvh := 0, f_tag := 0, f_bdo := 0, f_bdf := 0, f_bdn := 0, f_bds := 0 }

def tw_blobCount : List Nat → Nat
  | [] => 0
  | h :: t => bif Nat.beq h 0 then 0 else 1 + tw_blobCount t

def tw_bumpGo : List T_Entry → Nat → Nat → Nat → List T_Entry
  | [], _, _, _ => []
  | e :: t, pos, skip, w => (bif (Nat.blt 0 pos && !(Nat.beq pos skip)) then { e with f_bdf := e.f_bdf + w } else e) :: tw_bumpGo t (pos + 1) skip w

def tw_anyGo : List T_Ch → Nat → Nat → Nat → Bool
  | [], _, _, _ => false
  | c :: t, i, lo, hi => (((Nat.ble lo i) && (Nat.ble i hi)) && ((!(Nat.beq c.f_c 0)) && (!c.f_f))) || tw_anyGo t (i + 1) lo hi

def tw_clearGo : List T_Ch → Nat → Nat → Nat → List T_Ch
  | [], _, _, _ => []
  | c :: t, i, lo, hi => (bif ((Nat.ble lo i) && (Nat.ble i hi)) then hz_Ch else c) :: tw_clearGo t (i + 1) lo hi

def tw_zeroCsr : List T_Entry → List T_Entry
  | [] => []
  | e :: t => { e with f_csr := 0 } :: tw_zeroCsr t

def tw_setLastCsr : List T_Entry → Nat → List T_Entry
  | [], _ => []
  | [e], r => [{ e with f_csr := r }]
  | e :: t, r => e :: tw_setLastCsr t r

def tw_tagsExact : List T_Entry → Bool
  | [] => true
  | e :: t => (bif Nat.beq e.f_ver 2 then Nat.beq e.f_tag 2 else !(Nat.beq e.f_tag 2)) && tw_tagsExact t

def tw_hdrOf (e : T_Entry) : List Nat := [e.f_ver, e.f_tot, e.f_n, e.f_hb, e.f_prev, e.f_post, e.f_lbn]

def hs_bd : List T_Entry → List T_BD
  | [] => []
  | e :: t => ({ f_o := e.f_bdo, f_f := e.f_bdf, f_n := e.f_bdn, f_s := e.f_bds } : T_BD) :: hs_bd t

def hs_bvh : List T_Entry → List Nat
  | [] => []
  | e :: t => e.f_bvh :: hs_bvh t

def hs_csr : List T_Entry → List Nat
  | [] => []
  | e :: t => e.f_csr :: hs_csr t

def hs_tag : List T_Entry → List Nat
  | [] => []
  | e :: t => e.f_tag :: hs_tag t

def d_blob_hash (x_ver : Nat) (x_blobs : List Nat) : Nat :=
  (bif (Nat.beq x_ver 2) then (1000 + hl_enc x_blobs) else (bif (Nat.beq (hl_nthD x_blobs 0 0) 0) then 1 else (hl_nthD x_blobs 0 0)))

def d_enq_first (x_qpend : Nat) (x_qlen : Nat) (x_enq : List Nat) (x_t : Nat) : Nat :=
  (bif ((Nat.blt x_qpend x_qlen) && (!(Nat.beq (hl_nthD x_enq x_qpend 0) 0))) then (hl_nthD x_enq x_qpend 0) else x_t)

def d_lci (x_lfi : Nat) (x_win : List T_Entry) : Nat :=
  ((x_lfi + (List.length x_win)) - 1)

def d_in_win (x_lfi : Nat) (x_win : List T_Entry) (x_idx : Nat) : Bool :=
  ((Nat.ble x_lfi x_idx) && (Nat.ble x_idx (d_lci x_lfi x_win)))

def d_open_ch (x_chs : List T_Ch) (x_idx : Nat) : Bool :=
  ((!(Nat.beq ((hl_nthD x_chs x_idx hz_Ch).f_c) 0)) && (!((hl_nthD x_chs x_idx hz_Ch).f_f)))

def d_w (x_lfi : Nat) (x_win : List T_Entry) (x_idx : Nat) : T_Entry :=
  (bif (d_in_win x_lfi x_win x_idx) then (hl_nthD x_win (x_idx - x_lfi) hz_Entry) else hz_Entry)

def d_bvh_at (x_lfi : Nat) (x_win : List T_Entry) (x_s_bvh : List Nat) (x_idx : Nat) : Nat :=
  (bif (Nat.blt x_idx x_lfi) then 0 else (bif (Nat.ble x_idx (d_lci x_lfi x_win)) then (d_w x_lfi x_win x_idx).f_bvh else (hl_nthD x_s_bvh ((x_idx - (d_lci x_lfi x_win)) - 1) 0)))

def d_tag_at (x_lfi : Nat) (x_win : List T_Entry) (x_s_tag : List Nat) (x_idx : Nat) : Nat :=
  (bif (Nat.blt x_idx x_lfi) then 0 else (bif (Nat.ble x_idx (d_lci x_lfi x_win)) then (d_w x_lfi x_win x_idx).f_tag else (hl_nthD x_s_tag ((x_idx - (d_lci x_lfi x_win)) - 1) 0)))

inductive Dc_commitBatch where
  | rev (code : Nat)
  | ok (l_bvh : Nat) (l_tag : Nat) (l_tot : Nat) (l_prt : Nat)

def dec_commitBatch (r_t : Nat) (r_lfi : Nat) (r_inch : Bool) (r_bc : Nat) (r_rri : Nat) (r_paused : Bool) (r_W : Nat) (r_D : Nat) (r_qlen : Nat) (r_qpend : Nat) (r_enq : List Nat) (r_active : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (r_s_bvh : List Nat) (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) : Dc_commitBatch :=
  bif !(hl_mem i_who r_active) then Dc_commitBatch.rev 1 else
  bif !(Nat.beq r_rri 0) then Dc_commitBatch.rev 2 else
  bif !(!r_paused) then Dc_commitBatch.rev 3 else
  let l_next := (i_parent + 1)
  bif !(Nat.beq (d_bvh_at r_lfi r_win r_s_bvh l_next) 0) then Dc_commitBatch.rev 4 else
  let l_ef := (d_enq_first r_qpend r_qlen r_enq r_t)
  bif !((!(Nat.blt (l_ef + r_D) r_t)) || (Nat.blt 0 i_n)) then Dc_commitBatch.rev 5 else
  let l_b1 := (hl_nthD i_blobs 1 0)
  bif !((!(Nat.beq i_ver 2)) || (Nat.blt 0 (tw_blobCount i_blobs))) then Dc_commitBatch.rev 6 else
  bif !((Nat.beq i_ver 2) || (Nat.beq l_b1 0)) then Dc_commitBatch.rev 7 else
  let l_bvh := (d_blob_hash i_ver i_blobs)
  let l_tag := (bif (Nat.beq i_ver 2) then 2 else 1)
  bif !(Nat.ble i_ver 2) then Dc_commitBatch.rev 8 else
  bif !(!(Nat.beq i_prev 0)) then Dc_commitBatch.rev 9 else
  bif !(!(Nat.beq i_post 0)) then Dc_commitBatch.rev 10 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.blt l_lci l_next) then Dc_commitBatch.rev 11 else
  bif !(Nat.beq i_parent l_lci) then Dc_commitBatch.rev 12 else
  bif !(Nat.beq ((d_w r_lfi r_win i_parent).f_csr) i_prev) then Dc_commitBatch.rev 14 else
  let l_tot := (d_w r_lfi r_win i_parent).f_tot
  let l_cstart := (hl_nthD r_chs r_bc hz_Ch).f_s
  bif !((!r_inch) || (Nat.ble r_t (r_W + l_cstart))) then Dc_commitBatch.rev 16 else
  let l_prt := (bif r_inch then ((r_W + l_cstart) - r_t) else 0)
  Dc_commitBatch.ok l_bvh l_tag l_tot l_prt

def exe_commitBatch (d : Dc_commitBatch) (s : St) (i_who : Nat) (i_ver : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) : St :=
  match d with
  | Dc_commitBatch.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_commitBatch.ok l_bvh l_tag l_tot l_prt => { s with f_win := (s.f_win ++ [({ f_ver := i_ver, f_tot := (l_tot + i_n), f_n := i_n, f_hb := l_bvh, f_prev := i_prev, f_post := i_post, f_lbn := i_lbn, f_csr := i_post, f_bvh := l_bvh, f_tag := l_tag, f_bdo := s.f_t, f_bdf := ((s.f_t + s.f_F) + l_prt), f_bdn := i_lbn, f_bds := i_who } : T_Entry)]), f_s_csr := (List.tail s.f_s_csr), f_s_bd := (List.tail s.f_s_bd), f_s_bvh := (List.tail s.f_s_bvh), f_s_tag := (List.tail s.f_s_tag), f_log := Obs.ok :: s.f_log }

def stp_commitBatch (s : St) (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) : St :=
  exe_commitBatch (dec_commitBatch s.f_t s.f_lfi s.f_inch s.f_bc s.f_rri s.f_paused s.f_W s.f_D s.f_qlen s.f_qpend s.f_enq s.f_active s.f_chs s.f_win s.f_s_bvh i_who i_ver i_parent i_n i_prev i_post i_blobs) s i_who i_ver i_n i_lbn i_prev i_post

inductive Dc_commitState where
  | rev (code : Nat)
  | ok (l_bvh : Nat) (l_tag : Nat) (l_tot : Nat) (l_prt : Nat)

def dec_commitState (r_t : Nat) (r_lfi : Nat) (r_inch : Bool) (r_bc : Nat) (r_rri : Nat) (r_paused : Bool) (r_W : Nat) (r_qlen : Nat) (r_qpend : Nat) (r_enq : List Nat) (r_active : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (r_s_bvh : List Nat) (r_s_tag : List Nat) (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) : Dc_commitState :=
  bif !(hl_mem i_who r_active) then Dc_commitState.rev 1 else
  bif !(Nat.beq r_rri 0) then Dc_commitState.rev 2 else
  bif !(!r_paused) then Dc_commitState.rev 3 else
  let l_b0 := (hl_nthD i_blobs 0 0)
  bif !(Nat.beq l_b0 0) then Dc_commitState.rev 17 else
  let l_next := (i_parent + 1)
  let l_bvh := (d_bvh_at r_lfi r_win r_s_bvh l_next)
  bif !(!(Nat.beq l_bvh 0)) then Dc_commitState.rev 18 else
  let l_tag := (d_tag_at r_lfi r_win r_s_tag l_next)
  bif !(Nat.ble i_ver 2) then Dc_commitState.rev 8 else
  bif !(!(Nat.beq i_prev 0)) then Dc_commitState.rev 9 else
  bif !(!(Nat.beq i_post 0)) then Dc_commitState.rev 10 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.blt l_lci l_next) then Dc_commitState.rev 11 else
  bif !(Nat.beq i_parent l_lci) then Dc_commitState.rev 12 else
  bif !(Nat.beq ((d_w r_lfi r_win i_parent).f_csr) i_prev) then Dc_commitState.rev 14 else
  let l_tot := (d_w r_lfi r_win i_parent).f_tot
  let l_cstart := (hl_nthD r_chs r_bc hz_Ch).f_s
  bif !((!r_inch) || (Nat.ble r_t (r_W + l_cstart))) then Dc_commitState.rev 16 else
  let l_prt := (bif r_inch then ((r_W + l_cstart) - r_t) else 0)
  Dc_commitState.ok l_bvh l_tag l_tot l_prt

def exe_commitState (d : Dc_commitState) (s : St) (i_who : Nat) (i_ver : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) : St :=
  match d with
  | Dc_commitState.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_commitState.ok l_bvh l_tag l_tot l_prt => { s with f_win := (s.f_win ++ [({ f_ver := i_ver, f_tot := (l_tot + i_n), f_n := i_n, f_hb := l_bvh, f_prev := i_prev, f_post := i_post, f_lbn := i_lbn, f_csr := i_post, f_bvh := l_bvh, f_tag := l_tag, f_bdo := s.f_t, f_bdf := ((s.f_t + s.f_F) + l_prt), f_bdn := i_lbn, f_bds := i_who } : T_Entry)]), f_s_csr := (List.tail s.f_s_csr), f_s_bd := (List.tail s.f_s_bd), f_s_bvh := (List.tail s.f_s_bvh), f_s_tag := (List.tail s.f_s_tag), f_log := Obs.ok :: s.f_log }

def stp_commitState (s : St) (i_who : Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) : St :=
  exe_commitState (dec_commitState s.f_t s.f_lfi s.f_inch s.f_bc s.f_rri s.f_paused s.f_W s.f_qlen s.f_qpend s.f_enq s.f_active s.f_chs s.f_win s.f_s_bvh s.f_s_tag i_who i_ver i_parent i_prev i_post i_blobs) s i_who i_ver i_n i_lbn i_prev i_post

inductive Dc_commitBatchWithProof where
  | rev (code : Nat)
  | ok (l_bvh : Nat) (l_tag : Nat) (l_tot : Nat)

def dec_commitBatchWithProof (r_t : Nat) (r_lfi : Nat) (r_inch : Bool) (r_bc : Nat) (r_rri : Nat) (r_paused : Bool) (r_W : Nat) (r_D : Nat) (r_qlen : Nat) (r_qpend : Nat) (r_enq : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (r_s_bvh : List Nat) (r_s_tag : List Nat) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) (i_proof : Nat) : Dc_commitBatchWithProof :=
  bif !(Nat.beq r_rri 0) then Dc_commitBatchWithProof.rev 2 else
  bif !(!r_paused) then Dc_commitBatchWithProof.rev 3 else
  let l_lci0 := (d_lci r_lfi r_win)
  let l_rd := (Nat.blt ((d_w r_lfi r_win l_lci0).f_bdo + r_D) r_t)
  let l_ef := (d_enq_first r_qpend r_qlen r_enq r_t)
  let l_qd := (Nat.blt (l_ef + r_D) r_t)
  bif !(l_rd || ((!l_qd) || (Nat.blt 0 i_n))) then Dc_commitBatchWithProof.rev 5 else
  bif !(l_rd || l_qd) then Dc_commitBatchWithProof.rev 19 else
  let l_next := (i_parent + 1)
  let l_b0 := (hl_nthD i_blobs 0 0)
  let l_b1 := (hl_nthD i_blobs 1 0)
  let l_stored := (d_bvh_at r_lfi r_win r_s_bvh l_next)
  bif !((Nat.beq l_stored 0) || (Nat.beq l_b0 0)) then Dc_commitBatchWithProof.rev 20 else
  bif !((!(Nat.beq l_stored 0)) || ((!(Nat.beq i_ver 2)) || (Nat.blt 0 (tw_blobCount i_blobs)))) then Dc_commitBatchWithProof.rev 6 else
  bif !((!(Nat.beq l_stored 0)) || ((Nat.beq i_ver 2) || (Nat.beq l_b1 0))) then Dc_commitBatchWithProof.rev 7 else
  let l_bvh := (bif (!(Nat.beq l_stored 0)) then l_stored else (d_blob_hash i_ver i_blobs))
  let l_tag := (bif (!(Nat.beq l_stored 0)) then (d_tag_at r_lfi r_win r_s_tag l_next) else (bif (Nat.beq i_ver 2) then 2 else 1))
  bif !(Nat.ble i_ver 2) then Dc_commitBatchWithProof.rev 8 else
  bif !(!(Nat.beq i_prev 0)) then Dc_commitBatchWithProof.rev 9 else
  bif !(!(Nat.beq i_post 0)) then Dc_commitBatchWithProof.rev 10 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.blt l_lci l_next) then Dc_commitBatchWithProof.rev 11 else
  bif !(Nat.beq i_parent l_lci) then Dc_commitBatchWithProof.rev 12 else
  bif !(Nat.beq ((d_w r_lfi r_win i_parent).f_csr) i_prev) then Dc_commitBatchWithProof.rev 14 else
  let l_tot := (d_w r_lfi r_win i_parent).f_tot
  let l_cstart := (hl_nthD r_chs r_bc hz_Ch).f_s
  bif !((!r_inch) || (Nat.ble r_t (r_W + l_cstart))) then Dc_commitBatchWithProof.rev 16 else
  bif !(!(Nat.beq i_proof 0)) then Dc_commitBatchWithProof.rev 21 else
  Dc_commitBatchWithProof.ok l_bvh l_tag l_tot

def exe_commitBatchWithProof (d : Dc_commitBatchWithProof) (s : St) (i_ver : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) : St :=
  match d with
  | Dc_commitBatchWithProof.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_commitBatchWithProof.ok l_bvh l_tag l_tot => { s with f_win := (s.f_win ++ [({ f_ver := i_ver, f_tot := (l_tot + i_n), f_n := i_n, f_hb := l_bvh, f_prev := i_prev, f_post := i_post, f_lbn := i_lbn, f_csr := i_post, f_bvh := l_bvh, f_tag := l_tag, f_bdo := s.f_t, f_bdf := s.f_t, f_bdn := i_lbn, f_bds := 0 } : T_Entry)]), f_s_csr := (List.tail s.f_s_csr), f_s_bd := (List.tail s.f_s_bd), f_s_bvh := (List.tail s.f_s_bvh), f_s_tag := (List.tail s.f_s_tag), f_log := Obs.ok :: s.f_log }

def stp_commitBatchWithProof (s : St) (i_ver : Nat) (i_parent : Nat) (i_n : Nat) (i_lbn : Nat) (i_prev : Nat) (i_post : Nat) (i_blobs : List Nat) (i_proof : Nat) : St :=
  exe_commitBatchWithProof (dec_commitBatchWithProof s.f_t s.f_lfi s.f_inch s.f_bc s.f_rri s.f_paused s.f_W s.f_D s.f_qlen s.f_qpend s.f_enq s.f_chs s.f_win s.f_s_bvh s.f_s_tag i_ver i_parent i_n i_prev i_post i_blobs i_proof) s i_ver i_n i_lbn i_prev i_post

inductive Dc_revertBatch where
  | rev (code : Nat)
  | ok (l_lci : Nat) (l_p : Nat) (l_moved : List T_Entry)

def dec_revertBatch (r_lfi : Nat) (r_win : List T_Entry) (i_who : Nat) (i_idx : Nat) (i_count : Nat) : Dc_revertBatch :=
  bif !(Nat.beq i_who 1) then Dc_revertBatch.rev 23 else
  bif !(Nat.blt 0 i_count) then Dc_revertBatch.rev 24 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.ble i_idx l_lci) then Dc_revertBatch.rev 25 else
  bif !(Nat.blt l_lci (i_idx + i_count)) then Dc_revertBatch.rev 26 else
  bif !(Nat.blt r_lfi i_idx) then Dc_revertBatch.rev 27 else
  let l_p := (i_idx - r_lfi)
  let l_moved := (List.drop l_p r_win)
  Dc_revertBatch.ok l_lci l_p l_moved

def exe_revertBatch (d : Dc_revertBatch) (s : St) (i_idx : Nat) : St :=
  match d with
  | Dc_revertBatch.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_revertBatch.ok l_lci l_p l_moved => { s with f_inch := (s.f_inch && (!(tw_anyGo s.f_chs 0 i_idx l_lci))), f_rri := (bif ((Nat.blt 0 s.f_rri) && ((Nat.ble i_idx s.f_rri) && (Nat.ble s.f_rri l_lci))) then 0 else s.f_rri), f_chs := (tw_clearGo s.f_chs 0 i_idx l_lci), f_win := (List.take l_p s.f_win), f_s_csr := ((hs_csr l_moved) ++ s.f_s_csr), f_s_bd := ((hs_bd l_moved) ++ s.f_s_bd), f_s_bvh := ((hs_bvh l_moved) ++ s.f_s_bvh), f_s_tag := ((hs_tag l_moved) ++ s.f_s_tag), f_log := Obs.ok :: s.f_log }

def stp_revertBatch (s : St) (i_who : Nat) (i_idx : Nat) (i_count : Nat) : St :=
  exe_revertBatch (dec_revertBatch s.f_lfi s.f_win i_who i_idx i_count) s i_idx

inductive Dc_challengeState where
  | rev (code : Nat)
  | ok

def dec_challengeState (r_t : Nat) (r_lfi : Nat) (r_inch : Bool) (r_rri : Nat) (r_paused : Bool) (r_chals : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (i_who : Nat) (i_idx : Nat) (i_value : Nat) : Dc_challengeState :=
  bif !(hl_mem i_who r_chals) then Dc_challengeState.rev 28 else
  bif !(Nat.beq r_rri 0) then Dc_challengeState.rev 2 else
  bif !(!r_paused) then Dc_challengeState.rev 3 else
  bif !(!r_inch) then Dc_challengeState.rev 29 else
  bif !(Nat.blt r_lfi i_idx) then Dc_challengeState.rev 30 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.ble i_idx l_lci) then Dc_challengeState.rev 25 else
  bif !(Nat.blt 0 ((d_w r_lfi r_win i_idx).f_bdo)) then Dc_challengeState.rev 31 else
  bif !(Nat.beq ((hl_nthD r_chs i_idx hz_Ch).f_c) 0) then Dc_challengeState.rev 32 else
  bif !(Nat.blt r_t ((d_w r_lfi r_win i_idx).f_bdf)) then Dc_challengeState.rev 33 else
  bif !(Nat.ble 1 i_value) then Dc_challengeState.rev 34 else
  Dc_challengeState.ok

def exe_challengeState (d : Dc_challengeState) (s : St) (i_who : Nat) (i_idx : Nat) (i_value : Nat) : St :=
  match d with
  | Dc_challengeState.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_challengeState.ok => { s with f_inch := true, f_bc := i_idx, f_chs := (hl_setD s.f_chs i_idx ({ f_c := i_who, f_d := i_value, f_s := s.f_t, f_w := false, f_f := false } : T_Ch) hz_Ch), f_win := (tw_bumpGo s.f_win 0 (i_idx - s.f_lfi) s.f_W), f_log := Obs.ok :: s.f_log }

def stp_challengeState (s : St) (i_who : Nat) (i_idx : Nat) (i_value : Nat) : St :=
  exe_challengeState (dec_challengeState s.f_t s.f_lfi s.f_inch s.f_rri s.f_paused s.f_chals s.f_chs s.f_win i_who i_idx i_value) s i_who i_idx i_value

inductive Dc_proveState where
  | rev (code : Nat)
  | ok (l_ch : T_Ch) (l_timeout : Bool)

def dec_proveState (r_t : Nat) (r_lfi : Nat) (r_rri : Nat) (r_paused : Bool) (r_W : Nat) (r_active : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (i_who : Nat) (i_idx : Nat) (i_proof : Nat) : Dc_proveState :=
  bif !(Nat.beq r_rri 0) then Dc_proveState.rev 2 else
  bif !(!r_paused) then Dc_proveState.rev 3 else
  bif !(hl_mem i_who r_active) then Dc_proveState.rev 1 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.ble i_idx l_lci) then Dc_proveState.rev 25 else
  bif !(d_open_ch r_chs i_idx) then Dc_proveState.rev 35 else
  let l_ch := (hl_nthD r_chs i_idx hz_Ch)
  let l_timeout := (Nat.ble (l_ch.f_s + r_W) r_t)
  bif !(l_timeout || (!(Nat.beq i_proof 0))) then Dc_proveState.rev 21 else
  Dc_proveState.ok l_ch l_timeout

def exe_proveState (d : Dc_proveState) (s : St) (i_idx : Nat) : St :=
  match d with
  | Dc_proveState.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_proveState.ok l_ch l_timeout => { s with f_inch := false, f_rri := (bif l_timeout then i_idx else s.f_rri), f_active := (bif l_timeout then (hl_remove ((d_w s.f_lfi s.f_win i_idx).f_bds) s.f_active) else s.f_active), f_chs := (hl_setD s.f_chs i_idx ({ l_ch with f_f := true, f_w := l_timeout } : T_Ch) hz_Ch), f_log := Obs.ok :: s.f_log }

def stp_proveState (s : St) (i_who : Nat) (i_idx : Nat) (i_proof : Nat) : St :=
  exe_proveState (dec_proveState s.f_t s.f_lfi s.f_rri s.f_paused s.f_W s.f_active s.f_chs s.f_win i_who i_idx i_proof) s i_idx

inductive Dc_finalizeBatch where
  | rev (code : Nat)
  | ok (l_bn : Nat) (l_btot : Nat)

def dec_finalizeBatch (r_t : Nat) (r_lfi : Nat) (r_rri : Nat) (r_paused : Bool) (r_fsr : List Nat) (r_chs : List T_Ch) (r_win : List T_Entry) (i_idx : Nat) : Dc_finalizeBatch :=
  bif !(Nat.beq r_rri 0) then Dc_finalizeBatch.rev 2 else
  bif !(!r_paused) then Dc_finalizeBatch.rev 3 else
  let l_lci := (d_lci r_lfi r_win)
  bif !(Nat.ble i_idx l_lci) then Dc_finalizeBatch.rev 25 else
  bif !((Nat.ble r_lfi i_idx) && (Nat.blt 0 ((d_w r_lfi r_win i_idx).f_bdo))) then Dc_finalizeBatch.rev 31 else
  bif !(!(d_open_ch r_chs i_idx)) then Dc_finalizeBatch.rev 35 else
  bif !(!((hl_nthD r_chs i_idx hz_Ch).f_w)) then Dc_finalizeBatch.rev 36 else
  bif !(!(Nat.blt r_t ((d_w r_lfi r_win i_idx).f_bdf))) then Dc_finalizeBatch.rev 37 else
  bif !(Nat.ble 1 i_idx) then Dc_finalizeBatch.rev 41 else
  bif !(Nat.beq (hl_nthD r_fsr (i_idx - 1) 0) ((d_w r_lfi r_win i_idx).f_prev)) then Dc_finalizeBatch.rev 14 else
  bif !(Nat.beq (hl_nthD r_fsr i_idx 0) 0) then Dc_finalizeBatch.rev 38 else
  bif !(Nat.beq (r_lfi + 1) i_idx) then Dc_finalizeBatch.rev 12 else
  let l_bn := (d_w r_lfi r_win i_idx).f_n
  let l_btot := (d_w r_lfi r_win i_idx).f_tot
  Dc_finalizeBatch.ok l_bn l_btot

def exe_finalizeBatch (d : Dc_finalizeBatch) (s : St) (i_idx : Nat) : St :=
  match d with
  | Dc_finalizeBatch.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_finalizeBatch.ok l_bn l_btot => { s with f_lfi := i_idx, f_qpend := (bif (Nat.beq l_bn 0) then s.f_qpend else l_btot), f_fsr := (hl_setD s.f_fsr i_idx ((d_w s.f_lfi s.f_win i_idx).f_post) 0), f_chs := (hl_setD s.f_chs (i_idx - 1) hz_Ch hz_Ch), f_win := (List.drop 1 s.f_win), f_log := Obs.ok :: s.f_log }

def stp_finalizeBatch (s : St) (i_idx : Nat) : St :=
  exe_finalizeBatch (dec_finalizeBatch s.f_t s.f_lfi s.f_rri s.f_paused s.f_fsr s.f_chs s.f_win i_idx) s i_idx

inductive Dc_setPause where
  | rev (code : Nat)
  | ok

def dec_setPause (i_who : Nat) : Dc_setPause :=
  bif !(Nat.beq i_who 1) then Dc_setPause.rev 23 else
  Dc_setPause.ok

def exe_setPause (d : Dc_setPause) (s : St) (i_status : Bool) : St :=
  match d with
  | Dc_setPause.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_setPause.ok => { s with f_inch := (s.f_inch && (!i_status)), f_paused := i_status, f_chs := (bif (i_status && s.f_inch) then (hl_setD s.f_chs s.f_bc hz_Ch hz_Ch) else s.f_chs), f_log := Obs.ok :: s.f_log }

def stp_setPause (s : St) (i_who : Nat) (i_status : Bool) : St :=
  exe_setPause (dec_setPause i_who) s i_status

inductive Dc_sendMessage where
  | rev (code : Nat)
  | ok

def dec_sendMessage : Dc_sendMessage :=
  Dc_sendMessage.ok

def exe_sendMessage (d : Dc_sendMessage) (s : St) : St :=
  match d with
  | Dc_sendMessage.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_sendMessage.ok => { s with f_qlen := (s.f_qlen + 1), f_enq := (s.f_enq ++ [s.f_t]), f_log := Obs.ok :: s.f_log }

def stp_sendMessage (s : St) : St :=
  exe_sendMessage (dec_sendMessage) s

inductive Dc_wait where
  | rev (code : Nat)
  | ok

def dec_wait : Dc_wait :=
  Dc_wait.ok

def exe_wait (d : Dc_wait) (s : St) (i_dt : Nat) : St :=
  match d with
  | Dc_wait.rev c => { s with f_log := Obs.rev c :: s.f_log }
  | Dc_wait.ok => { s with f_t := (s.f_t + i_dt), f_log := Obs.ok :: s.f_log }

def stp_wait (s : St) (i_dt : Nat) : St :=
  exe_wait (dec_wait) s i_dt

def step (a : Act) (s : St) : St :=
  match a with
  | Act.a_commitBatch i_who i_ver i_parent i_n i_lbn i_prev i_post i_blobs => stp_commitBatch s i_who i_ver i_parent i_n i_lbn i_prev i_post i_blobs
  | Act.a_commitState i_who i_ver i_parent i_n i_lbn i_prev i_post i_blobs => stp_commitState s i_who i_ver i_parent i_n i_lbn i_prev i_post i_blobs
  | Act.a_commitBatchWithProof _ i_ver i_parent i_n i_lbn i_prev i_post i_blobs i_proof => stp_commitBatchWithProof s i_ver i_parent i_n i_lbn i_prev i_post i_blobs i_proof
  | Act.a_revertBatch i_who i_idx i_count => stp_revertBatch s i_who i_idx i_count
  | Act.a_challengeState i_who i_idx i_value => stp_challengeState s i_who i_idx i_value
  | Act.a_proveState i_who i_idx i_proof => stp_proveState s i_who i_idx i_proof
  | Act.a_finalizeBatch _ i_idx => stp_finalizeBatch s i_idx
  | Act.a_setPause i_who i_status => stp_setPause s i_who i_status
  | Act.a_sendMessage _ => stp_sendMessage s
  | Act.a_wait i_dt => stp_wait s i_dt

def run : List Act → St → St
  | [], s => s
  | a :: r, s => run r (step a s)

def s0 : St := { f_t := 10, f_lfi := 0, f_inch := false, f_bc := 0, f_rri := 0, f_paused := false, f_W := 10, f_F := 40, f_D := 20, f_qlen := 0, f_qpend := 0, f_enq := ([] : List Nat), f_active := [2, 3], f_chals := [4], f_fsr := [100], f_chs := ([] : List T_Ch), f_win := [({ f_ver := 0, f_tot := 0, f_n := 0, f_hb := 1, f_prev := 0, f_post := 100, f_lbn := 0, f_csr := 100, f_bvh := 1, f_tag := 1, f_bdo := 10, f_bdf := 10, f_bdn := 0, f_bds := 0 } : T_Entry)], f_s_csr := ([] : List Nat), f_s_bd := ([] : List T_BD), f_s_bvh := ([] : List Nat), f_s_tag := ([] : List Nat), f_log := ([] : List Obs) }

def obs (tr : List Act) (s : St) : List Obs :=
  (run tr { s with f_log := [] }).f_log

def fn_runs_ok (tr : List Act) (s : St) : Bool := hl_allOk (obs tr s)

def fn_last_ok (s : St) : Bool := hl_okHead s.f_log

def fn_no_code : List Obs → Nat → Bool
  | [], _ => true
  | Obs.ok :: t, k => fn_no_code t k
  | Obs.rev c :: t, k => !(Nat.beq c k) && fn_no_code t k

def fn_perm : Act → Bool
  | Act.a_commitBatch _ _ _ _ _ _ _ _ => false
  | Act.a_commitState _ _ _ _ _ _ _ _ => false
  | Act.a_commitBatchWithProof _ _ _ _ _ _ _ _ _ => true
  | Act.a_revertBatch _ _ _ => false
  | Act.a_challengeState _ _ _ => false
  | Act.a_proveState _ _ _ => false
  | Act.a_finalizeBatch _ _ => true
  | Act.a_setPause _ _ => false
  | Act.a_sendMessage _ => true
  | Act.a_wait _ => true

def fn_cost : List Act → Nat
  | [] => 0
  | Act.a_commitBatch _ _ _ _ _ _ _ _ :: r => 0 + fn_cost r
  | Act.a_commitState _ _ _ _ _ _ _ _ :: r => 0 + fn_cost r
  | Act.a_commitBatchWithProof _ _ _ _ _ _ _ _ _ :: r => 1000 + fn_cost r
  | Act.a_revertBatch _ _ _ :: r => 0 + fn_cost r
  | Act.a_challengeState _ _ _ :: r => 0 + fn_cost r
  | Act.a_proveState _ _ _ :: r => 0 + fn_cost r
  | Act.a_finalizeBatch _ _ :: r => 0 + fn_cost r
  | Act.a_setPause _ _ :: r => 0 + fn_cost r
  | Act.a_sendMessage _ :: r => 1 + fn_cost r
  | Act.a_wait _ :: r => 0 + fn_cost r

def fn_elapsed : List Act → Nat
  | [] => 0
  | Act.a_commitBatch _ _ _ _ _ _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_commitState _ _ _ _ _ _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_commitBatchWithProof _ _ _ _ _ _ _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_revertBatch _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_challengeState _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_proveState _ _ _ :: r => 0 + fn_elapsed r
  | Act.a_finalizeBatch _ _ :: r => 0 + fn_elapsed r
  | Act.a_setPause _ _ :: r => 0 + fn_elapsed r
  | Act.a_sendMessage _ :: r => 0 + fn_elapsed r
  | Act.a_wait i_dt :: r => i_dt + fn_elapsed r

def fn_is_commitBatch : Act → Bool
  | Act.a_commitBatch _ _ _ _ _ _ _ _ => true
  | _ => false

def fn_is_commitState : Act → Bool
  | Act.a_commitState _ _ _ _ _ _ _ _ => true
  | _ => false

def fn_is_commitBatchWithProof : Act → Bool
  | Act.a_commitBatchWithProof _ _ _ _ _ _ _ _ _ => true
  | _ => false

def fn_is_revertBatch : Act → Bool
  | Act.a_revertBatch _ _ _ => true
  | _ => false

def fn_is_challengeState : Act → Bool
  | Act.a_challengeState _ _ _ => true
  | _ => false

def fn_is_proveState : Act → Bool
  | Act.a_proveState _ _ _ => true
  | _ => false

def fn_is_finalizeBatch : Act → Bool
  | Act.a_finalizeBatch _ _ => true
  | _ => false

def fn_is_setPause : Act → Bool
  | Act.a_setPause _ _ => true
  | _ => false

def fn_is_sendMessage : Act → Bool
  | Act.a_sendMessage _ => true
  | _ => false

def fn_is_wait : Act → Bool
  | Act.a_wait _ => true
  | _ => false

def fn_blobs_of : Act → List Nat
  | Act.a_commitBatch _ _ _ _ _ _ _ i_blobs => i_blobs
  | Act.a_commitState _ _ _ _ _ _ _ i_blobs => i_blobs
  | Act.a_commitBatchWithProof _ _ _ _ _ _ _ i_blobs _ => i_blobs
  | Act.a_revertBatch _ _ _ => []
  | Act.a_challengeState _ _ _ => []
  | Act.a_proveState _ _ _ => []
  | Act.a_finalizeBatch _ _ => []
  | Act.a_setPause _ _ => []
  | Act.a_sendMessage _ => []
  | Act.a_wait _ => []

def ob_csr_last (s : St) : Nat :=
  (hl_lastD s.f_win hz_Entry).f_csr

def ob_kappa (s : St) : Bool :=
  (s.f_inch && (Nat.blt (s.f_W + (hl_nthD s.f_chs s.f_bc hz_Ch).f_s) s.f_t))

def ob_lci_of (s : St) : Nat :=
  (d_lci s.f_lfi s.f_win)

def ob_new_hdr (s : St) : List Nat :=
  (tw_hdrOf (hl_lastD s.f_win hz_Entry))

def ob_tags_ok (s : St) : Bool :=
  (tw_tagsExact s.f_win)

def mig_eta2 (s : St) (i_root : Nat) : St :=
  { s with f_win := (bif (Nat.beq ((hl_lastD s.f_win hz_Entry).f_csr) 0) then (tw_setLastCsr s.f_win i_root) else s.f_win) }

def mig_legacy (s : St) : St :=
  { s with f_win := (tw_zeroCsr s.f_win), f_s_csr := (hl_zeros s.f_s_csr) }

inductive Reach : St → Prop where
  | r0 : Reach s0
  | rstep (a : Act) (s : St) : Reach s → Reach (step a s)

end Model
