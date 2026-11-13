// Package seq is I126's planted fixture (tests_m6/test_i126_goloop_corpus_loops.py), written from the Go
// specification's rules, never from corpus code. Each op has a loop shape outside goloop's I67 class and outside
// I122's S1 and S2; the laws PAR derives over it (totality) are known by construction.
//
// Class SEQ (several counted loops in sequence, composed in program order; "Statements", "For statements with for
// clause", "Integer overflow"):
//   - Seq2 counts up over b[0..3] (it returns an error at a byte 0xff), then down over b[7], b[6], b[5], b[4] (it
//     panics at a byte 0x80). Its totality is false (witness b[7] = 0x80, the first loop's bytes at 0).
//   - WrapSeq counts over b[16], b[17] (an error at a byte 0), then steps a uint8 index by 4 from 252 until it equals
//     8: 252, then 0 (Go wraps 256 to 0), then 4, then 8 stops. It panics where b[k] == 0x7f and k < 16, which only
//     the wrapped iterations (k = 0, 4) reach: its totality is true under unbounded integers (252, 256, 260, ... is
//     never below 16) and false under Go's semantics (the planted false law; witness b[0] = 0x7f, b[16] = b[17] = 1).
//   - EmptyThen runs an empty counted loop (ten iterations, no read, no effect), then counts over b[32], b[34] (an
//     error at a byte 0). It never panics: its totality is true (never REFUTED).
//
// Just outside SEQ (Unsupported):
//   - Nested: a loop inside a loop.
//   - Carry: the second loop's condition reads a value the first loop computed.
//   - CallSeq: the first loop calls a function that stores into the array.
//   - Break: the first loop leaves early with break.
//   - MapRange: a range over a map (the frontend emits no loop body: no induction variable; iteration order is
//     unspecified).
//   - Spin: a for with no condition (no induction variable; termination is the body's).
package seq

import "errors"

var errHigh = errors.New("high")
var errZero = errors.New("zero")

// Blob is supplied by the environment.
type Blob [256]byte

func Seq2(b *Blob) error {
	for i := 0; i < 4; i++ {
		if b[i] == 0xff {
			return errHigh
		}
	}
	for j := 7; j >= 4; j-- {
		if b[j] == 0x80 {
			panic("seq2")
		}
	}
	return nil
}

func WrapSeq(b *Blob) error {
	for i := 16; i < 18; i++ {
		if b[i] == 0 {
			return errZero
		}
	}
	for k := uint8(252); k != 8; k += 4 {
		if b[k] == 0x7f && k < 16 {
			panic("wrapped")
		}
	}
	return nil
}

func EmptyThen(b *Blob) error {
	for i := 0; i < 10; i++ {
	}
	for j := 32; j < 36; j += 2 {
		if b[j] == 0 {
			return errZero
		}
	}
	return nil
}

func Nested(b *Blob) error {
	for i := 0; i < 2; i++ {
		for j := 0; j < 2; j++ {
			if b[2*i+j] == 9 {
				panic("nested")
			}
		}
	}
	return nil
}

func Carry(b *Blob) error {
	s := 0
	for i := 0; i < 4; i++ {
		s += int(b[i])
	}
	for j := 8; j < 10; j++ {
		if s > 100 && b[j] == 1 {
			panic("carry")
		}
	}
	return nil
}

func mark(b *Blob, i int) {
	b[i+8] = 1
}

func CallSeq(b *Blob) error {
	for i := 0; i < 2; i++ {
		mark(b, i)
	}
	for j := 8; j < 10; j++ {
		if b[j] == 1 {
			panic("call")
		}
	}
	return nil
}

func Break(b *Blob) error {
	for i := 0; i < 4; i++ {
		if b[i] == 0 {
			break
		}
	}
	for j := 8; j < 10; j++ {
		if b[j] == 0x80 {
			panic("break")
		}
	}
	return nil
}

func MapRange(b *Blob) error {
	m := map[int]byte{1: b[1], 2: b[2]}
	for k, v := range m {
		if k == 1 && v == 3 {
			panic("map")
		}
	}
	return nil
}

func Spin(b *Blob) error {
	for {
		if b[0] == 1 {
			return nil
		}
	}
}
