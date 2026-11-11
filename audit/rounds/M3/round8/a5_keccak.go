// Round 8 (M3) A5: every keccak256 table entry of the M3 records, re-hashed with golang.org/x/crypto/sha3's
// NewLegacyKeccak256 (the Ethereum Keccak-256 go-ethereum uses), independently of holon/keccak.py.
// Input on stdin: one "<key hex> <word hex>" per line. Output: counts and every mismatch.
package main

import (
	"bufio"
	"encoding/hex"
	"fmt"
	"os"
	"strings"

	"golang.org/x/crypto/sha3"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	n, bad := 0, 0
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		if len(f) != 2 {
			continue
		}
		k, err := hex.DecodeString(strings.TrimPrefix(f[0], "0x"))
		if err != nil {
			fmt.Println("bad key", f[0][:20])
			bad++
			continue
		}
		h := sha3.NewLegacyKeccak256()
		h.Write(k)
		got := hex.EncodeToString(h.Sum(nil))
		w := strings.TrimPrefix(f[1], "0x")
		w = strings.Repeat("0", 64-len(w)) + w
		n++
		if got != strings.ToLower(w) {
			bad++
			fmt.Println("MISMATCH", f[0][:40], f[1], got)
		}
	}
	fmt.Printf("%d entries, %d mismatches\n", n, bad)
}
