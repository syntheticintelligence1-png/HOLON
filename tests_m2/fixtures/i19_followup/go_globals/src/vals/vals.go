// Package vals holds package-level variables that the package initializer assigns (tests_m2/test_i19_followup.py).
package vals

import "toy.local/globals/hexlib"

var Magic = hexlib.Parse("0xa1b2c3")

var Odd = hexlib.Parse("0x123")

var Long = hexlib.Parse("0x0102030405")

var Bad = hexlib.Parse("0xzz")

var Count = 7

var Name = "abc"

// Use reads a global, so the package has a function besides its initializer.
func Use() [4]byte {
	return Magic
}
