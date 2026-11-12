// Package reg is a planted Go fixture for I109 (tests_m6/test_i109_pipeline_totality_3.py): every expectation of the
// tests is known from this source by construction.
package reg

import (
	"errors"

	"example.com/holon/i109/dep"
)

var (
	errOwner = errors.New("not owner")
	errZero  = errors.New("zero")
)

// Counter calls an opaque method (receiver counted as an argument) and takes len of a non-byte slice (a word).
type Counter struct {
	Count uint64
}

// Grow refuses empty coins and counts them.
func (c *Counter) Grow(cs dep.Coins) error {
	if cs.IsZero() {
		return errZero
	}
	c.Count += uint64(len(cs))
	return nil
}

// Named writes a whole string field.
type Named struct {
	Owner uint64
	Name  string
	Hits  uint64
}

// Rename is guarded by the owner and writes the whole string.
func (n *Named) Rename(caller uint64, s string) error {
	if caller != n.Owner {
		return errOwner
	}
	n.Name = s
	return nil
}

// Hit writes a scalar only.
func (n *Named) Hit() error {
	n.Hits++
	return nil
}

// Names is a string-keyed map machine (SP_b), made by its constructor.
type Names struct {
	Owner uint64
	Of    map[string]uint64
}

// NewNames is Names' constructor: Of is made, so it is never nil.
func NewNames(owner uint64) *Names {
	return &Names{Owner: owner, Of: make(map[string]uint64)}
}

// Put writes one string key.
func (n *Names) Put(caller uint64, k string, v uint64) error {
	if caller != n.Owner {
		return errOwner
	}
	n.Of[k] = v
	return nil
}

// Made is a uint-keyed map machine whose constructor makes the map (Q60: not nil in R0).
type Made struct {
	Owner uint64
	Bal   map[uint64]uint64
}

// NewMade makes Bal.
func NewMade(owner uint64) *Made {
	m := &Made{Owner: owner}
	m.Bal = make(map[uint64]uint64)
	return m
}

// Credit writes into Bal.
func (m *Made) Credit(who, n uint64) error {
	if n == 0 {
		return errZero
	}
	m.Bal[who] += n
	return nil
}

// Loose has a constructor that leaves its map nil on one path.
type Loose struct {
	Bal map[uint64]uint64
}

// NewLoose makes Bal only when asked.
func NewLoose(made bool) *Loose {
	l := &Loose{}
	if made {
		l.Bal = make(map[uint64]uint64)
	}
	return l
}

// Credit writes into Bal.
func (l *Loose) Credit(who, n uint64) error {
	l.Bal[who] += n
	return nil
}

// Bare has no constructor: R0 is the zero value, and Bal is nil.
type Bare struct {
	Bal map[uint64]uint64
}

// Credit writes into Bal.
func (b *Bare) Credit(who, n uint64) error {
	b.Bal[who] += n
	return nil
}
