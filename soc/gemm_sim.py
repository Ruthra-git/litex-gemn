#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import litex.tools.litex_sim as litex_sim
from litex.soc.integration.soc import SoCRegion
from gemm_wb import GemmWB

GEMM_BASE = 0x90000000
GEMM_SIZE = 0x100

_OrigSimSoC = litex_sim.SimSoC


class GemmSimSoC(_OrigSimSoC):
    def __init__(self, *args, **kwargs):
        _OrigSimSoC.__init__(self, *args, **kwargs)
        self.gemm = GemmWB(self.platform, lanes=int(os.environ.get("GEMM_LANES", "4")))
        self.bus.add_slave("gemm", self.gemm.bus,SoCRegion(origin=GEMM_BASE, size=GEMM_SIZE, cached=False))
        self.bus.add_master(name="gemm_dma", master=self.gemm.dma_bus)    
        self.irq.add("gemm", use_loc_if_exists=True)


litex_sim.SimSoC = GemmSimSoC

if __name__ == "__main__":
    litex_sim.main()
