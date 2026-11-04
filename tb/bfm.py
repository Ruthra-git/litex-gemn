import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


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
    """CPU-side Wishbone classic transfer into the DUT's slave port."""
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


class WbMemory:
    """Wishbone slave memory model answering the DUT's DMA master port.

    latency: cycles from request to ack (>= 1)
    err_addrs: byte addresses that answer with err instead of ack
    hang_addrs: byte addresses that never answer
    Addresses outside [base, base+size) also answer with err (unmapped)."""

    def __init__(self, dut, latency=1, base=0x40000000, size=0x100000):
        self.dut = dut
        self.latency = latency
        self.base = base
        self.size = size
        self.words = {}
        self.err_addrs = set()
        self.hang_addrs = set()
        self.reads = []
        self.writes = []

    def in_range(self, a):
        return self.base <= a < self.base + self.size

    def poke_word(self, a, v):
        self.words[a & ~3] = v & 0xFFFFFFFF

    def peek_word(self, a):
        return self.words.get(a & ~3, 0)

    def write_i8_matrix(self, addr, M, stride):
        rows, cols = M.shape
        for r in range(rows):
            for c4 in range(0, cols, 4):
                w = 0
                for j in range(4):
                    w |= (int(M[r, c4 + j]) & 0xFF) << (8 * j)
                self.poke_word(addr + r * stride + c4, w)

    def read_i32_matrix(self, addr, rows, cols, stride):
        out = np.zeros((rows, cols), dtype=np.int64)
        for r in range(rows):
            for c in range(cols):
                out[r, c] = s32(self.peek_word(addr + r * stride + 4 * c))
        return out

    def clear_log(self):
        self.reads.clear()
        self.writes.clear()

    async def run(self):
        dut = self.dut
        state = "idle"
        cnt = 0
        while True:
            await RisingEdge(dut.clk)
            if state == "ack":
                dut.m_ack.value = 0
                dut.m_err.value = 0
                state = "idle"
                continue
            cyc = int(dut.m_cyc.value)
            stb = int(dut.m_stb.value)
            if state == "idle":
                if cyc and stb:
                    self.adr = int(dut.m_adr.value)
                    self.we = int(dut.m_we.value)
                    self.dat = int(dut.m_dat_w.value)
                    self.sel = int(dut.m_sel.value)
                    cnt = self.latency - 1
                    state = "wait"
            if state == "wait":
                if not (cyc and stb):           # master aborted (e.g. soft reset)
                    state = "idle"
                    continue
                if cnt > 0:
                    cnt -= 1
                    continue
                a = self.adr
                if a in self.hang_addrs:
                    state = "hang"
                    continue
                if (not self.in_range(a)) or (a in self.err_addrs):
                    dut.m_err.value = 1
                    state = "ack"
                    continue
                if self.we:
                    new = self.peek_word(a)
                    for b in range(4):
                        if self.sel & (1 << b):
                            new = (new & ~(0xFF << (8 * b))) | (self.dat & (0xFF << (8 * b)))
                    self.poke_word(a, new)
                    self.writes.append(a)
                    dut.m_dat_r.value = 0
                else:
                    dut.m_dat_r.value = self.peek_word(a)
                    self.reads.append(a)
                dut.m_ack.value = 1
                state = "ack"
            elif state == "hang":
                if not (cyc and stb):
                    state = "idle"
