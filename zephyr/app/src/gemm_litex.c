#define DT_DRV_COMPAT litex_gemm_accel

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/irq.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_io.h>
#ifdef GEMM_USE_ZEPHYR_CACHE_API
#include <zephyr/cache.h>
#endif

#include "gemm_litex.h"

#define GEMM_TIMEOUT_MS 500
#define GEMM_POLL_LIMIT 1000000U

struct gemm_config {
	mem_addr_t base;
	void (*irq_config)(void);
};

struct gemm_data {
	struct k_sem done;
	struct k_mutex lock;
	volatile uint32_t isr_status;
	volatile uint32_t isr_count;
};

static inline void wr(mem_addr_t base, uint32_t off, uint32_t v)
{
	sys_write32(v, base + off);
}

static inline uint32_t rd(mem_addr_t base, uint32_t off)
{
	return sys_read32(base + off);
}

void gemm_dcache_flush(void)
{
#ifdef GEMM_USE_ZEPHYR_CACHE_API
	sys_cache_data_flush_and_invd_all();
#else
	__asm__ volatile(GEMM_DCACHE_FLUSH_INSN ::: "memory");
#endif
}

/* The interrupt line is level-sensitive (IRQ_EN & DONE/ERROR): record the status, clear DONE
 * (which also drops the line and clears IRQ_EN), then wake the waiting thread. */
static void gemm_isr(const struct device *dev)
{
	const struct gemm_config *cfg = dev->config;
	struct gemm_data *data = dev->data;
	uint32_t st = rd(cfg->base, GEMM_REG_DMA_STATUS);

	if (!(st & (GEMM_DMST_DONE | GEMM_DMST_ERROR))) {
		return; /* spurious: the level line is already low */
	}
	data->isr_status = st;
	data->isr_count++;
	wr(cfg->base, GEMM_REG_CTRL, GEMM_CTRL_DONE_CLR);
	(void)rd(cfg->base, GEMM_REG_CTRL); /* read back: the clear has reached the device */
	k_sem_give(&data->done);
}

static int run_desc_locked(const struct device *dev, uint32_t a, uint32_t as, uint32_t b,
			   uint32_t bs, uint32_t c, uint32_t cs, uint32_t k, bool program_shared,
			   bool use_irq, uint32_t *status)
{
	const struct gemm_config *cfg = dev->config;
	struct gemm_data *data = dev->data;
	mem_addr_t base = cfg->base;
	uint32_t st = 0;

	wr(base, GEMM_REG_CTRL, GEMM_CTRL_DONE_CLR); /* clear DONE/ERROR; IRQ_EN = 0 */
	if (program_shared) {
		wr(base, GEMM_REG_DMA_AS, as);
		wr(base, GEMM_REG_DMA_BS, bs);
		wr(base, GEMM_REG_DMA_CS, cs);
		wr(base, GEMM_REG_DMA_K, k);
	}
	wr(base, GEMM_REG_DMA_A, a);
	wr(base, GEMM_REG_DMA_B, b);
	wr(base, GEMM_REG_DMA_C, c);
	k_sem_reset(&data->done);
	/* enable the interrupt only after DONE is clear, so no spurious interrupt can fire */
	wr(base, GEMM_REG_CTRL, use_irq ? GEMM_CTRL_IRQ_EN : 0);
	wr(base, GEMM_REG_DMA_CTRL, GEMM_DMA_START);

	if (use_irq) {
		if (k_sem_take(&data->done, K_MSEC(GEMM_TIMEOUT_MS)) != 0) {
			wr(base, GEMM_REG_CTRL, GEMM_CTRL_DONE_CLR);
			if (status) {
				*status = rd(base, GEMM_REG_DMA_STATUS);
			}
			return -ETIMEDOUT;
		}
		st = data->isr_status;
	} else {
		uint32_t i;

		for (i = 0; i < GEMM_POLL_LIMIT; i++) {
			st = rd(base, GEMM_REG_DMA_STATUS);
			if (st & (GEMM_DMST_DONE | GEMM_DMST_ERROR)) {
				break;
			}
		}
		wr(base, GEMM_REG_CTRL, GEMM_CTRL_DONE_CLR);
		if (i == GEMM_POLL_LIMIT) {
			if (status) {
				*status = st;
			}
			return -ETIMEDOUT;
		}
	}
	if (status) {
		*status = st;
	}
	return (st & GEMM_DMST_ERROR) ? -EIO : 0;
}

int gemm_run_descriptor(const struct device *dev, uint32_t a, uint32_t a_stride, uint32_t b,
			uint32_t b_stride, uint32_t c, uint32_t c_stride, uint32_t k,
			bool use_irq, uint32_t *status)
{
	struct gemm_data *data = dev->data;
	int rc;

	k_mutex_lock(&data->lock, K_FOREVER);
	rc = run_desc_locked(dev, a, a_stride, b, b_stride, c, c_stride, k, true, use_irq, status);
	k_mutex_unlock(&data->lock);
	return rc;
}

int gemm_matmul(const struct device *dev, const int8_t *a, const int8_t *b, int32_t *c, int n,
		bool use_irq)
{
	struct gemm_data *data = dev->data;
	int rc = 0;
	bool first = true;

	if (n < 4 || (n % 4) != 0) {
		return -EINVAL;
	}
	k_mutex_lock(&data->lock, K_FOREVER);
	gemm_dcache_flush(); /* A and B must be visible to the DMA */
	for (int ti = 0; ti < n / 4 && rc == 0; ti++) {
		for (int tj = 0; tj < n / 4 && rc == 0; tj++) {
			rc = run_desc_locked(dev, (uint32_t)(uintptr_t)(a + ti * 4 * n), (uint32_t)n,
					     (uint32_t)(uintptr_t)(b + tj * 4), (uint32_t)n,
					     (uint32_t)(uintptr_t)(c + ti * 4 * n + tj * 4),
					     (uint32_t)(n * 4), (uint32_t)(n / 4), first, use_irq,
					     NULL);
			first = false;
		}
	}
	gemm_dcache_flush(); /* the DMA wrote C behind the CPU's back */
	k_mutex_unlock(&data->lock);
	return rc;
}

int gemm_get_info(const struct device *dev, struct gemm_info *info)
{
	const struct gemm_config *cfg = dev->config;
	uint32_t v = rd(cfg->base, GEMM_REG_INFO);

	info->lanes = v & 0xFF;
	info->tile = (v >> 8) & 0xFF;
	info->version = (uint16_t)(v >> 16);
	return 0;
}

int gemm_get_counters(const struct device *dev, struct gemm_counters *c)
{
	const struct gemm_config *cfg = dev->config;

	c->cycles = rd(cfg->base, GEMM_REG_DMA_CYC);
	c->xfers = rd(cfg->base, GEMM_REG_DMA_XFERS);
	c->waits = rd(cfg->base, GEMM_REG_DMA_WAITS);
	return 0;
}

uint32_t gemm_isr_count(const struct device *dev)
{
	struct gemm_data *data = dev->data;

	return data->isr_count;
}

static int gemm_init(const struct device *dev)
{
	const struct gemm_config *cfg = dev->config;
	struct gemm_data *data = dev->data;

	if (rd(cfg->base, GEMM_REG_ID) != GEMM_ID_VALUE) {
		return -ENODEV;
	}
	k_sem_init(&data->done, 0, 1);
	k_mutex_init(&data->lock);
	wr(cfg->base, GEMM_REG_CTRL, GEMM_CTRL_DONE_CLR);
	cfg->irq_config();
	return 0;
}

#define GEMM_INIT(n)                                                                              \
	static void gemm_irq_config_##n(void)                                                     \
	{                                                                                         \
		IRQ_CONNECT(DT_INST_IRQN(n), DT_INST_IRQ(n, priority), gemm_isr,                  \
			    DEVICE_DT_INST_GET(n), 0);                                            \
		irq_enable(DT_INST_IRQN(n));                                                      \
	}                                                                                         \
	static struct gemm_data gemm_data_##n;                                                    \
	static const struct gemm_config gemm_cfg_##n = {                                          \
		.base = DT_INST_REG_ADDR(n),                                                      \
		.irq_config = gemm_irq_config_##n,                                                \
	};                                                                                        \
	DEVICE_DT_INST_DEFINE(n, gemm_init, NULL, &gemm_data_##n, &gemm_cfg_##n, POST_KERNEL,     \
			      CONFIG_KERNEL_INIT_PRIORITY_DEVICE, NULL);

DT_INST_FOREACH_STATUS_OKAY(GEMM_INIT)
