// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// What the compiler and the EVM do, for the rules of the I19 transitions walker that round 2 of the follow-up added
// (tests_m2/test_i19_followup.py, TestCompilerSemantics; solc 0.8.24, optimizer off, cancun, as the rollup sidecar).
// V19-02: a bool read from storage is the raw byte; the compiler cleans a bool where it encodes, stores or compares
// it, and not in && (the truthiness of the raw value). V19-03: custom error revert data. V19-04: topics of indexed
// arguments. V19-05: Panic 0x41 of a memory allocation above 2^64 - 1 elements, no length check on a storage push,
// short calldata reverts with empty data.

interface Vm {
    struct Log {
        bytes32[] topics;
        bytes data;
        address emitter;
    }

    function store(address, bytes32, bytes32) external;
    function load(address, bytes32) external view returns (bytes32);
    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
}

contract B {
    bool public flag; // slot 0, offset 0
    bool public flag2; // slot 0, offset 1
    mapping(uint256 => bool) public mb; // slot 1
    bool public flag3; // slot 2
    uint256[] public arr; // slot 3

    struct S {
        uint256 a;
        uint256 b;
    }

    error E(uint256 a, string s);

    event Ev(string indexed s, bytes indexed b, uint256[] indexed xs, uint256 k);
    event Es(S indexed s);
    event Eb(bool indexed f, bool g);

    function raw() external view returns (uint256 r) {
        bool x = flag;
        assembly {
            r := x
        }
    }

    function raw2() external view returns (uint256 r) {
        bool x = flag2;
        assembly {
            r := x
        }
    }

    function rawm(uint256 k) external view returns (uint256 r) {
        bool x = mb[k];
        assembly {
            r := x
        }
    }

    function eqt() external view returns (bool) {
        return flag == true;
    }

    function notf() external view returns (bool) {
        return !flag;
    }

    function andb() external view returns (uint256 r) {
        bool x = flag && flag2;
        assembly {
            r := x
        }
    }

    function copyb() external {
        flag3 = flag;
    }

    function memb() external view returns (uint256 r) {
        bool[] memory m = new bool[](1);
        m[0] = flag;
        bool y = m[0];
        assembly {
            r := y
        }
    }

    function hashb() external view returns (bytes32) {
        return keccak256(abi.encode(flag));
    }

    function emitb() external {
        emit Eb(flag, flag);
    }

    function emits(string memory s, bytes memory b, uint256[] memory xs) external {
        emit Ev(s, b, xs, 7);
        emit Es(S(1, 2));
    }

    function alloc(uint256 n) external pure returns (uint256) {
        uint256[] memory m = new uint256[](n);
        return m.length;
    }

    function allocb(uint256 n) external pure returns (uint256) {
        bytes memory m = new bytes(n);
        return m.length;
    }

    function pushit() external {
        arr.push(5);
    }

    function two(uint256 a, uint64 b) external pure returns (uint256) {
        return a + b;
    }

    function err(uint256 a) external pure {
        revert E(a, "hi");
    }
}

contract SemanticsTest {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    function test_storage_bool_is_the_raw_byte() public {
        B b = new B();
        vm.store(address(b), bytes32(0), bytes32(uint256(0x0302)));
        require(b.raw() == 2, "flag reads its raw byte 2");
        require(b.raw2() == 3, "flag2 reads its raw byte 3");
        vm.store(address(b), bytes32(0), bytes32(uint256(0x0100)));
        require(b.raw() == 0, "flag reads only its own byte");
        bytes32 s = keccak256(abi.encode(uint256(5), uint256(1)));
        vm.store(address(b), s, bytes32(uint256(3)));
        require(b.rawm(5) == 3, "a mapping bool reads its raw byte");
    }

    function test_bools_are_cleaned_where_encoded_stored_or_compared() public {
        B b = new B();
        vm.store(address(b), bytes32(0), bytes32(uint256(0x0302)));
        (bool ok, bytes memory d) = address(b).call(abi.encodeWithSignature("flag()"));
        require(ok && keccak256(d) == keccak256(abi.encode(uint256(1))), "the ABI encoder cleans a returned bool");
        require(b.eqt(), "== compares cleaned bools");
        require(!b.notf(), "! is the truthiness of the raw byte");
        require(b.andb() == 3, "&& yields the raw value of its right operand");
        b.copyb();
        require(vm.load(address(b), bytes32(uint256(2))) == bytes32(uint256(1)), "a storage store cleans a bool");
        require(b.memb() == 1, "a memory store cleans a bool");
        require(b.hashb() == keccak256(abi.encode(uint256(1))), "abi.encode cleans a bool");
        vm.recordLogs();
        b.emitb();
        Vm.Log[] memory logs = vm.getRecordedLogs();
        require(logs[0].topics[1] == bytes32(uint256(1)), "an indexed bool's topic is cleaned");
        require(keccak256(logs[0].data) == keccak256(abi.encode(uint256(1))), "a bool in log data is cleaned");
    }

    function test_topics_of_indexed_reference_arguments() public {
        B b = new B();
        uint256[] memory xs = new uint256[](2);
        xs[0] = 3;
        xs[1] = 4;
        vm.recordLogs();
        b.emits("ab", hex"0102", xs);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        require(logs[0].topics[1] == keccak256(bytes("ab")), "string: keccak256 of its bytes");
        require(logs[0].topics[2] == keccak256(hex"0102"), "bytes: keccak256 of its bytes");
        require(logs[0].topics[3] == keccak256(abi.encode(uint256(3), uint256(4))), "array: of its in-place encoding");
        require(keccak256(logs[0].data) == keccak256(abi.encode(uint256(7))), "data: the arguments not indexed");
        require(logs[1].topics[1] == keccak256(abi.encode(uint256(1), uint256(2))), "struct: of its in-place encoding");
    }

    function test_memory_allocation_bound() public {
        B b = new B();
        bytes memory panic41 = abi.encodeWithSignature("Panic(uint256)", uint256(0x41));
        (bool ok, bytes memory d) = address(b).call{gas: 1_000_000}(abi.encodeCall(B.alloc, (uint256(1) << 64)));
        require(!ok && keccak256(d) == keccak256(panic41), "new uint256[](2^64): Panic 0x41");
        (ok, d) = address(b).call{gas: 1_000_000}(abi.encodeCall(B.allocb, (uint256(1) << 64)));
        require(!ok && keccak256(d) == keccak256(panic41), "new bytes(2^64): Panic 0x41");
        (ok, d) = address(b).call{gas: 1_000_000}(abi.encodeCall(B.alloc, ((uint256(1) << 64) - 1)));
        require(!ok && d.length == 0, "new uint256[](2^64 - 1): no panic (out of gas)");
    }

    function test_storage_push_has_no_length_check() public {
        B b = new B();
        vm.store(address(b), bytes32(uint256(3)), bytes32(uint256(1) << 64));
        b.pushit();
        require(vm.load(address(b), bytes32(uint256(3))) == bytes32((uint256(1) << 64) + 1), "push at length 2^64");
    }

    function test_short_calldata_reverts_with_empty_data() public {
        B b = new B();
        (bool ok, bytes memory d) = address(b).call(abi.encodePacked(B.two.selector, uint256(1), uint32(5)));
        require(!ok && d.length == 0, "4 + 36 bytes for (uint256, uint64): empty revert");
        (ok, d) = address(b).call(abi.encodePacked(B.two.selector, uint256(1), uint256(5)));
        require(ok, "4 + 64 bytes: the head");
        (ok, d) = address(b).call(abi.encodePacked(B.two.selector, uint256(1), uint256(5), uint8(1)));
        require(ok, "longer calldata is accepted");
    }

    function test_custom_error_revert_data() public {
        B b = new B();
        (bool ok, bytes memory d) = address(b).call(abi.encodeCall(B.err, (uint256(9))));
        require(!ok, "err reverts");
        require(bytes4(keccak256("E(uint256,string)")) == B.E.selector, "the selector is keccak256 of the signature");
        require(keccak256(d) == keccak256(abi.encodeWithSelector(B.E.selector, uint256(9), "hi")), "selector + args");
    }
}
