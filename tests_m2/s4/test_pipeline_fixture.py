"""Pipeline tests on synthetic fixtures: calldata decoding, layout diffs,
constant registry on a miniature morph tree."""

import json
import tempfile
import unittest
from pathlib import Path

from holon.frontends.link import calls, consts, links
from holon.frontends.link.layout import diff_layouts, normalize_layout
from holon.frontends.link.keccak import keccak256


def _w(v):
    if isinstance(v, str) and v.startswith("0x"):
        return int(v, 16).to_bytes(32, "big")
    if isinstance(v, int):
        return v.to_bytes(32, "big")
    raise ValueError(v)


def _bytes(blob):
    out = len(blob).to_bytes(32, "big") + blob
    return out + b"\x00" * ((32 - len(out) % 32) % 32)


def enc_upgrade_to_and_call(impl, init):
    head = _w(int(impl, 16)) + _w(0x40)
    return "0x4f1ef286" + (head + _bytes(init)).hex()


def enc_pa_upgrade_and_call(proxy, impl, init):
    head = (_w(int(proxy, 16)) + _w(int(impl, 16)) + _w(0x60))
    return "0x9623609d" + (head + _bytes(init)).hex()


def enc_exec_transaction(to, data):
    head_len = 32 * 10
    head = (_w(int(to, 16)) + _w(0) + _w(head_len) + _w(0)
            + _w(0) + _w(0) + _w(0) + _w(0) + _w(0) + _w(0x140))
    return "0x6a761202" + (head + _bytes(data)).hex()


def enc_initialize2(root):
    return keccak256(b"initialize2(bytes32)")[:4] + _w(int(root, 16))


IMPL_ABI = [
    {"type": "function", "name": "initialize",
     "inputs": [{"name": "_messageQueue", "type": "address"}]},
    {"type": "function", "name": "initialize2",
     "inputs": [{"name": "_prevStateRoot", "type": "bytes32"}]},
]

PROXY = "0x759894ced0e6af42c26668076ffa84d02e3cef60"
IMPL = "0xad900db30bcdf84c38df0067ea327bbecccf071a"
SAFE = "0xf101f7f59a348c1f971a2bc64fdbda58c7bbd887"
PA = "0x31110622d6ca24c9ff307d6ae1715f16e47f16a0"
HELPER = "0x542675e90e269f20ecbb9e0095d4751ac155b530"
ROOT = "0x2f3d926be55d78e42d1043dbe8fbcf8e59e4d2b45abc1000000000000000000"


class TestCalldata(unittest.TestCase):
    def test_direct_upgrade(self):
        init = enc_initialize2(ROOT)
        inp = enc_upgrade_to_and_call(IMPL, init)
        steps = calls.decode_upgrade_input(PROXY, inp, tx_from="0x2818a3af785975a32611155a6ee36c21cec068ca")
        kinds = [s["kind"] for s in steps]
        self.assertIn("proxy_upgrade", kinds)
        pu = next(s for s in steps if s["kind"] == "proxy_upgrade")
        self.assertEqual(pu["impl"], IMPL)
        self.assertEqual(pu["init_data"], "0x" + init.hex())
        r = calls.decode_initializer(pu["init_data"], IMPL_ABI)
        self.assertEqual(r["function"], "initialize2")
        self.assertEqual(r["reinitializer_version"], 2)
        self.assertEqual(r["args"]["_prevStateRoot"], "0x" + _w(int(ROOT, 16)).hex())

    def test_safe_pa_nested(self):
        init = enc_initialize2(ROOT)
        inner = enc_pa_upgrade_and_call(PROXY, IMPL, init)
        inp = enc_exec_transaction(PA, bytes.fromhex(inner[2:]))
        steps = calls.decode_upgrade_input(SAFE, inp, tx_from="0x05e1d4694041af987af6f8402d902686018e2136")
        kinds = [s["kind"] for s in steps]
        self.assertEqual(kinds[0], "tx_head")
        self.assertIn("safe_exec", kinds)
        self.assertIn("proxyadmin_upgrade", kinds)
        pa_step = next(s for s in steps if s["kind"] == "proxyadmin_upgrade")
        self.assertEqual(pa_step["impl"], IMPL)
        r = calls.decode_initializer(pa_step["init_data"], IMPL_ABI)
        self.assertEqual(r["function"], "initialize2")
        self.assertEqual(r["reinitializer_version"], 2)


class TestLayoutDiff(unittest.TestCase):
    def _lay(self, fields):
        return {"storage": [{"astId": i, "contract": "T:T", "label": n,
                             "offset": o, "slot": str(s), "type": t}
                            for i, (n, s, o, t) in enumerate(fields)],
                "types": {t: {"label": t[2:]} for _, _, _, t in fields}}

    def test_diff(self):
        a = normalize_layout(self._lay([("x", "0", 0, "t_uint256"),
                                        ("y", "1", 0, "t_bool")]))
        b = normalize_layout(self._lay([("x", "2", 0, "t_uint256"),
                                        ("z", "3", 0, "t_address"),
                                        ("y", "4", 0, "t_uint64")]))
        d = diff_layouts(a, b)
        self.assertEqual([f["label"] for f in d["added"]], ["z"])
        self.assertEqual([f["label"] for f in d["removed"]], [])
        self.assertEqual(sorted(m["label"] for m in d["moved"]), ["x", "y"])
        self.assertEqual([r["label"] for r in d["retyped"]], ["y"])

    def test_identical(self):
        lay = self._lay([("x", "0", 0, "t_uint256")])
        d = diff_layouts(normalize_layout(lay), normalize_layout(lay))
        self.assertEqual(d, {"added": [], "removed": [], "moved": [], "retyped": []})


class TestConstantsRegistry(unittest.TestCase):
    def _tree(self):
        d = Path(tempfile.mkdtemp())
        (d / "common/batch").mkdir(parents=True)
        (d / "common/blob").mkdir(parents=True)
        (d / "contracts/contracts/libraries/codec").mkdir(parents=True)
        (d / "contracts/contracts/l1/rollup").mkdir(parents=True)
        (d / "common/batch/batch_header.go").write_text(
            "const (\n\texpectedLengthV0 = 249\n\texpectedLengthV1 = 257\n"
            "\texpectedLengthV2 = 257\n\tBatchHeaderVersion2 = 2\n)\n"
            "binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)\n"
            "binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)\n"
            "binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)\n"
            "copy(batchBytes[25:], b.DataHash[:])\n"
            "copy(batchBytes[57:], b.BlobVersionedHash[:])\n"
            "copy(batchBytes[89:], b.PrevStateRoot[:])\n"
            "copy(batchBytes[121:], b.PostStateRoot[:])\n"
            "copy(batchBytes[153:], b.WithdrawalRoot[:])\n"
            "copy(batchBytes[185:], b.SequencerSetVerifyHash[:])\n"
            "copy(batchBytes[217:], b.ParentBatchHash[:])\n"
            "binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)\n"
            "batchBytes[0] = BatchHeaderVersion0\n")
        (d / "common/blob/payload.go").write_text(
            'var EmptyVersionedHash = common.HexToHash("0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014")\n'
            "const MaxBlobBytesSize = 4096 * 31\n")
        (d / "common/batch/blob.go").write_text("const MaxBlobBytesSize = 4096 * 31\n")
        (d / "common/batch/batch_cache.go").write_text("const replayProtocolMaxBlobs = 6\n")
        (d / "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol").write_text(
            "uint256 internal constant BATCH_HEADER_LENGTH = 249;\n"
            "mstore8(batchPtr, _version)\n"
            "mstore(add(batchPtr, 1), shl(192, _batchIndex))\n"
            "mstore(add(batchPtr, 9), shl(192, _l1MessagePopped))\n"
            "mstore(add(batchPtr, 17), shl(192, _totalL1MessagePopped))\n"
            "mstore(add(batchPtr, 25), _dataHash)\n"
            "mstore(add(batchPtr, 57), _blobVersionedHash)\n"
            "mstore(add(batchPtr, 89), _prevStateHash)\n"
            "mstore(add(batchPtr, 121), _postStateHash)\n"
            "mstore(add(batchPtr, 153), _withdrawRootHash)\n"
            "mstore(add(batchPtr, 185), _sequencerSetVerifyHash)\n"
            "mstore(add(batchPtr, 217), _parentBatchHash)\n")
        (d / "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol").write_text(
            "uint256 internal constant BATCH_HEADER_LENGTH = 257;\n"
            "mstore(add(batchPtr, 249), shl(192, _lastBlockNumber))\n")
        (d / "contracts/contracts/l1/rollup/Rollup.sol").write_text(
            "bytes32 internal constant ZERO_VERSIONED_HASH = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014;\n"
            'require(batchDataInput.version <= 2, "invalid version");\n'
            "BatchHeaderCodecV0.storeSequencerSetVerifyHash(_batchPtr, bytes32(0));\n")
        return d

    def test_all_linked(self):
        repo = self._tree()
        out = consts.extract_constants(repo)
        by_id = {c["id"]: c for c in out}
        self.assertEqual(by_id["batch_header_v0_length"]["linked"], True)
        self.assertEqual(by_id["zero_versioned_hash"]["linked"], True)
        self.assertEqual(by_id["blob_payload_bytes"]["linked"], "one_sided")
        self.assertEqual(by_id["sequencer_set_verify_hash_write"]["linked"], "asymmetric")

    def test_wire_layout(self):
        repo = self._tree()
        fields = links.extract_wire_layout(repo)
        self.assertEqual(len(fields), 12)
        for f in fields:
            self.assertTrue(f["linked"], f"field {f['name']} not linked")
        offs = {f["name"]: f["offset"] for f in fields}
        self.assertEqual(offs["batchIndex"], 1)
        self.assertEqual(offs["lastBlockNumber"], 249)


if __name__ == "__main__":
    unittest.main()
