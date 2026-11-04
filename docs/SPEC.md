# int8 GEMM Accelerator Specification (v0.1)

## 1. Function
C[M x N] = A[M x K] * B[K x N]. Inputs are signed int8, outputs are signed int32.
Phase 1 supports a fixed 4x4x4 tile (M=N=K=4). With K=4, |sum| <= 4*16384 = 65536,
so int32 cannot overflow. Larger matrices are handled by software tiling.
Parameter LANES (4, 8, 16) sets how many MACs run in parallel per cycle.

## 2. Data layout
- A: row-major, 4 int8 per 32-bit word, little-endian (element 0 in bits [7:0]).
- B: row-major (K x N), same packing.
- C: row-major, one int32 per 32-bit word.
- 4x4 tile: A = 4 words, B = 4 words, C = 16 words.

## 3. Control and status registers (LiteX CSRs; offsets are assigned by the SoC build)
- CTRL: start (write-1-pulse), irq_enable, soft_reset (write-1-pulse)
- STATUS: busy (RO), done (sticky, write-1-to-clear), error (RO)
- A_ADDR, B_ADDR, C_ADDR: main-memory addresses for DMA (used from Phase 2)
- CYCLES: cycles taken by the last operation, from start to done

## 4. Memory map
Phase 1: three Wishbone windows (A buffer, B buffer, C buffer), addresses set by the SoC build
and recorded in the generated register documentation.
Phase 2: engine reads A and B from main RAM via a Wishbone master and writes C back.
Addresses must be 4-byte aligned; misaligned addresses set `error`.

## 5. Behavior
- `start` while busy is ignored and sets `error`. `error` clears on the next accepted start.
- `done` sets when C is fully written, and clears when firmware writes 1 to it or on `start`.
- IRQ is level-sensitive: irq = done & irq_enable.
- `soft_reset` aborts any operation and clears busy, done and error.

## 6. Performance hypothesis (to be revised after Day 4)
Compute cycles = ceil(M*N*K / LANES) + fixed overhead. For 4x4x4 at LANES=4:
64/4 = 16 compute cycles + a few cycles of FSM overhead. Phase 1 total time will be
dominated by CPU copy time into the buffers, which is the motivation for DMA.

## 6. Timing (v0.2, verified in simulation)
LANES/4 dot-product units; LANES/4 output elements complete per cycle.
Compute cycles = 64 / LANES. The `cycles` register reads 64/LANES + 1 (it includes the
accept cycle): 17 for LANES=4, 9 for LANES=8, 5 for LANES=16.
Inputs A and B are latched when a start is accepted; later changes to the input buses
do not affect the running tile. `rst` acts as the soft reset.
## 7. Verification plan
- Unit: cocotb vs the NumPy golden model (bit-exact), plus corner cases.
- System: firmware on the simulated SoC compares engine output vs a software GEMM.
- Formal (Day 9): properties on the DMA FSM.

## 8. Non-goals
Floating point, saturating or rounding modes, tiles larger than 4x4x4 in hardware,
caching or prefetching, multi-engine arbitration.

## 9. Assumptions and known limitations
- Results come from cycle-accurate simulation with an ideal memory model.
- Fmax values are estimates from nextpnr on a chosen device, not measured silicon.
## Accumulate (v0.3)
CTRL.ACCUMULATE is latched when a start is accepted. 0: C = A*B. 1: C = C + A*B.
Accumulation wraps in two's complement; one tile adds at most 65536 in magnitude, so
wrap needs more than 32,000 accumulations. C is only valid when DONE is set.

## Bus behavior (v0.3)
Wishbone B4 classic, 32-bit, one transfer = access cycle + ack cycle. Byte enables
are honored on A and B writes. CTRL writes honor only byte lane 0 and replace the
ACCUMULATE and IRQ_EN bits with the written values. Writes to C and read-only
registers are ignored. Unmapped words read 0.
IRQ = DONE & IRQ_EN (level-sensitive); clear it with CTRL.DONE_CLEAR.

## DMA (v0.5)
Descriptor = one 4x4 output tile of a row-major matrix. Registers (byte offsets): DMA_CTRL 0xC0
(bit0 START pulse, bit1 ACC_FIRST), DMA_STATUS 0xC4 (bit0 BUSY, bit1 DONE, bit2 ERROR, [6:4] code),
A_ADDR 0xC8, A_STRIDE 0xCC, B_ADDR 0xD0, B_STRIDE 0xD4, C_ADDR 0xD8, C_STRIDE 0xDC, K_TILES 0xE0,
DMA_CYCLES 0xE4. Addresses and strides are byte values and must be 4-byte aligned; K_TILES >= 1.
Per K step the DMA reads 4 A words (A_ADDR + r*A_STRIDE) and 4 B words (B_ADDR + r*B_STRIDE), runs the
core (first step overwrites unless ACC_FIRST, later steps accumulate), then advances A_ADDR by 4 bytes and
B_ADDR by 4*B_STRIDE. After the last step it writes the 16 C words (C_ADDR + r*C_STRIDE + 4*col).
Errors: 1 misaligned, 2 bus error, 3 timeout (1024 cycles per transfer), 4 bad K_TILES. On error the
bus is released and ERROR is set. While busy, PIO writes to A/B buffers and PIO start are ignored.
DONE_CLR clears DMA done/error; SOFT_RESET aborts the DMA. IRQ = IRQ_EN & (DMA_DONE | DMA_ERROR |
(core DONE and not DMA busy)).
Cache coherency: the CPU must flush its data cache before starting a DMA and after it completes.
Measured model (RTL, ideal memory): DMA cycles = 50 + K * (core_cycles + 27); on the simulated SoC the
K=1 LANES=4 tile took 185 cycles (effective bus latency about 4.8 cycles per transfer).
