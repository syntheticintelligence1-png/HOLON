// Package bank is I112's planted fixture (tests_m6/test_i112_run_wall.py). Ledger is well typed. Gated is Ledger
// plus a guard in Bump that orders two strings: the Go frontend states a string's order as an unknown term (only + and
// ==/!= of strings have a meaning), so the guard reads a value that is neither storage, time nor a table, and the
// DISCH section refuses its blocked condition (holon.disch.section: a state condition reads more of the context than
// storage and time).
package bank

import "errors"

var (
	errNotOwner = errors.New("not owner")
	errCap      = errors.New("cap")
	errDenied   = errors.New("denied")
)

// Ledger counts up to a cap, owner-guarded.
type Ledger struct {
	Owner uint64
	Count uint64
}

func (l *Ledger) SetOwner(caller uint64, o uint64) error {
	if caller != l.Owner {
		return errNotOwner
	}
	l.Owner = o
	return nil
}

func (l *Ledger) Bump() error {
	if l.Count >= 10 {
		return errCap
	}
	l.Count++
	return nil
}

// Gated is Ledger with a string-ordered guard on Bump.
type Gated struct {
	Owner uint64
	Count uint64
}

func (g *Gated) SetOwner(caller uint64, o uint64) error {
	if caller != g.Owner {
		return errNotOwner
	}
	g.Owner = o
	return nil
}

func (g *Gated) Bump(tag string) error {
	if tag < "m" {
		return errDenied
	}
	if g.Count >= 10 {
		return errCap
	}
	g.Count++
	return nil
}
