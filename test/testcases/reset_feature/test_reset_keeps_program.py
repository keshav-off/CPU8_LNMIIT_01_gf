# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge 

async def test_reset_keeps_program(dut):
	prog = [0x03, 0x60, 0x41, 0xA5, 0x81, 0xE0, 0xE0, 0xE0]	

	trace1 = []
	trace2 = []
	pc = []
	acc = []
	ir = []

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
	
	for i in range(20):
		await FallingEdge(dut.clk)
		pc = dut.user_project.u_tcpu.pc.value
		acc = dut.user_project.u_tcpu.acc.value
		ir = dut.user_project.u_tcpu.ir.value
		out_data = dut.user_project.u_tcpu.out_data.value 
		halted = dut.user_project.u_tcpu.halted.value

		trace1.append((pc, acc, ir, halted, out_data))

	dut.rst_n.value = 0
	await ClockCycles(dut.clk, 2)
	dut.rst_n.value = 1
	
	dut.uio_in.value = 0b01
	await ClockCycles(dut.clk, 8)
	dut.rst_n.value = 0
	await ClockCycles(dut.clk, 2)
	dut.rst_n.value = 1
	
	dut.uio_in.value = 0b01
	for i in range(20):
		await FallingEdge(dut.clk)
		pc = dut.user_project.u_tcpu.pc.value
		acc = dut.user_project.u_tcpu.acc.value
		ir = dut.user_project.u_tcpu.ir.value
		out_data = dut.user_project.u_tcpu.out_data.value 
		halted = dut.user_project.u_tcpu.halted.value

		trace2.append((pc, acc, ir, halted, out_data))
	
	await ClockCycles(dut.clk, 1)

			 

	assert trace1 == trace2
	
	#reset mid program and check value of out 
	dut.uio_in.value = 0b00
	dut.rst_n.value = 0
	await ClockCycles(dut.clk, 2)
	dut.rst_n.value = 1
	await ClockCycles(dut.clk, 1)

	assert int(dut.uo_out.value) == 0x00

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
    await test_reset_keeps_program(dut)

 

    # Keep testing the module by changing the input values, waiting for
    # one or more clock cycles, and asserting the expected output values.
