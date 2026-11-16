# SPDX-License-Identifier: Apache-2.0
"""
TCPU-8 pin-only tests for the GATE-LEVEL simulation.

After synthesis the design is flattened, so pc / acc / memory cannot be read.
Everything here is checked through the chip pins only:
    ui_in = prog_data,  uio_in[1] = prog_load,  uio_in[0] = run,  uo_out = out_data
To see a value, the program ends with STORE, which copies ACC to uo_out.

The same file also runs in RTL simulation, so you can check it there first.
Run:  make COCOTB_TEST_MODULES=test_cpu8_gl            (RTL)
      make GATES=yes COCOTB_TEST_MODULES=test_cpu8_gl  (gate level)
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge


def LOAD(i): return 0x00 | i
def ADD(i):  return 0x20 | i
def SUB(i):  return 0x40 | i
def JMP(a):  return 0x80 | a
def JZ(a):   return 0xA0 | a
def XOR(i):  return 0xC0 | i
STORE = 0x60
HALT = 0xE0
COUNTDOWN = [LOAD(3), STORE, SUB(1), JZ(5), JMP(1), HALT, HALT, HALT]


def drive(dut, run=0, load=0, data=None):
    dut.uio_in.value = (load << 1) | run
    if data is not None:
        dut.ui_in.value = data


async def step(dut, n=1):
    """n rising edges, then return on the falling edge (settled values)."""
    for _ in range(n):
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)


async def load_prog(dut, prog, hold=1, gap=1):
    for word in prog + [HALT] * (8 - len(prog)):
        drive(dut, run=0, load=1, data=word)
        await step(dut, hold)
        drive(dut, run=0, load=0)
        await step(dut, gap)


async def fresh(dut, prog, hold=1, gap=1):
    """Reset, load a program, leave run = 0."""
    drive(dut, run=0, load=0)
    dut.rst_n.value = 0
    await step(dut, 2)
    dut.rst_n.value = 1
    await step(dut, 1)
    await load_prog(dut, prog, hold, gap)


async def run_edges(dut, n):
    drive(dut, run=1, load=0)
    await step(dut, n)


def out(dut):
    return int(dut.uo_out.value)


async def run_subs(dut, subs):
    failed = []
    for sub in subs:
        dut._log.info(f"  sub-feature: {sub.__name__}")
        try:
            await sub()
        except AssertionError as err:
            dut._log.error(f"  FAILED {sub.__name__}: {err}")
            failed.append(sub.__name__)
    assert not failed, f"failed sub-features: {failed}"


@cocotb.test()
async def gl_pin_only(dut):
    cocotb.start_soon(Clock(dut.clk, 1, unit="us").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await FallingEdge(dut.clk)

    async def check_program(prog, edges, want):
        await fresh(dut, prog)
        await run_edges(dut, edges)
        assert out(dut) == want, f"out_data got 0x{out(dut):02X}, expected 0x{want:02X}"

    async def test_reset_clears_output():
        await check_program([LOAD(9), STORE], 2, 0x09)
        drive(dut, run=0)
        dut.rst_n.value = 0
        await step(dut, 2)
        dut.rst_n.value = 1
        assert out(dut) == 0x00

    async def test_countdown_and_load_edge_detect():
        # prog_load is held 3 clocks per word: still exactly one write per pulse
        await fresh(dut, COUNTDOWN, hold=3, gap=2)
        drive(dut, run=1)
        seen = []
        for _ in range(16):
            await step(dut, 1)
            seen.append(out(dut))
        assert (seen[1], seen[5], seen[9]) == (3, 2, 1), f"outputs {seen}"
        assert seen[9:] == [1] * 7, f"output must hold after HALT, outputs {seen}"

    async def test_alu_operations():
        await check_program([LOAD(10), ADD(5), STORE], 3, 15)
        await check_program([LOAD(31), ADD(31), STORE], 3, 62)
        await check_program([LOAD(20), SUB(5), STORE], 3, 15)
        await check_program([LOAD(0), SUB(1), STORE], 3, 0xFF)       # underflow wrap
        await check_program([LOAD(0), SUB(1), ADD(1), STORE], 4, 0x00)
        await check_program([LOAD(15), XOR(5), STORE], 3, 0x0A)
        await check_program([LOAD(10), XOR(31), XOR(31), STORE], 4, 0x0A)
        await check_program([LOAD(0), SUB(1), XOR(31), STORE], 4, 0xE0)

    async def test_jmp():
        await check_program([JMP(2), LOAD(5), LOAD(3), STORE], 3, 0x03)   # word 1 skipped

    async def test_jz_taken_and_not_taken():
        await check_program([LOAD(1), SUB(1), JZ(4), LOAD(7), STORE], 4, 0x00)   # taken
        await check_program([LOAD(2), SUB(1), JZ(4), LOAD(7), STORE], 5, 0x07)   # not taken

    async def test_halt_stops_cpu():
        await check_program([LOAD(4), STORE, HALT, LOAD(9), STORE], 12, 0x04)

    async def test_pause_holds_output():
        await fresh(dut, [LOAD(9), STORE, LOAD(1), STORE])
        await run_edges(dut, 2)
        drive(dut, run=0)
        for _ in range(10):
            await step(dut, 1)
            assert out(dut) == 0x09, "output changed while paused"
        await run_edges(dut, 2)
        assert out(dut) == 0x01

    async def test_load_blocked_while_running():
        await fresh(dut, [LOAD(6), STORE])
        drive(dut, run=1, load=1, data=0xFF)       # try to overwrite word 0 while running
        await step(dut, 3)
        drive(dut, run=1, load=0)
        await step(dut, 1)
        assert out(dut) in (0x00, 0x06), f"unexpected out_data 0x{out(dut):02X}"
        # restart the same program: word 0 must still be LOAD 6
        drive(dut, run=0, load=0)
        dut.rst_n.value = 0
        await step(dut, 2)
        dut.rst_n.value = 1
        await run_edges(dut, 2)
        assert out(dut) == 0x06, "word 0 was overwritten while run = 1"

    await run_subs(dut, [
        test_reset_clears_output, test_countdown_and_load_edge_detect, test_alu_operations,
        test_jmp, test_jz_taken_and_not_taken, test_halt_stops_cpu,
        test_pause_holds_output, test_load_blocked_while_running,
    ])
