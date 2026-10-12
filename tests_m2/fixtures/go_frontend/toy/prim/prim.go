// Package prim is outside the extracted documents: the toy config declares ToWord's semantics
// (a "to_array" primitive of width 4), the way spec/M2/lib/go_frontend.json declares dependency primitives.
package prim

// ToWord copies b right-aligned into a 4-byte array.
func ToWord(b []byte) (w [4]byte) {
	if len(b) > len(w) {
		b = b[len(b)-len(w):]
	}
	copy(w[len(w)-len(b):], b)
	return w
}
