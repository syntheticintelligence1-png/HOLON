// Package extra plants two guard cases for I105 (tests_m6/test_i105_go_machines.py::TestGuardSoundness, added after
// the prereg): an error that may be nil, and a panic under a deferred recover.
package extra

import (
	"errors"
	"strconv"
)

// M is a one-field machine.
type M struct {
	N uint64
}

// Parse returns the error of an opaque call, which may be nil: the path fails only when it is not.
func (m *M) Parse(s string) error {
	_, err := strconv.ParseUint(s, 10, 64)
	return err
}

// Safe panics on zero, but a deferred recover turns the panic into an ordinary return.
func (m *M) Safe(n uint64) (err error) {
	defer func() {
		if recover() != nil {
			err = errors.New("recovered")
		}
	}()
	if n == 0 {
		panic("zero")
	}
	m.N = n
	return nil
}
