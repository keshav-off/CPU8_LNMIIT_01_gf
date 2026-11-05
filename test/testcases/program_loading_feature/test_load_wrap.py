# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

async def test_load_wrap(dut):
	prog = [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17]  	

	dut._log.info("load in program memory")
	for i in prog:
		dut.uio_in.value = 0b00
		dut.ui_in.value = i
		await ClockCycles(dut.clk, 1)
		dut.uio_in.value = 0b10
		await ClockCycles(dut.clk, 1)

	 #program loaded 
	dut._log.info("Instruction loaded")

	dut.uio_in.value = 0b00
	dut.ui_in.value = 0xEE
	await ClockCycles(dut.clk, 1)
	dut.uio_in.value = 0b10
	await ClockCycles(dut.clk, 2)
	
	assert int(dut.user_project.u_tcpu.U_program_memory.ir_mem[0].value) == 0xEE

	for i in range(7):
		assert int(dut.user_project.u_tcpu.U_program_memory.ir_mem[i+1].value) == 0x10 + i+1

	assert dut.user_project.u_tcpu.is_load_addr.value == 1



@cocotb.test()
async def program_loading(dut):
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
    await test_load_wrap(dut)

 

    # Keep testing the module by changing the input values, waiting for
    # one or more clock cycles, and asserting the expected output values.
