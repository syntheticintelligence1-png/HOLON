// Package m is a planted module whose go directive is 1.25 (I109 (b)): the Go machine frontend must run the lowest
// pinned release at or above it.
package m

// Tally is a one-field machine.
type Tally struct {
	N uint64
}

// Inc increments N.
func (t *Tally) Inc() error {
	t.N++
	return nil
}
