#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>

int main(void)
{
	printk("\n*** litex-gemm Zephyr hello ***\n");
	printk("hw cycles/s = %u, ticks/s = %u\n", (unsigned int)sys_clock_hw_cycles_per_sec(),
	       (unsigned int)CONFIG_SYS_CLOCK_TICKS_PER_SEC);

	uint32_t t0 = k_cycle_get_32();
	k_busy_wait(1000);
	uint32_t t1 = k_cycle_get_32();
	printk("1000 us busy-wait = %u cycles\n", (unsigned int)(t1 - t0));

	printk("GEMM ID=0x%08x INFO=0x%08x\n", (unsigned int)sys_read32(0x9000008CUL),
	       (unsigned int)sys_read32(0x90000090UL));

	for (int i = 1;; i++) {
		k_msleep(1000);
		printk("tick %d\n", i);
	}
	return 0;
}
