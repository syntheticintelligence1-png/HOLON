// Package latch is I124's planted fixture (tests_m6/test_i124_post_derive_crashes.py), written from the Go
// specification, never from corpus code. Each type is one Go-op component (its methods share the receiver type):
//   - Latch: no method reads a field, so the component's carrier has no leaves and its one value is the empty cell
//     sequence (F-M6-06). Trip always panics, so its totality law is false under Go's semantics, witnessed by that
//     one value; Rest always returns nil, so its totality law holds and must never be REFUTED.
//   - Valve: a guard over one bool field (HUMAN_ANSWERS Q91 (1)); Shut returns an error while Open holds and never
//     panics. It is the second component F-M6-08's planted run leaves unreached.
//   - Stale: Poke loads its field after storing it, which the Go-op model does not state exactly (the frontend's
//     "stale"), so the component is outside the model class: its laws stay UNKNOWN with that reason (the input just
//     outside F-M6-06's handled shape).
package latch

import "errors"

var errOpen = errors.New("open")

// Latch carries a field that no op reads.
type Latch struct {
	N int
}

func (l *Latch) Trip() error {
	panic("tripped")
}

func (l *Latch) Rest() error {
	return nil
}

// Valve is shut only while it is not open.
type Valve struct {
	Open bool
}

func (v *Valve) Shut() error {
	if v.Open {
		return errOpen
	}
	return nil
}

// Stale reads back what it wrote.
type Stale struct {
	N int
}

func (s *Stale) Poke() error {
	s.N = 1
	if s.N == 2 {
		panic("unreachable under Go's semantics")
	}
	return nil
}
