package reg

import "errors"

var errLong = errors.New("too long")

// Labeled reads the length of a string field (added after I109's run 1: len of a string cell, a free value).
type Labeled struct {
	Label string
	Ok    uint64
}

// Check refuses a long label and counts the checks it passes.
func (l *Labeled) Check() error {
	if len(l.Label) > 8 {
		return errLong
	}
	l.Ok++
	return nil
}
