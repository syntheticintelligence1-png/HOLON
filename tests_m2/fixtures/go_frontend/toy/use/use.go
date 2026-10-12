// Package use consumes the toy codec: view flows (one held across a write to its backing), a standalone
// encoder for a tag the codec package has no encoder for, a patched encoder output, and a call chain from a
// loop to the bounds-checked site of codec.Scan.
package use

import (
	"encoding/binary"

	"toy.local/fixture/codec"
)

func Consume(b *codec.Buf) int {
	j := b.Joined()
	return codec.Sum(j, len(j)/2)
}

func Hold(b *codec.Buf, h []byte) byte {
	v := b.Joined()
	b.Add(h, nil)
	return v[0]
}

func Fresh(b *codec.Buf) byte {
	v := b.Copy()
	b.Add(nil, nil)
	return v[0]
}

func Stamp() []byte {
	out := make([]byte, 21)
	out[0] = 9
	binary.BigEndian.PutUint64(out[1:], 5)
	return out
}

func Patch(r codec.RecB) codec.Frame {
	h := r.Bytes()
	h[0] = 9
	return h
}

func Top(ds []*[64]byte) int {
	n := 0
	for _, d := range ds {
		if _, err := mid(d); err == nil {
			n++
		}
	}
	return n
}

func mid(d *[64]byte) ([]byte, error) {
	return codec.Scan(d)
}
