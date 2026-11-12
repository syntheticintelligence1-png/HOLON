// Package wrap is I117's planted fixture (tests_m6/test_i117_go_op_semantics.py). Blob is an interface carrier; every
// op reads bytes of the blob at constant indexes, with no loop, so the Go-op model's straight-line class models it
// under the Go frontend's ops "typed". Each op's behaviour hangs on one Go integer rule (the Go specification), and the
// laws PAR derives over it are known by construction:
//   - SumWrap panics only where b[0]+b[1] wraps to 0 with b[0] != 0 (uint8 wraparound): its totality law holds under
//     unbounded integers and is false under Go's semantics (the planted false law; witness b[0]=1, b[1]=255);
//   - IncWrap panics only where b[2]+1 < b[2], which unbounded arithmetic calls impossible (the reasoner control);
//   - SignedLow returns an error where int8(b[3]) < -100 (a signed conversion), never panics;
//   - ShiftMix returns an error where uint8(b[4]<<4)>>4 differs from b[4]&15, which never happens, never panics;
//   - Widen panics where int(b[5])*int(b[6]) exceeds 64000 (int is 64 bits: no wrap);
//   - Quot divides by a non-constant byte: the division's panic is not on the frontend's paths, so the op stays
//     undefined in the model and its laws UNKNOWN;
//   - Counter is a Go machine (its document gives DISCH a section). Its Bump takes a *Counter, which the static go_ops
//     role also makes a carrier, but the frontend enumerates no paths for a function that is not codec-shaped, so
//     without ops "typed" the totality law over Bump is unbound (I115); under it Bump is a guard over the field Count
//     (Q91 (1)), it never panics, and its totality law is true (UNKNOWN: no proof route).
package wrap

import "errors"

var errLow = errors.New("low")

// Blob is supplied by the environment.
type Blob [8]byte

func SumWrap(b Blob) error {
	if b[0]+b[1] == 0 && b[0] != 0 {
		panic("wrapped")
	}
	return nil
}

func IncWrap(b Blob) error {
	if b[2]+1 < b[2] {
		panic("inc wrapped")
	}
	return nil
}

func SignedLow(b Blob) error {
	if int8(b[3]) < -100 {
		return errLow
	}
	return nil
}

func ShiftMix(b Blob) error {
	if (b[4]<<4)>>4 != b[4]&15 {
		return errLow
	}
	return nil
}

func Widen(b Blob) error {
	if int(b[5])*int(b[6]) > 64000 {
		panic("wide")
	}
	return nil
}

func Quot(b Blob) error {
	if b[7]/b[1] == 3 {
		return errLow
	}
	return nil
}

// Counter counts up to a cap.
type Counter struct {
	Count uint64
}

func (c *Counter) Bump() error {
	if c.Count >= 10 {
		return errLow
	}
	c.Count++
	return nil
}

// Gate guards over its fields (HUMAN_ANSWERS Q91 (1)): Admit panics only where Open holds and Lim+1 wraps below Lim
// (int32 wraparound at the maximum: its totality law holds under unbounded integers and is false under Go's, the
// planted false law over fields); Check returns an error on a nil Conn and panics when Items has more than 3 elements.
type Gate struct {
	Open  bool
	Lim   int32
	Conn  *int
	Items []int
}

func (g *Gate) Admit() error {
	if g.Open && g.Lim+1 < g.Lim {
		panic("lim wrapped")
	}
	return nil
}

func (g *Gate) Check() error {
	if g.Conn == nil {
		return errLow
	}
	if len(g.Items) > 3 {
		panic("many")
	}
	return nil
}
