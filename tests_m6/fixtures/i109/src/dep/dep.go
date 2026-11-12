// Package dep is outside the I109 fixture's documents: its methods are opaque calls to the Go machine frontend.
package dep

// Coins is a slice type with a value-receiver method.
type Coins []uint64

// IsZero is a method: a static call passes its receiver as the first argument (go/ssa's calling convention).
func (c Coins) IsZero() bool { return len(c) == 0 }
