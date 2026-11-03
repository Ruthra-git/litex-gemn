// fw/main.c - Day 4: programmed-I/O baseline for the int8 GEMM accelerator.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include <irq.h>
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

#define R(off)      GEMM_REG(GEMM_BASE, (off))
#define MAXN        32
#define POLL_LIMIT  1000000u

/* ---------- timing ---------- */
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

static void print_ratio(const char *label, uint32_t num, uint32_t den)
{
    uint32_t x100 = den ? (num * 100u) / den : 0;
    printf("%s%lu.%lu%lu x\n", label, (unsigned long)(x100 / 100),
           (unsigned long)((x100 % 100) / 10), (unsigned long)(x100 % 10));
}

/* ---------- data ---------- */
static uint32_t rng_state = 0x1234ABCDu;
static int8_t rnd8(void)
{
    rng_state = rng_state * 1664525u + 1013904223u;
    return (int8_t)(rng_state >> 24);
}
static void fill(int8_t *m, int count)
{
    for (int i = 0; i < count; i++) m[i] = rnd8();
}

static int8_t  mA[MAXN * MAXN]  __attribute__((aligned(4)));
static int8_t  mB[MAXN * MAXN]  __attribute__((aligned(4)));
static int32_t mCs[MAXN * MAXN];
static int32_t mCh[MAXN * MAXN];

/* ---------- software references (noinline so timing loops cannot be hoisted) ---------- */
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

__attribute__((noinline))
static void gemm_sw4_unrolled(const int8_t *A, const int8_t *B, int32_t *C)
{
    for (int i = 0; i < 4; i++) {
        int32_t a0 = A[i * 4], a1 = A[i * 4 + 1], a2 = A[i * 4 + 2], a3 = A[i * 4 + 3];
        for (int j = 0; j < 4; j++)
            C[i * 4 + j] = a0 * B[j] + a1 * B[4 + j] + a2 * B[8 + j] + a3 * B[12 + j];
    }
}

static int words_equal(const int32_t *a, const int32_t *b, int count)
{
    for (int i = 0; i < count; i++)
        if (a[i] != b[i]) return 0;
    return 1;
}

/* ---------- hardware access ---------- */
static inline uint32_t ld32(const int8_t *p) { uint32_t w; memcpy(&w, p, 4); return w; }
static inline void hw_ctrl(uint32_t v) { R(GEMM_CTRL_OFF) = v; }

static void hw_load_tile(const int8_t *A, const int8_t *B, int n, int ti, int tj, int tk)
{
    for (int r = 0; r < 4; r++) {
        R(GEMM_A_OFF + 4 * r) = ld32(A + (ti * 4 + r) * n + tk * 4);
        R(GEMM_B_OFF + 4 * r) = ld32(B + (tk * 4 + r) * n + tj * 4);
    }
}

static int hw_wait_done(void)
{
    for (uint32_t i = 0; i < POLL_LIMIT; i++) {
        uint32_t st = R(GEMM_STATUS_OFF);
        if (st & GEMM_ST_ERROR) return -2;
        if (st & GEMM_ST_DONE)  return 0;
    }
    return -1;
}

static void hw_read_tile(int32_t *C, int n, int ti, int tj)
{
    for (int r = 0; r < 4; r++)
        for (int c = 0; c < 4; c++)
            C[(ti * 4 + r) * n + tj * 4 + c] = (int32_t)R(GEMM_C_OFF + 4 * (r * 4 + c));
}

/* C = A*B for n x n int8 matrices (n multiple of 4), tiled; K-tiles use hardware accumulate. */
static int gemm_hw_pio(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
    int nt = n / 4;
    for (int ti = 0; ti < nt; ti++)
        for (int tj = 0; tj < nt; tj++) {
            for (int tk = 0; tk < nt; tk++) {
                uint32_t cfg = (tk > 0) ? GEMM_CTRL_ACCUM : 0;
                hw_ctrl(GEMM_CTRL_DONE_CLR | cfg);
                hw_load_tile(A, B, n, ti, tj, tk);
                hw_ctrl(GEMM_CTRL_START | cfg);
                int rc = hw_wait_done();
                if (rc) return rc;
            }
            hw_read_tile(C, n, ti, tj);
        }
    return 0;
}

/* ---------- correctness ---------- */
static int test_known_answers(void)
{
    int fails = 0;
    int8_t A[16], B[16];
    int32_t C[16];

    /* identity: A = 1..16, B = I  ->  C = A */
    for (int i = 0; i < 16; i++) { A[i] = (int8_t)(i + 1); B[i] = 0; }
    for (int d = 0; d < 4; d++) B[d * 4 + d] = 1;
    memset(C, 0, sizeof(C));
    if (gemm_hw_pio(A, B, C, 4)) return 99;
    for (int i = 0; i < 16; i++) if (C[i] != i + 1) fails++;

    /* constant fills, results computed by hand: 4*a*b */
    static const int8_t  av[3] = { -128, 127, -128 };
    static const int8_t  bv[3] = { -128, 127,  127 };
    static const int32_t ex[3] = { 65536, 64516, -65024 };
    for (int t = 0; t < 3; t++) {
        memset(A, av[t], 16);
        memset(B, bv[t], 16);
        if (gemm_hw_pio(A, B, C, 4)) return 99;
        for (int i = 0; i < 16; i++) if (C[i] != ex[t]) fails++;
    }
    return fails;
}

static int test_random_tiles(int count)
{
    int fails = 0;
    int8_t A[16], B[16];
    int32_t Cs[16], Ch[16], Cu[16];
    for (int t = 0; t < count; t++) {
        fill(A, 16);
        fill(B, 16);
        gemm_sw(A, B, Cs, 4);
        gemm_sw4_unrolled(A, B, Cu);
        if (gemm_hw_pio(A, B, Ch, 4)) return -1;
        if (!words_equal(Cs, Ch, 16) || !words_equal(Cs, Cu, 16)) fails++;
    }
    return fails;
}

/* ---------- benchmarks ---------- */
typedef struct { uint32_t clr, load, start, wait, read; } phases_t;

static int tile_phases(const int8_t *A, const int8_t *B, int32_t *C, phases_t *p)
{
    uint32_t t0, t1, t2, t3, t4, t5;
    t0 = now();
    hw_ctrl(GEMM_CTRL_DONE_CLR);
    t1 = now();
    hw_load_tile(A, B, 4, 0, 0, 0);
    t2 = now();
    hw_ctrl(GEMM_CTRL_START);
    t3 = now();
    int rc = hw_wait_done();
    t4 = now();
    hw_read_tile(C, 4, 0, 0);
    t5 = now();
    p->clr = t1 - t0; p->load = t2 - t1; p->start = t3 - t2;
    p->wait = t4 - t3; p->read = t5 - t4;
    return rc;
}

static void bench_tile(int reps, uint32_t ovh, uint32_t lanes)
{
    int8_t A[16], B[16];
    int32_t Cs[16], Ch[16];
    phases_t p;
    uint32_t s_clr = 0, s_load = 0, s_start = 0, s_wait = 0, s_read = 0;

    fill(A, 16);
    fill(B, 16);

    for (int r = 0; r < reps; r++) {
        if (tile_phases(A, B, Ch, &p)) { printf("  HW error in tile bench\n"); return; }
        s_clr += sub0(p.clr, ovh);     s_load += sub0(p.load, ovh);
        s_start += sub0(p.start, ovh); s_wait += sub0(p.wait, ovh);
        s_read += sub0(p.read, ovh);
    }
    uint32_t clr = s_clr / reps, load = s_load / reps, start = s_start / reps;
    uint32_t wait = s_wait / reps, rd = s_read / reps;
    uint32_t hw_total = clr + load + start + wait + rd;
    uint32_t core = R(GEMM_CYCLES_OFF);

    uint32_t t0 = now();
    for (int r = 0; r < reps; r++) { gemm_sw(A, B, Cs, 4); __asm__ volatile("" ::: "memory"); }
    uint32_t t1 = now();
    uint32_t sw_naive = sub0(t1 - t0, ovh) / reps;

    t0 = now();
    for (int r = 0; r < reps; r++) { gemm_sw4_unrolled(A, B, Cs); __asm__ volatile("" ::: "memory"); }
    t1 = now();
    uint32_t sw_unrolled = sub0(t1 - t0, ovh) / reps;

    printf("4x4 tile, average cycles over %d runs (LANES=%lu):\n", reps, (unsigned long)lanes);
    printf("  hw: clear=%lu load=%lu start=%lu wait=%lu read=%lu  total=%lu\n",
           (unsigned long)clr, (unsigned long)load, (unsigned long)start,
           (unsigned long)wait, (unsigned long)rd, (unsigned long)hw_total);
    printf("  engine-internal cycles (CYCLES reg) = %lu\n", (unsigned long)core);
    printf("  sw naive=%lu  sw unrolled=%lu\n", (unsigned long)sw_naive, (unsigned long)sw_unrolled);
    print_ratio("  speedup vs naive    : ", sw_naive, hw_total);
    print_ratio("  speedup vs unrolled : ", sw_unrolled, hw_total);
    print_ratio("  engine-only vs naive: ", sw_naive, core);
    printf("CSV,tile,%lu,4,%lu,%lu,%lu,%lu\n", (unsigned long)lanes, (unsigned long)sw_naive,
           (unsigned long)sw_unrolled, (unsigned long)hw_total, (unsigned long)core);
}

static int bench_size(int n, int reps, uint32_t ovh, uint32_t lanes)
{
    fill(mA, n * n);
    fill(mB, n * n);

    uint32_t t0 = now();
    for (int r = 0; r < reps; r++) { gemm_sw(mA, mB, mCs, n); __asm__ volatile("" ::: "memory"); }
    uint32_t t1 = now();
    uint32_t sw = sub0(t1 - t0, ovh) / reps;

    int rc = 0;
    t0 = now();
    for (int r = 0; r < reps && !rc; r++) rc = gemm_hw_pio(mA, mB, mCh, n);
    t1 = now();
    uint32_t hw = sub0(t1 - t0, ovh) / reps;

    int ok = (rc == 0) && words_equal(mCs, mCh, n * n);
    printf("N=%d reps=%d  sw=%lu  hw_pio=%lu  ", n, reps, (unsigned long)sw, (unsigned long)hw);
    print_ratio("speedup ", sw, hw);
    printf("  match=%s%s\n", ok ? "yes" : "NO", rc ? " (HW error)" : "");
    printf("CSV,size,%lu,%d,%lu,%lu,%d\n", (unsigned long)lanes, n, (unsigned long)sw,
           (unsigned long)hw, ok);
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
    printf("\n=== litex-gemm Day 4: PIO baseline ===\n");

    uint32_t id = R(GEMM_ID_OFF);
    uint32_t info = R(GEMM_INFO_OFF);
    uint32_t lanes = info & 0xFF;
    if (id != GEMM_ID_VALUE) {
        printf("ID mismatch: read 0x%08lx, expected 0x%08lx\n",
               (unsigned long)id, (unsigned long)GEMM_ID_VALUE);
        printf("RESULT: FAIL\n");
        while (1) {}
    }
    printf("ID ok, LANES=%lu, tile=%lu, version=0x%04lx, base=0x%08lx\n",
           (unsigned long)lanes, (unsigned long)((info >> 8) & 0xFF),
           (unsigned long)(info >> 16), (unsigned long)GEMM_BASE);

    int kf = test_known_answers();
    printf("known-answer tests: %s\n", kf == 0 ? "PASS" : "FAIL");
    if (kf) pass = 0;

    int rf = test_random_tiles(200);
    printf("random 4x4 tiles (200): %s\n", rf == 0 ? "PASS" : "FAIL");
    if (rf) pass = 0;

    uint32_t ovh = timer_overhead();
    printf("timer read overhead: %lu cycles (subtracted from results)\n", (unsigned long)ovh);

    bench_tile(100, ovh, lanes);

    static const int sizes[] = { 4, 8, 16, 32 };
    static const int reps[]  = { 20, 10, 3, 1 };
    for (int i = 0; i < 4; i++)
        if (!bench_size(sizes[i], reps[i], ovh, lanes)) pass = 0;

    printf("BENCH DONE\n");
    printf("RESULT: %s\n", pass ? "PASS" : "FAIL");
    while (1) {}
    return 0;
}
