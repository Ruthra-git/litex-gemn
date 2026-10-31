import os, sys, json
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model"))
from gemm_golden import make_vectors

LANES = int(os.environ.get("LANES", "4"))
EXPECTED_CYCLES = 64 // LANES + 1
TIMEOUT = 200


def pack_i8(M):
    v = 0
    for i, x in enumerate(M.flatten()):
        v |= (int(x) & 0xFF) << (8 * i)
    return v


def unpack_i32(v):
    out = []
    for i in range(16):
        w = (v >> (32 * i)) & 0xFFFFFFFF
        out.append(w - (1 << 32) if w & 0x80000000 else w)
    return np.array(out, dtype=np.int64).reshape(4, 4)


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    dut.rst.value = 1
    dut.start.value = 0
    dut.done_clear.value = 0
    dut.accumulate.value = 0
    dut.a_flat.value = 0
    dut.b_flat.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def start_tile(dut, A, B, acc=0):
    dut.a_flat.value = pack_i8(A)
    dut.b_flat.value = pack_i8(B)
    dut.accumulate.value = acc
    dut.start.value = 1
    await RisingEdge(dut.clk)      # the edge that accepts start
    dut.start.value = 0


async def wait_done(dut):
    for _ in range(TIMEOUT):
        await RisingEdge(dut.clk)
        if int(dut.done.value) == 1:
            await RisingEdge(dut.clk)   # settle before reading outputs
            return
    raise AssertionError("timeout waiting for done")


async def run_tile(dut, A, B, acc=0):
    await start_tile(dut, A, B, acc)
    await wait_done(dut)
    return unpack_i32(int(dut.c_flat.value)), int(dut.cycles.value)


@cocotb.test()
async def test_reset_state(dut):
    await reset(dut)
    assert int(dut.busy.value) == 0
    assert int(dut.done.value) == 0
    assert int(dut.error.value) == 0


@cocotb.test()
async def test_corner_cases(dut):
    await reset(dut)
    for n, (A, B, C) in enumerate(make_vectors(n_random=0)):
        got, _ = await run_tile(dut, A, B)
        assert (got == C.astype(np.int64)).all(), \
            f"corner case {n} mismatch:\n{got}\nexpected\n{C}"


@cocotb.test()
async def test_random_vectors(dut):
    await reset(dut)
    path = os.path.join(os.path.dirname(__file__), "vectors_4x4.json")
    with open(path) as f:
        vecs = json.load(f)
    for n, v in enumerate(vecs):
        A = np.array(v["A"], dtype=np.int8)
        B = np.array(v["B"], dtype=np.int8)
        C = np.array(v["C"], dtype=np.int64)
        got, _ = await run_tile(dut, A, B)
        assert (got == C).all(), f"vector {n} mismatch:\n{got}\nexpected\n{C}"
    dut._log.info(f"{len(vecs)} vectors matched bit-exact (LANES={LANES})")


@cocotb.test()
async def test_cycle_count(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    _, cycles = await run_tile(dut, A, B)
    assert cycles == EXPECTED_CYCLES, \
        f"cycles={cycles}, expected {EXPECTED_CYCLES} (LANES={LANES})"


@cocotb.test()
async def test_start_while_busy(dut):
    await reset(dut)
    (A, B, C), (A2, B2, _) = make_vectors(n_random=2)[-2:]
    await start_tile(dut, A, B)
    dut.a_flat.value = pack_i8(A2)       # different inputs, second start
    dut.b_flat.value = pack_i8(B2)
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.error.value) == 1, "start while busy must set error"
    await wait_done(dut)
    got = unpack_i32(int(dut.c_flat.value))
    assert (got == C.astype(np.int64)).all(), "ignored start must not disturb the tile"


@cocotb.test()
async def test_done_sticky_and_clear(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await run_tile(dut, A, B)
    for _ in range(5):
        await RisingEdge(dut.clk)
        assert int(dut.done.value) == 1, "done must stay set until cleared"
    dut.done_clear.value = 1
    await RisingEdge(dut.clk)
    dut.done_clear.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.done.value) == 0, "done_clear must clear done"


@cocotb.test()
async def test_reset_mid_run(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await start_tile(dut, A, B)
    await RisingEdge(dut.clk)
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.busy.value) == 0 and int(dut.done.value) == 0 \
        and int(dut.error.value) == 0
    got, _ = await run_tile(dut, A, B)
    assert (got == C.astype(np.int64)).all(), "core must work after a mid-run reset"


@cocotb.test()
async def test_accumulate(dut):
    await reset(dut)
    vecs = make_vectors(n_random=6)[-6:]
    total = None
    for n, (A, B, C) in enumerate(vecs):
        got, _ = await run_tile(dut, A, B, acc=(1 if n > 0 else 0))
        total = C.astype(np.int64) if n == 0 else total + C.astype(np.int64)
        assert (got == total).all(), f"accumulate step {n} mismatch:\n{got}\nexpected\n{total}"
    # acc=0 afterwards must overwrite, not add
    A, B, C = make_vectors(n_random=1)[-1]
    got, _ = await run_tile(dut, A, B, acc=0)
    assert (got == C.astype(np.int64)).all(), "acc=0 must overwrite the previous result"


@cocotb.test()
async def test_accumulate_latched_at_start(dut):
    await reset(dut)
    (A1, B1, C1), (A2, B2, C2) = make_vectors(n_random=2)[-2:]
    await run_tile(dut, A1, B1, acc=0)
    await start_tile(dut, A2, B2, acc=0)
    dut.accumulate.value = 1             # changing it after accept must not matter
    await wait_done(dut)
    got = unpack_i32(int(dut.c_flat.value))
    assert (got == C2.astype(np.int64)).all(), "accumulate must be latched at start accept"
