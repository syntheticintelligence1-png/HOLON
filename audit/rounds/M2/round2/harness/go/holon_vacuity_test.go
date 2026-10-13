// HOLON I21 (audit round M2/2, auditor A4) hypothesis harness, Go side (holon/audit/vacuity.py). It runs
// implementations of real oracles from the pinned checkout and its Go module graph on the inputs it is given and
// writes what they return; holon/audit/vacuity.py judges the hypotheses from these outputs.
//
// holon audit vacuity copies this file into the package of the round's header surface (a scratch copy of the pinned
// checkout's Go workspace), and runs `go test -run '^TestHolonVacuity$'` with HOLON_HOSTILE_IN (JSON) and
// HOLON_HOSTILE_OUT (one JSON array per line).
//
// Input {"header_hash": [hex, ..],          headers through (BatchHeaderBytes).Hash
//        "zero_blob": bool,                 the KZG versioned hash of the all-zero blob, and the package constant
//        "codec": [{"x": hex, "pad": n}, ..], CompressBatchBytes(x), n zero bytes appended, DecompressBatchBytes
//        "tx": bool}                        the transaction codec on a fixed sample of every transaction type
// Output ["H", i, hash | "error:<msg>"]
//        ["K", computed versioned hash, the blob package's empty versioned hash]
//        ["Z", i, encoded length | -1, "ok:<hex of the decoded bytes' sha256>" | "error:<msg>" | "enc_error:<msg>"]
//        ["T", i, description, encode-decode-encode identical (bool), detail]
//        ["DONE"]
package batch

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"strings"
	"testing"

	"morph-l2/common/blob"
	"morph-l2/common/codec/zstd"

	"github.com/morph-l2/go-ethereum/common"
	"github.com/morph-l2/go-ethereum/core/types"
	"github.com/morph-l2/go-ethereum/crypto"
	"github.com/morph-l2/go-ethereum/crypto/kzg4844"
)

type holonVacuityIn struct {
	HeaderHash []string `json:"header_hash"`
	ZeroBlob   bool     `json:"zero_blob"`
	Codec      []struct {
		X   string `json:"x"`
		Pad int    `json:"pad"`
	} `json:"codec"`
	Tx bool `json:"tx"`
}

func holonVacuityHex(s string) []byte {
	b, err := hex.DecodeString(strings.TrimPrefix(s, "0x"))
	if err != nil {
		panic(err)
	}
	return b
}

// the blob package's constant for the empty blob's versioned hash (common/blob/payload.go)
func holonVacuityEmptyHash() string {
	return blob.EmptyVersionedHash.Hex()
}

func holonVacuityTxs() ([]string, []*types.Transaction) {
	key, _ := crypto.ToECDSA(bytes.Repeat([]byte{0x11}, 32))
	chain := big.NewInt(2818)
	signer := types.LatestSignerForChainID(chain)
	to := common.HexToAddress("0x00000000000000000000000000000000000000aa")
	ref := common.Reference{}
	ref[0], ref[31] = 0x01, 0xff
	memo := []byte("i21")
	empty := []byte{}
	var names []string
	var txs []*types.Transaction
	add := func(name string, data types.TxData, sign bool) {
		tx := types.NewTx(data)
		if sign {
			s, err := types.SignTx(tx, signer, key)
			if err != nil {
				names = append(names, name+" (unsigned: "+err.Error()+")")
				txs = append(txs, tx)
				return
			}
			tx = s
		}
		names = append(names, name)
		txs = append(txs, tx)
	}
	for _, sign := range []bool{false, true} {
		for _, data := range [][]byte{nil, {0x01}, bytes.Repeat([]byte{0xab}, 100)} {
			for _, dst := range []*common.Address{nil, &to} {
				d := fmt.Sprintf("data %d, to %v, signed %v", len(data), dst != nil, sign)
				add("legacy "+d, &types.LegacyTx{Nonce: 1, GasPrice: big.NewInt(7), Gas: 21000, To: dst, Value: big.NewInt(3), Data: data}, sign)
				add("access list "+d, &types.AccessListTx{ChainID: chain, Nonce: 1, GasPrice: big.NewInt(7), Gas: 21000, To: dst, Value: big.NewInt(3), Data: data,
					AccessList: types.AccessList{{Address: to, StorageKeys: []common.Hash{{0x01}}}}}, sign)
				add("dynamic fee "+d, &types.DynamicFeeTx{ChainID: chain, Nonce: 1, GasTipCap: big.NewInt(1), GasFeeCap: big.NewInt(9), Gas: 21000, To: dst, Value: big.NewInt(3), Data: data}, sign)
				for _, ver := range []uint8{0, 1} {
					for _, fee := range []uint16{0, 1} {
						mt := &types.MorphTx{ChainID: chain, Nonce: 1, GasTipCap: big.NewInt(1), GasFeeCap: big.NewInt(9), Gas: 21000, To: dst, Value: big.NewInt(3), Data: data,
							Version: ver, FeeTokenID: fee}
						if fee != 0 {
							mt.FeeLimit = big.NewInt(1000)
						}
						if ver == 1 {
							for k, rm := range []struct {
								r *common.Reference
								m *[]byte
							}{{nil, nil}, {&ref, nil}, {nil, &memo}, {&ref, &memo}, {nil, &empty}} {
								c := *mt
								c.Reference, c.Memo = rm.r, rm.m
								add(fmt.Sprintf("morph v1 fee %d ref/memo %d %s", fee, k, d), &c, sign)
							}
						} else {
							add(fmt.Sprintf("morph v0 fee %d %s", fee, d), mt, sign)
						}
					}
				}
			}
			add(fmt.Sprintf("blob data %d signed %v", len(data), sign), &types.BlobTx{Nonce: 1, Gas: 21000, To: to, Data: data,
				BlobHashes: []common.Hash{{0x01, 0x02}}}, sign)
		}
	}
	for _, data := range [][]byte{nil, {0x01}, bytes.Repeat([]byte{0xcd}, 64)} {
		for _, q := range []uint64{0, 5} {
			add(fmt.Sprintf("l1 message queue %d data %d", q, len(data)), &types.L1MessageTx{QueueIndex: q, Gas: 100000, To: &to,
				Value: big.NewInt(0), Data: data, Sender: common.HexToAddress("0x00000000000000000000000000000000000000bb")}, false)
		}
	}
	return names, txs
}

func TestHolonVacuity(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_HOSTILE_IN"))
	if err != nil {
		t.Fatal(err)
	}
	var in holonVacuityIn
	if err := json.Unmarshal(raw, &in); err != nil {
		t.Fatal(err)
	}
	out, err := os.Create(os.Getenv("HOLON_HOSTILE_OUT"))
	if err != nil {
		t.Fatal(err)
	}
	defer out.Close()
	emit := func(v ...interface{}) {
		b, _ := json.Marshal(v)
		out.Write(append(b, '\n'))
	}
	for i, h := range in.HeaderHash {
		v, err := BatchHeaderBytes(holonVacuityHex(h)).Hash()
		if err != nil {
			emit("H", i, "error:"+err.Error())
		} else {
			emit("H", i, v.Hex())
		}
	}
	if in.ZeroBlob {
		zero := new(kzg4844.Blob)
		c, err := kzg4844.BlobToCommitment(zero)
		if err != nil {
			t.Fatal(err)
		}
		vh := kzg4844.CalcBlobHashV1(sha256.New(), &c)
		emit("K", "0x"+hex.EncodeToString(vh[:]), holonVacuityEmptyHash())
	}
	for i, c := range in.Codec {
		x := holonVacuityHex(c.X)
		enc, err := zstd.CompressBatchBytes(x)
		if err != nil {
			emit("Z", i, -1, "enc_error:"+err.Error())
			continue
		}
		padded := append(append([]byte{}, enc...), make([]byte, c.Pad)...)
		dec, err := zstd.DecompressBatchBytes(padded)
		if err != nil {
			emit("Z", i, len(enc), "error:"+err.Error())
			continue
		}
		sum := sha256.Sum256(dec)
		emit("Z", i, len(enc), fmt.Sprintf("ok:%x:%d", sum, len(dec)))
	}
	if in.Tx {
		names, txs := holonVacuityTxs()
		for i, tx := range txs {
			enc, err := tx.MarshalBinary()
			if err != nil {
				emit("T", i, names[i], false, "encode: "+err.Error())
				continue
			}
			var back types.Transaction
			if err := back.UnmarshalBinary(enc); err != nil {
				emit("T", i, names[i], false, "decode: "+err.Error())
				continue
			}
			again, err := back.MarshalBinary()
			if err != nil {
				emit("T", i, names[i], false, "re-encode: "+err.Error())
				continue
			}
			same := bytes.Equal(enc, again) && back.Hash() == tx.Hash()
			emit("T", i, names[i], same, fmt.Sprintf("%d bytes, type %d", len(enc), tx.Type()))
		}
	}
	emit("DONE")
}
