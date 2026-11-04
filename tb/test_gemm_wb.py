import os, sys
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model"))
from gemm_golden import make_vectors

LANES = int(os.environ.get("LANES", "4"))
EXPECTED_CYCLES = 64 // LANES + 1

# word addresses (byte offset / 4)
A_BASE, B_BASE, C_BASE = 0, 4, 16
CTRL, STATUS, CYCLES, ID_REG, INFO = 32, 33, 34, 35, 36

CTRL_START, CTRL_ACC, CTRL_IRQ, CTRL_SRST, CTRL_CLEAR = 0x01, 0x02, 0x04, 0x08, 0x10
ST_BUSY, ST_DONE, ST_ERROR = 0x1, 0x2, 0x4


def pack_i8(M):
    v = 0
    for i, x in enumerate(M.flatten()):
        v |= (int(x) & 0xFF) << (8 * i)
    return v


def split_words(v128):
    return [(v128 >> (32 * i)) & 0xFFFFFFFF for i in range(4)]


def s32(w):
    return w - (1 << 32) if w & 0x80000000 else w


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    dut.rst.value = 1
    dut.wb_cyc.value = 0
    dut.wb_stb.value = 0
    dut.wb_we.value = 0
    dut.wb_adr.value = 0
    dut.wb_dat_w.value = 0
    dut.wb_sel.value = 0xF
    dut.m_ack.value = 0
    dut.m_err.value = 0
    dut.m_dat_r.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def wb_xfer(dut, adr, we, data=0, sel=0xF):
    dut.wb_adr.value = adr
    dut.wb_we.value = 1 if we else 0
    dut.wb_dat_w.value = data
    dut.wb_sel.value = sel
    dut.wb_cyc.value = 1
    dut.wb_stb.value = 1
    for _ in range(16):
        await RisingEdge(dut.clk)
        if int(dut.wb_ack.value) == 1:
            rd = int(dut.wb_dat_r.value)
            dut.wb_cyc.value = 0
            dut.wb_stb.value = 0
            dut.wb_we.value = 0
            return rd
    raise AssertionError(f"wishbone timeout at word address {adr}")


async def wr(dut, adr, data, sel=0xF):
    await wb_xfer(dut, adr, True, data, sel)


async def rd(dut, adr):
    return await wb_xfer(dut, adr, False)


async def load_tile(dut, A, B):
    for i, w in enumerate(split_words(pack_i8(A))):
        await wr(dut, A_BASE + i, w)
    for i, w in enumerate(split_words(pack_i8(B))):
        await wr(dut, B_BASE + i, w)


async def wait_done(dut, max_polls=300):
    saw_busy = False
    for _ in range(max_polls):
        st = await rd(dut, STATUS)
        saw_busy = saw_busy or bool(st & ST_BUSY)
        if st & ST_DONE:
            return st, saw_busy
    raise AssertionError("timeout waiting for DONE")


async def read_c(dut):
    vals = []
    for i in range(16):
        vals.append(s32(await rd(dut, C_BASE + i)))
    return np.array(vals, dtype=np.int64).reshape(4, 4)


async def run_tile(dut, A, B, flags=0):
    await load_tile(dut, A, B)
    await wr(dut, CTRL, CTRL_START | flags)
    await wait_done(dut)
    return await read_c(dut)


@cocotb.test()
async def test_id_and_info(dut):
    await reset(dut)
    assert await rd(dut, ID_REG) == 0x47454D4D
    info = await rd(dut, INFO)
    assert (info & 0xFF) == LANES
    assert ((info >> 8) & 0xFF) == 4
    assert (info >> 16) == 0x0005


@cocotb.test()
async def test_buffer_readback_and_byte_enables(dut):
    await reset(dut)
    await wr(dut, A_BASE + 1, 0xAABBCCDD)
    assert await rd(dut, A_BASE + 1) == 0xAABBCCDD
    await wr(dut, A_BASE + 1, 0x11223344, sel=0b0101)   # bytes 0 and 2 only
    assert await rd(dut, A_BASE + 1) == 0xAA22CC44
    await wr(dut, B_BASE + 3, 0xDEADBEEF)
    assert await rd(dut, B_BASE + 3) == 0xDEADBEEF
    assert await rd(dut, A_BASE + 3) == 0, "A and B buffers must not alias"


@cocotb.test()
async def test_c_readonly_and_unmapped(dut):
    await reset(dut)
    await wr(dut, C_BASE, 0xFFFFFFFF)
    assert await rd(dut, C_BASE) == 0, "C window must be read-only"
    for adr in (8, 15, 37, 40, 63):
        await wr(dut, adr, 0xFFFFFFFF)
        assert await rd(dut, adr) == 0, f"unmapped word {adr} must read 0"
    # a write to word 40 must not alias onto CTRL and start anything
    st = await rd(dut, STATUS)
    assert st == 0, f"STATUS must be idle after unmapped writes, got {st:#x}"


@cocotb.test()
async def test_tile_via_bus_matches_golden(dut):
    await reset(dut)
    saw_busy_once = False
    vecs = make_vectors(n_random=100)
    for n, (A, B, C) in enumerate(vecs):
        await load_tile(dut, A, B)
        await wr(dut, CTRL, CTRL_START)
        _, saw_busy = await wait_done(dut)
        saw_busy_once = saw_busy_once or saw_busy
        got = await read_c(dut)
        assert (got == C.astype(np.int64)).all(), f"tile {n} mismatch:\n{got}\nexpected\n{C}"
    if LANES == 4:
        assert saw_busy_once, "BUSY should be observable by polling at LANES=4"


@cocotb.test()
async def test_cycles_register(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await run_tile(dut, A, B)
    assert await rd(dut, CYCLES) == EXPECTED_CYCLES


@cocotb.test()
async def test_accumulate_via_bus(dut):
    await reset(dut)
    vecs = make_vectors(n_random=4)[-4:]
    total = None
    for n, (A, B, C) in enumerate(vecs):
        got = await run_tile(dut, A, B, flags=(CTRL_ACC if n > 0 else 0))
        total = C.astype(np.int64) if n == 0 else total + C.astype(np.int64)
        assert (got == total).all(), f"accumulate step {n} mismatch"
    A, B, C = make_vectors(n_random=1)[-1]
    got = await run_tile(dut, A, B)                    # CTRL_ACC clear -> overwrite
    assert (got == C.astype(np.int64)).all()


@cocotb.test()
async def test_irq(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await run_tile(dut, A, B, flags=CTRL_IRQ)
    await RisingEdge(dut.clk)
    assert int(dut.irq.value) == 1, "irq must be asserted when DONE and IRQ_EN"
    await wr(dut, CTRL, CTRL_CLEAR | CTRL_IRQ)         # clear DONE, keep IRQ_EN
    await RisingEdge(dut.clk)
    assert int(dut.irq.value) == 0, "irq must drop once DONE is cleared"
    assert (await rd(dut, CTRL)) & 0x4, "IRQ_EN must read back as set"
    await run_tile(dut, A, B)                          # IRQ_EN now 0
    await RisingEdge(dut.clk)
    assert int(dut.irq.value) == 0, "irq must stay low when IRQ_EN is clear"


@cocotb.test()
async def test_start_while_busy(dut):
    await reset(dut)
    (A, B, C), _ = make_vectors(n_random=2)[-2:]
    await load_tile(dut, A, B)
    await wr(dut, CTRL, CTRL_START)
    await wr(dut, CTRL, CTRL_START | CTRL_ACC)         # second start while busy
    st, _ = await wait_done(dut)
    assert st & ST_ERROR, "ERROR must be set by start while busy"
    got = await read_c(dut)
    assert (got == C.astype(np.int64)).all(), "ignored start must not alter the result"


@cocotb.test()
async def test_buffer_writes_during_busy_do_not_corrupt(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await load_tile(dut, A, B)
    await wr(dut, CTRL, CTRL_START)
    await wr(dut, A_BASE, 0xFFFFFFFF)                  # clobber inputs while running
    await wr(dut, B_BASE, 0xFFFFFFFF)
    await wait_done(dut)
    got = await read_c(dut)
    assert (got == C.astype(np.int64)).all(), "inputs are latched at start accept"


@cocotb.test()
async def test_soft_reset_mid_run(dut):
    await reset(dut)
    A, B, C = make_vectors(n_random=1)[-1]
    await load_tile(dut, A, B)
    await wr(dut, CTRL, CTRL_START)
    await wr(dut, CTRL, CTRL_SRST)
    st = await rd(dut, STATUS)
    assert st == 0, f"soft reset must clear BUSY/DONE/ERROR, got {st:#x}"
    got = await run_tile(dut, A, B)
    assert (got == C.astype(np.int64)).all(), "engine must work after a soft reset"
