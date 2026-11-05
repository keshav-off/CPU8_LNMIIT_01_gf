# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

async def test_reset_clears_halt(dut):
	prog = [0x03, 0x60, 0x41, 0xA5, 0xE0, 0xE0, 0xE0, 0xE0] #one time counter 	

	dut._log.info("load in program memory")
	for i in prog:
		dut.uio_in.value = 0b00
		dut.ui_in.value = i
		await ClockCycles(dut.clk, 1)
		dut.uio_in.value = 0b10
		await ClockCycles(dut.clk, 1)

	 #program loaded 
	dut._log.info("Instruction loaded")

        #assert run 
	dut.uio_in.value = 0b01
	await ClockCycles(dut.clk, 7)

	assert dut.user_project.u_tcpu.is_halt.value == 1

	dut.rst_n.value = 0
	await ClockCycles(dut.clk, 2)
	assert dut.user_project.u_tcpu.is_halt.value == 0

	dut.rst_n.value = 1
	dut.uio_in.value = 0b01
	await ClockCycles(dut.clk, 2)	
	
	assert dut.user_project.u_tcpu.acc.value == 0x03 
	assert dut.user_project.u_tcpu.pc.value == 1


	 
	


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

    #test_reset_value 
    await test_reset_clears_halt(dut)

 

    # Keep testing the module by changing the input values, waiting for
    # one or more clock cycles, and asserting the expected output values.
