#!/usr/bin/env python3
# Idempotent Day 5 firmware patch for fw/main.c
import re

p = "fw/main.c"
s = open(p).read()
done = []

# 1) ld32: replace the memcpy-based definition with an aligned load
LD32_NEW = ("typedef uint32_t __attribute__((may_alias)) u32_alias;\n"
            "/* Matrices are 4-byte aligned and n is a multiple of 4, so every tile row is word aligned. */\n"
            "static inline uint32_t ld32(const int8_t *p) { return *(const u32_alias *)p; }")
if "u32_alias" in s:
    print("ld32: already patched")
else:
    s, n = re.subn(r"^static inline uint32_t ld32\(.*\}\s*$", LD32_NEW, s, flags=re.M)
    assert n == 1, "ld32 definition not found; send: grep -n ld32 fw/main.c"
    done.append("ld32")

# 2) optimized PIO routine
FAST = r'''
/* Optimized PIO: no per-word index arithmetic, unrolled tile load and read. */
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

'''
assert FAST.rstrip().endswith("}"), "closing brace missing in the pasted script; recopy it"
if "gemm_hw_pio_fast" in s:
    print("gemm_hw_pio_fast: already present")
else:
    marker = "/* ---------- correctness ---------- */"
    assert marker in s, "marker comment '/* ---------- correctness ---------- */' not found in fw/main.c"
    s = s.replace(marker, FAST + marker, 1)
    done.append("gemm_hw_pio_fast")

# 3) benchmark for the optimized routine
BENCH = r'''
static int bench_fast(int n, int reps, uint32_t ovh, uint32_t lanes)
{
    fill(mA, n * n);
    fill(mB, n * n);

    uint32_t t0 = now();
    for (int r = 0; r < reps; r++) { gemm_sw(mA, mB, mCs, n); __asm__ volatile("" ::: "memory"); }
    uint32_t t1 = now();
    uint32_t sw = sub0(t1 - t0, ovh) / reps;

    int rc = 0;
    t0 = now();
    for (int r = 0; r < reps && !rc; r++) rc = gemm_hw_pio_fast(mA, mB, mCh, n);
    t1 = now();
    uint32_t fast = sub0(t1 - t0, ovh) / reps;
    int ok = (rc == 0) && words_equal(mCs, mCh, n * n);

    printf("FAST N=%d  sw=%lu  hw_pio_fast=%lu  ", n, (unsigned long)sw, (unsigned long)fast);
    print_ratio("speedup ", sw, fast);
    printf("  match=%s\n", ok ? "yes" : "NO");
    printf("CSV,fast,%lu,%d,%lu,%lu,%d\n", (unsigned long)lanes, n, (unsigned long)sw,
           (unsigned long)fast, ok);
    return ok;
}

'''
if "bench_fast" in s:
    print("bench_fast: already present")
else:
    assert "int main(void)" in s, "'int main(void)' not found"
    s = s.replace("int main(void)", BENCH + "int main(void)", 1)
    old3 = '    printf("BENCH DONE\\n");'
    assert old3 in s, "BENCH DONE line not found in main()"
    new3 = ('    for (int i = 0; i < 4; i++)\n'
            '        if (!bench_fast(sizes[i], reps[i], ovh, lanes)) pass = 0;\n\n' + old3)
    s = s.replace(old3, new3, 1)
    done.append("bench_fast")

open(p, "w").write(s)
print("patched:", ", ".join(done) if done else "nothing (all steps already present)")
