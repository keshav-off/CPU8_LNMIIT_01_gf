# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

@cocotb.test()
async def test_add_wrap(dut):
    dut._log.info("Start")

    # Set the clock period to 10 us (100 KHz)
    clock = Clock(dut.clk, 1, unit="us")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 2)
    dut.rst_n.value = 1
    #await ClockCycles(dut.clk, 3)

    dut._log.info("load in program memory")
    #instr1
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0x1F
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr2
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0x3F
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr3
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0x60
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr4
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0xE0
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr5
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0xE0
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr6 
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0xE0
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr7
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0xE0
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10
    await ClockCycles(dut.clk, 1)

    #instr8
    dut.uio_in.value = 0b00
    dut.ui_in.value = 0xE0
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0b10

    # Wait for one clock cycle to see the output values
    await ClockCycles(dut.clk, 1)

    #program loaded 
    dut._log.info("Instruction loaded")

    #assert run 
    dut.uio_in.value = 0b01
    await ClockCycles(dut.clk, 4)

    assert int(dut.uo_out.value) == 62

    #reset 
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 2)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    assert int(dut.uo_out.value) == 0x00

    # Keep testing the module by changing the input values, waiting for
    # one or more clock cycles, and asserting the expected output values.
