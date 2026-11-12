// Package bank is I111's planted fixture (tests_m6/test_i111_types_totality.py). Ledger is well typed. Wiper writes
// a whole map (Reset), which the typed model refuses (I109's A4: no finite store states "every key reset"), so under
// the types fallback it is opaque. WiperKept is Wiper without Reset: the constrained control.
package bank

import "errors"

var (
	errNotOwner = errors.New("not owner")
	errCap      = errors.New("cap")
	errPaused   = errors.New("paused")
)

// Ledger counts up to a cap, owner-guarded.
type Ledger struct {
	Owner  uint64
	Paused bool
	Count  uint64
}

// SetPaused is guarded by the owner.
func (l *Ledger) SetPaused(caller uint64, p bool) error {
	if caller != l.Owner {
		return errNotOwner
	}
	l.Paused = p
	return nil
}

// Bump adds one while below the cap and not paused.
func (l *Ledger) Bump() error {
	if l.Paused {
		return errPaused
	}
	if l.Count >= 10 {
		return errCap
	}
	l.Count++
	return nil
}

// Wiper is Ledger's shape plus a map it can reset whole.
type Wiper struct {
	Owner  uint64
	Paused bool
	Count  uint64
	Seen   map[uint64]uint64
}

// SetPaused is guarded by the owner.
func (w *Wiper) SetPaused(caller uint64, p bool) error {
	if caller != w.Owner {
		return errNotOwner
	}
	w.Paused = p
	return nil
}

// Bump adds one while below the cap and not paused.
func (w *Wiper) Bump() error {
	if w.Paused {
		return errPaused
	}
	if w.Count >= 10 {
		return errCap
	}
	w.Count++
	return nil
}

// Reset writes the whole map: ill-sorted in the typed model.
func (w *Wiper) Reset(caller uint64) error {
	if caller != w.Owner {
		return errNotOwner
	}
	w.Seen = map[uint64]uint64{}
	w.Count = 0
	return nil
}

// WiperKept is Wiper without Reset (the constrained control).
type WiperKept struct {
	Owner  uint64
	Paused bool
	Count  uint64
	Seen   map[uint64]uint64
}

// SetPaused is guarded by the owner.
func (w *WiperKept) SetPaused(caller uint64, p bool) error {
	if caller != w.Owner {
		return errNotOwner
	}
	w.Paused = p
	return nil
}

// Bump adds one while below the cap and not paused.
func (w *WiperKept) Bump() error {
	if w.Paused {
		return errPaused
	}
	if w.Count >= 10 {
		return errCap
	}
	w.Count++
	return nil
}
