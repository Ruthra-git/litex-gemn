/* Day 7: Zephyr driver tests, CPU-offload demo, benchmarks. */
#include <errno.h>
#include <string.h>
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/version.h>

#include "gemm_litex.h"

#define MAXN 64

static const struct device *const gemm = DEVICE_DT_GET(DT_NODELABEL(gemm0));

/* ---------- timing ---------- */
#ifdef GEMM_TIMER_LATCH_ADDR
static inline uint32_t now(void)
{
	sys_write32(1, GEMM_TIMER_LATCH_ADDR);
	return sys_read32(GEMM_TIMER_CYCLES_ADDR + 4); /* 64-bit CSR, big word order: low word second */
}
#else
static inline uint32_t now(void)
{
	return k_cycle_get_32();
}
#endif

static uint32_t sub0(uint32_t v, uint32_t o) { return v > o ? v - o : 0; }

static uint32_t timer_overhead(void)
{
	uint32_t best = 0xFFFFFFFFu;

	for (int i = 0; i < 16; i++) {
		uint32_t t0 = now();
		uint32_t t1 = now();

		if (t1 - t0 < best) {
			best = t1 - t0;
		}
	}
	return best;
}

static const char *yn(int v) { return v ? "yes" : "NO"; }

static void put_ratio(uint32_t num, uint32_t den)
{
	uint32_t x = den ? (num * 100u) / den : 0;

	printk("%u.%u%ux", (unsigned int)(x / 100), (unsigned int)((x % 100) / 10),
	       (unsigned int)(x % 10));
}

/* ---------- data: one pool with skewed offsets (avoids data-cache conflicts) ---------- */
static uint8_t pool[49152] __aligned(4096);
#define mA  ((int8_t *)(pool + 0))
#define mB  ((int8_t *)(pool + 5120))
#define mCs ((int32_t *)(pool + 14336))
#define mCh ((int32_t *)(pool + 31744))

static uint32_t rng_state = 0x1234ABCDu;

static int8_t rnd8(void)
{
	rng_state = rng_state * 1664525u + 1013904223u;
	return (int8_t)(rng_state >> 24);
}

static void fill(int8_t *m, int count)
{
	for (int i = 0; i < count; i++) {
		m[i] = rnd8();
	}
}

static void fill_c(int32_t *c, int count, int32_t v)
{
	for (int i = 0; i < count; i++) {
		c[i] = v;
	}
}

static int words_equal(const int32_t *a, const int32_t *b, int count)
{
	for (int i = 0; i < count; i++) {
		if (a[i] != b[i]) {
			return 0;
		}
	}
	return 1;
}

/* ---------- software baselines ---------- */
__noinline static void gemm_sw(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
	for (int i = 0; i < n; i++) {
		for (int j = 0; j < n; j++) {
			int32_t acc = 0;

			for (int k = 0; k < n; k++) {
				acc += (int32_t)A[i * n + k] * (int32_t)B[k * n + j];
			}
			C[i * n + j] = acc;
		}
	}
}

__noinline static void gemm_sw_blocked(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
	for (int i = 0; i < n; i += 2) {
		for (int j = 0; j < n; j += 4) {
			int32_t c00 = 0, c01 = 0, c02 = 0, c03 = 0;
			int32_t c10 = 0, c11 = 0, c12 = 0, c13 = 0;
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

/* ---------- self-checks ---------- */
static int test_known_answers(void)
{
	int fails = 0;

	for (int i = 0; i < 16; i++) {
		mA[i] = (int8_t)(i + 1);
		mB[i] = 0;
	}
	for (int d = 0; d < 4; d++) {
		mB[d * 4 + d] = 1;
	}
	fill_c(mCh, 16, 0);
	if (gemm_matmul(gemm, mA, mB, mCh, 4, false)) {
		return 99;
	}
	for (int i = 0; i < 16; i++) {
		if (mCh[i] != i + 1) {
			fails++;
		}
	}

	static const int8_t av[3] = {-128, 127, -128};
	static const int8_t bv[3] = {-128, 127, 127};
	static const int32_t ex[3] = {65536, 64516, -65024};

	for (int t = 0; t < 3; t++) {
		memset(mA, av[t], 16);
		memset(mB, bv[t], 16);
		if (gemm_matmul(gemm, mA, mB, mCh, 4, false)) {
			return 99;
		}
		for (int i = 0; i < 16; i++) {
			if (mCh[i] != ex[t]) {
				fails++;
			}
		}
	}
	return fails;
}

static int test_random(int count)
{
	int fails = 0;

	for (int t = 0; t < count; t++) {
		fill(mA, 16);
		fill(mB, 16);
		gemm_sw(mA, mB, mCs, 4);
		fill_c(mCh, 16, 0);
		if (gemm_matmul(gemm, mA, mB, mCh, 4, (t & 1) != 0)) {
			return -1;
		}
		if (!words_equal(mCs, mCh, 16)) {
			fails++;
		}
	}
	return fails;
}

static int test_error_path(void)
{
	int fails = 0;
	uint32_t st = 0;

	/* misaligned A address on purpose */
	int rc = gemm_run_descriptor(gemm, (uint32_t)(uintptr_t)mA + 1, 4, (uint32_t)(uintptr_t)mB, 4,
				     (uint32_t)(uintptr_t)mCh, 16, 1, false, &st);

	if (rc != -EIO) {
		fails++;
	}
	if (GEMM_DMST_ERRCODE(st) != 1) {
		fails++;
	}
	/* the driver must recover with a valid descriptor */
	fill(mA, 16);
	fill(mB, 16);
	gemm_sw(mA, mB, mCs, 4);
	fill_c(mCh, 16, 0);
	if (gemm_matmul(gemm, mA, mB, mCh, 4, false) || !words_equal(mCs, mCh, 16)) {
		fails++;
	}
	return fails;
}

static int test_isr_count(void)
{
	int fails = 0;

	fill(mA, 16);
	fill(mB, 16);
	uint32_t c0 = gemm_isr_count(gemm);

	for (int i = 0; i < 10; i++) {
		if (gemm_matmul(gemm, mA, mB, mCh, 4, true)) {
			fails++;
		}
	}
	uint32_t events = gemm_isr_count(gemm) - c0;

	printk("ISR events for 10 interrupt-mode descriptors: %u\n", (unsigned int)events);
	if (events != 10) {
		fails++;
	}
	c0 = gemm_isr_count(gemm);
	for (int i = 0; i < 10; i++) {
		if (gemm_matmul(gemm, mA, mB, mCh, 4, false)) {
			fails++;
		}
	}
	events = gemm_isr_count(gemm) - c0;
	printk("ISR events for 10 poll-mode descriptors: %u\n", (unsigned int)events);
	if (events != 0) {
		fails++;
	}
	return fails;
}

static void coherency_probe(void)
{
	uint32_t st;

	for (int i = 0; i < 16; i++) {
		mA[i] = (int8_t)(i + 1);
		mB[i] = 0;
	}
	for (int d = 0; d < 4; d++) {
		mB[d * 4 + d] = 1;
	}
	fill_c(mCh, 16, 0x5A5A5A5A);
	volatile int32_t *vc = (volatile int32_t *)mCh;
	int32_t sink = 0;

	for (int i = 0; i < 16; i++) {
		sink += vc[i]; /* pull the sentinel lines into the data cache */
	}
	(void)sink;
	gemm_run_descriptor(gemm, (uint32_t)(uintptr_t)mA, 4, (uint32_t)(uintptr_t)mB, 4,
			    (uint32_t)(uintptr_t)mCh, 16, 1, false, &st);
	int stale = 0, after = 0;

	for (int i = 0; i < 16; i++) {
		if (vc[i] != i + 1) {
			stale++;
		}
	}
	gemm_dcache_flush();
	for (int i = 0; i < 16; i++) {
		if (vc[i] != i + 1) {
			after++;
		}
	}
	printk("coherency probe: stale words without flush = %d, after flush = %d\n", stale, after);
}

static void report_counters(int n, uint32_t lanes)
{
	uint32_t st;
	struct gemm_counters c;

	fill(mA, n * n);
	fill(mB, n * n);
	gemm_dcache_flush();
	int rc = gemm_run_descriptor(gemm, (uint32_t)(uintptr_t)mA, (uint32_t)n,
				     (uint32_t)(uintptr_t)mB, (uint32_t)n, (uint32_t)(uintptr_t)mCh,
				     (uint32_t)(n * 4), (uint32_t)(n / 4), false, &st);

	gemm_get_counters(gemm, &c);
	printk("DMA counters (K=%d): cycles=%u xfers=%u stall=%u%s\n", n / 4, (unsigned int)c.cycles,
	       (unsigned int)c.xfers, (unsigned int)c.waits, rc ? "  (HW error)" : "");
	printk("ZCSV,ctr,%u,%d,%u,%u,%u\n", (unsigned int)lanes, n / 4, (unsigned int)c.cycles,
	       (unsigned int)c.xfers, (unsigned int)c.waits);
}

/* ---------- CPU offload: how much CPU time do other threads get during a DMA matmul? ---------- */
static volatile uint32_t bg_count;

static void bg_fn(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);
	while (1) {
		bg_count++;
	}
}
K_THREAD_DEFINE(bg_tid, 1024, bg_fn, NULL, NULL, NULL, 10, 0, 0);

static void offload_demo(int n, uint32_t lanes)
{
	/* calibration: the background thread alone for 200 ms */
	uint32_t c0 = bg_count;
	uint32_t t0 = now();

	k_msleep(200);
	uint32_t cal_count = bg_count - c0;
	uint32_t cal_cycles = now() - t0;

	if (cal_count == 0) {
		printk("offload: background thread did not run during calibration\n");
		return;
	}
	fill(mA, n * n);
	fill(mB, n * n);
	for (int mode = 0; mode < 2; mode++) {
		uint32_t b0 = bg_count;

		t0 = now();
		int rc = gemm_matmul(gemm, mA, mB, mCh, n, mode == 1);
		uint32_t cycles = now() - t0;
		uint32_t bgd = bg_count - b0;
		uint32_t pct = (uint32_t)(((uint64_t)bgd * cal_cycles * 100ULL) /
					  ((uint64_t)cal_count * (uint64_t)(cycles ? cycles : 1)));

		printk("offload N=%d mode=%s: dma_cycles=%u bg_iterations=%u cpu_available=%u%%%s\n", n,
		       mode ? "irq " : "poll", (unsigned int)cycles, (unsigned int)bgd,
		       (unsigned int)pct, rc ? "  (error)" : "");
		printk("ZCSV,offload,%u,%d,%s,%u,%u,%u\n", (unsigned int)lanes, n, mode ? "irq" : "poll",
		       (unsigned int)cycles, (unsigned int)bgd, (unsigned int)pct);
	}
}

/* ---------- benchmarks ---------- */
typedef int (*gemm_fn)(const int8_t *, const int8_t *, int32_t *, int);

static int w_blocked(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
	gemm_sw_blocked(A, B, C, n);
	return 0;
}
static int w_dma_poll(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
	return gemm_matmul(gemm, A, B, C, n, false);
}
static int w_dma_irq(const int8_t *A, const int8_t *B, int32_t *C, int n)
{
	return gemm_matmul(gemm, A, B, C, n, true);
}

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

static int bench(int n, int reps, uint32_t ovh, uint32_t lanes)
{
	uint32_t sw, blk, dma, dmai;

	fill(mA, n * n);
	fill(mB, n * n);
	uint32_t t0 = now();

	for (int r = 0; r < reps; r++) {
		gemm_sw(mA, mB, mCs, n);
		__asm__ volatile("" ::: "memory");
	}
	uint32_t t1 = now();

	sw = sub0(t1 - t0, ovh) / (uint32_t)reps;
	int ok_blk = time_method(w_blocked, n, reps, ovh, &blk);
	int ok_dma = time_method(w_dma_poll, n, reps, ovh, &dma);
	int ok_irq = time_method(w_dma_irq, n, reps, ovh, &dmai);
	int ok = ok_blk && ok_dma && ok_irq;

	printk("N=%d reps=%d  sw=%u blk=%u dma=%u dma_irq=%u\n", n, reps, (unsigned int)sw,
	       (unsigned int)blk, (unsigned int)dma, (unsigned int)dmai);
	printk("  vs naive: blk=");
	put_ratio(sw, blk);
	printk(" dma=");
	put_ratio(sw, dma);
	printk(" dma_irq=");
	put_ratio(sw, dmai);
	printk("\n  vs blocked: dma=");
	put_ratio(blk, dma);
	printk(" dma_irq=");
	put_ratio(blk, dmai);
	printk("\n  match: blk=%s dma=%s dma_irq=%s\n", yn(ok_blk), yn(ok_dma), yn(ok_irq));
	printk("ZCSV,day7,%u,%d,%u,%u,%u,%u,%d\n", (unsigned int)lanes, n, (unsigned int)sw,
	       (unsigned int)blk, (unsigned int)dma, (unsigned int)dmai, ok);
	return ok;
}

int main(void)
{
	int pass = 1;

	printk("\n=== litex-gemm Day 7: Zephyr driver (v1) ===\n");
	printk("Zephyr %s, hw cycles/s = %u, ticks/s = %u\n", KERNEL_VERSION_STRING,
	       (unsigned int)sys_clock_hw_cycles_per_sec(), (unsigned int)CONFIG_SYS_CLOCK_TICKS_PER_SEC);
	if (!device_is_ready(gemm)) {
		printk("accelerator device not ready (ID mismatch or init failure)\nRESULT: FAIL\n");
		return 0;
	}
	struct gemm_info info;

	gemm_get_info(gemm, &info);
	printk("accelerator: LANES=%u tile=%u version=0x%04x\n", (unsigned int)info.lanes,
	       (unsigned int)info.tile, (unsigned int)info.version);
	printk("buffers: A=0x%08x B=0x%08x Cs=0x%08x Ch=0x%08x\n", (unsigned int)(uintptr_t)mA,
	       (unsigned int)(uintptr_t)mB, (unsigned int)(uintptr_t)mCs, (unsigned int)(uintptr_t)mCh);

	uint32_t ovh = timer_overhead();

	printk("timer read overhead: %u cycles (subtracted from results)\n", (unsigned int)ovh);

	int f = test_known_answers();

	printk("known-answer tests: %s\n", f == 0 ? "PASS" : "FAIL");
	pass &= (f == 0);
	f = test_random(100);
	printk("random 4x4 tiles (100, poll and interrupt alternating): %s\n", f == 0 ? "PASS" : "FAIL");
	pass &= (f == 0);
	f = test_error_path();
	printk("error path (misaligned descriptor) and recovery: %s\n", f == 0 ? "PASS" : "FAIL");
	pass &= (f == 0);
	f = test_isr_count();
	printk("interrupt count test: %s\n", f == 0 ? "PASS" : "FAIL");
	pass &= (f == 0);

	coherency_probe();
	report_counters(4, info.lanes);
	report_counters(16, info.lanes);
	report_counters(32, info.lanes);

	offload_demo(64, info.lanes);

	static const int sizes[] = {4, 8, 16, 32, 64};
	static const int reps[] = {20, 10, 3, 1, 1};

	for (int i = 0; i < 5; i++) {
		pass &= bench(sizes[i], reps[i], ovh, info.lanes) != 0;
	}
	printk("BENCH DONE\n");
	printk("RESULT: %s\n", pass ? "PASS" : "FAIL");
	return 0;
}
