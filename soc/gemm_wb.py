import os
from types import SimpleNamespace

from migen import *
from litex.soc.interconnect import wishbone

RTL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rtl"))


class GemmWB(Module):
    """Wraps rtl/gemm_wb.v: Wishbone slave (CPU), Wishbone master (DMA), interrupt line."""
    def __init__(self, platform, lanes=4, dma_timeout=1024):
        self.bus     = wishbone.Interface(data_width=32)   # slave: CPU accesses the accelerator
        self.dma_bus = wishbone.Interface(data_width=32)   # master: DMA accesses main RAM
        self.irq = Signal()
        self.ev  = SimpleNamespace(irq=self.irq)

        dma_adr = Signal(32)

        for f in ("gemm_core.v", "gemm_dma.v", "gemm_wb.v"):
            platform.add_source(os.path.join(RTL_DIR, f))

        self.specials += Instance("gemm_wb",
            p_LANES       = lanes,
            p_DMA_TIMEOUT = dma_timeout,
            i_clk      = ClockSignal(),
            i_rst      = ResetSignal(),
            i_wb_cyc   = self.bus.cyc,
            i_wb_stb   = self.bus.stb,
            i_wb_we    = self.bus.we,
            i_wb_adr   = self.bus.adr[0:6],
            i_wb_dat_w = self.bus.dat_w,
            i_wb_sel   = self.bus.sel,
            o_wb_dat_r = self.bus.dat_r,
            o_wb_ack   = self.bus.ack,
            o_m_cyc    = self.dma_bus.cyc,
            o_m_stb    = self.dma_bus.stb,
            o_m_we     = self.dma_bus.we,
            o_m_adr    = dma_adr,
            o_m_dat_w  = self.dma_bus.dat_w,
            o_m_sel    = self.dma_bus.sel,
            i_m_dat_r  = self.dma_bus.dat_r,
            i_m_ack    = self.dma_bus.ack,
            i_m_err    = self.dma_bus.err,
            o_irq      = self.irq,
        )
        self.comb += self.dma_bus.adr.eq(dma_adr[2:32])   # LiteX Wishbone uses word addresses
