# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

async def test_load_edge_detect(dut):
	prog = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]  	

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
	dut.ui_in.value = 0xA5
	await ClockCycles(dut.clk, 1)
	dut.uio_in.value = 0b10
	await ClockCycles(dut.clk, 5)

	dut.uio_in.value = 0b00
	await ClockCycles(dut.clk, 2)

	assert dut.user_project.u_tcpu.is_load_addr.value == 1
	assert int(dut.user_project.u_tcpu.U_program_memory.ir_mem[0].value) == 0xA5



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
    await test_load_edge_detect(dut)

 

    # Keep testing the module by changing the input values, waiting for
    # one or more clock cycles, and asserting the expected output values.
