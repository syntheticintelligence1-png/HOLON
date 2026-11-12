package machines

// sink is a function value: a call through it is dynamic, so the frontend cannot see what it writes.
var sink = func(p *uint64, v uint64) { *p = v }

// Alias plants writes the frontend must not drop.
type Alias struct {
	X uint64
	Y uint64
	P *uint64
}

// Through writes X through a local pointer to the field (an alias the frontend resolves).
func (a *Alias) Through(v uint64) {
	p := &a.X
	q := p
	*q = v
}

// Leak passes a pointer to Y to a dynamic call: Y may be written with any value.
func (a *Alias) Leak(v uint64) {
	sink(&a.Y, v)
}

// Deref writes through a pointer held in the state: it may point anywhere, the receiver's own fields included.
func (a *Alias) Deref(v uint64) {
	*a.P = v
}
