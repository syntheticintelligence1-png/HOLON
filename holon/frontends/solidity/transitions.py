"""Transitions of one contract: storage families, guards, effects, cost terms, principal predicates, hash and commit
edges, and the coverage of every statement (I19; whitepaper §10.1 Solidity, §9.3 G8), extended by the I19 follow-up
(A19: written values, implicit checks, every guard reach, loop records, events, the action interface, inherited
storage and actions). The contract is the docstring of tests_m2/test_extract_transitions.py (document) and
tests_m2/test_coverage.py (coverage); the follow-up keys are additive and documented here and in
spec/schemas/facts_0_3.schema.json; I17's compile (W1), spans (W2) and terms (W4) are reused from
holon.frontends.solidity.{compile, ast}.

Inputs: the compiler's AST and storage layout and the source bytes, through a sidecar with "transitions":
{"contract", "commit_interfaces"}. Nothing here reads a fact document, a law or a result, and no name of a target
appears here: the contract and the commit interfaces come from the sidecar.

The walk. Every external or public FunctionDefinition of the contract, its own and the ones it inherits (over its
linearization, most derived first, one per selector: an override wins), is an action. Its walk is a structured
symbolic execution of the body, depth first:
  * modifiers are inlined in order (a modifier's `_` walks the next modifier, then the body); internal, private,
    public and library-internal calls with a body are inlined (virtual calls dispatched against the contract's
    linearization), arguments evaluated left to right and bound by value (storage pointers by reference);
  * both branches of an if are walked (then before else) under the branch condition; a condition that folds to a
    constant walks only its branch; after the if, locals, storage and memory that differ are merged: locals and
    storage into conditional terms ["?", c, a, b], a memory region into its common prefix followed by the writes of
    each branch guarded by ["when", c, w]; a branch that always reverts contributes nothing to the merge; a branch
    that may leave by return, break or continue puts the condition under which control goes on into the context of
    what follows;
  * && and || evaluate their right operand only under the left operand's condition (its guards, checks, writes and
    calls carry that context, and what it changes is merged as for an if); so does the conditional operator;
  * loops (Solidity for, while, do-while, and Yul for) are summarised by a loop transformer (below);
  * inline assembly is walked with I17's Yul subset (W7) plus sload, blobhash, YulIf, YulSwitch (an if-chain), Yul
    for loops, user-defined Yul functions (inlined; `leave` returns), break/continue, revert/invalid, the signed
    builtins, addmod, mulmod, byte, signextend and a few environment builtins; other builtins are not represented
    (debt "unsupported", the variables they assign havocked to ["unknown", <span>, <name>]);
  * try/catch walks the success clause under ["callok", ...] of its call and the catch clauses under its negation;
    `new C(...)` is an external call whose result is ["new", C, args...]; `new T[](n)` allocates ["alloc", T, n].
The walk keeps a context: the conditions of the enclosing branches and loops (across inlined calls); K below.

Terms (JSON arrays; ints are constants mod 2^256, folded with EVM semantics as in I17 W4):
  ["param", name]           an entry parameter          ["caller"]                 msg.sender, _msgSender(), caller()
  ["storage", name]         a state variable before the transaction (also the base of mapping/array/struct reads)
  ["map", base, key]        a mapping read              ["index", base, i]         an array or bytes element
  ["member", base, name]    a struct member             ["len", x]                 .length
  ["byte", x, k]            byte k of input bytes x     ["word", x, k]             the 32 bytes at offset k of the memory
                                                                                   copy of input bytes x (calldatacopy)
  ["call", "<I>.<f>", args...]   the result of an external call of function f declared in I (the receiver is not an
                            argument); low-level calls: ["call", "address.<call|staticcall|delegatecall|send|transfer>",
                            receiver, args...] (["value", v] last when it carries value); ["at", k, t] a component
  ["callok", "<I>.<f>", receiver, args...]  the call succeeds (does not revert); free under A-env
  ["caught", "Error"|"Panic", callok]       a failed try call's revert data is that error
  ["new", C, args...] / ["alloc", T, n]     a created contract's address / a fresh memory array
  ["env", "<global>.<member>"]  block, msg (but sender) and tx members, gasleft; ["this"]; ["code", a]; ["balance", a];
                            ["codehash", a]
  ["immutable", name]       ["blobhash", i]  ["blockhash", i]  ["sload", slot]  ["str", hex]  ["slot", name]
  ["keccak256", b] / ["sha256", b]   a hash of b: input bytes, an abi encoding ["abi.encode"|..., args...], or
                            ["slice", mem, offset, length] of a memory region; ["abi.inplace", x] the in-place
                            encoding of an array or struct x (its elements' encodings, each padded to 32 bytes), whose
                            keccak256 is the topic of an indexed array or struct argument (events)
  ["mem", write...]         a memory region's writes in order: ["mstore", off, v], ["mstore8", off, v],
                            ["calldatacopy", off, x, from, n], ["when", c, write] (a write made only when c holds),
                            ["mloop", loop, ["iter", loop], count, [write...]] (for every k < count, in order, the
                            writes with ["iter", loop] bound to k), ["loop", loop] (writes of a loop not summarised),
                            ["unknown", span]
  ["mload", mem, off]       a memory read not resolved to a write; ["ptr", stack, off] a pointer into the region
                            allocated (mload(0x40)) at that call stack
  ["store", base, [accessor...], v]   storage base after writing v at the path (["map", k], ["index", i],
                            ["member", n]); a later read of the same path is v, of a disjoint path the base's value
  ["?", c, a, b]            a conditional (merges and the conditional operator)
  ["carried", loop, name]   the value of a name carried by the loop at the start of the generic iteration
  ["iter", loop]            the index (from 0) of the generic iteration
  ["count", loop]           the index of the iteration that leaves the loop (its head fails there, or it breaks or
                            returns there): the number of iterations completed, for a loop not counted by its header
  ["exit", loop, name]      the value of a carried name after the loop (defined by the loop record); ["exit", loop,
                            ["return", j]] the value a return path j of the loop returns
  ["returned", loop, j]     the walk reached the loop and left it (and the function) by its return path j
  ["sum", loop, ["iter", loop], count, t]   the sum over k < count of t with ["iter", loop] bound to k (cost terms
                            of loops inside a loop's generic iteration)
                            A loop is named by its span; a loop reached a second time in the same action carries the
                            reach index as an extra last element (["iter", loop, 1], ["exit", loop, name, 1], ...).
                            A name is a local's or Yul variable's source name, or ["storage", family].
  ["unknown", span, name]   a havocked value
  ["struct", name, [[member, v], ...]]  ["tuple", ...]  ["array", ...]  ["update", base, target, v]
  ["push", array, v] / ["pop", array]   a storage array after push / pop (the value of such a write)
  ["input", x, from, n]     the value of a calldatacopy record (mstores): n bytes of input x from offset from
  ["range", x, a, b] (x[a:b]), ["cdoff", x] (x.offset), ["calldataload", o], ["calldata", o], ["revertdata", kind,
  callok] (a catch clause's parameter), ["decl", id], ["type", ...], ["global", name], ["enum", name],
  ["constant", name], ["ref", family, path]   further leaves of the walk (I17 W4 and the cases above)
  [op, a, b] / ["!", a]     operators: I17's DSL ops (== != < <= > >= ! && || + - * / % & | ^ << >>), plus "~",
                            "neg", "**", ["trunc", bits, t] (the low bits of t), ["sext", bits, t] (the low bits of t
                            sign-extended), the signed operators "s<" "s<=" "s>" "s>=" "sdiv" "smod" "sar" (chosen when
                            the operands are intN), ["addmod", a, b, n] and ["mulmod", a, b, n] (EVM semantics: 0 when
                            n is 0), ["wbyte", x, n] (byte n of the word x, 0 the most significant),
                            ["signextend", b, x] (Yul, b not constant); context conjunctions are n-ary "&&".
  ["fits", N, [op, a, b]] / ["sfits", N, [op, a, b]]   the exact (integer, not modular) result of op on the unsigned /
                            signed values a and b lies in [0, 2^N) / [-2^(N-1), 2^(N-1)); op is + - * ** neg or sdiv
Terms are simplified as they are built (ite(c, ite(c, a, b), d) is ite(c, a, d); ite(c, 1, 0) of a boolean c is c;
ite(x == k, a, b) is b when b with x := k folds to a; for c = x or c = !x, x is 0 where x fails and, for a boolean
x, 1 where it holds, and a conditional whose branches agree at that value of x is the branch taken where x has the
other value (ite(!x, 0, x) and ite(x, x, 0) are x for any x; ite(!x, 1, x) is 1 for a boolean x); x * 1, x - x, ...)
and when rendered: inside ite(c, a, b), a is rendered knowing c and b knowing !c, and inside a || b (a && b), b
knowing !a (a); a conditional whose condition is then known is replaced by its branch, and a term standing where
only its truthiness counts (a condition: an expr of a guard, check, panic or call, a cond, a loop's head and break, a
principal's predicate, an operand of !, && and ||, the condition of a conditional or of a when, and the branches of
a conditional that stands there) is rendered 1 or 0 when it is known to hold or fail. A rendered term over
TERM_BUDGET nodes is an extraction error (exit 3).

Booleans (V19-02). A term is a boolean (0 or 1) when it is an operator of BOOL_TAGS, a conditional of two booleans, or
a boolean leaf: a bool entry parameter or bool member of a struct parameter (the ABI decoder checks them, checks
"abi", before they are used), or the bool result of an external call (the decoder of its return data checks it,
inside callok). A bool read from storage is not one: the compiler reads the raw byte at its offset and does not clean
it (with byte 2 stored, a read of the bool is 2), so ["storage", f] of a bool family is a word in [0, 256). The
compiler cleans a bool where it writes or compares one, and the terms do the same with ["!=", v, 0] (v itself when it
is a boolean): the ABI encoding (the action's returns, event args and topics, revert data args, external call
arguments, abi.encode*), storage and memory stores of a bool (writes, struct constructors, inline arrays, pushes),
and both operands of == and != on bools. Conditions (if, require, !, &&, ||, ?:) use the truthiness of the raw value.

Per action (document "actions", sorted by name). The I19 keys:
  guards     every require, assert and revert reached (Solidity revert, revert E(...), Yul revert/invalid), one entry
             per span (the first reach of a depth-first walk: modifiers in order, then the body; then before else).
             kind "modifier" when reached inside a modifier's own code (including the calls it makes), else "require"
             (require, assert) or "revert". reason: the string literal (or string constant), the custom error's name,
             else null. expr: the condition that must hold for the walk to pass the guard: a require's condition c, or
             ["||", ["!", K], c] under the context K; a revert's ["!", K] (0 when unconditional). The entry's src,
             kind, reason and expr are those of its first reach.
             (V19-03) error and args, present when the revert data is not empty and not a Panic: error {name, signature,
             selector}: a custom error E(...) (name: the declaring contract's name, a dot and E; signature: E and its
             canonical ABI parameter types; selector: "0x" and the first 4 bytes of keccak256(signature), checked
             against the compiler's errorSelector), or {"Error", "Error(string)", "0x08c379a0"} for a string reason
             (constant or not); args: the argument values in parameter order (named arguments reordered), as the ABI
             encoder writes them (Booleans). The revert data is the selector followed by abi.encode(args...). The
             entry's error and args are its first reach's; every reach carries its own args. A guard without error
             reverts with empty data (require(c), revert(), Yul revert), or with Panic(0x01) (an assert: code 1).
  principal  the first of the action's modifiers whose own code reaches a require whose condition mentions
             ["caller"] (its predicate: that condition), or a revert whose context within the function that reaches
             it mentions ["caller"] (its predicate: the negation of that context).
  effects    every storage write reached ({family, src}: the written state variable and the span of the assignment,
             ++/--, delete, push or pop), deduplicated, sorted by (src, family) as strings.
  cost       one term per loop reached whose body writes no storage: {loop: its span, iters}: the sum over the loop's
             reaches of ite(K, n, 0) (K elided when 1; the ite simplified as above), n the reach's bound: the count of a
             counted loop (see loops), the header's bound of a loop that also breaks, else ["count", loop]; a reach
             inside an enclosing loop's generic iteration is summed over that loop (["sum", ...]).
  edges      HASH: keccak256 (Solidity or Yul) and sha256 calls; COMMIT: blobhash (Solidity or Yul) and external calls
             of functions declared in an interface the sidecar's commit_interfaces names. {kind, fn, src}, first
             reach order, deduplicated.
The follow-up keys (A19). Every record carries "seq", an integer unique in the action, in walk order (the order in
which the walk meets it), "src" (its span) and "stack" (the spans of the inlined calls and of the modifier
invocations entered, outermost first; the body under a modifier's `_` has its function's stack); a record made in a
loop's generic iteration carries "loop": the seq of the innermost such loop record (it happens once per iteration):
  declared_in  the contract that declares the function.
  params     [{name, type, width (bits of an elementary type, of an address, contract or enum; null otherwise),
             location ("calldata", "memory", "default", ...), fields: [{name, type, width}] for a struct}].
  returns    the value the action returns, as the ABI encoder writes it (Booleans; a term, ["tuple", ...] for
             several), null when it returns nothing or never returns. payable: bool. mutability: the function's
             stateMutability.
  guards[].reaches   every reach of the guard, in walk order: {seq, stack, expr (the condition of that reach, as for
             the entry), loop?, code? (1 for an assert: its revert is Panic(0x01)), args? (V19-03: the revert data's
             args at that reach)}. The first reach's expr is the entry's expr.
  checks     implicit checks that are not panics: {seq, src, stack, kind, expr, param?}: "callvalue" (first, for an
             action that is not payable: ["==", ["env", "msg.value"], 0]), "calldatasize" (V19-05; next, for a function
             with parameters (not a fallback: its bytes parameter is the raw calldata): [">=", ["env",
             "msg.data.length"], 4 + h], h the size of the head of the parameters' ABI encoding: 32 bytes per value
             type and per dynamic type (its offset), a static array or struct in place; shorter calldata reverts with
             empty data), "abi" (the ABI decoder's range check of a
             parameter narrower than a word: ["<", x, 2^N] for uintN and enums (N their bound), addresses and bools,
             ["sfits", N, x] for intN, the unused low bytes of bytesN zero; a memory or value parameter is checked at
             entry in parameter order, a member of a calldata struct where the walk first reads it), "slice" (a
             calldata or memory slice x[a:b] needs a <= b <= len(x)), "uncaught" (a failed try call whose revert
             data no catch clause takes). expr holds the context like a guard's.
  panics     every checked operation reached: {seq, src, stack, code, op, args: [operands], expr: the condition under
             which the operation does not panic, with the context as for a guard}. code 17 (Panic 0x11, arithmetic
             overflow: + - * ** ++ -- unary - outside unchecked blocks; expr ["fits", N, [op, a, b]] or ["sfits", ...];
             signed / by -1), 18 (0x12: / and % (also inside unchecked blocks), addmod and mulmod: ["!=", d, 0]),
             50 (0x32: an array or bytes index out of bounds: ["<", i, ["len", x]]; a fixed array's length), 33 (0x21:
             a conversion to an enum: ["<", v, members]), 49 (0x31: pop of an empty storage array), 65 (0x41, V19-05:
             a memory allocation new T[](n), new bytes(n), new string(n) of more than 2^64 - 1 elements: ["<=", n,
             2^64 - 1]). Uncheckedness is lexical: an unchecked block covers its own statements, not the functions it
             calls; Yul never panics. A push on a storage array does not panic (the compiler checks no length there).
  calls      every external call reached: {seq, src, stack, fn, receiver, args, value, mutability, cond (K), commit
             (a COMMIT edge), try (a try call), expr}: expr the condition under which it does not revert:
             ["||", ["!", K], ["callok", fn, receiver, args...]] for a high-level call and transfer, 1 for a low-level
             call, send and a try call (their failure is a value). A view call is a LOAD of another contract's state.
  writes     every storage write: {seq, src, stack, family, path: [[kind, key], ...], value (delete writes 0),
             cond (K, 1 when unconditional)}, in walk order; effects is derived from it.
  mstores    every Yul memory write but mstore(0x40, .): {seq, src, stack, region (the allocation stack of the
             region, null when the address is not resolved), op (mstore, mstore8, calldatacopy), offset, value
             (calldatacopy: ["input", x, from, n]), cond}.
  events     every emit: {seq, src, stack, event ("<Contract>.<Event>"), signature (canonical ABI types), topic0
             ("0x" + keccak256(signature); null for an anonymous event), args (as the ABI encoder writes them:
             Booleans), indexed: [bool], topics, anonymous, cond}. topics (V19-04): the topic of each indexed argument,
             in order: a string or bytes argument x gives ["keccak256", x] (folded to its value for a constant), an
             array or struct x gives ["keccak256", ["abi.inplace", x]], any other argument its ABI word. The log's
             topics are topic0 followed by topics (topics alone for an anonymous event); its data is the ABI encoding
             of the arguments that are not indexed.
  loops      every loop reached: {seq, src, stack, kind (for, while, dowhile, yulfor), cond (K at the loop), carried:
             [{name, entry, value}] (the names whose value changes from one iteration to the next: entry its value
             before the loop, value its value at the start of the generic iteration: a closed form entry + d * iter
             when every continuing path adds the loop-invariant d to it, else ["carried", loop, name]), regions:
             [{region, writes}] (the memory regions the iteration writes; writes: the iteration's writes when they
             depend on the iteration only through closed forms, else null), head (the loop condition at the start of
             the generic iteration; dowhile: at its end), next: [{name, value}] (the carried values at the end of a
             continuing iteration), break (the condition under which the generic iteration breaks, 0 when it never
             does), at_break: [{name, value}], returns: [{cond, value}] (the generic iteration's return paths j: the
             condition under which it takes path j and the value it returns), count (the number of iterations: for a
             loop without break or return whose head compares a closed-form name stepped by a constant with a
             loop-invariant bound, the count that comparison gives (I19's header rule); ite(head, 1, 0) for a loop
             whose iteration never continues; else ["count", loop]), bound (the header's count, null when there is
             none), exit: [{name, value}] (the value each carried or break-changed name has after the loop: its closed
             form at iter = count for a loop without break; its break value at iter = count for a loop that only ends
             by break, when that value has a closed form; else ["exit", loop, name]; a region gets the iteration's
             writes as one ["mloop", ...] entry (and, for a loop that only ends by break, the breaking iteration's
             writes at iter = count) when they have closed forms, else a ["loop", loop] entry), steps: [seq of the
             records made directly in its generic iteration]}.
             The carried set is a fixpoint: the body is walked with the names found so far carried (bound to fresh
             symbols) until no further name changes; then once more with the closed forms, recording. A return path
             j of the generic iteration returns from the function under ["returned", loop, j], its value and state at
             iter = count (exit terms when they do not have a closed form); what follows the loop runs under the
             negation of every ["returned", loop, j].
  post       {family: term} for every family whose value after the action differs from ["storage", family] (a scalar
             written v is rendered v; a mapping, array or struct family as its store chain; a family whose simplified
             value is ["storage", family] is left out), sorted; {} when the action always reverts.
  order      the checks in walk order: ["check", i] | ["guard", src, k] (reach k of the guard at src) | ["panic", i] |
             ["call", i] (calls whose expr is not 1) | ["loop", i] (where the loop's per-iteration checks start; they
             carry its seq as "loop"). The transaction reverts at the first check whose expr is false.

Document level (A19): "inherited_storage" (holon.frontends.solidity.storage.inherited: the inherited state variables
with their compiler slots, offsets and declared_in).

Coverage (coverage_document): the statements are every Solidity Statement node inside the bodies of the actions and
of every function and modifier they reach (the bodies themselves excluded). A statement is extracted when the walk
used it for a guard, an effect, a cost term, an edge, a principal or an event, when it is control flow (block, if,
return, break, continue, `_`, try) or an inlined call, or when it is local computation (a local's declaration or
assignment, memory writes) whose local is read by some walked statement or is a return variable. Debt entries ({src,
kind, detail}): external_call (an external call that is not a COMMIT edge, contract creation included),
value_transfer (a call with value, send, transfer), loop_storage_write (a loop whose body writes storage; detail: the
families), unsupported (a statement or Yul construct the walk does not represent, with its node type; the statements
nested in an unsupported statement count as that debt). A statement neither extracted nor debt, including one the
walk never reached (dead code), is unaccounted.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from .. import ExtractionError, FACTS_VERSION
from .ast import Index, MASK, WORD, conversion_bits, fold as _fold, literal_value, type_string
from . import storage as STORAGE

TRANSITIONS_VERSION = "holon-frontend-solidity/0.3"
MAX_CALL_DEPTH = 24
MAX_FIXPOINT = 64
TERM_BUDGET = 400_000          # nodes of one rendered term
SMALL_TERM = 160               # ite simplification by substitution only looks at branches this small

STATEMENTS = frozenset({"Block", "UncheckedBlock", "PlaceholderStatement", "IfStatement", "TryStatement",
                        "WhileStatement", "DoWhileStatement", "ForStatement", "Continue", "Break", "Return", "Throw",
                        "EmitStatement", "RevertStatement", "VariableDeclarationStatement", "ExpressionStatement",
                        "InlineAssembly"})
LOOPS = frozenset({"ForStatement", "WhileStatement", "DoWhileStatement"})
LOOP_KIND = {"ForStatement": "for", "WhileStatement": "while", "DoWhileStatement": "dowhile", "YulForLoop": "yulfor"}
EXTRACTED_TAGS = frozenset({"guard", "principal", "effect", "cost", "edge", "control", "inlined", "event"})
LOW_LEVEL = ("call", "delegatecall", "staticcall", "send", "transfer")
YUL_PURE = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%", "and": "&", "or": "|", "xor": "^",
            "eq": "==", "lt": "<", "gt": ">", "exp": "**", "slt": "s<", "sgt": "s>", "sdiv": "sdiv", "smod": "smod"}
YUL_ENV = {"timestamp": ("env", "block.timestamp"), "number": ("env", "block.number"),
           "chainid": ("env", "block.chainid"), "callvalue": ("env", "msg.value"), "gas": ("env", "gasleft"),
           "origin": ("env", "tx.origin"), "gasprice": ("env", "tx.gasprice"), "coinbase": ("env", "block.coinbase"),
           "basefee": ("env", "block.basefee"), "blobbasefee": ("env", "block.blobbasefee"),
           "prevrandao": ("env", "block.prevrandao"), "calldatasize": ("env", "msg.data.length"),
           "returndatasize": ("env", "returndatasize"), "codesize": ("env", "codesize"),
           "caller": ("caller",), "address": ("this",)}
YUL_OTHER = frozenset({"shl", "shr", "sar", "iszero", "not", "mload", "mstore", "mstore8", "calldatacopy", "keccak256",
                       "sload", "blobhash", "revert", "invalid", "extcodesize", "extcodehash", "calldataload",
                       "balance", "selfbalance", "addmod", "mulmod", "byte", "signextend", "pop"})
CMP = ("==", "!=", "<", "<=", ">", ">=")
SIGNED_CMP = {"<": "s<", "<=": "s<=", ">": "s>", ">=": "s>="}
BOOL_TAGS = frozenset({"==", "!=", "<", "<=", ">", ">=", "!", "&&", "||", "s<", "s<=", "s>", "s>=", "fits", "sfits",
                       "callok", "caught"})
SYMBOL_TAGS = frozenset({"carried", "exit", "iter", "count", "loop", "returned"})

ASSUMPTIONS = {
    "A-env": ("Environment terms (storage before the transaction, block, msg and tx members, blobhash, results of "
              "external calls and whether they succeed (callok, caught), sload) are free: every value of them is "
              "possible. The result of an external call is a function of its function and arguments."),
    "A-implicit": ("Implicit reverts are checks (checks, panics, calls), except the ABI decoding of dynamic calldata "
                   "(offsets and lengths inside the calldata, and the Panic 0x41 of allocating a decoded dynamic "
                   "value in memory) and the range of array elements of narrow types: they are not checked. A member "
                   "of a calldata struct is range-checked where the walk first reads it under a context, as the "
                   "compiler validates it on access. Running out of gas is not a check."),
    "A-loop": ("A loop is walked at a generic iteration: the names it carries from one iteration to the next are found "
               "by a fixpoint and bound to closed forms (entry + d * iter) or carried symbols; a check inside it holds "
               "at every iteration; after it, a carried name holds a closed form at the iteration count (counted loops "
               "and loops that only end by break) or an exit term defined by the loop record. Counts assume the "
               "induction variable does not wrap (a wrapping counter would panic or loop forever)."),
    "A-reach": ("Every reach of a require, assert or revert is recorded (guards[].reaches, with its call stack): a "
                "guard entry's expr is its first reach's, and the later reaches keep their own expressions."),
    "A-reentrancy": ("External calls do not change this contract's storage (no reentrancy): a storage read after an "
                     "external call is the value this contract last wrote, or the value before the transaction."),
}


# ------------------------------------------------------------------------------------------------ terms
def _sgn(x: int) -> int:
    return x - WORD if x >> 255 else x


def _sdiv(a: int, b: int) -> int:
    a, b = _sgn(a), _sgn(b)
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    return (-q if (a < 0) != (b < 0) else q) & MASK


def _smod(a: int, b: int) -> int:
    a, b = _sgn(a), _sgn(b)
    if b == 0:
        return 0
    r = abs(a) % abs(b)
    return (-r if a < 0 else r) & MASK


def _sext(bits: int, v: int) -> int:
    if bits >= 256:
        return v & MASK
    v &= (1 << bits) - 1
    return (v - (1 << bits) if v >> (bits - 1) else v) & MASK


def fold(op: str, *args):
    """I17's folding (W4), distributed over conditionals of pointers so that pointer arithmetic stays resolvable, plus
    the signed operators, addmod, mulmod, trunc, sext, wbyte and a few identities (x + 0, x * 1, x - x, ...)."""
    for i, a in enumerate(args):
        if is_ite(a) and has_ptr(a):
            return ite(a[1], fold(op, *(args[:i] + (a[2],) + args[i + 1:])),
                       fold(op, *(args[:i] + (a[3],) + args[i + 1:])))
    if all(isinstance(a, int) for a in args):
        if op in ("s<", "s<=", "s>", "s>="):
            a, b = _sgn(args[0]), _sgn(args[1])
            return int({"s<": a < b, "s<=": a <= b, "s>": a > b, "s>=": a >= b}[op])
        if op == "sdiv":
            return _sdiv(*args)
        if op == "smod":
            return _smod(*args)
        if op == "sar":
            a, b = args
            return (_sgn(a) >> min(b, 256)) & MASK
        if op in ("addmod", "mulmod"):
            a, b, n = args
            if n == 0:
                return 0
            return ((a + b) if op == "addmod" else (a * b)) % n
        if op == "trunc":
            return args[1] & ((1 << args[0]) - 1)
        if op == "sext":
            return _sext(args[0], args[1])
        if op == "wbyte":
            x, n = args
            return (x >> (8 * (31 - n))) & 0xFF if n < 32 else 0
        return _fold(op, *args)
    if op in ("+", "-") and len(args) == 2:
        a, b = args
        if is_ptr(a) and not is_ptr(b):
            return ("ptr", a[1], fold(op, a[2], b))
        if op == "+" and is_ptr(b) and not is_ptr(a):
            return ("ptr", b[1], fold("+", b[2], a))
        if op == "-" and is_ptr(a) and is_ptr(b) and a[1] == b[1]:
            return fold("-", a[2], b[2])
        if b == 0:                              # x + 0 = x - 0 = x
            return a
        if op == "+" and a == 0:
            return b
        if op == "-" and a == b:
            return 0
        if isinstance(b, int) and isinstance(a, tuple) and len(a) == 3 and a[0] in ("+", "-") \
                and isinstance(a[2], int) and not isinstance(a[1], int):   # (x +- c) +- d = x + (+-c +- d)
            c = (a[2] if a[0] == "+" else -a[2]) + (b if op == "+" else -b)
            return fold("+", a[1], c & MASK) if (c & MASK) >> 255 == 0 else fold("-", a[1], (-c) & MASK)
    if op in ("&&", "||") and len(args) == 2:
        a, b = args
        return conj([a, b]) if op == "&&" else disj2(a, b)
    if op in ("==", "&") and len(args) == 2:     # a boolean b: b == 1 is b, b == 0 is !b, b & 1 is b
        a, b = args
        if isinstance(a, int):
            a, b = b, a
        if isinstance(b, int) and not isinstance(a, int) and is_bool(a):
            if op == "&":
                return a if b & 1 else 0
            return a if b == 1 else (neg(a) if b == 0 else 0)
    if op == "*" and len(args) == 2:
        a, b = args
        if a == 0 or b == 0:
            return 0
        if a == 1:
            return b
        if b == 1:
            return a
    if op == "/" and len(args) == 2 and args[1] == 1:
        return args[0]
    return _fold(op, *args)


def is_ptr(t) -> bool:
    return isinstance(t, tuple) and len(t) == 3 and t[0] == "ptr"


def is_ite(t) -> bool:
    return isinstance(t, tuple) and len(t) == 4 and t[0] == "?"


def is_mem(t) -> bool:
    return isinstance(t, tuple) and t[:1] == ("mem",)


def has_ptr(t) -> bool:
    if is_ptr(t):
        return True
    return is_ite(t) and (has_ptr(t[2]) or has_ptr(t[3]))


_BOOL_LEAVES: set = set()      # the boolean leaves of the walk in progress (Walk.run; module docstring, "Booleans")


def is_bool(t) -> bool:
    """Whether the word t is 0 or 1: a constant 0/1, an operator of BOOL_TAGS, a conditional of two booleans, or a
    boolean leaf of the walk in progress (a bool parameter or parameter member, a bool result of an external call).
    A bool read from storage is not one: the compiler reads the raw byte (module docstring, "Booleans")."""
    if isinstance(t, int):
        return t in (0, 1)
    if not isinstance(t, tuple) or not t:
        return False
    if t[0] in BOOL_TAGS:
        return True
    if t[0] == "?" and len(t) == 4:
        return is_bool(t[2]) and is_bool(t[3])
    return t in _BOOL_LEAVES


def clean_bool(v):
    """The word the compiler writes for a bool value v (ABI encoding, storage and memory stores, == and !=): v when it
    is a boolean, else ["!=", v, 0]."""
    return v if is_bool(v) else fold("!=", v, 0)


def abi_word(ts: str, v):
    """The word the ABI encoder (and a storage or memory store, and == and !=) makes of a value v of type ts: a bool
    is cleaned (clean_bool); any other value is itself (the walk's values of narrow types are in range: parameters are
    range-checked, checked arithmetic panics, unchecked arithmetic and conversions truncate, storage reads mask)."""
    return clean_bool(v) if _bare(ts) == "bool" else v


def small(t, limit: int = SMALL_TERM) -> bool:
    n, stack = 0, [t]
    while stack:
        x = stack.pop()
        n += 1
        if n > limit:
            return False
        if isinstance(x, tuple):
            stack.extend(x)
        elif isinstance(x, Ref):
            stack.extend(x.path)
    return True


def ite(c, a, b):
    if a == b:
        return a
    if isinstance(c, int):
        return a if c else b
    if is_ite(a) and a[1] == c:
        a = a[2]
    if is_ite(b) and b[1] == c:
        b = b[3]
    if a == b:
        return a
    if a == 1 and b == 0 and is_bool(c):
        return c
    if a == 0 and b == 1 and is_bool(c):
        return neg(c)
    eq = c
    if isinstance(eq, tuple) and len(eq) == 3 and eq[0] == "==":
        x, k = (eq[1], eq[2]) if isinstance(eq[2], int) else (eq[2], eq[1])
        if isinstance(k, int) and not isinstance(x, int) and small(b) and small(a) and subst(b, x, k) == a:
            return b
    if isinstance(eq, tuple) and len(eq) == 2 and eq[0] == "!" and isinstance(eq[1], tuple) and len(eq[1]) == 3 \
            and eq[1][0] == "==":
        e = eq[1]
        x, k = (e[1], e[2]) if isinstance(e[2], int) else (e[2], e[1])
        if isinstance(k, int) and not isinstance(x, int) and small(a) and small(b) and subst(a, x, k) == b:
            return a
    # c = x or c = !x: x is 0 exactly where x fails (any word x), and 1 where it holds when x is a boolean; when the
    # branches agree at that value of x, the conditional is the branch taken where x has the other value (ite(!x, 0, x)
    # is x and ite(x, x, 0) is x for any x; ite(!x, 1, x) is 1 and ite(x, 1, x) is x for a boolean x)
    negated = isinstance(c, tuple) and len(c) == 2 and c[0] == "!"
    x = c[1] if negated else c
    if not isinstance(x, int) and small(a) and small(b):
        if subst(a, x, 0) == subst(b, x, 0):
            return b if negated else a
        if is_bool(x) and subst(a, x, 1) == subst(b, x, 1):
            return a if negated else b
    return ("?", c, a, b)


def neg(c):
    if isinstance(c, int):
        return int(not c)
    if isinstance(c, tuple) and len(c) == 2 and c[0] == "!":
        return c[1]
    return ("!", c)


def conj(items) -> object:
    xs = []
    for x in items:
        if isinstance(x, int):
            if not x:
                return 0
            continue
        xs.append(x)
    if not xs:
        return 1
    return xs[0] if len(xs) == 1 else ("&&",) + tuple(xs)


def disj2(a, b):
    if isinstance(a, int):
        return 1 if a else b
    if isinstance(b, int):
        return 1 if b else a
    return ("||", a, b)


def disj(items) -> object:
    out = 0
    for x in items:
        out = disj2(out, x)
    return out


def branch_falls(c, f1, f2):
    """The condition under which control goes on after `if (c) S1 else S2`, given S1's and S2's."""
    if f1 == f2:
        return f1
    if f1 == 1 and f2 == 0:
        return c
    if f1 == 0 and f2 == 1:
        return neg(c)
    if f2 == 1:
        return disj2(neg(c), f1)
    if f1 == 1:
        return disj2(c, f2)
    if f1 == 0:
        return conj([neg(c), f2])
    if f2 == 0:
        return conj([c, f1])
    return ("||", conj([c, f1]), conj([neg(c), f2]))


def mentions_caller(t) -> bool:
    if t == ("caller",):
        return True
    return isinstance(t, tuple) and any(mentions_caller(x) for x in t[1:])


def mentions_symbols(t, spans) -> bool:
    """Whether t holds a loop symbol (carried, exit, iter, count, loop) of a loop named in spans."""
    stack = [t]
    while stack:
        x = stack.pop()
        if isinstance(x, tuple):
            if len(x) >= 2 and x[0] in SYMBOL_TAGS and x[1] in spans:
                return True
            stack.extend(x)
        elif isinstance(x, Ref):
            stack.extend(x.path)
    return False


def exact_fits(bits: int, signed: bool, e) -> int | None:
    op, *xs = e
    if not all(isinstance(x, int) for x in xs):
        return None
    vals = [_sgn(x) for x in xs] if signed else list(xs)
    if op == "+":
        r = vals[0] + vals[1]
    elif op == "-":
        r = vals[0] - vals[1]
    elif op == "*":
        r = vals[0] * vals[1]
    elif op == "neg":
        r = -vals[0]
    elif op == "sdiv":
        if vals[1] == 0:
            return 1
        q = abs(vals[0]) // abs(vals[1])
        r = -q if (vals[0] < 0) != (vals[1] < 0) else q
    elif op == "**":
        a, b = vals
        if abs(a) <= 1 or b <= 512:
            r = a ** b
        else:
            return 0
    else:
        return None
    lo, hi = ((-(1 << (bits - 1)), 1 << (bits - 1)) if signed else (0, 1 << bits))
    return int(lo <= r < hi)


def fits(bits: int, signed: bool, e):
    """["fits"|"sfits", bits, e] folded: constants exactly; x + 0, x - 0, x * 0, x * 1 always fit."""
    v = exact_fits(bits, signed, e)
    if v is not None:
        return v
    op = e[0]
    if op in ("+", "-") and e[2] == 0:
        return 1
    if op == "+" and e[1] == 0:
        return 1
    if op == "*" and (e[1] in (0, 1) or e[2] in (0, 1)):
        return 1
    return ("sfits" if signed else "fits", bits, e)


FOLD_OPS = frozenset({"+", "-", "*", "/", "%", "**", "&", "|", "^", "<<", ">>", "==", "!=", "<", "<=", ">", ">=",
                      "!", "~", "not", "neg", "s<", "s<=", "s>", "s>=", "sdiv", "smod", "sar", "addmod", "mulmod",
                      "trunc", "sext", "wbyte"})


def subst(t, x, k):
    """t with every occurrence of the term x replaced by k, refolded (binders of ["iter", loop] respected)."""
    if t == x:
        return k
    if isinstance(t, Ref):
        return Ref(t.fam, tuple((a, subst(b, x, k)) for a, b in t.path))
    if not isinstance(t, tuple) or not t:
        return t
    h = t[0]
    if h in ("mloop", "sum") and isinstance(x, tuple) and x[:1] == ("iter",) and x[1:2] == (t[1],):
        return t[:3] + (subst(t[3], x, k),) + t[4:]
    if h == "ptr":
        return ("ptr", t[1], subst(t[2], x, k))
    if h == "store":
        return ("store", subst(t[1], x, k), tuple((a[0], subst(a[1], x, k)) for a in t[2]), subst(t[3], x, k))
    if h == "struct":
        return ("struct", t[1], t[2], tuple(subst(v, x, k) for v in t[3]))
    if h in ("fits", "sfits"):
        e = t[2]
        return fits(t[1], h == "sfits", (e[0],) + tuple(subst(a, x, k) for a in e[1:]))
    if h == "writes":
        return ("writes",) + tuple(subst(w, x, k) for w in t[1:])
    args = tuple(subst(a, x, k) for a in t[1:])
    if args == t[1:]:
        return t
    if h == "?":
        return ite(*args)
    if h == "&&":
        return conj(args)
    if h == "||":
        return disj(args)
    if h in FOLD_OPS:
        return fold(h, *args)
    return (h,) + args


@dataclass(frozen=True)
class Ref:
    """A storage location: a state variable and an access path of ("map", key), ("index", i), ("member", name)."""
    fam: str
    path: tuple = ()


class _Renderer:
    """Terms as JSON (lists, ints, strings), simplified under known conditions (module docstring), with a budget."""

    def __init__(self, budget: int = TERM_BUDGET):
        self.left = budget

    @staticmethod
    def _lookup(known, c):
        k = known
        while k is not None:
            if k[0] == c:
                return k[1]
            k = k[2]
        if isinstance(c, tuple) and len(c) == 2 and c[0] == "!":
            v = _Renderer._lookup(known, c[1])
            return None if v is None else (not v)
        return None

    @staticmethod
    def _assume(known, c, v: bool):
        known = (c, v, known)
        if isinstance(c, tuple) and c:
            if c[0] == "!" and len(c) == 2:
                known = (c[1], not v, known)
            elif v and c[0] == "&&":
                for x in c[1:]:
                    known = _Renderer._assume(known, x, True)
            elif not v and c[0] == "||":
                for x in c[1:]:
                    known = _Renderer._assume(known, x, False)
        return known

    def go(self, t, known=None, cond=False):
        """t rendered under the known conditions; cond: t stands where only its truthiness counts (a condition: a
        guard's, check's or call's expr, a context, a loop's head, an operand of !, && and ||, the condition of a
        conditional or of a when, and the branches of a conditional that stands there), so a term known to hold or
        fail renders as 1 or 0."""
        self.left -= 1
        if self.left < 0:
            raise ExtractionError(f"a term exceeds the size budget of {TERM_BUDGET} nodes")
        if isinstance(t, bool):
            return int(t)
        if isinstance(t, int) or t is None or isinstance(t, str):
            return t
        if isinstance(t, Ref):
            return ["ref", t.fam, [self.go(list(a), known) for a in t.path]]
        if isinstance(t, list):
            return [self.go(x, known) for x in t]
        if not isinstance(t, tuple):
            raise ExtractionError(f"a value the document cannot hold: {t!r:.200}")
        h = t[0] if t else "tuple"
        if cond and known is not None:
            v = self._lookup(known, t)
            if v is not None:
                return int(v)
        if h == "?" and len(t) == 4:
            v = self._lookup(known, t[1])
            if v is True:
                return self.go(t[2], known, cond)
            if v is False:
                return self.go(t[3], known, cond)
            c = self.go(t[1], known, True)
            if isinstance(c, int):
                return self.go(t[2] if c else t[3], known, cond)
            a = self.go(t[2], self._assume(known, t[1], True), cond)
            b = self.go(t[3], self._assume(known, t[1], False), cond)
            return a if a == b else ["?", c, a, b]
        if h in ("||", "&&") and len(t) >= 3:
            out, k = [], known
            for x in t[1:]:
                v = self._lookup(k, x)
                if v is not None:
                    if (h == "||") == v:
                        return 1 if h == "||" else 0
                    continue
                r = self.go(x, k, True)
                if isinstance(r, int):
                    if (h == "||") == bool(r):
                        return 1 if h == "||" else 0
                    continue
                out.append(r)
                k = self._assume(k, x, h == "&&")
            if not out:
                return 0 if h == "||" else 1
            return out[0] if len(out) == 1 else [h] + out
        if h == "!" and len(t) == 2:
            r = self.go(t[1], known, True)
            return int(not r) if isinstance(r, int) else ["!", r]
        if h == "when" and len(t) == 3:
            c = self.go(t[1], known, True)
            return self.go(t[2], known) if c == 1 else ["when", c, self.go(t[2], known)]
        if h == "store":
            return ["store", self.go(t[1], known), [[a[0], self.go(a[1], known)] for a in t[2]], self.go(t[3], known)]
        if h == "ptr":
            return ["ptr", list(t[1][1]), self.go(t[2], known)]
        if h == "struct":
            return ["struct", t[1], [[m, self.go(v, known)] for m, v in zip(t[2], t[3])]]
        if h == "mloop":
            return ["mloop", t[1], self.go(t[2], known), self.go(t[3], known), [self.go(w, known) for w in t[4][1:]]]
        return [h] + [self.go(x, known) for x in t[1:]]


def render(t, cond: bool = False):
    """A term as JSON (lists, ints, strings), simplified (module docstring); cond: t is a condition (only its
    truthiness counts); ExtractionError over the budget."""
    try:
        return _Renderer().go(t, None, cond)
    except RecursionError as e:
        raise ExtractionError("a term is nested too deeply to render") from e


# ------------------------------------------------------------------------------------------------ frames and state
@dataclass
class Frame:
    fn: dict
    name: str
    vars: dict = field(default_factory=dict)
    zone: str = "body"                      # "modifier" inside a modifier's own code (and what it calls)
    mod_index: int | None = None            # the action modifier whose code this is (principal detection)
    is_action: bool = False
    returns: list = field(default_factory=list)   # [(local condition, value, storage, memory)]
    ctx_base: int = 0
    result: object = None
    placeholder: object = None
    yul: list = field(default_factory=list)
    yulfns: list = field(default_factory=list)
    asm: dict | None = None
    unchecked: int = 0
    stack_base: int = 0


@dataclass
class Snap:
    vars: dict
    yul: list
    storage: dict
    memory: dict


@dataclass
class LoopCtx:
    span: str
    r: int
    spans: set
    body_base: int = 0
    breaks: list = field(default_factory=list)
    conts: list = field(default_factory=list)
    seq: int | None = None
    count: object = None
    iter_t: object = None


@dataclass
class IterResult:
    head: object
    next: Snap | None
    breaks: list
    start: Snap
    exit_kind: str | None
    ran: bool
    rets: int = 0                           # return paths the iteration took (entries of the frame's returns)


class Collector:
    """What the walks of every action of one contract record for coverage (shared by the actions)."""

    def __init__(self):
        self.tags: dict[int, set] = {}
        self.defs: dict[int, set] = {}
        self.reads: set = set()
        self.debt: dict = {}                # (src, kind, detail) -> None, first record order
        self.reached: dict[int, dict] = {}  # function / modifier id -> node
        self.covered_by_debt: set = set()


def _sym(tag: str, span: str, r: int, *rest):
    return (tag, span) + rest + ((r,) if r else ())


# ------------------------------------------------------------------------------------------------ the walk
class Walk:
    """The walk of one action (see the module docstring)."""

    def __init__(self, index: Index, contract: dict, action: dict, coll: Collector, commit: list[str]):
        self.ix = index
        self.contract = contract
        self.action = action
        self.coll = coll
        self.commit = set(commit)
        self.frames: list[Frame] = []
        self.sites: list[str] = []          # spans of the inlined calls (memory regions are named by them)
        self.stack: list[str] = []          # spans of the inlined calls and modifier invocations (records)
        self.ctx: list = []
        self.storage: dict = {}
        self.memory: dict = {}
        self.exit: str | None = None
        self.recording = True
        self.stmts: list[int] = []
        self.regions = 0
        self.seq = 0
        self.guards: dict = {}
        self.effects: dict = {}
        self.cost: dict = {}
        self.edges: dict = {}
        self.principal: dict = {}
        self.written: list[str] = []
        self.checks: list = []
        self.panics: list = []
        self.calls: list = []
        self.writes: list = []
        self.mstores: list = []
        self.events: list = []
        self.loops: list = []
        self.order: list = []
        self.loopstack: list[LoopCtx] = []
        self.loop_reach: dict = {}
        self.dry = 0
        self.yul_returns: list = []
        self.try_node = None
        self.try_ok = None
        self.abi_seen: set = set()
        self.bools: set = set()             # the boolean leaves of this walk (is_bool; module docstring, "Booleans")

    # -- bookkeeping
    @property
    def frame(self) -> Frame:
        return self.frames[-1]

    def span(self, node: dict) -> str:
        return self.ix.span(node["src"])

    def r(self, t):
        return render(t)

    def rc(self, t):
        """A condition rendered (only its truthiness counts)."""
        return render(t, True)

    def tag(self, t: str, defs=()) -> None:
        if not self.recording or not self.stmts or self.stmts[-1] is None:
            return
        sid = self.stmts[-1]
        self.coll.tags.setdefault(sid, set()).add(t)
        if defs:
            self.coll.defs.setdefault(sid, set()).update(defs)

    def read_decl(self, decl) -> None:
        if self.recording:
            self.coll.reads.add(decl)

    def debt(self, kind: str, detail: str, node: dict) -> None:
        if not self.recording:
            return
        self.coll.debt.setdefault((self.span(node), kind, detail), None)
        self.tag("debt")

    def edge(self, kind: str, fn: str, node: dict) -> None:
        if not self.recording:
            return
        self.edges.setdefault((kind, fn, self.span(node)), None)
        self.tag("edge")

    def reach(self, fn: dict) -> None:
        if self.recording:
            self.coll.reached.setdefault(fn["id"], fn)

    def cur_loop(self):
        for lc in reversed(self.loopstack):
            if lc.seq is not None:
                return lc.seq
        return None

    def record(self, lst: list, src: str, **fields) -> dict | None:
        """Append a record (seq, src, stack, loop?, fields) to lst when recording."""
        if not self.recording:
            return None
        rec = {"seq": self.seq, "src": src, "stack": list(self.stack)}
        self.seq += 1
        loop = self.cur_loop()
        if loop is not None:
            rec["loop"] = loop
        rec.update(fields)
        lst.append(rec)
        return rec

    def snapshot(self) -> Snap:
        f = self.frame
        return Snap(dict(f.vars), [dict(s) for s in f.yul], dict(self.storage), dict(self.memory))

    def restore(self, s: Snap) -> None:
        f = self.frame
        f.vars = dict(s.vars)
        f.yul = [dict(x) for x in s.yul]
        self.storage = dict(s.storage)
        self.memory = dict(s.memory)

    def merge(self, c, a: Snap, b: Snap, keys: Snap) -> None:
        """The state after a two-way branch on c whose branches ended in a and b (keys: the state before it)."""
        self.restore(merge_snaps(c, a, b, keys))

    # -- the action
    def run(self) -> dict:
        global _BOOL_LEAVES
        saved = _BOOL_LEAVES
        _BOOL_LEAVES = self.bools
        try:
            return self._run()
        finally:
            _BOOL_LEAVES = saved

    def _run(self) -> dict:
        fn = self.action
        f = Frame(fn=fn, name=self.ix.fn_name(fn), is_action=True)
        for p in fn["parameters"]["parameters"]:
            f.vars[p["id"]] = ("param", p["name"])
            self.bool_leaves(("param", p["name"]), p.get("typeName") or {}, type_string(p))
        for p in fn["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.reach(fn)
        self.frames.append(f)
        try:
            self.entry_checks(fn)
        finally:
            self.frames.pop()
        v = self.chain_function(fn, f)
        return self.result(v)

    def bool_leaves(self, t, tn: dict, ts: str) -> None:
        """Register t (an entry parameter, validated by the ABI decoder) and the bool members of a struct t as
        boolean leaves."""
        if _bare(ts) == "bool":
            self.bools.add(t)
            return
        sd = struct_def(self.ix, tn)
        if sd is not None:
            for m in sd.get("members") or []:
                if _bare(type_string(m.get("typeName") or {}) or type_string(m)) == "bool":
                    self.bools.add(("member", t, m["name"]))

    def entry_checks(self, fn: dict) -> None:
        """callvalue (an action that is not payable) and the ABI range checks of value and memory parameters."""
        if fn.get("stateMutability") != "payable":
            self.check("callvalue", self.span(fn), ("==", ("env", "msg.value"), 0))
        params = fn["parameters"]["parameters"]
        if params and fn.get("kind") == "function":    # the decoder needs the head of the parameters' encoding
            # (a fallback's bytes parameter is the raw calldata: nothing is decoded)
            head = abi_head_size([abi_type(self.ix, p.get("typeName") or {}) for p in params])
            self.check("calldatasize", self.span(fn), (">=", ("env", "msg.data.length"), 4 + head))
        for p in fn["parameters"]["parameters"]:
            loc = p.get("storageLocation") or "default"
            if loc == "calldata":
                continue
            t = ("param", p["name"])
            c = abi_check(self.ix, t, p.get("typeName") or {}, type_string(p))
            if c is not None:
                self.check("abi", self.span(p), c, param=p["name"])
            sd = struct_def(self.ix, p.get("typeName") or {})
            if sd is not None and loc == "memory":
                for m in sd.get("members") or []:
                    c = abi_check(self.ix, ("member", t, m["name"]), m.get("typeName") or {}, type_string(m))
                    if c is not None:
                        self.check("abi", self.span(p), c, param=p["name"])

    def result(self, value) -> dict:
        fn = self.action
        mods = [m["modifierName"]["name"] for m in fn.get("modifiers") or []
                if m.get("kind", "modifierInvocation") == "modifierInvocation"]
        principal = None
        if self.principal:
            i = min(self.principal)
            principal = {"modifier": mods[i], "predicate": self.rc(self.principal[i])}
        effects = sorted(({"family": fam, "src": src} for fam, src in self.effects), key=lambda e: (e["src"],
                                                                                                    e["family"]))
        sel = fn.get("functionSelector")
        owner = self.ix.contract_of(fn)
        children: dict = {}
        for lst in (self.checks, self.panics, self.calls, self.writes, self.mstores, self.events, self.loops):
            for rec in lst:
                if "loop" in rec:
                    children.setdefault(rec["loop"], []).append(rec["seq"])
        for g in self.guards.values():
            for rc in g["reaches"]:
                if "loop" in rc:
                    children.setdefault(rc["loop"], []).append(rc["seq"])
        for lp in self.loops:
            lp["steps"] = sorted(children.get(lp["seq"], []))
        post = {}
        if self.exit is None:
            for fam in sorted(self.storage):
                v = self.storage[fam]
                if v != ("storage", fam):
                    pv = self.r(post_value(v))
                    if pv != ["storage", fam]:      # a family whose value, simplified, does not change is left out
                        post[fam] = pv
        cost = []
        for span, reaches in self.cost.items():
            total = 0
            for t in reaches:
                total = fold("+", total, t)
            cost.append({"loop": span, "iters": self.r(total)})
        return {
            "name": fn.get("name") or fn.get("kind"),
            "selector": ("0x" + sel) if sel else None,
            "src": self.span(fn),
            "declared_in": owner["name"] if owner else None,
            "modifiers": mods,
            "principal": principal,
            "guards": list(self.guards.values()),
            "effects": effects,
            "cost": {"terms": cost},
            "edges": [{"kind": k, "fn": f, "src": src} for (k, f, src) in self.edges],
            "params": params_of(self.ix, fn),
            "returns": self.r(self.return_words(value)) if value is not None and self.exit is None else None,
            "payable": fn.get("stateMutability") == "payable",
            "mutability": fn.get("stateMutability"),
            "checks": self.checks,
            "panics": self.panics,
            "calls": self.calls,
            "writes": self.writes,
            "mstores": self.mstores,
            "events": self.events,
            "loops": self.loops,
            "post": post,
            "order": self.order,
        }

    def return_words(self, value):
        """The action's return value as the ABI encoder writes it (abi_word per return parameter)."""
        rets = self.action["returnParameters"]["parameters"]
        if len(rets) == 1:
            return abi_word(type_string(rets[0]), value)
        if isinstance(value, tuple) and value[:1] == ("tuple",) and len(value) == len(rets) + 1:
            return ("tuple",) + tuple(abi_word(type_string(p), v) for p, v in zip(rets, value[1:]))
        return value

    def chain_function(self, fn: dict, f: Frame):
        """Walk fn's modifiers and body in the frame f (pushed here); returns fn's result."""
        mods = [m for m in fn.get("modifiers") or [] if m.get("kind", "modifierInvocation") == "modifierInvocation"]
        f.stack_base = len(self.stack)
        self.frames.append(f)
        try:
            self._chain(fn, f, mods, 0)
        finally:
            self.frames.pop()
        return f.result

    def _chain(self, fn: dict, f: Frame, mods: list, i: int) -> None:
        if i == len(mods):
            f.returns = []
            f.ctx_base = len(self.ctx)
            falls = self.block(fn["body"])
            f.result = self.finish(f, falls)
            return
        m = mods[i]
        mdef = self._modifier(m)
        if mdef is None or not mdef.get("body"):
            self.stmts.append(m["id"])
            try:
                self.debt("unsupported", "ModifierInvocation", m)
            finally:
                self.stmts.pop()
            self._chain(fn, f, mods, i + 1)
            return
        args = [self.ev(a) for a in m.get("arguments") or []]
        mf = Frame(fn=mdef, name=self.ix.fn_name(mdef), zone="modifier",
                   mod_index=(i if f.is_action else f.mod_index))
        for p, v in zip(mdef["parameters"]["parameters"], args):
            mf.vars[p["id"]] = self.bind(p, v)
        mf.placeholder = (fn, f, mods, i + 1)
        self.reach(mdef)
        self.stack.append(self.span(m))
        self.frames.append(mf)
        try:
            mf.returns = []
            mf.ctx_base = len(self.ctx)
            falls = self.block(mdef["body"])
            self.finish(mf, falls)
        finally:
            self.frames.pop()
            self.stack.pop()

    def _modifier(self, m: dict) -> dict | None:
        d = self.ix.nodes.get(m["modifierName"].get("referencedDeclaration"))
        if d is None or d.get("nodeType") != "ModifierDefinition":
            return None
        if d.get("virtual") or d.get("overrides"):
            for cid in self.contract.get("linearizedBaseContracts", []):
                for x in (self.ix.nodes.get(cid) or {}).get("nodes", []):
                    if x.get("nodeType") == "ModifierDefinition" and x.get("name") == d["name"] and x.get("body"):
                        return x
        return d

    def placeholder(self) -> None:
        fn, f, mods, j = self.frame.placeholder
        saved = self.stack
        self.stack = saved[:f.stack_base]
        self.frames.append(f)
        try:
            self._chain(fn, f, mods, j)
        finally:
            self.frames.pop()
            self.stack = saved

    def finish(self, f: Frame, falls):
        """The end of a body: merge its returns and its fall-through into the state; the body's value."""
        entries = list(f.returns)
        if self.exit is None:
            rets = f.fn.get("returnParameters", {}).get("parameters", []) if f.fn.get("nodeType") == \
                "FunctionDefinition" else []
            vals = [f.vars.get(p["id"], 0) for p in rets]
            v = None if not vals else (vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals))
            entries.append((falls, v, dict(self.storage), dict(self.memory)))
        f.returns = []
        if not entries:
            self.exit = "revert"
            return None
        self.exit = None
        _, v, st, mem = entries[-1]
        for c, vi, sti, memi in reversed(entries[:-1]):
            v = ite_value(c, vi, v)
            st = merge_storage(c, sti, st)
            mem = merge_memory(c, memi, mem)
        self.storage, self.memory = st, mem
        return v

    # -- statements
    def block(self, n: dict):
        base = len(self.ctx)
        falls = 1
        try:
            for s in n.get("statements") or []:
                if self.exit:
                    break
                f = self.stmt(s)
                if self.exit:
                    break
                if f != 1:
                    self.ctx.append(f)
                    falls = conj([falls, f])
        finally:
            del self.ctx[base:]
        return falls

    def stmt(self, n: dict):
        self.stmts.append(n["id"])
        try:
            return self._stmt(n)
        finally:
            self.stmts.pop()

    def _stmt(self, n: dict):
        nt = n["nodeType"]
        if nt == "Block":
            self.tag("control")
            return self.block(n)
        if nt == "UncheckedBlock":
            self.tag("control")
            self.frame.unchecked += 1
            try:
                return self.block(n)
            finally:
                self.frame.unchecked -= 1
        if nt == "ExpressionStatement":
            self.ev(n["expression"])
            return 1
        if nt == "VariableDeclarationStatement":
            self.var_decl(n)
            return 1
        if nt == "IfStatement":
            self.tag("control")
            return self.if_stmt(n)
        if nt == "Return":
            self.tag("control")
            return self.ret(n)
        if nt in ("Break", "Continue"):
            self.tag("control")
            self.loop_exit("break" if nt == "Break" else "continue")
            return 0
        if nt == "PlaceholderStatement":
            self.tag("control")
            if self.frame.placeholder is None:
                self.debt("unsupported", nt, n)
                return 1
            self.placeholder()
            return 1
        if nt == "EmitStatement":
            self.emit(n)
            return 1
        if nt == "RevertStatement":
            call = n["errorCall"]
            name = call["expression"].get("name") or call["expression"].get("memberName")
            ea = self.error_of(call)
            if ea is None:
                for a in call.get("arguments") or []:
                    self.val(self.ev(a))
            self.guard("revert", n, None, name, data=ea)
            self.exit = "revert"
            return 1
        if nt == "InlineAssembly":
            self.assembly(n)
            return 1
        if nt in LOOPS:
            return self.loop(n)
        if nt == "TryStatement":
            return self.try_stmt(n)
        self.unsupported(n, nt)
        return 1

    def unsupported(self, n: dict, what: str) -> None:
        """A statement the walk does not represent: debt; the locals it may assign are havocked; the statements
        nested in it count as that debt; every memory region gets an ["unknown", span] entry."""
        self.debt("unsupported", what, n)
        self.havoc_memory(n)
        if self.recording:
            stack = [n]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    if x is not n and x.get("nodeType") in STATEMENTS and isinstance(x.get("id"), int):
                        self.coll.covered_by_debt.add(x["id"])
                    stack.extend(v for k, v in x.items() if k != "AST" and isinstance(v, (dict, list)))
                elif isinstance(x, list):
                    stack.extend(x)
        self.havoc(n)

    def havoc_memory(self, n: dict) -> None:
        span = self.span(n)
        for r in list(self.memory):
            self.memory[r] = mem_append(self.memory[r], ("unknown", span))

    def havoc(self, n: dict) -> None:
        span = self.span(n)
        stack = [n]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                nt = x.get("nodeType")
                if nt == "Assignment":
                    for d in _lvalue_decls(x.get("leftHandSide")):
                        self._havoc_decl(d, span)
                elif nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete"):
                    for d in _lvalue_decls(x.get("subExpression")):
                        self._havoc_decl(d, span)
                elif nt == "YulAssignment":
                    for v in x.get("variableNames", []):
                        self._havoc_yul(v, span)
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)

    def _havoc_decl(self, d, span: str) -> None:
        if d in self.frame.vars:
            node = self.ix.nodes.get(d) or {}
            self.frame.vars[d] = ("unknown", span, node.get("name", ""))

    def _havoc_yul(self, ident: dict, span: str) -> None:
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                scope[name] = ("unknown", span, name)
                return
        ref = _external_ref(self.frame.asm, ident)
        if ref is not None:
            self._havoc_decl(ref["declaration"], span)

    def var_decl(self, n: dict) -> None:
        decls = n.get("declarations") or []
        ids = [d["id"] for d in decls if d is not None]
        self.tag("local", ids)
        if n.get("initialValue") is None:
            for d in decls:
                if d is not None:
                    self.frame.vars[d["id"]] = 0
            return
        v = self.ev(n["initialValue"])
        if len(decls) == 1:
            if decls[0] is not None:
                self.frame.vars[decls[0]["id"]] = self.bind(decls[0], v)
            return
        for d, x in zip(decls, components(v, len(decls))):
            if d is not None:
                self.frame.vars[d["id"]] = self.bind(d, x)

    def bind(self, decl: dict, v):
        """A value bound to a parameter or local: storage pointers keep their location, anything else its value."""
        if isinstance(v, Ref) and decl.get("storageLocation") == "storage":
            return v
        return self.val(v)

    def if_stmt(self, n: dict):
        c = self.val(self.ev(n["condition"]))
        if isinstance(c, int):
            if c:
                return self.stmt(n["trueBody"])
            return self.stmt(n["falseBody"]) if n.get("falseBody") is not None else 1
        fb = n.get("falseBody")
        return self.branch(c, lambda: self.stmt(n["trueBody"]), (lambda: self.stmt(fb)) if fb is not None else None)

    def branch(self, c, run_true, run_false):
        """A two-way branch on the (non-constant) condition c; the condition under which control goes on."""
        before = self.snapshot()
        self.ctx.append(c)
        try:
            f1 = run_true()
        finally:
            self.ctx.pop()
        e1, s1 = self.exit, self.snapshot()
        self.exit = None
        self.restore(before)
        f2 = 1
        if run_false is not None:
            self.ctx.append(neg(c))
            try:
                f2 = run_false()
            finally:
                self.ctx.pop()
        e2, s2 = self.exit, self.snapshot()
        self.exit = None
        if e1 and e2:
            self.restore(s2)
            self.exit = "revert" if e1 == e2 == "revert" else ("return" if "return" in (e1, e2) else
                                                                (e1 if e1 != "revert" else e2))
            return 0
        if e1:
            self.restore(s2)
        elif e2:
            self.restore(s1)
        else:
            self.merge(c, s1, s2, before)
        g1 = 1 if e1 == "revert" else (0 if e1 else f1)
        g2 = 1 if e2 == "revert" else (0 if e2 else f2)
        return branch_falls(c, g1, g2)

    def ret(self, n: dict):
        f = self.frame
        v = None
        rets = f.fn.get("returnParameters", {}).get("parameters", []) if f.fn.get("nodeType") == \
            "FunctionDefinition" else []
        if n.get("expression") is not None:
            v = self.ev(n["expression"])
            if len(rets) == 1:
                v = self.bind(rets[0], v)
            elif isinstance(v, tuple) and v[:1] == ("tuple",):
                v = ("tuple",) + tuple(self.bind(p, x) for p, x in zip(rets, v[1:]))
            else:
                v = self.val(v)
        else:
            vals = [f.vars.get(p["id"], 0) for p in rets]
            v = None if not vals else (vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals))
        if self.exit:
            return 0
        f.returns.append((conj(self.ctx[f.ctx_base:]), v, dict(self.storage), dict(self.memory)))
        self.exit = "return"
        return 0

    def try_stmt(self, n: dict):
        self.tag("control")
        call = n["externalCall"]
        saved = self.try_node
        self.try_node, self.try_ok = call.get("id"), None
        try:
            v = self.ev(call)
        finally:
            self.try_node = saved
        if self.exit:
            return 1
        ok = self.try_ok if self.try_ok is not None else ("callok", "?")
        clauses = n.get("clauses") or []
        succ, catches = clauses[0], clauses[1:]

        def run_success():
            params = ((succ.get("parameters") or {}).get("parameters")) or []
            if params:
                for p, x in zip(params, components(v, len(params))):
                    if p is not None:
                        self.frame.vars[p["id"]] = self.bind(p, x)
            return self.stmt(succ["block"])

        def run_catch(i):
            if i >= len(catches):
                self.check("uncaught", self.span(n), 0)
                self.exit = "revert"
                return 1
            cl = catches[i]
            name = cl.get("errorName") or ""
            params = ((cl.get("parameters") or {}).get("parameters")) or []

            def body():
                for p in params:
                    if p is not None:
                        self.frame.vars[p["id"]] = ("revertdata", name or "bytes", ok)
                return self.stmt(cl["block"])
            if not name:
                return body()
            return self.branch(("caught", name, ok), body, lambda: run_catch(i + 1))
        return self.branch(ok, run_success, lambda: run_catch(0))

    # -- guards and checks
    def reason(self, a: dict):
        """(reason, data) of the reason argument a of require or revert: data is (error, args), the revert data's
        error and argument values (module docstring, guards[].error): a custom error E(...) gives E's error_of and
        reason E; a string gives Error(string) with its value, and reason its text when it is a constant (else
        null)."""
        if a.get("nodeType") == "FunctionCall":
            ea = self.error_of(a)
            if ea is not None:
                ex = a.get("expression") or {}
                return ex.get("name") or ex.get("memberName"), ea
        rv = self.val(self.ev(a))
        if a.get("nodeType") == "Literal" and a.get("kind") in ("string", "unicodeString"):
            return a.get("value") or "", (error_string(), [rv])
        if isinstance(rv, tuple) and rv[:1] == ("str",):
            return _text(rv), (error_string(), [rv])
        return None, (error_string(), [rv])

    def guard(self, kind: str, node: dict, cond, reason, code=None, data=None) -> None:
        """A require, assert or revert reached (module docstring, guards); data: (error, args) of its revert data
        (reason), None when it reverts with no data (or with Panic(0x01): code 1)."""
        f = self.frame
        if kind == "require" and f.zone == "modifier" and f.mod_index is not None and self.recording \
                and mentions_caller(cond):
            if f.mod_index not in self.principal:
                self.principal[f.mod_index] = cond
            self.tag("principal")
        if kind == "revert" and f.zone == "modifier" and f.mod_index is not None and self.recording:
            local = conj(self.ctx[f.ctx_base:])
            if mentions_caller(local):
                if f.mod_index not in self.principal:
                    self.principal[f.mod_index] = neg(local)
                self.tag("principal")
        if not self.recording:
            return
        self.tag("guard")
        span = self.span(node)
        k = conj(self.ctx)
        if kind == "revert":
            expr = neg(k)
        else:
            expr = cond if k == 1 else disj2(neg(k), cond)
        reach = {"seq": self.seq, "stack": list(self.stack), "expr": self.rc(expr)}
        self.seq += 1
        loop = self.cur_loop()
        if loop is not None:
            reach["loop"] = loop
        if code is not None:
            reach["code"] = code
        if data is not None:
            reach["args"] = [self.r(a) for a in data[1]]
        entry = self.guards.get(span)
        if entry is None:
            entry = {"src": span, "kind": "modifier" if f.zone == "modifier" else kind, "reason": reason,
                     "expr": reach["expr"], "reaches": []}
            if data is not None:
                entry["error"] = dict(data[0])
                entry["args"] = reach["args"]
            self.guards[span] = entry
        entry["reaches"].append(reach)
        self.order.append(["guard", span, len(entry["reaches"]) - 1])

    def check(self, kind: str, src: str, c, **extra) -> None:
        """An implicit check that is not a panic (module docstring); c the condition under which it passes."""
        if c == 1 or not self.recording:
            return
        k = conj(self.ctx)
        expr = c if k == 1 else (neg(k) if c == 0 else disj2(neg(k), c))
        rendered = self.rc(expr)
        if kind == "abi":
            key = repr(rendered)
            if key in self.abi_seen:
                return
            self.abi_seen.add(key)
        self.record(self.checks, src, kind=kind, expr=rendered, **extra)
        self.order.append(["check", len(self.checks) - 1])

    def panic(self, code: int, node: dict, op: str, args: list, c) -> None:
        """A checked operation: it panics with code unless c holds (module docstring)."""
        if c == 1:
            return
        if self.recording:
            k = conj(self.ctx)
            expr = c if k == 1 else (neg(k) if c == 0 else disj2(neg(k), c))
            self.record(self.panics, self.span(node), code=code, op=op, args=[self.r(a) for a in args],
                        expr=self.rc(expr))
            self.order.append(["panic", len(self.panics) - 1])
        if c == 0:
            self.exit = "revert"

    # -- loops
    def loop_exit(self, kind: str) -> None:
        """break / continue: the state and condition of the leaving path go to the innermost loop."""
        if self.loopstack:
            lc = self.loopstack[-1]
            cond = conj(self.ctx[lc.body_base:])
            (lc.breaks if kind == "break" else lc.conts).append((cond, self.snapshot()))
        self.exit = kind

    def loop(self, n: dict):
        span = self.span(n)
        nt = n["nodeType"]
        f = self.frame
        if nt == "YulForLoop":
            pre = n.get("pre") or {}
            f.yul.append({})
            f.yulfns.append(_yul_functions(pre))
            try:
                for s in pre.get("statements") or []:
                    if self.exit:
                        break
                    self.yul_stmt(s)
                if self.exit:
                    return 1
                return self._loop(n, span)
            finally:
                f.yul.pop()
                f.yulfns.pop()
        if nt == "ForStatement" and n.get("initializationExpression") is not None:
            self.stmt(n["initializationExpression"])
            if self.exit:
                return 1
        return self._loop(n, span)

    def _reach_index(self, span: str) -> int:
        if self.recording:
            r = self.loop_reach.get(span, 0)
            self.loop_reach[span] = r + 1
            return r
        self.dry += 1
        return -self.dry

    def _keys(self, snaps: list) -> list:
        """The names a loop may carry: the frame's locals, the Yul variables in scope, the families and the regions
        that exist before it (families also when a state below writes them)."""
        before = snaps[0]
        keys = [("v", k) for k in before.vars]
        for i, scope in enumerate(before.yul):
            keys += [("y", i, name) for name in scope]
        fams = set(before.storage)
        for s in snaps[1:]:
            if s is not None:
                fams |= set(s.storage)
        keys += [("s", fam) for fam in sorted(fams)]
        keys += [("m", r) for r in sorted(before.memory, key=lambda r: r[0])]
        return keys

    @staticmethod
    def _get(snap: Snap, k):
        t = k[0]
        if t == "v":
            return snap.vars.get(k[1])
        if t == "y":
            return snap.yul[k[1]].get(k[2]) if k[1] < len(snap.yul) else None
        if t == "s":
            return snap.storage.get(k[1], ("storage", k[1]))
        return snap.memory.get(k[1])

    def _set(self, k, v) -> None:
        t = k[0]
        if t == "v":
            self.frame.vars[k[1]] = v
        elif t == "y":
            self.frame.yul[k[1]][k[2]] = v
        elif t == "s":
            if v == ("storage", k[1]):
                self.storage.pop(k[1], None)
            else:
                self.storage[k[1]] = v
        else:
            self.memory[k[1]] = v

    def _display(self, k, names: dict):
        if k[0] == "v":
            return names.get(k, (self.ix.nodes.get(k[1]) or {}).get("name", str(k[1])))
        if k[0] == "y":
            return names.get(k, k[2])
        if k[0] == "s":
            return ("storage", k[1])
        return ("mem", k[1][1])

    def _names(self, keys: list) -> dict:
        """Display names of local and Yul keys, disambiguated (name#id) when two share a name."""
        raw = {}
        for k in keys:
            if k[0] == "v":
                raw[k] = (self.ix.nodes.get(k[1]) or {}).get("name", str(k[1]))
            elif k[0] == "y":
                raw[k] = k[2]
        out = {}
        for k, nm in raw.items():
            dup = sum(1 for x in raw.values() if x == nm) > 1
            out[k] = f"{nm}#{k[1] if k[0] == 'v' else k[1]}" if dup else nm
        return out

    def _carried_value(self, k, before: Snap, lc: LoopCtx, names: dict):
        v0 = self._get(before, k)
        if k[0] == "m":
            return mem_append(v0, _sym("loop", lc.span, lc.r))
        name = self._display(k, names)
        if k[0] in ("v", "y") and is_ptr(v0):
            return ("ptr", v0[1], _sym("carried", lc.span, lc.r, name))
        return _sym("carried", lc.span, lc.r, name)

    def _iterate(self, n: dict, kind: str, before: Snap, binding: dict, lc: LoopCtx) -> IterResult:
        """One generic iteration from before with the carried names bound (binding)."""
        self.restore(before)
        for k, v in binding.items():
            self._set(k, v)
        start = self.snapshot()
        lc.breaks, lc.conts = [], []
        self.loopstack.append(lc)
        base = len(self.ctx)
        nret = len(self.frame.returns)
        head, nxt, exit_kind, ran = 1, None, None, True
        try:
            if kind != "dowhile":
                head = self._head(n, kind)
                if self.exit:
                    return IterResult(0, None, [], start, self.exit, False)
                if isinstance(head, int) and not head:
                    return IterResult(0, None, [], start, None, False)
                if not isinstance(head, int):
                    self.ctx.append(head)
            lc.body_base = len(self.ctx)
            f = self._body(n, kind)
            ex, self.exit = self.exit, None
            conts = list(lc.conts)
            if ex is None:
                conts.append((f, self.snapshot()))
            elif ex not in ("break", "continue"):
                exit_kind = ex
            breaks = list(lc.breaks)
            if conts:
                self.restore(merge_list(conts, start))
                ccond = disj([c for c, _ in conts])
                if ccond != 1:
                    self.ctx.append(ccond)
                if kind == "for" and n.get("loopExpression") is not None:
                    self.stmt(n["loopExpression"])
                elif kind == "yulfor":
                    self.yul_block(n.get("post") or {})
                elif kind == "dowhile":
                    head = self.val(self.ev(n["condition"])) if n.get("condition") is not None else 1
                if self.exit:
                    exit_kind, self.exit = self.exit, None
                elif not (kind == "dowhile" and isinstance(head, int) and not head):
                    nxt = self.snapshot()
            return IterResult(head, nxt, breaks, start, exit_kind, ran, len(self.frame.returns) - nret)
        finally:
            del self.ctx[base:]
            self.loopstack.pop()
            self.exit = None

    def _head(self, n: dict, kind: str):
        if kind == "yulfor":
            c = self.yul_expr(n["condition"])
            return c if isinstance(c, int) or is_bool(c) else fold("!=", c, 0)
        if n.get("condition") is None:
            return 1
        return self.val(self.ev(n["condition"]))

    def _body(self, n: dict, kind: str):
        if kind == "yulfor":
            return self.yul_block(n["body"])
        return self.stmt(n["body"])

    def _loop(self, n: dict, span: str):
        kind = LOOP_KIND[n["nodeType"]]
        rec_outer = self.recording
        r = self._reach_index(span)
        for outer in self.loopstack:
            outer.spans.add(span)
        lc = LoopCtx(span=span, r=r, spans={span})
        before = self.snapshot()
        nret, nwritten = len(self.frame.returns), len(self.written)
        K = conj(self.ctx)
        # 1. the carried set: a fixpoint of dry runs
        self.recording = False
        carried: list = []
        names: dict = {}
        try:
            res = it0 = None

            def dry():
                del self.frame.returns[nret:]
                del self.written[nwritten:]
                b = {k: self._carried_value(k, before, lc, names) for k in carried}
                return self._iterate(n, kind, before, b, lc)
            for _ in range(MAX_FIXPOINT):
                res = dry()
                if it0 is None:
                    it0 = res
                if res.next is None:
                    break
                new = [k for k in self._keys([before, res.next])
                       if k not in carried and self._get(res.next, k) != self._get(res.start, k)]
                if not new:
                    break
                carried = carried + new
            else:
                raise ExtractionError(f"loop {span}: the carried set does not reach a fixpoint")
            names = self._names(carried)
            if any(names[k] != self._display(k, {}) for k in names):
                res = dry()                 # the carried symbols are renamed (two names alike): walk them again
            fams = sorted(set(self.written[nwritten:]))
        finally:
            self.recording = rec_outer
            self.restore(before)
            del self.frame.returns[nret:]
            del self.written[nwritten:]
        # 2. closed forms and the count
        iter_t = _sym("iter", span, r)
        syms = {k: self._carried_value(k, before, lc, names) for k in carried}
        closed, steps = {}, {}
        if res.next is not None:
            for k in carried:
                if k[0] not in ("v", "y"):
                    continue
                d = affine_step(self._get(res.next, k), syms[k], lc.spans)
                if d is not None:
                    steps[k] = d
                    closed[k] = closed_form(self._get(before, k), d, iter_t)
        has_break = bool(res.breaks)
        has_return = res.rets > 0
        bound = None
        if res.next is not None and kind in ("for", "while", "yulfor"):
            bound = header_count(res.head, syms, steps, before, self._get, lc.spans)
        if res.next is None:
            head0 = it0.head
            count_t = ite(head0, 1, 0) if not isinstance(head0, int) else int(bool(head0))
        elif bound is not None and not has_break and not has_return:
            count_t = bound
        else:
            count_t = _sym("count", span, r)
        lc.count, lc.iter_t = count_t, iter_t
        # 3. the recording pass (or the final dry pass inside an enclosing dry run)
        binding = {k: (closed[k] if k in closed else syms[k]) for k in carried}
        rec = None
        if self.recording:
            rec = {"seq": self.seq, "src": span, "stack": list(self.stack)}
            self.seq += 1
            outer = self.cur_loop()
            if outer is not None:
                rec["loop"] = outer
            self.loops.append(rec)
            self.order.append(["loop", len(self.loops) - 1])
            lc.seq = rec["seq"]
            if not fams:
                self.tag("cost")
                self.cost.setdefault(span, [])      # cost terms in first-reach order (outer loops first)
        nret_rec = len(self.frame.returns)
        fin = self._iterate(n, kind, before, binding, lc)
        lc.seq = None
        returns = []
        if res.next is not None and len(self.frame.returns) > nret_rec:
            # a return in the generic iteration: the function returns at the iteration that leaves the loop
            for j, (c, v, st, mem) in enumerate(list(self.frame.returns[nret_rec:])):
                returns.append({"cond": self.rc(c), "value": self.r(v) if v is not None else None})
                self.frame.returns[nret_rec + j] = self._loop_return(j, c, v, st, mem, before, lc, count_t)
        if fams:
            self.debt("loop_storage_write", ", ".join(fams), n)
        elif self.recording:
            iters = bound if bound is not None else count_t
            term = ite(K, iters, 0)
            for outer in reversed(self.loopstack):
                if outer.count is not None and term != 0:
                    term = ("sum", outer.span, outer.iter_t, outer.count, term)
            self.cost.setdefault(span, []).append(term)
        # 4. the state after the loop
        brk = merge_list(fin.breaks, fin.start) if fin.breaks else None
        exit_keys = list(carried)
        if brk is not None:
            for k in self._keys([before, brk]):
                if k not in exit_keys and self._get(brk, k) != self._get(fin.start, k):
                    exit_keys.append(k)
        self.restore(before)
        falls = 1
        exits = {}
        only_break = has_break and isinstance(fin.head, int) and fin.head == 1
        if fin.next is None and res.next is None:
            # the iteration never continues: at most one iteration (iteration 0), left by break, return or revert
            head0 = it0.head
            if brk is not None:
                self.restore(merge_snaps(head0, brk, before, before) if not isinstance(head0, int) else
                             (brk if head0 else before))
                for k in exit_keys:
                    exits[k] = self._get(self.snapshot(), k)
            elif isinstance(head0, int) and head0:
                self.exit = fin.exit_kind or "revert"
                falls = 0
            else:   # control goes on when the loop does not run (a reverting iteration is a check, as for an if)
                falls = neg(head0) if not isinstance(head0, int) and fin.exit_kind != "revert" else 1
        else:
            falls = conj([neg(_sym("returned", span, r, j)) for j in range(len(returns))])
            for k in exit_keys:
                if k[0] == "m":
                    v = self._region_exit(k, before, fin, brk, count_t, iter_t, lc, only_break, has_break)
                elif k in closed and not has_break:
                    v = subst(closed[k], iter_t, count_t)
                elif only_break and brk is not None and k[0] in ("v", "y") \
                        and not mentions_symbols(self._get(brk, k), lc.spans - {span}) \
                        and not _mentions_carried(self._get(brk, k), span):
                    v = subst(self._get(brk, k), iter_t, count_t)
                else:
                    v0 = self._get(before, k)
                    name = self._display(k, names)
                    v = ("ptr", v0[1], _sym("exit", span, r, name)) if is_ptr(v0) and \
                        is_ptr(self._get(fin.start, k)) else _sym("exit", span, r, name)
                exits[k] = v
                self._set(k, v)
        if rec is not None:
            rec.update({
                "kind": kind,
                "cond": self.rc(K),
                "carried": sorted(({"name": self.r(self._display(k, names)), "entry": self.r(self._get(before, k)),
                                    "value": self.r(binding[k])} for k in carried if k[0] != "m"),
                                  key=lambda e: repr(e["name"])),
                "regions": [{"region": list(k[1][1]), "writes": self._region_writes(k, fin, lc)}
                            for k in carried if k[0] == "m"],
                "head": self.rc(fin.head),
                "next": sorted(({"name": self.r(self._display(k, names)), "value": self.r(self._get(fin.next, k))}
                                for k in carried if k[0] != "m" and fin.next is not None),
                               key=lambda e: repr(e["name"])),
                "break": self.rc(disj([c for c, _ in fin.breaks])),
                "at_break": sorted(({"name": self.r(self._display(k, names)), "value": self.r(self._get(brk, k))}
                                    for k in exit_keys if k[0] != "m" and brk is not None),
                                   key=lambda e: repr(e["name"])),
                "count": self.r(count_t),
                "bound": self.r(bound) if bound is not None else None,
                "exit": sorted(({"name": self.r(self._display(k, names)), "value": self.r(v)}
                                for k, v in exits.items() if k[0] != "m"), key=lambda e: repr(e["name"])),
                "returns": returns,
            })
        return falls

    def _loop_return(self, j: int, c, v, st: dict, mem: dict, before: Snap, lc: LoopCtx, count_t):
        """A return path j of a loop's generic iteration, as the enclosing function sees it: taken when the loop is
        left by it (["returned", loop, j]), its value and state at the iteration count when they have a closed form,
        else exit terms (["exit", loop, ["return", j]], ["exit", loop, ["storage", f]]; a region gets a loop entry)."""
        span, r = lc.span, lc.r
        iter_t = _sym("iter", span, r)

        def at(t, name):
            if _mentions_carried(t, span) or mentions_symbols(t, lc.spans - {span}):
                return _sym("exit", span, r, name)
            return subst(t, iter_t, count_t)
        v2 = at(v, ("return", j)) if v is not None else None
        st2 = {}
        for fam, x in st.items():
            st2[fam] = x if x == before.storage.get(fam) else at(x, ("storage", fam))
        mem2 = {}
        for rid, x in mem.items():
            if rid not in before.memory or x == before.memory[rid]:
                mem2[rid] = x
            elif _mentions_carried(x, span) or mentions_symbols(x, lc.spans - {span}):
                mem2[rid] = mem_append(before.memory[rid], _sym("loop", span, r))
            else:
                mem2[rid] = subst(x, iter_t, count_t)
        return (_sym("returned", span, r, j), v2, st2, mem2)

    def _region_writes(self, k, fin: IterResult, lc: LoopCtx):
        ws = _appended(fin.start and self._get(fin.start, k), fin.next and self._get(fin.next, k))
        if ws is None or any(_mentions_carried(w, lc.span) for w in ws):
            return None
        return [self.r(w) for w in ws]

    def _region_exit(self, k, before, fin, brk, count_t, iter_t, lc, only_break, has_break):
        v0 = self._get(before, k)
        start = self._get(fin.start, k)
        loop_entry = _sym("loop", lc.span, lc.r)
        ws = _appended(start, self._get(fin.next, k) if fin.next is not None else start)
        ok = ws is not None and not any(_mentions_carried(w, lc.span) or mentions_symbols(w, lc.spans - {lc.span})
                                        for w in ws)
        if ok and (not has_break or only_break):
            out = v0
            if count_t != 0 and ws:
                out = mem_append(v0, ("mloop", lc.span, iter_t, count_t, ("writes",) + tuple(ws)))
            if has_break:
                bw = _appended(start, self._get(brk, k))
                if bw is None or any(_mentions_carried(w, lc.span) or mentions_symbols(w, lc.spans - {lc.span})
                                     for w in bw):
                    return mem_append(v0, loop_entry)
                for w in bw:
                    out = mem_append(out, subst(w, iter_t, count_t))
            return out
        return mem_append(v0, loop_entry)

    # -- expressions
    def val(self, v):
        """The value of an evaluation result: a storage location is read."""
        if isinstance(v, Ref):
            return self.read(v)
        return v

    def read(self, r: Ref):
        base = self.storage.get(r.fam, ("storage", r.fam))
        return resolve(base, r.path)

    def write(self, r: Ref, v, node: dict) -> None:
        v = self.val(v)
        cur = self.storage.get(r.fam, ("storage", r.fam))
        if not r.path:
            new = ("store", ("storage", r.fam), (), v)
        else:
            if isinstance(cur, tuple) and cur[:1] == ("store",) and cur[2] == r.path:
                cur = cur[1]
            new = ("store", cur, r.path, v)
        self.storage[r.fam] = new
        self.written.append(r.fam)    # every write, recorded or not (a loop's dry run reads it)
        if self.recording:
            span = self.span(node)
            self.effects.setdefault((r.fam, span), None)
            self.record(self.writes, span, family=r.fam, path=[[a[0], self.r(a[1])] for a in r.path],
                        value=self.r(v), cond=self.rc(conj(self.ctx)))
            self.tag("effect")

    def ev(self, n: dict):
        nt = n["nodeType"]
        if nt == "Literal":
            return literal_value(n)
        if nt == "Identifier":
            return self.identifier(n)
        if nt == "MemberAccess":
            return self.member(n)
        if nt == "IndexAccess":
            return self.index_access(n)
        if nt == "IndexRangeAccess":
            base = self.val(self.ev(n["baseExpression"]))
            lo = self.val(self.ev(n["startExpression"])) if n.get("startExpression") else 0
            hi = self.val(self.ev(n["endExpression"])) if n.get("endExpression") else ("len", base)
            self.check("slice", self.span(n), conj([fold("<=", lo, hi), fold("<=", hi, ("len", base))]))
            return ("range", base, lo, hi)
        if nt == "BinaryOperation":
            op = n["operator"]
            if op in ("&&", "||"):
                return self.short_circuit(n, op)
            a = self.val(self.ev(n["leftExpression"]))
            b = self.val(self.ev(n["rightExpression"]))
            ts = (n.get("commonType") or {}).get("typeString") or type_string(n)
            if op in ("+", "-", "*", "/", "%", "**", "<<", ">>"):
                return self.arith(op, a, b, ts, n)
            if op in ("==", "!=") and _bare(ts) == "bool":     # the compiler compares cleaned bools
                a, b = clean_bool(a), clean_bool(b)
            if op in SIGNED_CMP and _is_signed(ts):
                return fold(SIGNED_CMP[op], a, b)
            return fold(op, a, b)
        if nt == "UnaryOperation":
            return self.unary(n)
        if nt == "Conditional":
            return self.conditional(n)
        if nt == "TupleExpression":
            if n.get("isInlineArray"):
                return ("array",) + tuple(abi_word(type_string(c), self.val(self.ev(c))) for c in n.get("components") or [])
            comps = n.get("components") or []
            vals = [self.ev(c) if c is not None else None for c in comps]
            return vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals)
        if nt == "FunctionCall":
            return self.call(n)
        if nt == "Assignment":
            return self.assign(n)
        if nt == "ElementaryTypeNameExpression":
            return ("type", type_string(n))
        self.unsupported_expr(n, nt)
        return ("unknown", self.span(n), nt)

    def short_circuit(self, n: dict, op: str):
        a = self.val(self.ev(n["leftExpression"]))
        right = n["rightExpression"]
        if isinstance(a, int):
            if (op == "&&" and not a) or (op == "||" and a):
                return 0 if op == "&&" else 1
            return fold(op, a, self.val(self.ev(right)))
        c = a if op == "&&" else neg(a)
        before = self.snapshot()
        self.ctx.append(c)
        try:
            b = self.val(self.ev(right))
        finally:
            self.ctx.pop()
        if self.exit:                       # the right operand always reverts: control goes on when it does not run
            self.exit = None
            self.restore(before)
            return 0 if op == "&&" else 1
        after = self.snapshot()
        if after != before:
            self.merge(c, after, before, before)
        return fold(op, a, b)

    def conditional(self, n: dict):
        c = self.val(self.ev(n["condition"]))
        if isinstance(c, int):
            return self.val(self.ev(n["trueExpression"] if c else n["falseExpression"]))
        before = self.snapshot()
        self.ctx.append(c)
        try:
            a = self.val(self.ev(n["trueExpression"]))
        finally:
            self.ctx.pop()
        e1, s1 = self.exit, self.snapshot()
        self.exit = None
        self.restore(before)
        self.ctx.append(neg(c))
        try:
            b = self.val(self.ev(n["falseExpression"]))
        finally:
            self.ctx.pop()
        e2, s2 = self.exit, self.snapshot()
        self.exit = None
        if e1 and e2:
            self.restore(s2)
            self.exit = "revert"
            return 0
        if e1:
            self.restore(s2)
            return b
        if e2:
            self.restore(s1)
            return a
        if s1 != before or s2 != before:
            self.merge(c, s1, s2, before)
        return ite(c, a, b)

    def arith(self, op: str, a, b, ts: str, node: dict):
        """A Solidity arithmetic or shift operator on values of type ts: its panics and its value."""
        info = int_info(ts)
        if info is None:
            return fold(op, a, b)
        bits, signed = info
        if op in ("/", "%"):
            self.panic(18, node, op, [a, b], fold("!=", b, 0))
        checked = not self.frame.unchecked
        if checked and (op in ("+", "-", "*", "**") or (signed and op == "/")):
            eop = "sdiv" if op == "/" else op
            self.panic(17, node, op, [a, b], fits(bits, signed, (eop, a, b)))
        sop = {"/": "sdiv", "%": "smod", ">>": "sar"}.get(op, op) if signed else op
        v = fold(sop, a, b)
        if bits < 256 and (op == "<<" or (not checked and op in ("+", "-", "*", "**"))):
            v = fold("sext" if signed else "trunc", bits, v)
        return v

    def unsupported_expr(self, n: dict, what: str) -> None:
        self.debt("unsupported", what, n)
        self.havoc(n)

    def identifier(self, n: dict):
        ref = n.get("referencedDeclaration")
        name = n.get("name")
        if ref in self.frame.vars:
            self.read_decl(ref)
            return self.frame.vars[ref]
        if ref is None or ref < 0:
            if name in ("msg", "block", "tx", "abi", "this", "super", "bytes", "string"):
                return ("this",) if name == "this" else ("global", name)
            if name == "now":
                return ("env", "block.timestamp")
            return ("global", name)
        d = self.ix.nodes.get(ref)
        if d is None:
            return ("unknown", self.span(n), name)
        nt = d.get("nodeType")
        if nt == "VariableDeclaration":
            if d.get("constant"):
                v = fold_constant(self.ix, d)
                return v if v is not None else ("constant", name)
            if d.get("stateVariable"):
                if d.get("mutability") == "immutable":
                    return ("immutable", name)
                return Ref(name)
            return ("unknown", self.span(n), name)
        return ("decl", ref)

    def member(self, n: dict):
        ref = n.get("referencedDeclaration")
        d = self.ix.nodes.get(ref) if isinstance(ref, int) and ref >= 0 else None
        name = n["memberName"]
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
            v = fold_constant(self.ix, d)
            return v if v is not None else ("constant", d.get("name"))
        if d is not None and d.get("nodeType") == "EnumValue":
            enum = self.ix.nodes.get(d.get("scope")) or {}
            members = [m.get("id") for m in enum.get("members", [])]
            return members.index(d["id"]) if d["id"] in members else ("enum", name)
        if d is not None and d.get("nodeType") in ("FunctionDefinition", "EventDefinition", "ErrorDefinition"):
            return ("decl", ref)
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("stateVariable"):
            return ("immutable", d["name"]) if d.get("mutability") == "immutable" else Ref(d["name"])
        base_node = n["expression"]
        if base_node.get("nodeType") == "FunctionCall" and (base_node.get("expression") or {}).get("name") == "type":
            return self._meta_member(base_node, name)
        base = self.ev(base_node)
        if isinstance(base, tuple) and base[:1] == ("global",):
            g = base[1]
            if g == "msg" and name == "sender":
                return ("caller",)
            if g in ("msg", "block", "tx"):
                return ("env", f"{g}.{name}")
            return ("global", f"{g}.{name}")
        if isinstance(base, Ref):
            if name == "length":
                return ("len", self.read(base))
            return Ref(base.fam, base.path + (("member", name),))
        if isinstance(base, tuple) and base[:1] == ("struct",):
            members, values = base[2], base[3]
            return values[members.index(name)] if name in members else ("member", base, name)
        bts = type_string(base_node)
        if name == "length":
            return ("len", base)
        if bts in ("address", "address payable") or bts.startswith("contract "):
            if name == "code":
                return ("code", base)
            if name == "balance":
                return ("balance", base)
            if name == "codehash":
                return ("codehash", base)
        out = ("member", base, name)
        if bts.startswith("struct ") and bts.endswith(" calldata") and _is_input(base):
            c = abi_check(self.ix, out, None, type_string(n))
            if c is not None:
                self.check("abi", self.span(n), c, param=_input_root(base))
        return out

    def _meta_member(self, call: dict, name: str):
        args = call.get("arguments") or []
        ts = type_string(args[0]) if args else ""
        m = re.fullmatch(r"type\((u?int)(\d*)\)", ts)
        if m:
            b = int(m.group(2) or 256)
            if m.group(1) == "uint":
                return {"max": (1 << b) - 1, "min": 0}.get(name, ("type", ts, name))
            return {"max": (1 << (b - 1)) - 1, "min": (-(1 << (b - 1))) & MASK}.get(name, ("type", ts, name))
        return ("type", ts, name)

    def index_access(self, n: dict):
        base = self.ev(n["baseExpression"])
        idx = self.val(self.ev(n["indexExpression"])) if n.get("indexExpression") is not None else None
        bts = type_string(n["baseExpression"])
        is_map = bts.startswith("mapping")
        if not is_map and idx is not None and not bts.startswith("type("):
            m = re.search(r"\[(\d+)\](?: (?:storage|memory|calldata)(?: (?:ref|pointer))?)?$", bts)
            mb = re.fullmatch(r"bytes(\d+)", bts)
            if m:
                length = int(m.group(1))
            elif mb:
                length = int(mb.group(1))
            elif isinstance(base, Ref):
                length = ("len", self.read(base))
            else:
                length = ("len", self.val(base))
            self.panic(50, n, "index", [idx, length], fold("<", idx, length))
        if isinstance(base, Ref):
            return Ref(base.fam, base.path + ((("map" if is_map else "index"), idx),))
        if (bts == "bytes" or bts.startswith("bytes ")) and isinstance(idx, int):
            return ("byte", base, idx)
        return ("index", base, idx)

    def unary(self, n: dict):
        op = n["operator"]
        sub = n["subExpression"]
        ts = type_string(sub)
        if op in ("++", "--"):
            target = self.ev(sub)
            old = self.val(target)
            new = self.arith("+" if op == "++" else "-", old, 1, ts, n)
            self.store(sub, target, new, n)
            return new if n.get("prefix") else old
        if op == "delete":
            target = self.ev(sub)
            self.store(sub, target, 0, n)
            return ("tuple",)
        a = self.val(self.ev(sub))
        if op == "-":
            info = int_info(ts)
            if info is not None and info[1] and not self.frame.unchecked:
                self.panic(17, n, "neg", [a], fits(info[0], True, ("neg", a)))
        return fold({"-": "neg"}.get(op, op), a)

    def assign(self, n: dict):
        op = n.get("operator", "=")
        v = self.val(self.ev(n["rightHandSide"]))
        lhs = n["leftHandSide"]
        if lhs.get("nodeType") == "TupleExpression":
            comps = lhs.get("components") or []
            for c, x in zip(comps, components(v, len(comps))):
                if c is not None:
                    self.store(c, self.ev(c), x, n)
            return v
        target = self.ev(lhs)
        if op != "=":
            v = self.arith(op[:-1], self.val(target), v, type_string(n) or type_string(lhs), n) \
                if op[:-1] in ("+", "-", "*", "/", "%", "**", "<<", ">>") else fold(op[:-1], self.val(target), v)
        self.store(lhs, target, v, n)
        return v

    def store(self, lhs: dict, target, v, node: dict) -> None:
        if isinstance(target, Ref):
            self.write(target, abi_word(type_string(lhs), self.val(v)), node)
            return
        if lhs.get("nodeType") == "Identifier":
            ref = lhs.get("referencedDeclaration")
            if ref in self.frame.vars or _is_local(self.ix, ref):
                d = self.ix.nodes.get(ref) or {}
                self.frame.vars[ref] = self.bind(d, v)
                self.tag("local", [ref])
                return
        if lhs.get("nodeType") in ("IndexAccess", "MemberAccess"):
            root = _root_decl(lhs)
            if root in self.frame.vars:   # a write into a memory struct or array held by a local
                self.frame.vars[root] = ("update", self.frame.vars[root], self.val(target) if not isinstance(
                    target, Ref) else target, abi_word(type_string(lhs), self.val(v)))
                self.tag("local", [root])
                return
        self.unsupported_expr(node, "Assignment")

    # -- calls
    def call(self, n: dict):
        kind = n.get("kind")
        args = n.get("arguments") or []
        callee = n["expression"]
        opts = {}
        if callee.get("nodeType") == "FunctionCallOptions":
            for name, o in zip(callee.get("names") or [], callee.get("options") or []):
                opts[name] = self.val(self.ev(o))
            callee = callee["expression"]
        if kind == "typeConversion":
            if len(args) != 1:
                self.unsupported_expr(n, "FunctionCall")
                return ("unknown", self.span(n), "conversion")
            v = self.val(self.ev(args[0]))
            dst = type_string(n)
            if dst.startswith("enum "):
                ed = self.ix.nodes.get(callee.get("referencedDeclaration")) or {}
                k = len(ed.get("members") or [])
                if k and not type_string(args[0]).startswith("enum "):
                    self.panic(33, n, "enum", [v, k], fold("<", v, k))
            return convert(v, type_string(args[0]), dst)
        if kind == "structConstructorCall":
            vals = tuple(self.val(self.ev(a)) for a in args)
            sd = self.ix.nodes.get(callee.get("referencedDeclaration")) or {}
            members = [m.get("name") for m in sd.get("members", [])]
            names = n.get("names") or []
            if names:
                by = dict(zip(names, vals))
                vals = tuple(by.get(m, 0) for m in members)
            vals = tuple(abi_word(type_string(m), v) for m, v in zip(sd.get("members", []), vals))
            return ("struct", sd.get("name", ""), tuple(members), vals)
        if callee.get("nodeType") == "NewExpression":
            return self.new(n, callee, args, opts)
        if callee.get("nodeType") == "Identifier" and (callee.get("referencedDeclaration") or 0) < 0:
            return self.builtin(callee.get("name"), n, args)
        if callee.get("nodeType") == "MemberAccess":
            base_node = callee["expression"]
            if base_node.get("nodeType") == "Identifier" and (base_node.get("referencedDeclaration") or 0) < 0 \
                    and base_node.get("name") in ("abi", "bytes", "string"):
                vals = [abi_word(type_string(a), self.val(self.ev(a))) for a in args]
                return (f"{base_node['name']}.{callee['memberName']}",) + tuple(vals)
        target = self.ix.nodes.get(callee.get("referencedDeclaration")) if callee.get("nodeType") in (
            "Identifier", "MemberAccess") else None
        cts = type_string(callee)
        low = callee.get("nodeType") == "MemberAccess" and callee.get("memberName") in LOW_LEVEL and target is None
        if " external" in cts or low:
            return self.external(n, callee, target, args, opts, low)
        if callee.get("nodeType") == "MemberAccess" and target is None and callee.get("memberName") in ("push", "pop"):
            base = self.ev(callee["expression"])
            elem = re.sub(r"\[\d*\](?: (?:storage|memory|calldata)(?: (?:ref|pointer))?)?$", "",
                          type_string(callee["expression"]))
            vals = [abi_word(elem, self.val(self.ev(a))) for a in args]
            if isinstance(base, Ref):
                if callee["memberName"] == "pop":
                    ln = ("len", self.read(base))
                    self.panic(49, n, "pop", [ln], fold("!=", ln, 0))
                self.write(base, (callee["memberName"], self.read(base)) + tuple(vals), n)
                return ("tuple",)
        if target is None or target.get("nodeType") != "FunctionDefinition":
            for a in args:
                self.val(self.ev(a))
            self.unsupported_expr(n, "FunctionCall")
            return results(n, ("unknown", self.span(n), "call"))
        target = self.dispatch(target, callee)
        arg_nodes = list(args)
        if callee.get("nodeType") == "MemberAccess" and len(arg_nodes) + 1 == len(target["parameters"]["parameters"]) \
                and not type_string(callee["expression"]).startswith("type("):
            arg_nodes = [callee["expression"]] + arg_nodes   # a bound library call x.f(y)
        if not target.get("body") or not target.get("implemented", True) \
                or len(self.sites) + 1 > MAX_CALL_DEPTH or any(f.fn["id"] == target["id"] for f in self.frames):
            for a in arg_nodes:
                self.val(self.ev(a))
            self.unsupported_expr(n, "FunctionCall")
            return results(n, ("unknown", self.span(n), target.get("name", "call")))
        return self.inline(target, arg_nodes, n)

    def dispatch(self, target: dict, callee: dict) -> dict:
        """Virtual dispatch of a plain internal call against the contract's linearization."""
        if callee.get("nodeType") != "Identifier" or not target.get("virtual") and not target.get("overrides"):
            return target
        sig = [type_string(p) for p in target["parameters"]["parameters"]]
        for cid in self.contract.get("linearizedBaseContracts", []):
            for x in (self.ix.nodes.get(cid) or {}).get("nodes", []):
                if x.get("nodeType") == "FunctionDefinition" and x.get("name") == target.get("name") \
                        and [type_string(p) for p in x["parameters"]["parameters"]] == sig and x.get("body"):
                    return x
        return target

    def inline(self, target: dict, arg_nodes: list, call_node: dict):
        caller = self.frame
        vals = [self.ev(a) for a in arg_nodes]
        self.tag("inlined")
        f = Frame(fn=target, name=self.ix.fn_name(target), zone=caller.zone, mod_index=caller.mod_index)
        for p, v in zip(target["parameters"]["parameters"], vals):
            f.vars[p["id"]] = self.bind(p, v)
        for p in target["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.reach(target)
        span = self.span(call_node)
        self.sites.append(span)
        self.stack.append(span)
        try:
            v = self.chain_function(target, f)
        finally:
            self.sites.pop()
            self.stack.pop()
        if v is None:
            return ("tuple",)
        return v

    def external(self, n: dict, callee: dict, target: dict | None, args: list, opts: dict, low: bool):
        recv = self.val(self.ev(callee["expression"])) if callee.get("nodeType") == "MemberAccess" else None
        vals = [abi_word(type_string(a), self.val(self.ev(a))) for a in args]
        member = callee.get("memberName") or callee.get("name") or "call"
        iface = None
        if low:
            fname = f"address.{member}"
            term = ("call", fname, recv) + tuple(vals) + ((("value", opts["value"]),) if "value" in opts else ())
        else:
            owner = self.ix.contract_of(target) if target is not None else None
            if owner is not None:
                iface = owner["name"]
            else:
                iface = re.sub(r"^(contract|interface) ", "", type_string(callee.get("expression") or {})) or "?"
            fname = f"{iface}.{target['name'] if target is not None else member}"
            term = ("call", fname) + tuple(vals)
        commit = not low and iface in self.commit
        if commit:
            self.edge("COMMIT", fname, n)
        else:
            self.debt("external_call", fname, n)
        if "value" in opts or (low and member in ("send", "transfer")):
            self.debt("value_transfer", fname, n)
        ok = ("callok", fname, recv) + tuple(vals)
        is_try = self.try_node is not None and n.get("id") == self.try_node
        reverts = (not low or member == "transfer") and not is_try
        if is_try:
            self.try_ok = ok
        k = conj(self.ctx)
        expr = (ok if k == 1 else disj2(neg(k), ok)) if reverts else 1
        mut = (target or {}).get("stateMutability") or ("payable" if "value" in opts else "nonpayable")
        if self.recording:
            self.record(self.calls, self.span(n), fn=fname, receiver=self.r(recv), args=[self.r(v) for v in vals],
                        value=self.r(opts.get("value", 0)), mutability=mut, cond=self.rc(k), commit=commit,
                        **({"try": True} if is_try else {}), expr=self.rc(expr))
            if reverts:
                self.order.append(["call", len(self.calls) - 1])
        out = results(n, term)
        ts = type_string(n)
        types = _tuple_types(ts) if ts.startswith("tuple(") else [ts]
        for t, cts in zip(list(out[1:]) if len(types) > 1 else [out], types):
            if _bare(cts) == "bool":            # the ABI decoder validates a returned bool (inside callok)
                self.bools.add(t)
        return out

    def new(self, n: dict, callee: dict, args: list, opts: dict):
        tn = callee.get("typeName") or {}
        vals = [self.val(self.ev(a)) for a in args]
        d = self.ix.nodes.get(tn.get("referencedDeclaration")) if tn.get("nodeType") == "UserDefinedTypeName" else None
        if d is None or d.get("nodeType") != "ContractDefinition":
            size = vals[0] if vals else 0
            if vals:    # the compiler allocates at most 2^64 - 1 elements, else Panic(0x41)
                self.panic(65, n, "alloc", [size], fold("<=", size, (1 << 64) - 1))
            return ("alloc", type_string(n), size)
        fname = f"new {d['name']}"
        self.debt("external_call", fname, n)
        if "value" in opts:
            self.debt("value_transfer", fname, n)
        k = conj(self.ctx)
        ok = ("callok", fname, None) + tuple(vals)
        if self.recording:
            self.record(self.calls, self.span(n), fn=fname, receiver=None, args=[self.r(v) for v in vals],
                        value=self.r(opts.get("value", 0)), mutability="payable" if "value" in opts else "nonpayable",
                        cond=self.rc(k), commit=False, expr=self.rc(ok if k == 1 else disj2(neg(k), ok)))
            self.order.append(["call", len(self.calls) - 1])
        return ("new", d["name"]) + tuple(vals)

    def builtin(self, name: str, n: dict, args: list):
        if name in ("require", "assert"):
            c = self.val(self.ev(args[0]))
            reason, data = None, None
            if name == "require" and len(args) > 1:
                reason, data = self.reason(args[1])
            self.guard("require", n, c, reason, code=1 if name == "assert" else None, data=data)
            if c == 0:
                self.exit = "revert"
            return ("tuple",)
        if name == "revert":
            reason, data = self.reason(args[0]) if args else (None, None)
            self.guard("revert", n, None, reason, data=data)
            self.exit = "revert"
            return ("tuple",)
        vals = [self.val(self.ev(a)) for a in args]
        if name in ("keccak256", "sha256"):
            self.edge("HASH", name, n)
            return (name,) + tuple(vals)
        if name == "blobhash":
            self.edge("COMMIT", "blobhash", n)
            return ("blobhash",) + tuple(vals)
        if name in ("blockhash", "ripemd160", "ecrecover"):
            return (name,) + tuple(vals)
        if name == "gasleft":
            return ("env", "gasleft")
        if name in ("addmod", "mulmod") and len(vals) == 3:
            self.panic(18, n, name, list(vals), fold("!=", vals[2], 0))
            return fold(name, *vals)
        self.unsupported_expr(n, name or "FunctionCall")
        return results(n, ("unknown", self.span(n), name or "call"))

    def emit(self, n: dict) -> None:
        call = n["eventCall"]
        expr = call.get("expression") or {}
        vals = [self.val(self.ev(a)) for a in call.get("arguments") or []]
        decl = self.ix.nodes.get(expr.get("referencedDeclaration"))
        if decl is None or decl.get("nodeType") != "EventDefinition":
            self.debt("unsupported", "EmitStatement", n)
            return
        params = decl["parameters"]["parameters"]
        names = call.get("names") or []
        if names:
            by = dict(zip(names, vals))
            vals = [by.get(p["name"], 0) for p in params]
        vals = [abi_word(type_string(p), v) for p, v in zip(params, vals)]
        types = [abi_type(self.ix, p.get("typeName") or {}) for p in params]
        sig = f"{decl['name']}({','.join(types)})"
        from ...keccak import keccak256
        topic0 = keccak256(sig.encode()).hex()
        if decl.get("eventSelector") and decl["eventSelector"] != topic0:
            raise ExtractionError(f"event {sig}: keccak256 of the signature is not the compiler's eventSelector")
        owner = owner_of(self.ix, decl)
        anon = bool(decl.get("anonymous"))
        self.tag("event")
        if self.recording:
            topics = [topic_term(t, v) for p, t, v in zip(params, types, vals) if p.get("indexed")]
            self.record(self.events, self.span(n), event=f"{owner['name']}.{decl['name']}" if owner else decl["name"],
                        signature=sig, topic0=None if anon else "0x" + topic0, args=[self.r(v) for v in vals],
                        indexed=[bool(p.get("indexed")) for p in params], topics=[self.r(t) for t in topics],
                        anonymous=anon, cond=self.rc(conj(self.ctx)))

    def error_of(self, call: dict):
        """(error, args) of a call of a custom error E(...) (revert E(...), require(c, E(...))): error {name (the
        declaring contract's name, a dot and E), signature (canonical ABI types), selector ("0x" and the first 4
        bytes of keccak256(signature))} and the argument values in parameter order as the ABI encoder writes them;
        None when call does not name an error."""
        decl = self.ix.nodes.get((call.get("expression") or {}).get("referencedDeclaration"))
        if decl is None or decl.get("nodeType") != "ErrorDefinition":
            return None
        vals = [self.val(self.ev(a)) for a in call.get("arguments") or []]
        params = decl["parameters"]["parameters"]
        names = call.get("names") or []
        if names:
            by = dict(zip(names, vals))
            vals = [by.get(p["name"], 0) for p in params]
        vals = [abi_word(type_string(p), v) for p, v in zip(params, vals)]
        sig = f"{decl['name']}({','.join(abi_type(self.ix, p.get('typeName') or {}) for p in params)})"
        from ...keccak import keccak256
        sel = keccak256(sig.encode())[:4].hex()
        if decl.get("errorSelector") and decl["errorSelector"] != sel:
            raise ExtractionError(f"error {sig}: keccak256 of the signature is not the compiler's errorSelector")
        owner = owner_of(self.ix, decl)
        name = f"{owner['name']}.{decl['name']}" if owner else decl["name"]
        return {"name": name, "signature": sig, "selector": "0x" + sel}, vals

    # -- inline assembly
    def assembly(self, n: dict) -> None:
        f = self.frame
        saved = (f.asm, f.yul, f.yulfns)
        f.asm, f.yul, f.yulfns = n, [], []
        try:
            self.yul_block(n["AST"])
        finally:
            f.asm, f.yul, f.yulfns = saved

    def yul_block(self, b: dict):
        f = self.frame
        f.yul.append({})
        f.yulfns.append(_yul_functions(b))
        base = len(self.ctx)
        falls = 1
        try:
            for s in b.get("statements") or []:
                if self.exit:
                    break
                x = self.yul_stmt(s)
                if self.exit:
                    break
                if x != 1:
                    self.ctx.append(x)
                    falls = conj([falls, x])
        finally:
            del self.ctx[base:]
            f.yul.pop()
            f.yulfns.pop()
        return falls

    def yul_stmt(self, s: dict):
        nt = s["nodeType"]
        if nt == "YulBlock":
            return self.yul_block(s)
        if nt == "YulVariableDeclaration":
            names = [v["name"] for v in s.get("variables", [])]
            if s.get("value") is None:
                vals = [0] * len(names)
            else:
                v = self.yul_expr(s["value"])
                vals = [v] if len(names) == 1 else components(v, len(names))
            for name, v in zip(names, vals):
                self.frame.yul[-1][name] = v
            return 1
        if nt == "YulAssignment":
            v = self.yul_expr(s["value"])
            targets = s.get("variableNames", [])
            vals = [v] if len(targets) == 1 else components(v, len(targets))
            for t, x in zip(targets, vals):
                self.yul_set(t, x)
            return 1
        if nt == "YulExpressionStatement":
            self.yul_expr(s["expression"])
            return 1
        if nt == "YulIf":
            c = self.yul_expr(s["condition"])
            c = c if isinstance(c, int) or is_bool(c) else fold("!=", c, 0)
            if isinstance(c, int):
                return self.yul_block(s["body"]) if c else 1
            return self.branch(c, lambda: self.yul_block(s["body"]), None)
        if nt == "YulSwitch":
            v = self.yul_expr(s["expression"])
            return self._switch(v, s.get("cases") or [], 0)
        if nt == "YulForLoop":
            return self.loop(s)
        if nt in ("YulBreak", "YulContinue"):
            self.loop_exit("break" if nt == "YulBreak" else "continue")
            return 0
        if nt == "YulLeave":
            self.yul_leave()
            return 0
        if nt == "YulFunctionDefinition":
            return 1
        self.debt("unsupported", nt, s)
        self.havoc(s)
        self.havoc_memory(s)
        return 1

    def _switch(self, v, cases: list, i: int):
        if i >= len(cases):
            return 1
        case = cases[i]
        if case.get("value") == "default":
            return self.yul_block(case["body"])
        c = fold("==", v, self.yul_expr(case["value"]))
        if isinstance(c, int):
            return self.yul_block(case["body"]) if c else self._switch(v, cases, i + 1)
        return self.branch(c, lambda: self.yul_block(case["body"]), lambda: self._switch(v, cases, i + 1))

    def yul_function(self, name: str):
        for fns in reversed(self.frame.yulfns):
            if name in fns:
                return fns[name]
        return None

    def yul_leave(self) -> None:
        if self.yul_returns:
            ctx = self.yul_returns[-1]
            scope = self.frame.yul[0]
            ctx["returns"].append((conj(self.ctx[ctx["base"]:]), [scope.get(x) for x in ctx["names"]],
                                   dict(self.storage), dict(self.memory)))
        self.exit = "leave"

    def yul_inline(self, fdef: dict, vals: list, e: dict):
        f = self.frame
        if len(self.yul_returns) + len(self.sites) + 1 > MAX_CALL_DEPTH or \
                any(x["def"] is fdef for x in self.yul_returns):
            self.debt("unsupported", "recursive Yul function", e)
            return ("unknown", self.span(e), fdef["name"])
        names = [r["name"] for r in fdef.get("returnVariables") or []]
        scope = {p["name"]: v for p, v in zip(fdef.get("parameters") or [], vals)}
        scope.update({x: 0 for x in names})
        saved = (f.yul, f.yulfns)
        f.yul, f.yulfns = [scope], list(f.yulfns)
        ctx = {"def": fdef, "base": len(self.ctx), "names": names, "returns": []}
        self.yul_returns.append(ctx)
        try:
            falls = self.yul_block(fdef["body"])
            entries = list(ctx["returns"])
            if self.exit is None:
                entries.append((falls, [f.yul[0].get(x) for x in names], dict(self.storage), dict(self.memory)))
        finally:
            self.yul_returns.pop()
            f.yul, f.yulfns = saved
        if self.exit not in (None, "leave") and not entries:
            return ("tuple",)
        self.exit = None
        if not entries:
            self.exit = "revert"
            return ("tuple",)
        _, vs, st, mem = entries[-1]
        for c, vi, sti, memi in reversed(entries[:-1]):
            vs = [ite(c, a, b) for a, b in zip(vi, vs)]
            st = merge_storage(c, sti, st)
            mem = merge_memory(c, memi, mem)
        self.storage, self.memory = st, mem
        if not vs:
            return ("tuple",)
        return vs[0] if len(vs) == 1 else ("tuple",) + tuple(vs)

    def yul_set(self, ident: dict, v) -> None:
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                scope[name] = v
                return
        ref = _external_ref(self.frame.asm, ident)
        if ref is not None:
            self.frame.vars[ref["declaration"]] = v
            self.tag("local", [ref["declaration"]])
            return
        self.frame.yul[-1][name] = v

    def yul_get(self, ident: dict):
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                return scope[name]
        ref = _external_ref(self.frame.asm, ident)
        if ref is None:
            return ("unknown", self.span(ident), name)
        decl = ref["declaration"]
        suffix = ref.get("suffix")
        d = self.ix.nodes.get(decl) or {}
        if suffix == "slot" or ref.get("isSlot"):
            return ("slot", d.get("name", ""))
        if decl in self.frame.vars:
            self.read_decl(decl)
            v = self.val(self.frame.vars[decl])
        elif d.get("constant"):
            v = fold_constant(self.ix, d)
            v = v if v is not None else ("constant", d.get("name"))
        else:
            v = ("unknown", self.span(ident), name)
        if suffix == "offset" or (ref.get("isOffset") and suffix != "slot"):
            return ("cdoff", v)
        if suffix == "length":
            return ("len", v)
        return v

    def yul_expr(self, e: dict):
        nt = e["nodeType"]
        if nt == "YulLiteral":
            if e.get("kind") == "bool":
                return 1 if e.get("value") == "true" else 0
            if e.get("kind") == "number":
                return int(e["value"], 0) & MASK
            raw = bytes.fromhex(e["hexValue"]) if e.get("hexValue") else (e.get("value") or "").encode()
            return int.from_bytes(raw[:32].ljust(32, b"\0"), "big")
        if nt == "YulIdentifier":
            return self.yul_get(e)
        if nt != "YulFunctionCall":
            self.debt("unsupported", nt, e)
            return ("unknown", self.span(e), nt)
        name = e["functionName"]["name"]
        args = e.get("arguments") or []
        fdef = self.yul_function(name)
        if fdef is None and not (name in YUL_PURE or name in YUL_ENV or name in YUL_OTHER):
            self.debt("unsupported", name, e)
            self.havoc(e)
            return ("unknown", self.span(e), name)
        vals = [None] * len(args)
        for i in range(len(args) - 1, -1, -1):   # Yul evaluates arguments right to left
            vals[i] = self.yul_expr(args[i])
        if fdef is not None:
            return self.yul_inline(fdef, vals, e)
        if name in YUL_ENV:
            return YUL_ENV[name]
        if name in YUL_PURE:
            return fold(YUL_PURE[name], vals[0], vals[1])
        if name == "shl":
            return fold("<<", vals[1], vals[0])
        if name == "shr":
            return fold(">>", vals[1], vals[0])
        if name == "sar":
            return fold("sar", vals[1], vals[0])
        if name == "iszero":
            return fold("==", vals[0], 0)
        if name == "not":
            return fold("~", vals[0])
        if name in ("addmod", "mulmod"):
            return fold(name, vals[0], vals[1], vals[2])
        if name == "byte":
            return fold("wbyte", vals[1], vals[0])
        if name == "signextend":
            b = vals[0]
            if isinstance(b, int):
                return fold("sext", 8 * (b + 1), vals[1]) if b < 31 else vals[1]
            return ("signextend", b, vals[1])
        if name == "pop":
            return ("tuple",)
        if name == "sload":
            return ("sload", vals[0])
        if name == "blobhash":
            self.edge("COMMIT", "blobhash", e)
            return ("blobhash", vals[0])
        if name == "extcodesize":
            return ("len", ("code", vals[0]))
        if name == "extcodehash":
            return ("codehash", vals[0])
        if name == "balance":
            return ("balance", vals[0])
        if name == "selfbalance":
            return ("balance", ("this",))
        if name == "calldataload":
            return ("calldataload", vals[0])
        if name in ("revert", "invalid"):
            self.guard("revert", e, None, None)
            self.exit = "revert"
            return ("tuple",)
        return self.yul_memory(name, vals, e)

    def yul_memory(self, name: str, vals: list, e: dict):
        p = vals[0]
        if name == "mload":
            if p == 0x40:
                self.regions += 1
                rid = (self.regions, tuple(self.sites) + (self.span(e),))
                self.memory[rid] = ("mem",)
                return ("ptr", rid, 0)
            return self.mload(p, e)
        if name == "keccak256":
            self.edge("HASH", "keccak256", e)
            return self.hash_mem(p, vals[1], e)
        if name == "mstore" and p == 0x40:
            return ("tuple",)
        if name == "calldatacopy":
            src, n = vals[1], vals[2]
            x, k = None, None
            if isinstance(src, tuple) and src[:1] == ("cdoff",):
                x, k = src[1], 0
            elif isinstance(src, tuple) and src[:1] == ("+",) and len(src) == 3:
                a, b = src[1], src[2]
                if isinstance(a, tuple) and a[:1] == ("cdoff",):
                    x, k = a[1], b
                elif isinstance(b, tuple) and b[:1] == ("cdoff",):
                    x, k = b[1], a
            w = (lambda off: ("calldatacopy", off, x, k, n)) if x is not None else \
                (lambda off: ("calldatacopy", off, ("calldata", src), 0, n))
        else:
            v = vals[1]
            w = (lambda off: (name, off, v))
        self.mem_write(p, w, e)
        self.tag("local")
        self.tag("memory")
        return ("tuple",)

    def mem_write(self, p, w, e: dict, cond=None) -> None:
        if is_ite(p):
            self.mem_write(p[2], w, e, p[1] if cond is None else conj([cond, p[1]]))
            self.mem_write(p[3], w, e, neg(p[1]) if cond is None else conj([cond, neg(p[1])]))
            return
        if is_ptr(p) and p[1] in self.memory:
            entry = w(p[2])
            self.record_mstore(e, p[1], entry, cond)
            self.memory[p[1]] = mem_append(self.memory[p[1]], entry if cond is None else when(cond, entry))
            return
        self.record_mstore(e, None, w(p), cond)
        self.debt("unsupported", f"{e['functionName']['name']} at an unresolved address", e)
        for r in list(self.memory):
            self.memory[r] = mem_append(self.memory[r], ("unknown", self.span(e)))

    def record_mstore(self, e: dict, rid, entry, cond) -> None:
        if not self.recording:
            return
        op = entry[0]
        value = entry[2] if op in ("mstore", "mstore8") else ("input", entry[2], entry[3], entry[4])
        c = conj(self.ctx + ([cond] if cond is not None else []))
        self.record(self.mstores, self.span(e), region=list(rid[1]) if rid is not None else None, op=op,
                    offset=self.r(entry[1]), value=self.r(value), cond=self.rc(c))

    def mload(self, p, e: dict):
        if is_ite(p):
            return ite(p[1], self.mload(p[2], e), self.mload(p[3], e))
        if is_ptr(p) and p[1] in self.memory:
            return resolve_word(self.memory[p[1]], p[2])
        return ("mload", ("unknown", self.span(e), "memory"), p)

    def hash_mem(self, p, n, e: dict):
        if is_ite(p):
            return ite(p[1], self.hash_mem(p[2], n, e), self.hash_mem(p[3], n, e))
        if is_ptr(p) and p[1] in self.memory:
            return ("keccak256", resolve_bytes(self.memory[p[1]], p[2], n))
        return ("keccak256", ("slice", ("unknown", self.span(e), "memory"), p, n))


# ------------------------------------------------------------------------------------------------ helpers
def _text(s) -> str:
    return bytes.fromhex(s[1]).decode("utf-8", "replace")


def _yul_functions(b: dict) -> dict:
    return {s["name"]: s for s in (b or {}).get("statements") or [] if s.get("nodeType") == "YulFunctionDefinition"}


def _mentions_carried(t, span: str) -> bool:
    """Whether t holds a carried symbol or a ["loop", span] entry of the loop at span (any reach)."""
    stack = [t]
    while stack:
        x = stack.pop()
        if isinstance(x, tuple):
            if len(x) >= 2 and x[0] in ("carried", "loop") and x[1] == span:
                return True
            stack.extend(x)
        elif isinstance(x, Ref):
            stack.extend(x.path)
    return False


def affine_step(nv, sym, spans: set):
    """d when nv (a carried name's value at the end of a continuing iteration) is sym + d with d loop-invariant (no
    symbol of a loop in spans), as (sign, d); else None. Pointers keep their region and step their offset."""
    if is_ptr(sym):
        if not is_ptr(nv) or nv[1] != sym[1]:
            return None
        nv, sym = nv[2], sym[2]
    if not isinstance(nv, tuple) or len(nv) != 3 or nv[0] not in ("+", "-"):
        return None
    op, a, b = nv
    if a == sym and not mentions_symbols(b, spans):
        d = b
    elif op == "+" and b == sym and not mentions_symbols(a, spans):
        d = a
    else:
        return None
    if isinstance(d, int) and d >> 255:          # a negative constant step written as an addition
        return ("-" if op == "+" else "+", (-d) & MASK)
    return (op, d)


def closed_form(entry, step, iter_t):
    op, d = step
    if is_ptr(entry):
        return ("ptr", entry[1], fold(op, entry[2], fold("*", d, iter_t)))
    return fold(op, entry, fold("*", d, iter_t))


def header_count(head, syms: dict, steps: dict, before: Snap, get, spans: set):
    """I19's header rule on closed forms: head is [cmp, X, N] (or [cmp, N, X]) with X a carried name stepped by a
    constant and N loop-invariant; the count it gives (count), else None."""
    if not isinstance(head, tuple) or len(head) != 3 or head[0] not in ("<", "<=", "!=", ">", ">="):
        return None
    op, lhs, rhs = head
    flip = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "!=": "!="}
    for k, s in syms.items():
        if k not in steps:
            continue
        x = s[2] if is_ptr(s) else s
        if lhs == s and not mentions_symbols(rhs, spans):
            o, n = op, rhs
        elif rhs == s and not mentions_symbols(lhs, spans):
            o, n = flip[op], lhs
        else:
            continue
        sop, d = steps[k]
        if not isinstance(d, int) or is_ptr(s) or x is None or d == 0:
            return None
        step = d if sop == "+" else -d
        return count(o, get(before, k), n, step)
    return None


def _appended(start, end):
    """The writes end appends to start (both plain regions), else None."""
    if not (is_mem(start) and is_mem(end)) or end[:len(start)] != start:
        return None
    return list(end[len(start):])


def when(c, w):
    if c == 1:
        return w
    if isinstance(w, tuple) and w[:1] == ("when",):
        return ("when", conj([c, w[1]]), w[2])
    return ("when", c, w)


def post_value(t):
    """A family's value after the action, a scalar's store rendered as its value."""
    if is_ite(t):
        return ite(t[1], post_value(t[2]), post_value(t[3]))
    if isinstance(t, tuple) and t[:1] == ("store",) and t[2] == () and t[1][:1] == ("storage",):
        return t[3]
    return t


def ite_value(c, a, b):
    if isinstance(a, tuple) and isinstance(b, tuple) and a[:1] == b[:1] == ("tuple",) and len(a) == len(b):
        return ("tuple",) + tuple(ite(c, x, y) for x, y in zip(a[1:], b[1:]))
    return ite(c, a, b)


def merge_snaps(c, a: Snap, b: Snap, keys: Snap) -> Snap:
    """ite(c, a, b) over the names of keys (locals declared inside the branches are out of scope after them)."""
    vs = {k: ite(c, a.vars.get(k, v), b.vars.get(k, v)) for k, v in keys.vars.items()}
    yul = []
    for i, scope in enumerate(keys.yul):
        sa = a.yul[i] if i < len(a.yul) else {}
        sb = b.yul[i] if i < len(b.yul) else {}
        yul.append({k: ite(c, sa.get(k, v), sb.get(k, v)) for k, v in scope.items()})
    return Snap(vs, yul, merge_storage(c, a.storage, b.storage), merge_memory(c, a.memory, b.memory))


def merge_list(entries: list, keys: Snap) -> Snap:
    """The state of mutually exclusive paths [(condition, state), ...] (at least one), over the names of keys."""
    s = entries[-1][1]
    acc = Snap({k: s.vars.get(k, v) for k, v in keys.vars.items()},
               [{nm: (s.yul[i] if i < len(s.yul) else {}).get(nm, v) for nm, v in scope.items()}
                for i, scope in enumerate(keys.yul)], dict(s.storage), dict(s.memory))
    for c, s in reversed(entries[:-1]):
        acc = merge_snaps(c, s, acc, keys)
    return acc


def merge_storage(c, a: dict, b: dict) -> dict:
    out = {}
    for f in sorted(set(a) | set(b)):
        p = ("storage", f)
        v = ite(c, a.get(f, p), b.get(f, p))
        if v != p:
            out[f] = v
    return out


def merge_memory(c, a: dict, b: dict) -> dict:
    out = {}
    for r in sorted(set(a) | set(b), key=lambda r: r[0]):
        if r in a and r in b:
            out[r] = merge_region(c, a[r], b[r])
        else:
            out[r] = a[r] if r in a else b[r]
    return out


def merge_region(c, x, y):
    """A region after a branch on c: the common prefix, then each branch's own writes under ["when", ...]."""
    if x == y:
        return x
    if isinstance(c, int):
        return x if c else y
    if is_mem(x) and is_mem(y):
        k = 0
        while k < len(x) and k < len(y) and x[k] == y[k]:
            k += 1
        return x[:k] + tuple(when(c, w) for w in x[k:]) + tuple(when(neg(c), w) for w in y[k:])
    return ite(c, x, y)


def mem_append(content, w):
    if is_ite(content):
        return ("?", content[1], mem_append(content[2], w), mem_append(content[3], w))
    return content + (w,)


def resolve_word(content, off, upto=None):
    """mload at offset off of a region: the value of an mstore exactly there (a guarded one conditionally), the word of
    a calldatacopy covering it, else ["mload", content, off]."""
    if is_ite(content):
        return ite(content[1], resolve_word(content[2], off), resolve_word(content[3], off))
    end = len(content) if upto is None else upto
    if isinstance(off, int):
        for j in range(end - 1, 0, -1):
            w = content[j]
            cond = None
            if w[0] == "when":
                cond, w = w[1], w[2]
            kind = w[0]
            if kind in ("mstore", "mstore8"):
                wo = w[1]
                if not isinstance(wo, int):
                    break
                width = 32 if kind == "mstore" else 1
                if wo + width <= off or off + 32 <= wo:
                    continue
                if kind == "mstore" and wo == off:
                    return w[2] if cond is None else ite(cond, w[2], resolve_word(content, off, j))
                break
            if kind == "calldatacopy":
                wo, x, frm, n = w[1], w[2], w[3], w[4]
                if not isinstance(wo, int):
                    break
                if isinstance(n, int) and (off + 32 <= wo or wo + n <= off):
                    continue
                if off >= wo and (not isinstance(n, int) or off + 32 <= wo + n):
                    v = ("word", x, fold("+", off - wo, frm))
                    return v if cond is None else ite(cond, v, resolve_word(content, off, j))
                break
            break
    return ("mload", content if upto is None else content[:upto], off)


def resolve_bytes(content, off, n):
    """The bytes keccak256(off, n) hashes: the input itself when the region is exactly its copy, else a slice."""
    if is_ite(content):
        return ite(content[1], resolve_bytes(content[2], off, n), resolve_bytes(content[3], off, n))
    ws = content[1:]
    if off == 0 and len(ws) == 1 and ws[0][0] == "calldatacopy" and ws[0][1] == 0 and ws[0][3] == 0 and ws[0][4] == n:
        return ws[0][2]
    return ("slice", content, off, n)


def resolve(base, path: tuple):
    """A storage read of path in base (a family's value: ["storage", f], a store chain, a loop symbol or a
    conditional)."""
    if is_ite(base):
        return ite(base[1], resolve(base[2], path), resolve(base[3], path))
    if isinstance(base, tuple) and base[:1] == ("store",):
        _, b, wpath, v = base
        rel = _compare(wpath, path)
        if rel == "same":
            return v
        if rel == "prefix":
            return project(v, path[len(wpath):])
        if rel == "disjoint":
            return resolve(b, path)
    return apply_path(base, path)


def _compare(wpath: tuple, path: tuple) -> str:
    for a, b in zip(wpath, path):
        if a == b:
            continue
        if a[0] == "member" and b[0] == "member":
            return "disjoint"
        if a[0] == b[0] and isinstance(a[1], int) and isinstance(b[1], int):
            return "disjoint"
        return "unknown"
    if len(wpath) == len(path):
        return "same"
    return "prefix" if len(wpath) < len(path) else "unknown"


def project(v, rest: tuple):
    for a in rest:
        if v == 0:
            return 0
        if a[0] == "member" and isinstance(v, tuple) and v[:1] == ("struct",) and a[1] in v[2]:
            v = v[3][v[2].index(a[1])]
        else:
            v = apply_path(v, (a,))
    return v


def apply_path(base, path: tuple):
    t = base
    for kind, x in path:
        t = (kind, t, x)
    return t


def components(v, k: int) -> list:
    if isinstance(v, tuple) and v[:1] == ("tuple",) and len(v) - 1 == k:
        return list(v[1:])
    if k == 1:
        return [v]
    return [("at", i, v) for i in range(k)]


def results(n: dict, term):
    """The value of a call: its term, or its components when it returns a tuple."""
    ts = type_string(n)
    if ts.startswith("tuple("):
        k = _tuple_arity(ts)
        if k == 0:
            return ("tuple",)
        if k > 1:
            return ("tuple",) + tuple(("at", i, term) for i in range(k))
    return term


def int_info(ts: str):
    """(bits, signed) of an integer type string, else None (int_const and rational constants included)."""
    m = re.fullmatch(r"(u?)int(\d*)", (ts or "").strip())
    if not m:
        return None
    return int(m.group(2) or 256), m.group(1) == ""


def _is_signed(ts: str) -> bool:
    info = int_info(ts)
    return info is not None and info[1]


def convert(v, src_ts: str, dst_ts: str):
    """W4: a conversion of a constant folds; to the same or a larger size it is the identity on terms; a narrowing
    conversion is ["trunc", bits, t] (["sext", bits, t] to a signed type, which is also a change of sign)."""
    if isinstance(v, int) or (isinstance(v, tuple) and v[:1] == ("str",)):
        return convert_const(v, dst_ts)
    if dst_ts in ("address", "address payable") and v == ("this",):
        return v
    sb, db = conversion_bits(src_ts), conversion_bits(dst_ts)
    if sb is None or db is None:
        return v
    ssig, dsig = _is_signed(src_ts), _is_signed(dst_ts)
    if dsig and not (ssig and db >= sb):
        return ("sext", db, v) if db < 256 else v
    if ssig and not dsig:
        return ("trunc", db, v) if db < 256 else v
    if db < sb:
        return ("trunc", db, v)
    return v


def convert_const(a, dst_ts: str):
    if isinstance(a, tuple) and a[:1] == ("str",):
        m = re.fullmatch(r"bytes(\d+)", dst_ts)
        if m:
            raw = bytes.fromhex(a[1])[:32].ljust(32, b"\0")
            return int.from_bytes(raw, "big")
        return a
    db = conversion_bits(dst_ts)
    if isinstance(a, int) and db is not None and db < 256:
        return _sext(db, a) if _is_signed(dst_ts) else a & ((1 << db) - 1)
    return a


def fold_constant(index: Index, decl: dict, seen=()):
    """The folded value of a constant VariableDeclaration (W4; also keccak256 of a literal), or None."""
    if decl["id"] in seen or decl.get("value") is None:
        return None
    v = _const_expr(index, decl["value"], seen + (decl["id"],))
    if isinstance(v, int) or (isinstance(v, tuple) and v[:1] == ("str",)):
        return v
    return None


def _const_expr(index: Index, n: dict, seen):
    nt = n.get("nodeType")
    if nt == "Literal":
        return literal_value(n)
    if nt in ("Identifier", "MemberAccess"):
        d = index.nodes.get(n.get("referencedDeclaration"))
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
            return fold_constant(index, d, seen)
        return None
    if nt == "BinaryOperation":
        a, b = _const_expr(index, n["leftExpression"], seen), _const_expr(index, n["rightExpression"], seen)
        return _fold(n["operator"], a, b) if isinstance(a, int) and isinstance(b, int) else None
    if nt == "UnaryOperation" and n.get("operator") in ("-", "~", "!"):
        a = _const_expr(index, n["subExpression"], seen)
        return _fold({"-": "neg"}.get(n["operator"], n["operator"]), a) if isinstance(a, int) else None
    if nt == "FunctionCall" and n.get("kind") == "typeConversion" and len(n.get("arguments") or []) == 1:
        a = _const_expr(index, n["arguments"][0], seen)
        return convert_const(a, type_string(n)) if a is not None else None
    if nt == "FunctionCall" and (n.get("expression") or {}).get("name") == "keccak256" \
            and (n["expression"].get("referencedDeclaration") or 0) < 0 and len(n.get("arguments") or []) == 1:
        a = _const_expr(index, n["arguments"][0], seen)
        if isinstance(a, tuple) and a[:1] == ("str",):
            from ...keccak import keccak256
            return int.from_bytes(keccak256(bytes.fromhex(a[1])), "big")
        return None
    if nt == "TupleExpression" and len(n.get("components") or []) == 1 and not n.get("isInlineArray"):
        return _const_expr(index, n["components"][0], seen)
    return None


def count(op: str, a, n, step: int):
    """Iterations of `for (i = a; i op n; i += step)` (step < 0: i -= |step|)."""
    def sub(x, y):
        return x if y == 0 else fold("-", x, y)

    def div(x, k):
        return x if k == 1 else fold("/", x, k)

    if step > 0:
        s = step
        if op == "<":
            body = div(sub(n, a) if s == 1 else fold("+", sub(n, a), s - 1), s)
            return body if a == 0 else ite(fold("<", a, n), body, 0)
        if op == "<=":
            body = fold("+", div(sub(n, a), s), 1)
            return body if a == 0 else ite(fold("<=", a, n), body, 0)
        if op == "!=" and s == 1:
            return sub(n, a)
        return None
    s = -step
    if op == ">":
        body = div(sub(a, n) if s == 1 else fold("+", sub(a, n), s - 1), s)
        return body if n == 0 else ite(fold(">", a, n), body, 0)
    if op == ">=":
        return ite(fold(">=", a, n), fold("+", div(sub(a, n), s), 1), 0)
    if op == "!=" and s == 1:
        return sub(a, n)
    return None


def _root_decl(n: dict):
    x = n
    while x.get("nodeType") in ("IndexAccess", "MemberAccess", "IndexRangeAccess"):
        x = x.get("baseExpression") or x.get("expression") or {}
    return x.get("referencedDeclaration") if x.get("nodeType") == "Identifier" else None


def _lvalue_decls(n) -> set:
    out = set()
    if not isinstance(n, dict):
        return out
    if n.get("nodeType") == "Identifier" and isinstance(n.get("referencedDeclaration"), int):
        out.add(n["referencedDeclaration"])
    elif n.get("nodeType") == "TupleExpression":
        for c in n.get("components") or []:
            out |= _lvalue_decls(c)
    return out


def _is_local(index: Index, ref) -> bool:
    d = index.nodes.get(ref) if isinstance(ref, int) else None
    return d is not None and d.get("nodeType") == "VariableDeclaration" and not d.get("stateVariable")


def _is_input(t) -> bool:
    while isinstance(t, tuple) and t[:1] == ("member",):
        t = t[1]
    return isinstance(t, tuple) and t[:1] == ("param",)


def _input_root(t) -> str:
    while isinstance(t, tuple) and t[:1] == ("member",):
        t = t[1]
    return t[1]


def _external_ref(asm: dict | None, ident: dict):
    if asm is None:
        return None
    for r in asm.get("externalReferences") or []:
        if r.get("src") == ident.get("src"):
            return r
    return None


def _tuple_types(ts: str) -> list[str]:
    """The component type strings of "tuple(...)"."""
    inner = ts[len("tuple("):-1]
    if not inner.strip():
        return []
    out, depth, cur = [], 0, ""
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _tuple_arity(ts: str) -> int:
    inner = ts[len("tuple("):-1]
    if not inner.strip():
        return 0
    depth, k = 0, 1
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            k += 1
    return k


# ------------------------------------------------------------------------------------------------ the interface
def owner_of(index: Index, decl: dict) -> dict | None:
    """The ContractDefinition whose nodes hold decl (events and errors carry no scope in the compact AST)."""
    owners = getattr(index, "_owners", None)
    if owners is None:
        owners = {}
        for unit in sorted(index.asts):
            for c in index.asts[unit].get("nodes", []):
                if c.get("nodeType") == "ContractDefinition":
                    for x in c.get("nodes") or []:
                        if isinstance(x.get("id"), int):
                            owners[x["id"]] = c
        index._owners = owners
    return owners.get(decl.get("id")) or index.contract_of(decl)


def struct_def(index: Index, tn: dict | None):
    if not tn or tn.get("nodeType") != "UserDefinedTypeName":
        return None
    d = index.nodes.get(tn.get("referencedDeclaration"))
    return d if d is not None and d.get("nodeType") == "StructDefinition" else None


def _bare(ts: str) -> str:
    return re.sub(r" (storage|memory|calldata)( (ref|pointer|slice))?$", "", ts or "")


def width_of(ts: str):
    ts = _bare(ts)
    if ts.startswith("struct ") or ts.endswith("]") or ts in ("bytes", "string") or ts.startswith("mapping"):
        return None
    return conversion_bits(ts)


def params_of(index: Index, fn: dict) -> list[dict]:
    out = []
    for p in fn["parameters"]["parameters"]:
        tn = p.get("typeName") or {}
        ts = _bare(type_string(tn) or type_string(p))
        e = {"name": p["name"], "type": ts, "width": width_of(ts), "location": p.get("storageLocation") or "default"}
        sd = struct_def(index, tn)
        if sd is not None:
            e["fields"] = []
            for m in sd.get("members") or []:
                mts = _bare(type_string(m.get("typeName") or {}) or type_string(m))
                e["fields"].append({"name": m["name"], "type": mts, "width": width_of(mts)})
        out.append(e)
    return out


def abi_check(index: Index, t, tn: dict | None, ts: str):
    """The ABI decoder's range check of a value of type ts held by the term t (module docstring), or None."""
    ts = _bare(ts)
    info = int_info(ts)
    if info is not None:
        bits, signed = info
        if bits >= 256:
            return None
        return ("sfits", bits, t) if signed else ("<", t, 1 << bits)
    if ts in ("address", "address payable") or ts.startswith("contract ") or ts.startswith("interface "):
        return ("<", t, 1 << 160)
    if ts == "bool":
        return ("<", t, 2)
    m = re.fullmatch(r"bytes(\d+)", ts)
    if m and int(m.group(1)) < 32:
        return ("==", ("&", t, (1 << (256 - 8 * int(m.group(1)))) - 1), 0)
    if ts.startswith("enum "):
        d = index.nodes.get((tn or {}).get("referencedDeclaration")) if tn else None
        if d is None:
            name = ts[len("enum "):]
            for x in index.nodes.values():
                if x.get("nodeType") == "EnumDefinition" and x.get("canonicalName") == name:
                    d = x
                    break
        k = len((d or {}).get("members") or [])
        return ("<", t, k) if k else None
    return None


def abi_type(index: Index, tn: dict) -> str:
    """The canonical ABI type of a type name (event signatures)."""
    nt = tn.get("nodeType")
    if nt == "ElementaryTypeName":
        ts = type_string(tn) or tn.get("name") or ""
        if ts.startswith("address"):
            return "address"
        return {"uint": "uint256", "int": "int256", "byte": "bytes1"}.get(ts, ts)
    if nt == "UserDefinedTypeName":
        d = index.nodes.get(tn.get("referencedDeclaration")) or {}
        dt = d.get("nodeType")
        if dt == "ContractDefinition":
            return "address"
        if dt == "EnumDefinition":
            return "uint8"
        if dt == "StructDefinition":
            return "(" + ",".join(abi_type(index, m.get("typeName") or {}) for m in d.get("members") or []) + ")"
        if dt == "UserDefinedValueTypeDefinition":
            return abi_type(index, d.get("underlyingType") or {})
    if nt == "ArrayTypeName":
        base = abi_type(index, tn.get("baseType") or {})
        ln = tn.get("length")
        if ln is None:
            return base + "[]"
        v = _const_expr(index, ln, ())
        if not isinstance(v, int):
            raise ExtractionError(f"an array length the frontend cannot fold: {type_string(tn)}")
        return f"{base}[{v}]"
    if nt == "FunctionTypeName":
        return "function"
    raise ExtractionError(f"a type the ABI signature cannot hold: {type_string(tn) or nt}")


def _abi_components(t: str) -> list[str]:
    """The component types of a canonical tuple type "(a,b,...)"."""
    inner, out, depth, cur = t[1:-1], [], 0, ""
    if not inner:
        return []
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def abi_static_size(t: str) -> int | None:
    """The bytes a value of canonical ABI type t takes in place (the head of a tuple holding it), None for a dynamic
    type (string, bytes, T[], and arrays and tuples holding one), whose head is a 32-byte offset."""
    if t in ("string", "bytes") or t.endswith("[]"):
        return None
    m = re.fullmatch(r"(.+)\[(\d+)\]", t)
    if m:
        s = abi_static_size(m.group(1))
        return None if s is None else s * int(m.group(2))
    if t.startswith("("):
        sizes = [abi_static_size(c) for c in _abi_components(t)]
        return None if any(s is None for s in sizes) else sum(sizes)
    return 32


def abi_head_size(types: list[str]) -> int:
    """The size of the head of the ABI encoding of a tuple of the canonical types: what the decoder of an action's
    parameters requires of the calldata after the selector."""
    return sum(32 if s is None else s for s in (abi_static_size(t) for t in types))


def error_string() -> dict:
    """The revert data's error of a string reason: Error(string)."""
    from ...keccak import keccak256
    return {"name": "Error", "signature": "Error(string)", "selector": "0x" + keccak256(b"Error(string)")[:4].hex()}


def topic_term(t: str, v):
    """The log topic of an indexed event argument of canonical ABI type t whose ABI word (abi_word) is v: string and
    bytes ["keccak256", v] (folded for a constant), arrays and tuples ["keccak256", ["abi.inplace", v]] (the in-place
    encoding: the elements' encodings, each padded to 32 bytes), any other type v itself."""
    if t in ("string", "bytes"):
        if isinstance(v, tuple) and v[:1] == ("str",):
            from ...keccak import keccak256
            return int.from_bytes(keccak256(bytes.fromhex(v[1])), "big")
        return ("keccak256", v)
    if t.endswith("]") or t.startswith("("):
        return ("keccak256", ("abi.inplace", v))
    return v


# ------------------------------------------------------------------------------------------------ the contract
def find_contract(index: Index, name: str) -> dict:
    cs = index.contracts_named(name)
    if len(cs) != 1:
        raise ExtractionError(f"contract {name} found {len(cs)} times")
    return cs[0]


def actions_of(index: Index, contract: dict) -> list[dict]:
    """Every external or public FunctionDefinition with a body (not a constructor) of the contract, its own and the
    inherited ones: over the linearization, most derived first, one per selector (receive and fallback by kind)."""
    out, seen = [], set()
    for cid in contract.get("linearizedBaseContracts") or [contract["id"]]:
        c = index.nodes.get(cid) or {}
        for n in c.get("nodes") or []:
            if n.get("nodeType") == "FunctionDefinition" and n.get("visibility") in ("external", "public") \
                    and n.get("kind") in ("function", "receive", "fallback") and n.get("body") is not None:
                key = n.get("functionSelector") or n.get("kind")
                if key in seen:
                    continue
                seen.add(key)
                out.append(n)
    return sorted(out, key=lambda n: (n.get("name") or n.get("kind"), n["id"]))


def walk_contract(compiled, side: dict):
    """(index, contract, actions, collector): every action walked."""
    index = Index(compiled)
    tr = side["transitions"]
    contract = find_contract(index, tr["contract"])
    coll = Collector()
    acts = []
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 8000))
    try:
        for fn in actions_of(index, contract):
            acts.append(Walk(index, contract, fn, coll, tr.get("commit_interfaces") or []).run())
    except RecursionError as e:
        raise ExtractionError("the walk exceeds the recursion budget (a term or a call chain is too deep)") from e
    finally:
        sys.setrecursionlimit(limit)
    names = [a["name"] for a in acts]
    if len(set(names)) != len(names):
        dup = sorted({x for x in names if names.count(x) > 1})
        raise ExtractionError(f"contract {tr['contract']}: overloaded actions {dup} (one entry per name)")
    return index, contract, acts, coll


def build(compiled, side: dict, sidecar_rel: str, sidecar_sha256: str) -> dict:
    """The transitions document of a sidecar with "transitions"."""
    import hashlib
    index, contract, acts, _ = walk_contract(compiled, side)
    return {
        "facts_version": FACTS_VERSION,
        "target": dict(side["target"]),
        "extraction": {
            "method": "extracted",
            "frontend": "solidity",
            "kind": "transitions",
            "frontend_version": TRANSITIONS_VERSION,
            "sidecar": {"path": sidecar_rel, "sha256": sidecar_sha256},
            "toolchain": {"solc": {"version": compiled.version, "sha256": compiled.solc_sha256}},
            "settings": compiled.settings,
            "inputs": [{"unit": u, "sha256": hashlib.sha256(compiled.units[u]).hexdigest()}
                       for u in sorted(compiled.units)],
        },
        "contract": contract["name"],
        "constants": STORAGE.constants(contract, lambda d: fold_constant(index, d)),
        "storage": STORAGE.families(compiled, index, contract),
        "inherited_storage": STORAGE.inherited(compiled, index, contract),
        "actions": acts,
        "assumptions": [{"id": k, "text": v} for k, v in sorted(ASSUMPTIONS.items())],
    }


def statements_of(body: dict) -> list[dict]:
    """The Solidity Statement nodes inside a body (the body itself excluded; Yul is not entered)."""
    out, stack = [], [body]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x is not body and x.get("nodeType") in STATEMENTS and isinstance(x.get("id"), int):
                out.append(x)
            stack.extend(v for k, v in x.items() if k != "AST" and isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


def coverage_document(compiled, side: dict) -> dict:
    """{statements, extracted, debt, unaccounted} of the sidecar's contract (module docstring)."""
    index, contract, acts, coll = walk_contract(compiled, side)
    stmts: dict[int, dict] = {}
    returns: set = set()
    for fid in sorted(coll.reached):
        fn = coll.reached[fid]
        for s in statements_of(fn["body"]):
            stmts[s["id"]] = s
        for p in (fn.get("returnParameters") or {}).get("parameters", []):
            returns.add(p["id"])
    extracted, unaccounted = 0, []
    for sid in sorted(stmts):
        tags = coll.tags.get(sid, set())
        feeding = "local" in tags and ("memory" in tags or any(d in coll.reads or d in returns
                                                                for d in coll.defs.get(sid, ())))
        if tags & EXTRACTED_TAGS or feeding:
            extracted += 1
        elif "debt" in tags or sid in coll.covered_by_debt:
            continue
        else:
            s = stmts[sid]
            unaccounted.append({"src": index.span(s["src"]), "node": s["nodeType"]})
    debt = [{"src": src, "kind": kind, "detail": detail} for (src, kind, detail) in coll.debt]
    return {
        "statements": len(stmts),
        "extracted": extracted,
        "debt": sorted(debt, key=lambda d: (d["src"], d["kind"], d["detail"])),
        "unaccounted": sorted(unaccounted, key=lambda d: (d["src"], d["node"])),
    }
