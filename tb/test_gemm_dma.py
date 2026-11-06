import os, sys
import numpy as np
import cocotb
from cocotb.triggers import RisingEdge

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bfm import reset, wr, rd, WbMemory

LANES = int(os.environ.get("LANES", "4"))

# word addresses
A_BUF, B_BUF = 0, 4
CTRL = 32
DMA_CTRL, DMA_STATUS, DMA_A, DMA_AS, DMA_B, DMA_BS, DMA_C, DMA_CS, DMA_K, DMA_CYC = range(48, 58)

CTRL_START, CTRL_ACC, CTRL_IRQ, CTRL_SRST, CTRL_CLEAR = 0x01, 0x02, 0x04, 0x08, 0x10
DMA_START, DMA_ACC_FIRST = 0x1, 0x2
DS_BUSY, DS_DONE, DS_ERROR = 0x1, 0x2, 0x4
E_ALIGN, E_BUS, E_TIMEOUT, E_PARAM = 1, 2, 3, 4

BASE = 0x40000000
A_MEM, B_MEM, C_MEM = BASE + 0x1000, BASE + 0x2000, BASE + 0x4000


def rand_i8(rng, shape):
    return rng.integers(-128, 128, shape, dtype=np.int8)


def err_code(st):
    return (st >> 4) & 0x7


async def setup(dut, latency=1):
    await reset(dut)
    mem = WbMemory(dut, latency=latency)
    cocotb.start_soon(mem.run())
    return mem


async def dma_wait(dut, max_polls=3000):
    for _ in range(max_polls):
        st = await rd(dut, DMA_STATUS)
        if st & (DS_DONE | DS_ERROR):
            return st
    raise AssertionError("timeout waiting for DMA done/error")


async def program(dut, a, a_stride, b, b_stride, c, c_stride, k):
    await wr(dut, DMA_A, a)
    await wr(dut, DMA_AS, a_stride)
    await wr(dut, DMA_B, b)
    await wr(dut, DMA_BS, b_stride)
    await wr(dut, DMA_C, c)
    await wr(dut, DMA_CS, c_stride)
    await wr(dut, DMA_K, k)


async def run_desc(dut, a, a_stride, b, b_stride, c, c_stride, k, acc_first=0, max_polls=3000):
    await program(dut, a, a_stride, b, b_stride, c, c_stride, k)
    await wr(dut, CTRL, CTRL_CLEAR)
    await wr(dut, DMA_CTRL, DMA_START | (DMA_ACC_FIRST if acc_first else 0))
    return await dma_wait(dut, max_polls)


async def run_matrix(dut, mem, n, seed):
    """C = A*B for n x n int8 matrices, one DMA descriptor per 4x4 output tile."""
    rng = np.random.default_rng(seed)
    A = rand_i8(rng, (n, n))
    B = rand_i8(rng, (n, n))
    mem.write_i8_matrix(A_MEM, A, n)
    mem.write_i8_matrix(B_MEM, B, n)
    mem.clear_log()
    nt = n // 4
    await wr(dut, DMA_AS, n)
    await wr(dut, DMA_BS, n)
    await wr(dut, DMA_CS, 4 * n)
    await wr(dut, DMA_K, nt)
    cyc = 0
    for ti in range(nt):
        for tj in range(nt):
            await wr(dut, DMA_A, A_MEM + ti * 4 * n)
            await wr(dut, DMA_B, B_MEM + tj * 4)
            await wr(dut, DMA_C, C_MEM + ti * 16 * n + tj * 16)
            await wr(dut, CTRL, CTRL_CLEAR)
            await wr(dut, DMA_CTRL, DMA_START)
            st = await dma_wait(dut)
            assert (st & DS_DONE) and not (st & DS_ERROR), f"tile ({ti},{tj}) status {st:#x}"
            cyc = await rd(dut, DMA_CYC)
    got = mem.read_i32_matrix(C_MEM, n, n, 4 * n)
    exp = A.astype(np.int64) @ B.astype(np.int64)
    assert (got == exp).all(), f"matrix {n}x{n} mismatch"
    return cyc, nt


@cocotb.test()
async def test_dma_register_readback(dut):
    await reset(dut)
    vals = {DMA_A: 0x40001234, DMA_AS: 0x20, DMA_B: 0x40002000,
            DMA_BS: 0x40, DMA_C: 0x40003000, DMA_CS: 0x80}
    for r, v in vals.items():
        await wr(dut, r, v)
    for r, v in vals.items():
        assert await rd(dut, r) == v, f"register {r} readback"
    await wr(dut, DMA_K, 0x12345)
    assert await rd(dut, DMA_K) == 0x2345, "K_TILES is 16 bits"
    assert await rd(dut, DMA_STATUS) == 0
    assert await rd(dut, DMA_CYC) == 0


@cocotb.test()
async def test_single_tile(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(1)
    A, B = rand_i8(rng, (4, 4)), rand_i8(rng, (4, 4))
    mem.write_i8_matrix(A_MEM, A, 4)
    mem.write_i8_matrix(B_MEM, B, 4)
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_DONE) and not (st & DS_ERROR) and not (st & DS_BUSY)
    got = mem.read_i32_matrix(C_MEM, 4, 4, 16)
    assert (got == A.astype(np.int64) @ B.astype(np.int64)).all()
    assert len(mem.reads) == 8, f"expected 8 reads, saw {len(mem.reads)}"
    assert len(mem.writes) == 16, f"expected 16 writes, saw {len(mem.writes)}"
    cyc = await rd(dut, DMA_CYC)
    dut._log.info(f"single tile: DMA cycles = {cyc} (LANES={LANES}, memory latency=1)")
    assert 48 < cyc < 480


@cocotb.test()
async def test_matrix_sizes(dut):
    mem = await setup(dut)
    for n in (4, 8, 16, 32):
        cyc, nt = await run_matrix(dut, mem, n, seed=n)
        # bus traffic: 8 reads per K step, C written once per output tile
        assert len(mem.reads) == nt * nt * nt * 8, f"N={n}: reads {len(mem.reads)}"
        assert len(mem.writes) == nt * nt * 16, f"N={n}: writes {len(mem.writes)}"
        dut._log.info(f"N={n}: matches numpy; last tile DMA cycles = {cyc} (K steps = {nt})")


@cocotb.test()
async def test_acc_first(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(2)
    A1, B1, A2, B2 = (rand_i8(rng, (4, 4)) for _ in range(4))
    mem.write_i8_matrix(A_MEM, A1, 4)
    mem.write_i8_matrix(B_MEM, B1, 4)
    mem.write_i8_matrix(A_MEM + 0x100, A2, 4)
    mem.write_i8_matrix(B_MEM + 0x100, B2, 4)
    c1 = A1.astype(np.int64) @ B1.astype(np.int64)
    c2 = A2.astype(np.int64) @ B2.astype(np.int64)
    await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (mem.read_i32_matrix(C_MEM, 4, 4, 16) == c1).all()
    await run_desc(dut, A_MEM + 0x100, 4, B_MEM + 0x100, 4, C_MEM + 0x100, 16, 1, acc_first=1)
    assert (mem.read_i32_matrix(C_MEM + 0x100, 4, 4, 16) == c1 + c2).all(), \
        "ACC_FIRST must add onto the core's previous result"


@cocotb.test()
async def test_alignment_and_param_errors(dut):
    mem = await setup(dut)
    good = dict(a=A_MEM, a_stride=4, b=B_MEM, b_stride=4, c=C_MEM, c_stride=16, k=1)
    cases = [
        ("A misaligned", dict(a=A_MEM + 1), E_ALIGN),
        ("B misaligned", dict(b=B_MEM + 2), E_ALIGN),
        ("C misaligned", dict(c=C_MEM + 3), E_ALIGN),
        ("A stride misaligned", dict(a_stride=6), E_ALIGN),
        ("C stride misaligned", dict(c_stride=17), E_ALIGN),
        ("K_TILES = 0", dict(k=0), E_PARAM),
    ]
    for name, override, code in cases:
        mem.clear_log()
        d = dict(good)
        d.update(override)
        st = await run_desc(dut, d["a"], d["a_stride"], d["b"], d["b_stride"],
                            d["c"], d["c_stride"], d["k"])
        assert st & DS_ERROR, f"{name}: ERROR not set"
        assert not (st & DS_DONE), f"{name}: DONE must not be set"
        assert err_code(st) == code, f"{name}: code {err_code(st)}, expected {code}"
        assert len(mem.reads) == 0 and len(mem.writes) == 0, f"{name}: bus traffic on a bad descriptor"
        await wr(dut, CTRL, CTRL_CLEAR)
        assert await rd(dut, DMA_STATUS) == 0, f"{name}: DONE_CLR must clear the error"


@cocotb.test()
async def test_bus_error_on_read(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(3)
    A, B = rand_i8(rng, (4, 4)), rand_i8(rng, (4, 4))
    mem.write_i8_matrix(A_MEM, A, 4)
    mem.write_i8_matrix(B_MEM, B, 4)
    mem.err_addrs.add(A_MEM + 4)                       # second A word fails
    mem.clear_log()
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_ERROR) and err_code(st) == E_BUS and not (st & DS_DONE)
    assert len(mem.reads) == 1, f"DMA must stop after the failing read, saw {len(mem.reads)} reads"
    assert len(mem.writes) == 0
    for _ in range(10):
        await RisingEdge(dut.clk)
    assert int(dut.m_cyc.value) == 0 and int(dut.m_stb.value) == 0, "bus must be released"
    mem.err_addrs.clear()                              # recovery
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_DONE) and not (st & DS_ERROR)
    assert (mem.read_i32_matrix(C_MEM, 4, 4, 16) == A.astype(np.int64) @ B.astype(np.int64)).all()


@cocotb.test()
async def test_bus_error_on_write(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(4)
    A, B = rand_i8(rng, (4, 4)), rand_i8(rng, (4, 4))
    mem.write_i8_matrix(A_MEM, A, 4)
    mem.write_i8_matrix(B_MEM, B, 4)
    mem.err_addrs.add(C_MEM + 16)                      # row 1 of the C tile fails
    mem.clear_log()
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_ERROR) and err_code(st) == E_BUS
    assert len(mem.writes) == 4, f"expected 4 successful writes, saw {len(mem.writes)}"
    await wr(dut, CTRL, CTRL_CLEAR)
    mem.err_addrs.clear()
    mem.clear_log()
    # unmapped (out-of-range) destination
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, 0x20000000, 16, 1)
    assert (st & DS_ERROR) and err_code(st) == E_BUS
    assert len(mem.writes) == 0 and len(mem.reads) == 8


@cocotb.test()
async def test_timeout(dut):
    mem = await setup(dut)
    mem.hang_addrs.add(B_MEM)                          # first B read never answers
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1, max_polls=4000)
    assert (st & DS_ERROR) and err_code(st) == E_TIMEOUT, f"status {st:#x}"
    assert await rd(dut, DMA_CYC) >= 1024, "timeout must take at least the timeout interval"
    for _ in range(10):
        await RisingEdge(dut.clk)
    assert int(dut.m_cyc.value) == 0 and int(dut.m_stb.value) == 0
    mem.hang_addrs.clear()
    await wr(dut, CTRL, CTRL_CLEAR)
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_DONE) and not (st & DS_ERROR)


@cocotb.test()
async def test_dma_irq(dut):
    mem = await setup(dut, latency=2)
    rng = np.random.default_rng(5)
    n = 16
    A, B = rand_i8(rng, (n, n)), rand_i8(rng, (n, n))
    mem.write_i8_matrix(A_MEM, A, n)
    mem.write_i8_matrix(B_MEM, B, n)
    await program(dut, A_MEM, n, B_MEM, n, C_MEM, 4 * n, n // 4)   # K = 4 steps
    await wr(dut, CTRL, CTRL_CLEAR | CTRL_IRQ)                     # clear, IRQ_EN = 1
    await wr(dut, DMA_CTRL, DMA_START)
    seen = False
    for _ in range(4000):
        await RisingEdge(dut.clk)
        if int(dut.irq.value):
            assert int(dut.u_dma.done.value) == 1 or int(dut.u_dma.error.value) == 1, \
                "irq must not rise before the DMA completes (core done pulses are masked)"
            seen = True
            break
    assert seen, "irq never asserted"
    await wr(dut, CTRL, CTRL_CLEAR | CTRL_IRQ)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.irq.value) == 0, "irq must drop after DONE_CLR"


@cocotb.test()
async def test_pio_ignored_during_dma(dut):
    mem = await setup(dut, latency=3)
    rng = np.random.default_rng(6)
    n = 16
    A, B = rand_i8(rng, (n, n)), rand_i8(rng, (n, n))
    mem.write_i8_matrix(A_MEM, A, n)
    mem.write_i8_matrix(B_MEM, B, n)
    await program(dut, A_MEM, n, B_MEM, n, C_MEM, 4 * n, n // 4)
    await wr(dut, CTRL, CTRL_CLEAR)
    await wr(dut, DMA_CTRL, DMA_START)
    st = 0
    for _ in range(3000):
        await wr(dut, A_BUF, 0xFFFFFFFF)         # must be ignored while the DMA runs
        await wr(dut, B_BUF + 1, 0xFFFFFFFF)
        await wr(dut, CTRL, CTRL_START)          # PIO start must be ignored too
        st = await rd(dut, DMA_STATUS)
        if st & (DS_DONE | DS_ERROR):
            break
    assert (st & DS_DONE) and not (st & DS_ERROR), f"status {st:#x}"
    exp = (A.astype(np.int64) @ B.astype(np.int64))[0:4, 0:4]
    assert (mem.read_i32_matrix(C_MEM, 4, 4, 4 * n) == exp).all(), "PIO traffic corrupted the DMA result"


@cocotb.test()
async def test_latency_sweep(dut):
    mem = await setup(dut, latency=1)
    cycles = []
    for lat in (1, 2, 5, 9):
        mem.latency = lat
        cyc, _ = await run_matrix(dut, mem, 8, seed=7)
        cycles.append(cyc)
        dut._log.info(f"memory latency {lat}: matches numpy, last tile DMA cycles = {cyc}")
    assert cycles == sorted(cycles) and cycles[0] < cycles[-1], f"cycles should grow with latency: {cycles}"


@cocotb.test()
async def test_soft_reset_mid_dma(dut):
    mem = await setup(dut, latency=2)
    rng = np.random.default_rng(8)
    n = 16
    A, B = rand_i8(rng, (n, n)), rand_i8(rng, (n, n))
    mem.write_i8_matrix(A_MEM, A, n)
    mem.write_i8_matrix(B_MEM, B, n)
    await program(dut, A_MEM, n, B_MEM, n, C_MEM, 4 * n, n // 4)
    await wr(dut, CTRL, CTRL_CLEAR)
    await wr(dut, DMA_CTRL, DMA_START)
    for _ in range(60):
        await RisingEdge(dut.clk)
    assert int(dut.u_dma.busy.value) == 1, "DMA should still be running"
    await wr(dut, CTRL, CTRL_SRST)
    for _ in range(6):
        await RisingEdge(dut.clk)
    assert int(dut.u_dma.busy.value) == 0 and int(dut.m_cyc.value) == 0, "soft reset must abort the DMA"
    assert await rd(dut, DMA_STATUS) == 0
    mem.clear_log()
    st = await run_desc(dut, A_MEM, n, B_MEM, n, C_MEM, 4 * n, n // 4)
    assert (st & DS_DONE) and not (st & DS_ERROR)
    exp = (A.astype(np.int64) @ B.astype(np.int64))[0:4, 0:4]
    assert (mem.read_i32_matrix(C_MEM, 4, 4, 4 * n) == exp).all()


DMA_XFERS, DMA_WAITS = 58, 59


@cocotb.test()
async def test_dma_counters(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(9)
    n = 8
    A, B = rand_i8(rng, (n, n)), rand_i8(rng, (n, n))
    mem.write_i8_matrix(A_MEM, A, n)
    mem.write_i8_matrix(B_MEM, B, n)
    k = n // 4
    for lat in (1, 3):
        mem.latency = lat
        st = await run_desc(dut, A_MEM, n, B_MEM, n, C_MEM, 4 * n, k)
        assert (st & DS_DONE) and not (st & DS_ERROR)
        xfers = await rd(dut, DMA_XFERS)
        waits = await rd(dut, DMA_WAITS)
        assert xfers == 8 * k + 16, f"xfers {xfers}, expected {8 * k + 16}"
        assert waits == xfers * lat, f"waits {waits}, expected xfers*latency = {xfers * lat}"
        dut._log.info(f"latency {lat}: xfers={xfers} waits={waits}")


@cocotb.test()
async def test_back_to_back_cycles(dut):
    mem = await setup(dut)
    rng = np.random.default_rng(10)
    A, B = rand_i8(rng, (4, 4)), rand_i8(rng, (4, 4))
    mem.write_i8_matrix(A_MEM, A, 4)
    mem.write_i8_matrix(B_MEM, B, 4)
    st = await run_desc(dut, A_MEM, 4, B_MEM, 4, C_MEM, 16, 1)
    assert (st & DS_DONE) and not (st & DS_ERROR)
    cyc = await rd(dut, DMA_CYC)
    core = 64 // LANES + 1
    dut._log.info(f"back-to-back single tile: DMA cycles = {cyc} (v0.5 design: {77 + core}, LANES={LANES})")
    assert cyc <= 65 + core, f"cycles {cyc} should be well below the v0.5 value {77 + core}"
