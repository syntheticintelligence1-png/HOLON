// Package codec is the planted toy of the I18 Go frontend (tests_m2/test_extract_go_toy.py): two cached
// value-receiver encoders (one embeds the other and shadows its cache), a tagged frame decoder, slice views
// over a buffer, and loops whose bounds and bounds-checked sites are known by construction.
package codec

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"

	"toy.local/fixture/prim"
)

type Word [4]byte

type Frame []byte

const (
	lenA = 13
	lenB = 21
)

type RecA struct {
	Seq  uint64
	Tag  Word
	memo []byte
}

type RecB struct {
	RecA
	Tail uint64
	memo []byte
}

func (r RecA) Bytes() Frame {
	if len(r.memo) > 0 {
		return Frame(r.memo)
	}
	out := make([]byte, lenA)
	out[0] = 7
	binary.BigEndian.PutUint64(out[1:], r.Seq)
	copy(out[9:], r.Tag[:])
	r.memo = out
	return out
}

func (r RecB) Bytes() Frame {
	if len(r.memo) > 0 {
		return Frame(r.memo)
	}
	out := make([]byte, lenB)
	out[0] = 8
	binary.BigEndian.PutUint64(out[1:], r.Seq)
	copy(out[9:], r.Tag[:])
	binary.BigEndian.PutUint64(out[13:], r.Tail)
	r.memo = out
	return out
}

var (
	errEmpty = errors.New("empty frame")
	errLen   = errors.New("bad frame length")
	errKind  = errors.New("bad frame kind")
)

func (f Frame) kind() (uint8, error) {
	if len(f) == 0 {
		return 0, errEmpty
	}
	return f[0], nil
}

func (f Frame) check() error {
	k, err := f.kind()
	if err != nil {
		return err
	}
	switch k {
	case 7:
		if len(f) != lenA {
			return errLen
		}
	case 8, 9:
		if len(f) != lenB {
			return errLen
		}
	default:
		return errKind
	}
	return nil
}

func (f Frame) Kind() (uint8, error) {
	return f.kind()
}

func (f Frame) Seq() (uint64, error) {
	if err := f.check(); err != nil {
		return 0, err
	}
	return binary.BigEndian.Uint64(f[1:9]), nil
}

func (f Frame) Tag() (Word, error) {
	if err := f.check(); err != nil {
		return Word{}, err
	}
	return Word(prim.ToWord(f[9:13])), nil
}

func (f Frame) Tail() (uint64, error) {
	if err := f.check(); err != nil {
		return 0, err
	}
	k, _ := f.kind()
	if k < 8 {
		return 0, errKind
	}
	return binary.BigEndian.Uint64(f[13:21]), nil
}

func (f Frame) Unsafe() uint64 {
	return binary.BigEndian.Uint64(f[13:21])
}

type Buf struct {
	head []byte
	body []byte
}

func NewBuf() *Buf {
	return &Buf{head: make([]byte, 0), body: make([]byte, 0)}
}

func (b *Buf) Add(h, x []byte) {
	b.head = append(b.head, h...)
	b.body = append(b.body, x...)
}

func (b *Buf) Joined() []byte {
	return append(b.head, b.body...)
}

func (b *Buf) Body() []byte {
	return b.body
}

func (b *Buf) Copy() []byte {
	out := make([]byte, len(b.head)+len(b.body))
	copy(out, b.head)
	copy(out[len(b.head):], b.body)
	return out
}

func Sum(xs []byte, n int) int {
	t := 0
	for i := 0; i < n; i++ {
		t += int(xs[i*2])
	}
	for _, x := range xs {
		t += int(x)
	}
	return t
}

func Scan(data *[64]byte) ([]byte, error) {
	buf := make([]byte, 48)
	for i := 0; i < 16; i++ {
		if data[i*4] != 0 {
			return nil, fmt.Errorf("bad high byte %x of word %d", buf[i*4], i)
		}
		copy(buf[i*3:i*3+3], data[i*4+1:i*4+4])
	}
	return buf, nil
}

func ScanSafe(data *[64]byte) ([]byte, error) {
	buf := make([]byte, 48)
	for i := 0; i < 16; i++ {
		if data[i*4] != 0 {
			return nil, fmt.Errorf("bad high byte %x of word %d", data[i*4], i)
		}
		copy(buf[i*3:i*3+3], data[i*4+1:i*4+4])
	}
	return buf, nil
}

func Forever(r io.Reader) int {
	c := 0
	for {
		var b [1]byte
		n, err := r.Read(b[:])
		if err != nil || n == 0 {
			break
		}
		c++
	}
	return c
}

func Between(lo, hi uint64) uint64 {
	var s uint64
	for n := lo; n <= hi; n++ {
		s += n
	}
	return s
}
