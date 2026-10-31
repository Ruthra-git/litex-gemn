import os
from types import SimpleNamespace

from migen import *
from litex.soc.interconnect import wishbone

RTL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rtl"))


class GemmWB(Module):
    """Wraps rtl/gemm_wb.v as a Wishbone slave with an interrupt line."""
    def __init__(self, platform, lanes=4):
        self.bus = wishbone.Interface(data_width=32)
        self.irq = Signal()
        # Minimal 'ev.irq' contract that SoC.irq.add(...) looks for.
        self.ev = SimpleNamespace(irq=self.irq)

        platform.add_source(os.path.join(RTL_DIR, "gemm_core.v"))
        platform.add_source(os.path.join(RTL_DIR, "gemm_wb.v"))

        self.specials += Instance("gemm_wb",
            p_LANES    = lanes,
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
            o_irq      = self.irq,
        )
