#ifndef GEMM_LITEX_H_
#define GEMM_LITEX_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/device.h>

#define GEMM_ID_VALUE        0x47454D4DU

/* Register offsets inside the 0x100-byte window */
#define GEMM_REG_CTRL        0x80
#define GEMM_REG_STATUS      0x84
#define GEMM_REG_ID          0x8C
#define GEMM_REG_INFO        0x90
#define GEMM_REG_DMA_CTRL    0xC0
#define GEMM_REG_DMA_STATUS  0xC4
#define GEMM_REG_DMA_A       0xC8
#define GEMM_REG_DMA_AS      0xCC
#define GEMM_REG_DMA_B       0xD0
#define GEMM_REG_DMA_BS      0xD4
#define GEMM_REG_DMA_C       0xD8
#define GEMM_REG_DMA_CS      0xDC
#define GEMM_REG_DMA_K       0xE0
#define GEMM_REG_DMA_CYC     0xE4
#define GEMM_REG_DMA_XFERS   0xE8
#define GEMM_REG_DMA_WAITS   0xEC

#define GEMM_CTRL_IRQ_EN     (1U << 2)
#define GEMM_CTRL_DONE_CLR   (1U << 4)
#define GEMM_DMA_START       (1U << 0)
#define GEMM_DMST_BUSY       (1U << 0)
#define GEMM_DMST_DONE       (1U << 1)
#define GEMM_DMST_ERROR      (1U << 2)
#define GEMM_DMST_ERRCODE(s) (((s) >> 4) & 7U)

/* VexRiscv data-cache flush as encoded by LiteX (verified in M0). Override if needed. */
#ifndef GEMM_DCACHE_FLUSH_INSN
#define GEMM_DCACHE_FLUSH_INSN ".word 0x500F"
#endif

struct gemm_info {
	uint8_t lanes;
	uint8_t tile;
	uint16_t version;
};

struct gemm_counters {
	uint32_t cycles;
	uint32_t xfers;
	uint32_t waits;
};

/* Flush/invalidate the CPU data cache (needed around every DMA). */
void gemm_dcache_flush(void);

int gemm_get_info(const struct device *dev, struct gemm_info *info);
int gemm_get_counters(const struct device *dev, struct gemm_counters *c);
uint32_t gemm_isr_count(const struct device *dev);

/* One 4x4 output tile as a descriptor (low level; no cache handling).
 * Returns 0, -EIO (DMA error; *status has the code), or -ETIMEDOUT. */
int gemm_run_descriptor(const struct device *dev, uint32_t a, uint32_t a_stride, uint32_t b,
			uint32_t b_stride, uint32_t c, uint32_t c_stride, uint32_t k,
			bool use_irq, uint32_t *status);

/* C = A*B for n x n int8 matrices (n a multiple of 4, row-major, 4-byte aligned) with
 * int32 output; one descriptor per 4x4 output tile. Handles cache flushes. If use_irq is
 * true the calling thread blocks on a semaphore and other threads run during the DMA. */
int gemm_matmul(const struct device *dev, const int8_t *a, const int8_t *b, int32_t *c, int n,
		bool use_irq);

#endif /* GEMM_LITEX_H_ */
