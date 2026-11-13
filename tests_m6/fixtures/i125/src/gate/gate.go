// Package gate is I125's planted fixture (tests_m6/test_i125_derive_goops_consistency.py), written from the Go
// specification alone. Blob is an interface carrier with three ops; what holon.gen.goloop does with each is known by
// construction:
//   - Low reads one byte at a constant index with no loop and a signed conversion (int8(b[0]) < -100), so the Go-op
//     model's straight-line class (I117) defines it: the supported op;
//   - Quot divides by a non-constant byte. Integer division by zero panics at run time (the Go specification,
//     "Integer operators"), and the frontend's paths do not record that panic, so the straight-line class refuses it:
//     the straight-line refusal;
//   - Twice runs two counted loops in sequence. goloop's loop classes (I67, and I122's S1 and S2) each take one loop
//     body, so it is refused: the loop refusal;
//   - Counter is a Go machine, there only so that the composed route has a machine document for DISCH (a route with
//     none refuses at DISCH, before derive). Its Bump guards over the field Count, inside the straight-line class.
// No op of this package is copied or adapted from any corpus entry.
package gate

import "errors"

var errLow = errors.New("low")

// Blob is supplied by the environment.
type Blob [8]byte

func Low(b Blob) error {
	if int8(b[0]) < -100 {
		return errLow
	}
	return nil
}

func Quot(b Blob) error {
	if b[7]/b[1] == 3 {
		return errLow
	}
	return nil
}

func Twice(b Blob) error {
	for i := 0; i < 4; i++ {
		if b[i] == 0 {
			return errLow
		}
	}
	for j := 4; j < 8; j++ {
		if b[j] == 0 {
			return errLow
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
		return errLow
	}
	c.Count++
	return nil
}
