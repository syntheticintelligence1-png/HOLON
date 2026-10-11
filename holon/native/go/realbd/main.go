// realbd — drives the REAL morph common/batch.BatchData. JSON lines.
// Request: {"steps":[[op,args...]...]}  op 1 = append{bctx,payload}
//          encoded per step as [1, nctx, ctx..., npay, pay...] or [2]
//          -> {"obs":["ok","rev <panic>"...], "view":[bytes]}
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"morph-l2/common/batch"
)

type req struct {
	Steps [][]uint64 `json:"steps"`
}

func bytesOf(xs []uint64) []byte {
	b := make([]byte, len(xs))
	for i, x := range xs {
		b[i] = byte(x)
	}
	return b
}

func uintsOf(b []byte) []uint64 {
	out := make([]uint64, len(b))
	for i, x := range b {
		out[i] = uint64(x)
	}
	return out
}

func main() {
	enc := json.NewEncoder(os.Stdout)
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 64<<20), 64<<20)
	for sc.Scan() {
		var r req
		if err := json.Unmarshal(sc.Bytes(), &r); err != nil {
			enc.Encode(map[string]any{"error": err.Error()})
			continue
		}
		d := batch.NewBatchData()
		obs := []string{}
		view := []uint64{}
		for _, w := range r.Steps {
			step := func() (o string) {
				defer func() {
					if e := recover(); e != nil {
						o = fmt.Sprintf("rev panic:%v", e)
					}
				}()
				switch int(w[0]) {
				case 1:
					nc := int(w[1])
					ctx := bytesOf(w[2 : 2+nc])
					np := int(w[2+nc])
					pay := bytesOf(w[3+nc : 3+nc+np])
					d.Append(ctx, pay, nil)
				case 2:
					view = uintsOf(d.TxsPayloadV2())
				}
				return "ok"
			}
			obs = append(obs, step())
		}
		enc.Encode(map[string]any{"obs": obs, "view": view})
	}
}
