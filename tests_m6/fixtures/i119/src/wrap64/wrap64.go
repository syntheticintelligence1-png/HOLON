// Package wrap64 is I119's planted fixture (tests_m6/test_i119_go_reasoner_soundness.py). Each function hangs on one
// rule of the Go specification ("Integer overflow": for signed and unsigned integers, + - * and << are computed
// modulo 2^n, n the type's width; int is 64 bits on the pinned linux/amd64), never on corpus code:
//   - Inc64: a branch reachable only through 64-bit wraparound (x = MaxInt64 makes x+1 < x). A reasoner that reads
//     Go integers as unbounded calls x+1 < x impossible and prunes the panic path; Go's semantics keeps it.
//   - Idx: the claim "b[i] is in bounds" holds under unbounded integers (i >= 0 and i+1 <= len(b) imply i < len(b))
//     and is false under Go's wraparound (i = MaxInt makes i+1 = MinInt <= len(b), and b[i] panics). So its site
//     must not be "safe" (the frontend's own claim that the index never panics) under the default.
//   - Plus: a control with no wraparound in its branch, whose paths every reading agrees on.
package wrap64

func Inc64(b []byte, x int64) error {
	if x+1 < x {
		panic("wrapped")
	}
	return nil
}

func Idx(b []byte, i int) byte {
	if i >= 0 && i+1 <= len(b) {
		return b[i]
	}
	return 0
}

func Plus(b []byte) error {
	if len(b) < 2 {
		return nil
	}
	if b[0] == 7 {
		panic("seven")
	}
	return nil
}
