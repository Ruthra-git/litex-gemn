#ifndef GEMM_REGS_H
#define GEMM_REGS_H
#include <stdint.h>

/* Byte offsets within the 0x100-byte window */
#define GEMM_A_OFF      0x00   /* 4 words, RW, 16 x int8 row-major */
#define GEMM_B_OFF      0x10   /* 4 words, RW */
#define GEMM_C_OFF      0x40   /* 16 words, RO, 16 x int32 row-major */
#define GEMM_CTRL_OFF   0x80
#define GEMM_STATUS_OFF 0x84
#define GEMM_CYCLES_OFF 0x88
#define GEMM_ID_OFF     0x8C
#define GEMM_INFO_OFF   0x90

#define GEMM_ID_VALUE   0x47454D4Du

#define GEMM_CTRL_START     (1u << 0)
#define GEMM_CTRL_ACCUM     (1u << 1)
#define GEMM_CTRL_IRQ_EN    (1u << 2)
#define GEMM_CTRL_SOFT_RST  (1u << 3)
#define GEMM_CTRL_DONE_CLR  (1u << 4)

#define GEMM_ST_BUSY   (1u << 0)
#define GEMM_ST_DONE   (1u << 1)
#define GEMM_ST_ERROR  (1u << 2)

/* DMA registers */
#define GEMM_DMA_CTRL_OFF    0xC0
#define GEMM_DMA_STATUS_OFF  0xC4
#define GEMM_DMA_A_OFF       0xC8
#define GEMM_DMA_AS_OFF      0xCC
#define GEMM_DMA_B_OFF       0xD0
#define GEMM_DMA_BS_OFF      0xD4
#define GEMM_DMA_C_OFF       0xD8
#define GEMM_DMA_CS_OFF      0xDC
#define GEMM_DMA_K_OFF       0xE0
#define GEMM_DMA_CYC_OFF     0xE4
#define GEMM_DMA_XFERS_OFF   0xE8
#define GEMM_DMA_WAITS_OFF   0xEC

#define GEMM_DMA_START       (1u << 0)
#define GEMM_DMA_ACC_FIRST   (1u << 1)
#define GEMM_DMST_BUSY       (1u << 0)
#define GEMM_DMST_DONE       (1u << 1)
#define GEMM_DMST_ERROR      (1u << 2)
#define GEMM_DMST_ERRCODE(s) (((s) >> 4) & 7u)

#define GEMM_REG(base, off) (*(volatile uint32_t *)((uintptr_t)(base) + (off)))
#endif
