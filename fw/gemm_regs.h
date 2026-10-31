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

#define GEMM_REG(base, off) (*(volatile uint32_t *)((uintptr_t)(base) + (off)))
#endif
