// Package ledger is a planted Go fixture for I108 (tests_m6/test_i108_pipeline_totality.py): every expectation of the
// tests is known from this source by construction.
package ledger

import "errors"

var (
	errNeg     = errors.New("negative")
	errLimit   = errors.New("over limit")
	errOwner   = errors.New("not owner")
	errUnknown = errors.New("unknown account")
)

// Acct is a signed-integer machine: Go's int64 comparisons and arithmetic (the IR's s<, s>, sext).
type Acct struct {
	Owner uint64
	Bal   int64
	Limit int64
}

// Add credits n (n >= 0) while the balance stays at or below the limit.
func (a *Acct) Add(n int64) error {
	if n < 0 {
		return errNeg
	}
	if a.Bal+n > a.Limit {
		return errLimit
	}
	a.Bal += n
	return nil
}

// SetLimit is guarded by the owner; a limit below zero is refused.
func (a *Acct) SetLimit(caller uint64, l int64) error {
	if caller != a.Owner {
		return errOwner
	}
	if l < 0 {
		return errNeg
	}
	a.Limit = l
	return nil
}

// Book is a map machine: Bal is nil in Book's zero value, so a write into it panics until it is made.
type Book struct {
	Owner uint64
	Bal   map[uint64]uint64
}

// Credit writes into the map field Bal.
func (b *Book) Credit(who, n uint64) error {
	if n == 0 {
		return errUnknown
	}
	b.Bal[who] += n
	return nil
}

// SetOwner writes a scalar only.
func (b *Book) SetOwner(caller, o uint64) error {
	if caller != b.Owner {
		return errOwner
	}
	b.Owner = o
	return nil
}
