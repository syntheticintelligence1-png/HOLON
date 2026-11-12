// Package vault is a planted Go machine for I105's demonstration (not a prediction): Bank's shape with integer keys,
// which the typed model compiles (tests_m6/test_i105_go_machines.py::TestDemo).
package vault

import "errors"

var (
	errNotOwner = errors.New("not owner")
	errPaused   = errors.New("paused")
	errLow      = errors.New("low")
)

// Vault holds balances keyed by account number.
type Vault struct {
	Owner  uint64
	Paused bool
	Total  uint64
	Bal    map[uint64]uint64
}

// SetPaused is guarded by the owner.
func (v *Vault) SetPaused(caller uint64, p bool) error {
	if caller != v.Owner {
		return errNotOwner
	}
	v.Paused = p
	return nil
}

// Deposit credits an account while not paused.
func (v *Vault) Deposit(who, n uint64) error {
	if v.Paused {
		return errPaused
	}
	v.Bal[who] += n
	v.Total += n
	return nil
}

// Withdraw debits an account while not paused, if it holds enough.
func (v *Vault) Withdraw(who, n uint64) error {
	if v.Paused {
		return errPaused
	}
	if v.Bal[who] < n {
		return errLow
	}
	v.Bal[who] -= n
	v.Total -= n
	return nil
}
