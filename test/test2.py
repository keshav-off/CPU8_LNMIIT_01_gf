import cocotb
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject
from cocotb.triggers import ClockCycles, FallingEdge

PROG = [0x1F, 0x3F, 0x60, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0]


def find_reg(scope, name):
    for child in scope:
        if child._name == name:
            return child
        if isinstance(child, HierarchyObject):
            r = find_reg(child, name)
            if r is not None:
                return r
    return None


async def monitor(dut):
    pc, acc = find_reg(dut, "pc"), find_reg(dut, "acc")
    ir, halted = find_reg(dut, "ir"), find_reg(dut, "halted")
    while True:
        await FallingEdge(dut.clk)
        dut._log.info(f"pc={pc.value} ir={ir.value} acc={acc.value} "
                      f"halted={halted.value} uo_out={dut.uo_out.value} "
                      f"uio_in={dut.uio_in.value}")


async def load_word(dut, word):
    dut.ui_in.value = word
    dut.uio_in.value = 0b10          # prog_load = 1, run = 0
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = 0b00
    await ClockCycles(dut.clk, 3)


@cocotb.test()
async def test_debug(dut):
    cocotb.start_soon(Clock(dut.clk, 1, unit="us").start())
    cocotb.start_soon(monitor(dut))

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 3)

    for w in PROG:
        await load_word(dut, w)

    dut.uio_in.value = 0b01          # run
    await ClockCycles(dut.clk, 8)

    assert int(dut.uo_out.value) == 62
