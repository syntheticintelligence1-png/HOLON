// Package scan is I115's planted fixture (tests_m6/test_i115_binding_wall.py). Blob is an interface carrier whose two
// ops each have one loop over the blob's bytes, the class holon.gen.goloop models, so the PAR laws over Blob's Go-op
// component are bound to its model and decided. Counter is a Go machine (its document gives DISCH a section); its
// method Bump takes a *Counter receiver and returns error, so the static go_ops role makes Counter a carrier too, but
// Bump has no loop body: the Go-op model leaves it out (Unsupported), so the totality law over it names a definition
// its model does not define. That law cannot be bound: the planted control of the binding check.
package scan

import "errors"

var errFF = errors.New("ff")

// Blob is supplied by the environment.
type Blob [8]byte

// ScanFF refuses a blob holding a 0xff byte.
func ScanFF(b Blob) error {
	for i := 0; i < 8; i++ {
		if b[i] == 0xff {
			return errFF
		}
	}
	return nil
}

// ScanZero panics on a zero byte.
func ScanZero(b Blob) error {
	for i := 0; i < 8; i++ {
		if b[i] == 0 {
			panic("zero")
		}
	}
	return nil
}

// Counter counts up to a cap.
type Counter struct {
	Count uint64
}

func (c *Counter) Bump() error {
	if c.Count >= 10 {
		return errFF
	}
	c.Count++
	return nil
}
