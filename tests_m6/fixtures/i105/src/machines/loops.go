package machines

// Loop plants writes inside a loop whose trip count is an argument (unbounded for the frontend).
type Loop struct {
	N   uint64
	Arr map[uint64]uint64
	K   uint64
}

// Fill writes Arr and N on every iteration.
func (l *Loop) Fill(n uint64) {
	for i := uint64(0); i < n; i++ {
		l.Arr[i] = i
		l.N++
	}
	l.K = 7
}

// Spawn plants a goroutine that writes the state.
type Spawn struct {
	X uint64
	Z uint64
}

// Go writes X from a goroutine (out of scope: coverage debt, X havocked).
func (s *Spawn) Go() {
	go func() {
		s.X = 1
	}()
	s.Z = 2
}
