// Package hexlib is outside the extracted document: the fixture config declares Parse's semantics (a "hex_to_array"
// primitive of width 4), the way a target sidecar declares a dependency's.
package hexlib

// Parse returns the 4-byte array of the hexadecimal digits of s, right-aligned and cropped to its last 4 bytes.
func Parse(s string) (w [4]byte) {
	if len(s) >= 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X') {
		s = s[2:]
	}
	if len(s)%2 == 1 {
		s = "0" + s
	}
	n := len(s) / 2
	k := 0
	if n > len(w) {
		k = n - len(w)
	}
	for i := k; i < n; i++ {
		w[len(w)-n+i] = digit(s[2*i])<<4 | digit(s[2*i+1])
	}
	return w
}

func digit(c byte) byte {
	switch {
	case c >= '0' && c <= '9':
		return c - '0'
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10
	case c >= 'A' && c <= 'F':
		return c - 'A' + 10
	}
	return 0
}
