"""keccak256 must agree with the canonical Ethereum digest."""

import unittest

from holon.frontends.link.keccak import keccak256, keccak256_hex


class TestKeccak(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(
            keccak256_hex(b""),
            "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

    def test_transfer_topic(self):
        self.assertEqual(
            keccak256_hex(b"Transfer(address,address,uint256)"),
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")

    def test_upgraded_topic(self):
        self.assertEqual(
            keccak256_hex(b"Upgraded(address)"),
            "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b")

    def test_selector_size(self):
        from holon.frontends.link.abi import selector_hex
        self.assertEqual(selector_hex({"name": "upgradeToAndCall",
                                     "inputs": [{"type": "address"}, {"type": "bytes"}]}),
                         "0x4f1ef286")


if __name__ == "__main__":
    unittest.main()
