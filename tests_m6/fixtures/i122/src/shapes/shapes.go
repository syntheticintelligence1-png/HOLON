// Package shapes is I122's planted fixture (tests_m6/test_i122_goloop_loop_shapes.py), written from the Go
// specification's rules, never from corpus code. Each op has one loop of a shape outside goloop's I67 class; the laws
// PAR derives over it (totality, domain coherence) are known by construction:
//
// Class S1 (a range over a carrier slice; the trip count is the slice's length, read from the carrier):
//   - Frame.Scan ranges over the field Data ([]uint8): it panics at the first element 0xff, returns an error at the
//     first element 0 (from index 1 on), and returns nil after len(Data) iterations; its totality is false (witness
//     Data = [255]).
//   - Frame.Tail ranges over Data and never panics (its totality is true: never REFUTED).
//   - Signed ranges over a []int8 parameter: it panics at the first element below -100 (signed order: the cell
//     encoding must keep it; witness [-101]).
//   - Frame.Wide ranges over Words ([]uint64): a 64-bit element is outside S1 (Unsupported).
//
// Class S2 (a counted loop with a constant step other than 1, over a fixed-length byte array):
//   - Back counts down from 7 by 2 (7, 5, 3, 1), panicking where b[i] == 0x80 at i < 4.
//   - WrapScan steps a uint8 index by 4 from 250 until it equals 6: 250, 254, then 2 (Go wraps 258 to 2), then 6
//     stops. It panics where b[i] == 0x7f and i < 8, which only the wrapped iteration (i = 2) reaches: its totality
//     is true under unbounded integers (250, 254, 258, ... is never below 8) and false under Go's semantics (the
//     planted false law; witness b[2] = 0x7f).
//   - Down never panics (it returns an error where a byte is 0; its totality is true: never REFUTED).
//   - Pair reads b[i] and b[i+1] per iteration (two cells): outside S2 (Unsupported).
package shapes

import "errors"

var errZero = errors.New("zero")

// Frame is supplied by the environment.
type Frame struct {
	Data  []uint8
	Words []uint64
}

func (f *Frame) Scan() error {
	for i, x := range f.Data {
		if x == 0xff {
			panic("scan")
		}
		if x == 0 && i >= 1 {
			return errZero
		}
	}
	return nil
}

func (f *Frame) Tail() error {
	for _, x := range f.Data {
		if x == 0 {
			return errZero
		}
	}
	return nil
}

func (f *Frame) Wide() error {
	for _, w := range f.Words {
		if w == 1 {
			panic("wide")
		}
	}
	return nil
}

// Sig is supplied by the environment.
type Sig []int8

func Signed(s Sig) error {
	for _, v := range s {
		if v < -100 {
			panic("signed")
		}
	}
	return nil
}

// Blob is supplied by the environment.
type Blob [256]byte

func Back(b *Blob) error {
	for i := 7; i >= 0; i -= 2 {
		if b[i] == 0x80 && i < 4 {
			panic("back")
		}
	}
	return nil
}

func WrapScan(b *Blob) error {
	for i := uint8(250); i != 6; i += 4 {
		if b[i] == 0x7f && i < 8 {
			panic("wrapped")
		}
	}
	return nil
}

func Down(b *Blob) error {
	for i := 30; i > 0; i -= 3 {
		if b[i] == 0 {
			return errZero
		}
	}
	return nil
}

func Pair(b *Blob) error {
	for i := 0; i < 8; i += 2 {
		if b[i] == 1 && b[i+1] == 2 {
			panic("pair")
		}
	}
	return nil
}
