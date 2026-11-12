// Package keeper holds a planted KV-store machine (the keeper pattern) for I105.
package keeper

import (
	"errors"
	"strconv"
)

// KVStore is a byte-keyed store.
type KVStore interface {
	Get(key []byte) []byte
	Has(key []byte) bool
	Set(key, value []byte)
	Delete(key []byte)
}

// BalancePrefix prefixes every balance key.
const BalancePrefix = "bal/"

var errNotFound = errors.New("not found")

// Keeper keeps its state in a KV store: keys are a constant prefix plus an argument.
type Keeper struct {
	store     KVStore
	authority string
}

func balanceKey(addr string) []byte {
	return []byte(BalancePrefix + addr)
}

// SetBalance: guarded by the authority; writes store[balanceKey(addr)].
func (k Keeper) SetBalance(caller, addr string, amt uint64) error {
	if caller != k.authority {
		return errors.New("unauthorized")
	}
	k.store.Set(balanceKey(addr), []byte(strconv.FormatUint(amt, 10)))
	return nil
}

// Remove: guarded by Has; deletes store[balanceKey(addr)].
func (k Keeper) Remove(addr string) error {
	key := balanceKey(addr)
	if !k.store.Has(key) {
		return errNotFound
	}
	k.store.Delete(key)
	return nil
}

// Balance reads store[balanceKey(addr)].
func (k Keeper) Balance(addr string) []byte {
	return k.store.Get(balanceKey(addr))
}
