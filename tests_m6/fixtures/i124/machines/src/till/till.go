// Package till is I124's planted Go machine fixture for F-M6-07 (tests_m6/test_i124_post_derive_crashes.py), written
// from the Go specification. Two machines of the same well-typed shape, each a counter under an owner guard, so the
// DISCH runner can build and decide both documents; the test makes one document's typed model unloadable and checks
// that only that document's laws are touched.
package till

import "errors"

var (
	errOwner = errors.New("owner")
	errFull  = errors.New("full")
)

// Till counts sales up to a limit; only its keeper rekeys it.
type Till struct {
	Keeper uint64
	Sales  uint64
}

func (t *Till) Rekey(caller uint64, k uint64) error {
	if caller != t.Keeper {
		return errOwner
	}
	t.Keeper = k
	return nil
}

func (t *Till) Sell() error {
	if t.Sales >= 7 {
		return errFull
	}
	t.Sales++
	return nil
}

// Drawer counts openings up to a limit; only its holder hands it over.
type Drawer struct {
	Holder uint64
	Opens  uint64
}

func (d *Drawer) Hand(caller uint64, h uint64) error {
	if caller != d.Holder {
		return errOwner
	}
	d.Holder = h
	return nil
}

func (d *Drawer) Open() error {
	if d.Opens >= 3 {
		return errFull
	}
	d.Opens++
	return nil
}
