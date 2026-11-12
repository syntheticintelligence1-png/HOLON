// Package machines holds planted struct-field state machines for I105 (tests_m6/test_i105_go_machines.py).
// Every expectation of the test is known by construction from this source.
package machines

import "errors"

// ErrPaused is returned while the bank is paused.
var ErrPaused = errors.New("paused")

// Bank is a struct-field machine: its fields are the state, its exported methods the actions.
type Bank struct {
	Owner  string
	Paused bool
	Count  uint64
	Bal    map[string]uint64
}

// SetPaused: guarded by an early error return; writes Paused.
func (b *Bank) SetPaused(caller string, p bool) error {
	if caller != b.Owner {
		return errors.New("not owner")
	}
	b.Paused = p
	return nil
}

// Deposit: writes Bal[who] and Count (uint64 arithmetic wraps).
func (b *Bank) Deposit(who string, n uint64) error {
	if b.Paused {
		return ErrPaused
	}
	b.Bal[who] = b.Bal[who] + n
	b.Count = b.Count + 1
	return nil
}

// Withdraw: two guards, then writes Bal[who].
func (b *Bank) Withdraw(who string, n uint64) error {
	if b.Paused {
		return ErrPaused
	}
	if b.Bal[who] < n {
		return errors.New("low")
	}
	b.Bal[who] -= n
	return nil
}

// Total: a value receiver that only reads.
func (b Bank) Total() uint64 {
	return b.Count
}

// Credit: a value receiver writes through its map field, which the copy shares with the original.
func (b Bank) Credit(who string, n uint64) {
	b.Bal[who] += n
}

// Lose: a value receiver's field assignment writes the copy only: no state write.
func (b Bank) Lose() {
	b.Count = 5
	_ = b.Count
}

// Tick writes Count through an unexported helper (not an action itself).
func (b *Bank) Tick() {
	b.bump()
}

func (b *Bank) bump() {
	b.Count++
}

// Halt panics while paused (a panic path is a guard).
func (b *Bank) Halt() {
	if b.Paused {
		panic("halted")
	}
	b.Paused = true
}
