// fw/day6_main.c (v2) - DMA driver, interrupt-driven completion, cache handling,
// benchmarks up to 64x64.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include <irq.h>
#include <system.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

#include "gemm_regs.h"

#ifndef GEMM_BASE
#define GEMM_BASE 0x90000000UL
#endif
#ifndef CSR_TIMER0_UPTIME_CYCLES_ADDR
#error "timer0 uptime CSRs missing: regenerate the SoC with --timer-uptime"
#endif
#ifndef GEMM_INTERRUPT
#error "GEMM_INTERRUPT missing: the SoC must register the accelerator IRQ (irq.add)"
#endif

#define R(off)        GEMM_REG(GEMM_BASE, (off))
#define MAXN          64
#define POLL_LIMIT    1000000u
#define IRQ_LIMIT     2000000u
#define GEMM_IRQ_BIT  (1u << GEMM_INTERRUPT)

/* ---------- timing and printing ---------- */
static inline uint32_t now(void)
{
    timer0_uptime_latch_write(1);
    return (uint32_t)timer0_uptime_cycles_read();
}
static uint32_t sub0(uint32_t v, uint32_t o) { return v > o ? v - o : 0; }

static uint32_t timer_overhead(void)
{
    uint32_t best = 0xFFFFFFFFu;
    for (int i = 0; i < 16; i++) {
        uint32_t t0 = now();
        uint32_t t1 = now();
        if (t1 - t0 < best) best = t1 - t0;
    }
    return best;
}

static void put_ratio(uint32_t num, uint32_t den)
{
    uint32_t x = den ? (num * 100u) / den : 0;
    printf("%lu.%lu%lux", (unsigned long)(x / 100), (unsigned long)((x % 100) / 10),
           (unsigned long)(x % 10));
}
static const char *yn(int v) { return v ? "yes" : "NO"; }
static void spin(int n) { for (volatile int d = 0; d < n; d++) {} }

/* ---------- interrupt handling ----------
 * The accelerator line is level-sensitive: the ISR counts the event and masks the line;
 * the foreground code clears DONE and re-arms it for the next operation. */
volatile uint32_t gemm_irq_events;

void isr(void);
void isr(void)
{
    unsigned int irqs = irq_pending() & irq_getmask();
#ifndef UART_POLLING
    if (irqs & (1u << UART_INTERRUPT))
        uart_isr();
#endif
    if (irqs & GEMM_IRQ_BIT) {
        gemm_irq_events++;
        irq_setmask(irq_getmask() & ~GEMM_IRQ_BIT);
    }
}
static inline void gemm_irq_arm(void)    { irq_setmask(irq_getmask() | GEMM_IRQ_BIT); }
static inline void gemm_irq_disarm(void) { irq_setmask(irq_getmask() & ~GEMM_IRQ_BIT); }

/* ---------- data ----------
 * One pool with deliberately skewed offsets (cache-index offsets 0, 1024, 2048, 3072 within a
 * 4 KiB window): arrays whose bases are a multiple of a small direct-mapped cache apart would
 * evict each other on every access. */
static uint8_t pool[49152] __attribute__((aligned(4096)));
static int8_t  *const mA  = (int8_t  *)(pool + 0);
static int8_t  *const mB  = (int8_t  *)(pool + 5120);
static int32_t *const mCs = (int32_t *)(pool + 14336);
static int32_t *const mCh = (int32_t *)(pool + 31744);

static uint32_t rng_state = 0x1234ABCDu;
static int8_t rnd8(void)
{
    rng_state = rng_state * 1664525u + 1013904223u;
    return (int8_t)(rng_state >> 24);
}
static void fill(int8_t *m, int count) { for (int i = 0; i < count; i++) m[i] = rnd8(); }
static void fill_c(int32_t *c, int count, int32_t v) { for (int i = 0; i < count; i++) c[i] = v; }
static int words_equal(const int32_t *a, const int32_t *b, int count)
{
    for (int i = 0; i < count; i++)
        if (a[i] != b[i]) return 0;
    return 1;
}

/* ---------- software baselines (noinline so timing loops cannot be hoisted) ---------- */
__attribute__((noinline))
static void gemm_sw(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            int32_t acc = 0;
            for (int k = 0; k < n; k++)
                acc += (int32_t)A[i * n + k] * (int32_t)B[k * n + j];
            C[i * n + j] = acc;
        }
}

/* Register-blocked 2x4 kernel: 8 accumulators, 8 MACs per 6 loads. n must be a multiple of 4. */
__attribute__((noinline))
static void gemm_sw_blocked(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
    for (int i = 0; i < n; i += 2) {
        for (int j = 0; j < n; j += 4) {
            int32_t c00 = 0, c01 = 0, c02 = 0, c03 = 0, c10 = 0, c11 = 0, c12 = 0, c13 = 0;
            const int8_t *a0p = A + i * n;
            const int8_t *a1p = a0p + n;
            const int8_t *bp = B + j;
            for (int k = 0; k < n; k++) {
                int32_t a0 = a0p[k], a1 = a1p[k];
                int32_t b0 = bp[0], b1 = bp[1], b2 = bp[2], b3 = bp[3];
                c00 += a0 * b0; c01 += a0 * b1; c02 += a0 * b2; c03 += a0 * b3;
                c10 += a1 * b0; c11 += a1 * b1; c12 += a1 * b2; c13 += a1 * b3;
                bp += n;
            }
            int32_t *c0 = C + i * n + j;
            int32_t *c1 = c0 + n;
            c0[0] = c00; c0[1] = c01; c0[2] = c02; c0[3] = c03;
            c1[0] = c10; c1[1] = c11; c1[2] = c12; c1[3] = c13;
        }
    }
}

/* ---------- PIO (optimized, from Day 5) ---------- */
typedef uint32_t __attribute__((may_alias)) u32_alias;
static inline uint32_t ld32(const int8_t *p) { return *(const u32_alias *)p; }

static int hw_wait_done(void)
{
    for (uint32_t i = 0; i < POLL_LIMIT; i++) {
        uint32_t st = R(GEMM_STATUS_OFF);
        if (st & GEMM_ST_ERROR) return -2;
        if (st & GEMM_ST_DONE)  return 0;
    }
    return -1;
}

static int gemm_hw_pio_fast(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
    volatile uint32_t *regs = (volatile uint32_t *)GEMM_BASE;
    const int nt = n / 4;
    const int n2 = 2 * n, n3 = 3 * n;
    for (int ti = 0; ti < nt; ti++) {
        for (int tj = 0; tj < nt; tj++) {
            for (int tk = 0; tk < nt; tk++) {
                const int8_t *a = A + ti * 4 * n + tk * 4;
                const int8_t *b = B + tk * 4 * n + tj * 4;
                uint32_t cfg = (tk > 0) ? GEMM_CTRL_ACCUM : 0;
                regs[GEMM_CTRL_OFF / 4] = GEMM_CTRL_DONE_CLR | cfg;
                regs[GEMM_A_OFF / 4 + 0] = ld32(a);
                regs[GEMM_A_OFF / 4 + 1] = ld32(a + n);
                regs[GEMM_A_OFF / 4 + 2] = ld32(a + n2);
                regs[GEMM_A_OFF / 4 + 3] = ld32(a + n3);
                regs[GEMM_B_OFF / 4 + 0] = ld32(b);
                regs[GEMM_B_OFF / 4 + 1] = ld32(b + n);
                regs[GEMM_B_OFF / 4 + 2] = ld32(b + n2);
                regs[GEMM_B_OFF / 4 + 3] = ld32(b + n3);
                regs[GEMM_CTRL_OFF / 4] = GEMM_CTRL_START | cfg;
                int rc = hw_wait_done();
                if (rc) return rc;
            }
            int32_t *c = C + ti * 4 * n + tj * 4;
            for (int r = 0; r < 4; r++) {
                c[0] = (int32_t)regs[GEMM_C_OFF / 4 + r * 4 + 0];
                c[1] = (int32_t)regs[GEMM_C_OFF / 4 + r * 4 + 1];
                c[2] = (int32_t)regs[GEMM_C_OFF / 4 + r * 4 + 2];
                c[3] = (int32_t)regs[GEMM_C_OFF / 4 + r * 4 + 3];
                c += n;
            }
        }
    }
    return 0;
}

/* ---------- DMA driver ---------- */
static int dma_wait_poll(void)
{
    for (uint32_t i = 0; i < POLL_LIMIT; i++) {
        uint32_t st = R(GEMM_DMA_STATUS_OFF);
        if (st & GEMM_DMST_ERROR) return -2;
        if (st & GEMM_DMST_DONE)  return 0;
    }
    return -1;
}

/* Interrupt-driven wait: spin on a cached counter (no bus traffic) until the ISR runs. */
static int dma_wait_irq(uint32_t events_before)
{
    for (uint32_t i = 0; i < IRQ_LIMIT; i++)
        if (gemm_irq_events != events_before)
            return (R(GEMM_DMA_STATUS_OFF) & GEMM_DMST_ERROR) ? -2 : 0;
    return -1;
}

static void dma_setup_strides(int n)
{
    R(GEMM_DMA_AS_OFF) = (uint32_t)n;
    R(GEMM_DMA_BS_OFF) = (uint32_t)n;
    R(GEMM_DMA_CS_OFF) = (uint32_t)(n * (int)sizeof(int32_t));
    R(GEMM_DMA_K_OFF)  = (uint32_t)(n / 4);
}

static void dma_set_tile(const int8_t *a, const int8_t *b, int32_t *c)
{
    R(GEMM_DMA_A_OFF) = (uint32_t)(uintptr_t)a;
    R(GEMM_DMA_B_OFF) = (uint32_t)(uintptr_t)b;
    R(GEMM_DMA_C_OFF) = (uint32_t)(uintptr_t)c;
}

/* C = A*B for n x n int8 matrices, one DMA descriptor per 4x4 output tile (K loop in hardware). */
static int gemm_hw_dma(const int8_t *A, const int8_t *B, int32_t *C, int n, int use_irq)
{
    const int nt = n / 4;
    int rc = 0;
    __asm__ volatile("" ::: "memory");
    flush_cpu_dcache();                      /* A and B must be visible to the DMA */
    dma_setup_strides(n);
    for (int ti = 0; ti < nt && !rc; ti++) {
        for (int tj = 0; tj < nt && !rc; tj++) {
            uint32_t ev0 = gemm_irq_events;
            R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR | (use_irq ? GEMM_CTRL_IRQ_EN : 0);
            dma_set_tile(A + ti * 4 * n, B + tj * 4, C + ti * 4 * n + tj * 4);
            if (use_irq) gemm_irq_arm();     /* armed after DONE was cleared: no spurious interrupt */
            R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
            rc = use_irq ? dma_wait_irq(ev0) : dma_wait_poll();
            if (use_irq) gemm_irq_disarm();
        }
    }
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;   /* drop DONE and the IRQ line, IRQ_EN = 0 */
    flush_cpu_dcache();                      /* the DMA wrote C behind the CPU's back */
    __asm__ volatile("" ::: "memory");
    return rc;
}

/* ---------- self-checks ---------- */
static void irq_diag(void)
{
    printf("  irq diag: mask=0x%lx pending=0x%lx events=%lu ctrl=0x%lx status=0x%lx dma_status=0x%lx\n",
           (unsigned long)irq_getmask(), (unsigned long)irq_pending(),
           (unsigned long)gemm_irq_events, (unsigned long)R(GEMM_CTRL_OFF),
           (unsigned long)R(GEMM_STATUS_OFF), (unsigned long)R(GEMM_DMA_STATUS_OFF));
}

static int test_dma_known_answers(void)
{
    int fails = 0;
    for (int i = 0; i < 16; i++) { mA[i] = (int8_t)(i + 1); mB[i] = 0; }
    for (int d = 0; d < 4; d++) mB[d * 4 + d] = 1;
    fill_c(mCh, 16, 0);
    if (gemm_hw_dma(mA, mB, mCh, 4, 0)) return 99;
    for (int i = 0; i < 16; i++) if (mCh[i] != i + 1) fails++;

    static const int8_t  av[3] = { -128, 127, -128 };
    static const int8_t  bv[3] = { -128, 127,  127 };
    static const int32_t ex[3] = { 65536, 64516, -65024 };
    for (int t = 0; t < 3; t++) {
        memset(mA, av[t], 16);
        memset(mB, bv[t], 16);
        if (gemm_hw_dma(mA, mB, mCh, 4, 0)) return 99;
        for (int i = 0; i < 16; i++) if (mCh[i] != ex[t]) fails++;
    }
    return fails;
}

static int test_dma_random(int count)
{
    int fails = 0;
    for (int t = 0; t < count; t++) {
        fill(mA, 16);
        fill(mB, 16);
        gemm_sw(mA, mB, mCs, 4);
        fill_c(mCh, 16, 0);
        if (gemm_hw_dma(mA, mB, mCh, 4, t & 1)) return -1;   /* alternate poll / interrupt wait */
        if (!words_equal(mCs, mCh, 16)) fails++;
    }
    return fails;
}

static int test_dma_error_path(void)
{
    int fails = 0;
    dma_setup_strides(4);
    dma_set_tile(mA + 1, mB, mCh);                       /* misaligned A on purpose */
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;
    R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
    int rc = dma_wait_poll();
    uint32_t st = R(GEMM_DMA_STATUS_OFF);
    if (rc != -2) fails++;
    if (GEMM_DMST_ERRCODE(st) != 1) fails++;
    if (st & GEMM_DMST_DONE) fails++;
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;
    spin(50);
    if (R(GEMM_DMA_STATUS_OFF) != 0) fails++;            /* DONE_CLR clears the error */
    return fails;
}

static int test_irq_line(void)
{
    int fails = 0;
    uint32_t ev0;
    fill(mA, 16);
    fill(mB, 16);
    flush_cpu_dcache();
    dma_setup_strides(4);
    dma_set_tile(mA, mB, mCh);
    gemm_irq_disarm();

    /* 1. IRQ_EN = 0: no interrupt even though DONE is set */
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;
    spin(50);
    ev0 = gemm_irq_events;
    gemm_irq_arm();
    R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
    if (dma_wait_poll()) fails++;
    spin(200);
    if (gemm_irq_events != ev0) fails++;
    gemm_irq_disarm();

    /* 2. IRQ_EN = 1: exactly one interrupt per completion (the ISR silences the level line) */
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR | GEMM_CTRL_IRQ_EN;
    spin(50);
    ev0 = gemm_irq_events;
    gemm_irq_arm();
    R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
    if (dma_wait_irq(ev0)) fails++;
    spin(200);
    if (gemm_irq_events != ev0 + 1) fails++;

    /* 3. after DONE_CLR the line is low: re-arming must not fire */
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR | GEMM_CTRL_IRQ_EN;
    spin(50);
    gemm_irq_arm();
    spin(200);
    if (gemm_irq_events != ev0 + 1) fails++;
    gemm_irq_disarm();
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;               /* leave IRQ_EN = 0 */
    if (fails) irq_diag();
    return fails;
}

/* Does the CPU data cache serve stale C data after a DMA write? After a flush it must not. */
static void coherency_probe(void)
{
    for (int i = 0; i < 16; i++) { mA[i] = (int8_t)(i + 1); mB[i] = 0; }
    for (int d = 0; d < 4; d++) mB[d * 4 + d] = 1;
    fill_c(mCh, 16, 0x5A5A5A5A);
    volatile int32_t *vc = (volatile int32_t *)mCh;
    int32_t sink = 0;
    for (int i = 0; i < 16; i++) sink += vc[i];          /* pull the sentinel lines into the cache */
    (void)sink;

    dma_setup_strides(4);
    dma_set_tile(mA, mB, mCh);
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;
    R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
    dma_wait_poll();

    int stale = 0, after = 0;
    for (int i = 0; i < 16; i++) if (vc[i] != i + 1) stale++;   /* read WITHOUT flushing */
    flush_cpu_dcache();
    for (int i = 0; i < 16; i++) if (vc[i] != i + 1) after++;
    printf("coherency probe: stale words without flush = %d, after flush = %d\n", stale, after);
}

static void report_flush_cost(uint32_t ovh)
{
    uint32_t best = 0xFFFFFFFFu;
    for (int i = 0; i < 5; i++) {
        uint32_t t0 = now();
        flush_cpu_dcache();
        uint32_t t1 = now();
        if (t1 - t0 < best) best = t1 - t0;
    }
    printf("dcache flush cost: %lu cycles (minimum of 5)\n", (unsigned long)sub0(best, ovh));
}

static void report_dma_counters(int n, uint32_t lanes)
{
    fill(mA, n * n);
    fill(mB, n * n);
    fill_c(mCh, n * n, 0);
    flush_cpu_dcache();
    dma_setup_strides(n);
    dma_set_tile(mA, mB, mCh);
    R(GEMM_CTRL_OFF) = GEMM_CTRL_DONE_CLR;
    R(GEMM_DMA_CTRL_OFF) = GEMM_DMA_START;
    int rc = dma_wait_poll();
    uint32_t cyc = R(GEMM_DMA_CYC_OFF);
    uint32_t xf = R(GEMM_DMA_XFERS_OFF);
    uint32_t wt = R(GEMM_DMA_WAITS_OFF);
    uint32_t avg100 = xf ? (wt * 100u) / xf : 0;
    printf("DMA counters (K=%d): cycles=%lu xfers=%lu stall=%lu avg_stall=%lu.%lu%lu%s\n",
           n / 4, (unsigned long)cyc, (unsigned long)xf, (unsigned long)wt,
           (unsigned long)(avg100 / 100), (unsigned long)((avg100 % 100) / 10),
           (unsigned long)(avg100 % 10), rc ? "  (HW error)" : "");
    printf("CSV,dmactr,%lu,%d,%lu,%lu,%lu\n", (unsigned long)lanes, n / 4, (unsigned long)cyc,
           (unsigned long)xf, (unsigned long)wt);
}

/* ---------- benchmarks ---------- */
typedef int (*gemm_fn)(const int8_t *, const int8_t *, int32_t *, int);
static int w_blocked(const int8_t *A, const int8_t *B, int32_t *C, int n) { gemm_sw_blocked(A, B, C, n); return 0; }
static int w_pio(const int8_t *A, const int8_t *B, int32_t *C, int n)      { return gemm_hw_pio_fast(A, B, C, n); }
static int w_dma_poll(const int8_t *A, const int8_t *B, int32_t *C, int n) { return gemm_hw_dma(A, B, C, n, 0); }
static int w_dma_irq(const int8_t *A, const int8_t *B, int32_t *C, int n)  { return gemm_hw_dma(A, B, C, n, 1); }

static int time_method(gemm_fn fn, int n, int reps, uint32_t ovh, uint32_t *cycles)
{
    int rc = 0, done = 0;
    fill_c(mCh, n * n, (int32_t)0xDEADBEEF);
    uint32_t t0 = now();
    for (int r = 0; r < reps && !rc; r++) {
        rc = fn(mA, mB, mCh, n);
        __asm__ volatile("" ::: "memory");
        done++;
    }
    uint32_t t1 = now();
    *cycles = sub0(t1 - t0, ovh) / (uint32_t)(done ? done : 1);
    return (rc == 0) && words_equal(mCs, mCh, n * n);
}

static int bench_day6(int n, int reps, uint32_t ovh, uint32_t lanes)
{
    uint32_t sw, blk, pio, dma, dmai;
    fill(mA, n * n);
    fill(mB, n * n);

    uint32_t t0 = now();
    for (int r = 0; r < reps; r++) { gemm_sw(mA, mB, mCs, n); __asm__ volatile("" ::: "memory"); }
    uint32_t t1 = now();
    sw = sub0(t1 - t0, ovh) / (uint32_t)reps;

    int ok_blk = time_method(w_blocked, n, reps, ovh, &blk);
    int ok_pio = time_method(w_pio, n, reps, ovh, &pio);
    int ok_dma = time_method(w_dma_poll, n, reps, ovh, &dma);
    int ok_irq = time_method(w_dma_irq, n, reps, ovh, &dmai);
    int ok = ok_blk && ok_pio && ok_dma && ok_irq;

    printf("N=%d reps=%d  sw=%lu blk=%lu pio=%lu dma=%lu dma_irq=%lu\n", n, reps,
           (unsigned long)sw, (unsigned long)blk, (unsigned long)pio,
           (unsigned long)dma, (unsigned long)dmai);
    printf("  vs naive:");
    printf(" blk="); put_ratio(sw, blk);
    printf(" pio="); put_ratio(sw, pio);
    printf(" dma="); put_ratio(sw, dma);
    printf(" dma_irq="); put_ratio(sw, dmai);
    printf("\n  vs blocked:");
    printf(" pio="); put_ratio(blk, pio);
    printf(" dma="); put_ratio(blk, dma);
    printf(" dma_irq="); put_ratio(blk, dmai);
    printf("\n  match: blk=%s pio=%s dma=%s dma_irq=%s\n", yn(ok_blk), yn(ok_pio), yn(ok_dma), yn(ok_irq));
    printf("CSV,day6,%lu,%d,%lu,%lu,%lu,%lu,%lu,%d\n", (unsigned long)lanes, n,
           (unsigned long)sw, (unsigned long)blk, (unsigned long)pio,
           (unsigned long)dma, (unsigned long)dmai, ok);
    return ok;
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
    irq_setmask(0);
    irq_setie(1);
#endif
    uart_init();

    int pass = 1;
    printf("\n=== litex-gemm Day 6: DMA driver and benchmarks (v2) ===\n");

    uint32_t id = R(GEMM_ID_OFF);
    uint32_t info = R(GEMM_INFO_OFF);
    uint32_t lanes = info & 0xFF;
    if (id != GEMM_ID_VALUE) {
        printf("ID mismatch: read 0x%08lx\nRESULT: FAIL\n", (unsigned long)id);
        while (1) {}
    }
    printf("ID ok, LANES=%lu, tile=%lu, version=0x%04lx, base=0x%08lx, irq line=%d\n",
           (unsigned long)lanes, (unsigned long)((info >> 8) & 0xFF),
           (unsigned long)(info >> 16), (unsigned long)GEMM_BASE, (int)GEMM_INTERRUPT);
    printf("buffers: A=0x%08lx B=0x%08lx Cs=0x%08lx Ch=0x%08lx\n", (unsigned long)(uintptr_t)mA,
           (unsigned long)(uintptr_t)mB, (unsigned long)(uintptr_t)mCs, (unsigned long)(uintptr_t)mCh);

    uint32_t ovh = timer_overhead();
    printf("timer read overhead: %lu cycles (subtracted from results)\n", (unsigned long)ovh);
    report_flush_cost(ovh);

    int f = test_dma_known_answers();
    printf("DMA known-answer tests: %s\n", f == 0 ? "PASS" : "FAIL");
    if (f) pass = 0;

    f = test_dma_random(100);
    printf("DMA random 4x4 tiles (100, poll and interrupt wait alternating): %s\n", f == 0 ? "PASS" : "FAIL");
    if (f) pass = 0;

    f = test_dma_error_path();
    printf("DMA error path (misaligned descriptor): %s\n", f == 0 ? "PASS" : "FAIL");
    if (f) pass = 0;

    f = test_irq_line();
    printf("IRQ line (ISR event counting): %s\n", f == 0 ? "PASS" : "FAIL");
    if (f) pass = 0;

    coherency_probe();

    report_dma_counters(4, lanes);
    report_dma_counters(16, lanes);
    report_dma_counters(32, lanes);

    static const int sizes[] = { 4, 8, 16, 32, 64 };
    static const int reps[]  = { 20, 10, 3, 1, 1 };
    for (int i = 0; i < 5; i++)
        if (!bench_day6(sizes[i], reps[i], ovh, lanes)) pass = 0;

    printf("BENCH DONE\n");
    printf("RESULT: %s\n", pass ? "PASS" : "FAIL");
    while (1) {}
    return 0;
}
