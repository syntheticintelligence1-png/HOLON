// HOLON I59 blob check, Go side (holon/historical/replay.py).
//
// The replay copies this file into a scratch copy of morph common/batch at the facts' commit (the same
// workspace the I16 codec harness uses) and runs
//   (cd common && HOLON_KZG_IN=… HOLON_KZG_OUT=… go test ./batch -run '^TestHolonKzg$' -count=1 -v)
// For every input line "<blob file> <commitment hex>" it reads the blob (gzip when the name ends in .gz),
// computes kzg4844.BlobToCommitment with the go-ethereum fork the checkout pins, and writes one output line
// per input, in input order: "ok" (the blob commits to the commitment), "mismatch", or "error: <reason>".
// It compares nothing else and decides nothing: the replay reads the lines.
package batch

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"
	"sync"
	"testing"

	"github.com/morph-l2/go-ethereum/crypto/kzg4844"
)

func holonKzgOne(path, commitHex string) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "error: read"
	}
	if strings.HasSuffix(path, ".gz") {
		zr, err := gzip.NewReader(bytes.NewReader(raw))
		if err != nil {
			return "error: gzip"
		}
		raw, err = io.ReadAll(zr)
		if err != nil {
			return "error: gzip"
		}
	}
	var blob kzg4844.Blob
	if len(raw) != len(blob) {
		return fmt.Sprintf("error: %d bytes", len(raw))
	}
	copy(blob[:], raw)
	want, err := hex.DecodeString(strings.TrimPrefix(commitHex, "0x"))
	if err != nil || len(want) != 48 {
		return "error: commitment"
	}
	got, err := kzg4844.BlobToCommitment(&blob)
	if err != nil {
		return "error: not a canonical blob"
	}
	if bytes.Equal(got[:], want) {
		return "ok"
	}
	return "mismatch"
}

func TestHolonKzg(t *testing.T) {
	f, err := os.Open(os.Getenv("HOLON_KZG_IN"))
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	var lines []string
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	for sc.Scan() {
		if s := strings.TrimSpace(sc.Text()); s != "" {
			lines = append(lines, s)
		}
	}
	if err := sc.Err(); err != nil {
		t.Fatal(err)
	}
	out := make([]string, len(lines))
	jobs := make(chan int)
	var wg sync.WaitGroup
	for w := 0; w < runtime.NumCPU(); w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := range jobs {
				parts := strings.Fields(lines[i])
				if len(parts) != 2 {
					out[i] = "error: input line"
					continue
				}
				out[i] = holonKzgOne(parts[0], parts[1])
			}
		}()
	}
	for i := range lines {
		jobs <- i
	}
	close(jobs)
	wg.Wait()
	if err := os.WriteFile(os.Getenv("HOLON_KZG_OUT"), []byte(strings.Join(out, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	fmt.Printf("HOLON kzg: %d blobs\n", len(out))
}
