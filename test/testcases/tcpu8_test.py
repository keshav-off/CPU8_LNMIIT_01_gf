# SPDX-License-Identifier: Apache-2.0
"""
TCPU-8 cocotb tests - one file for the whole test plan (TCPU8_Test_Plan.xlsx).

Layout
    * Each FEATURE of the plan is one @cocotb.test() function  (feature_01_reset, ...).
    * Each SUB-FEATURE is a small async function defined inside its feature
      function and named like the "Test name" column of the plan.
    * run_subs() runs the sub-features one after the other. A failing
      sub-feature is reported by name and the others still run.

How the timing works (so you never need "extra" clock waits)
    * Every input is changed right after a FALLING clock edge.
    * step(dut, n) waits for n rising edges and returns on the falling edge
      after the last one, so the CPU registers have settled and can be read.
    * "Edge k" in the plan = the k-th rising edge after run went high.

Run:  cd test && make COCOTB_TEST_MODULES=test_cpu8_plan
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

# ----------------------------------------------------------------------------
# Instruction encoding:  opcode in bits 7:5, operand in bits 4:0
# ----------------------------------------------------------------------------
def LOAD(i): return 0x00 | i
def ADD(i):  return 0x20 | i
def SUB(i):  return 0x40 | i
def JMP(a):  return 0x80 | a
def JZ(a):   return 0xA0 | a
def XOR(i):  return 0xC0 | i
STORE = 0x60
HALT = 0xE0

# Spec section 8 worked example (also used by many tests)
COUNTDOWN = [LOAD(3), STORE, SUB(1), JZ(5), JMP(1), HALT, HALT, HALT]

RANDOM_PROGRAMS = 1000      # test_random_programs: number of random programs
RANDOM_EDGES = 64           # clock edges per random program


# ----------------------------------------------------------------------------
# Pin helpers.  Pins: ui_in = prog_data, uio_in[1] = prog_load, uio_in[0] = run
# ----------------------------------------------------------------------------
def drive(dut, run=0, load=0, data=None):
    """Set run / prog_load (and optionally prog_data). Takes effect at the next edge."""
    dut.uio_in.value = (load << 1) | run
    if data is not None:
        dut.ui_in.value = data


async def step(dut, n=1):
    """Wait n rising edges, then return on the falling edge (settled values)."""
    for _ in range(n):
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)


async def init(dut):
    """Start the clock and apply the first reset (called once per feature)."""
    cocotb.start_soon(Clock(dut.clk, 1, unit="us").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await FallingEdge(dut.clk)


async def reset(dut, edges=2):
    """Hold rst_n low for `edges` clocks (run = 0), then release it."""
    drive(dut, run=0, load=0)
    dut.rst_n.value = 0
    await step(dut, edges)
    dut.rst_n.value = 1


async def write_word(dut, word, hold=1, gap=1, run=0):
    """One load pulse: prog_load high for `hold` clocks, then low for `gap` clocks."""
    drive(dut, run=run, load=1, data=word)
    await step(dut, hold)
    drive(dut, run=run, load=0)
    await step(dut, gap)


async def load_prog(dut, prog):
    """Write 8 words (a shorter program is padded with HALT). Leaves run = 0."""
    for word in prog + [HALT] * (8 - len(prog)):
        await write_word(dut, word)


async def fresh(dut, prog=None):
    """Reset, optionally load a program. Leaves run = 0 and the CPU at pc = 0."""
    await reset(dut)
    await step(dut, 1)
    if prog is not None:
        await load_prog(dut, prog)


async def run_edges(dut, n=1):
    """Set run = 1 and run n clock edges."""
    drive(dut, run=1, load=0)
    await step(dut, n)


async def pause(dut, n=1):
    """Set run = 0 and wait n clock edges."""
    drive(dut, run=0, load=0)
    await step(dut, n)


# ----------------------------------------------------------------------------
# Reading the design (RTL simulation: internal signals through the hierarchy)
# ----------------------------------------------------------------------------
def cpu(dut):
    return dut.user_project.u_tcpu


def state(dut):
    """All visible CPU state as a dict of ints."""
    t = cpu(dut)
    return {
        "pc": int(t.pc.value),
        "acc": int(t.acc.value),
        "ir": int(t.ir.value),
        "out_r": int(t.out_r.value),
        "halted": int(t.halted.value),
        "out_data": int(dut.uo_out.value),
        "load_addr": int(t.is_load_addr.value),
    }


def cpu_only(dut):
    """State without load_addr (the CPU registers only)."""
    s = state(dut)
    del s["load_addr"]
    return s


def mem(dut):
    """The 8 program memory words."""
    m = cpu(dut).U_program_memory.ir_mem
    return [int(m[i].value) for i in range(8)]


def expect(dut, **want):
    """expect(dut, pc=1, acc=0x03) - assert the given fields."""
    s = state(dut)
    for name, value in want.items():
        assert s[name] == value, f"{name}: got 0x{s[name]:02X}, expected 0x{value:02X}   (state {s})"


def expect_mem(dut, words):
    assert mem(dut) == list(words), f"memory: got {[hex(x) for x in mem(dut)]}, expected {[hex(x) for x in words]}"


async def run_subs(dut, subs):
    """Run the sub-features one by one; report every failure at the end."""
    failed = []
    for sub in subs:
        dut._log.info(f"  sub-feature: {sub.__name__}")
        try:
            await sub()
        except AssertionError as err:
            dut._log.error(f"  FAILED {sub.__name__}: {err}")
            failed.append(sub.__name__)
    assert not failed, f"failed sub-features: {failed}"


# ----------------------------------------------------------------------------
# Reference model (spec section 7.1): used by the lock-step tests
# ----------------------------------------------------------------------------
class Model:
    def __init__(self, prog):
        self.mem = list(prog) + [HALT] * (8 - len(prog))
        self.pc = self.acc = self.ir = self.out = self.halted = 0
        self.addr = 0
        self.prev_load = 0

    def edge(self, rst_n, run, load, data):
        pulse = load and not self.prev_load and not run
        if not rst_n:
            self.pc = self.acc = self.ir = self.out = self.halted = 0
            self.addr = 0
        else:
            if pulse:
                self.mem[self.addr] = data
                self.addr = (self.addr + 1) & 7
            if run and not self.halted:
                self.execute()
        self.prev_load = load

    def execute(self):
        ins = self.mem[self.pc]
        op, imm, tgt = ins >> 5, ins & 0x1F, ins & 7
        acc, pc = self.acc, (self.pc + 1) & 7
        if op == 0:   self.acc = imm
        elif op == 1: self.acc = (acc + imm) & 0xFF
        elif op == 2: self.acc = (acc - imm) & 0xFF
        elif op == 3: self.out = acc
        elif op == 4: pc = tgt
        elif op == 5: pc = tgt if acc == 0 else pc
        elif op == 6: self.acc = acc ^ imm
        elif op == 7: self.halted, pc = 1, self.pc
        self.ir, self.pc = ins, pc

    def as_dict(self):
        return {"pc": self.pc, "acc": self.acc, "ir": self.ir, "out_r": self.out,
                "halted": self.halted, "out_data": self.out, "load_addr": self.addr}


async def cycle(dut, model, run=0, load=0, data=0, rst_n=1):
    """One clock edge on the design and on the model, then compare everything."""
    drive(dut, run=run, load=load, data=data)
    dut.rst_n.value = rst_n
    await step(dut, 1)
    model.edge(rst_n, run, load, data)
    got, want = state(dut), model.as_dict()
    assert got == want, f"mismatch: design {got}  model {want}"


# ============================================================================
# FEATURE 1: Reset
# ============================================================================
@cocotb.test()
async def feature_01_reset(dut):
    await init(dut)

    async def test_reset_values():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 5)                       # make the state dirty
        assert state(dut)["pc"] != 0 and state(dut)["acc"] != 0
        await reset(dut)
        expect(dut, pc=0, acc=0, ir=0, out_r=0, halted=0, out_data=0)

    async def test_reset_keeps_program():
        await fresh(dut, COUNTDOWN)
        first = []
        drive(dut, run=1)
        for _ in range(20):
            await step(dut, 1)
            first.append(cpu_only(dut))
        await reset(dut)
        await run_edges(dut, 7)                       # reset in the middle of the program
        await reset(dut)
        second = []
        drive(dut, run=1)                             # no reload
        for _ in range(20):
            await step(dut, 1)
            second.append(cpu_only(dut))
        assert first == second, "trace after reset differs from the first trace"

    async def test_reset_clears_load_addr():
        await fresh(dut)
        for w in (0x11, 0x22, 0x33):
            await write_word(dut, w)
        await reset(dut)
        expect(dut, load_addr=0)
        await write_word(dut, 0x44)
        assert mem(dut)[0] == 0x44
        expect(dut, load_addr=1)

    async def test_reset_clears_halt():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        expect(dut, halted=1)
        await reset(dut)
        expect(dut, halted=0)
        await run_edges(dut, 1)
        expect(dut, acc=0x03, pc=1)

    async def test_reset_clears_output():
        await fresh(dut, [LOAD(9), STORE])
        await run_edges(dut, 2)
        expect(dut, out_data=0x09)
        await reset(dut)
        expect(dut, out_data=0x00, acc=0x00)

    async def test_reset_during_load():
        await fresh(dut)
        for w in (0xA1, 0xB2, 0xC3):
            await write_word(dut, w)
        await reset(dut)
        await write_word(dut, 0xD4)
        assert mem(dut)[:3] == [0xD4, 0xB2, 0xC3]
        expect(dut, load_addr=1)

    async def test_reset_priority_over_load():
        await fresh(dut, [0x00] * 8)
        drive(dut, run=0, load=0)
        dut.rst_n.value = 0
        await step(dut, 1)
        drive(dut, run=0, load=1, data=0xDD)          # load pulse while in reset
        await step(dut, 1)
        drive(dut, run=0, load=0)
        await step(dut, 1)
        dut.rst_n.value = 1
        expect_mem(dut, [0x00] * 8)
        expect(dut, load_addr=0)

    await run_subs(dut, [
        test_reset_values, test_reset_keeps_program, test_reset_clears_load_addr,
        test_reset_clears_halt, test_reset_clears_output, test_reset_during_load,
        test_reset_priority_over_load,
    ])


# ============================================================================
# FEATURE 2: Program loading
# ============================================================================
@cocotb.test()
async def feature_02_program_loading(dut):
    await init(dut)

    async def test_load_edge_detect():
        await fresh(dut, [0x00] * 8)
        drive(dut, run=0, load=1, data=0xA5)          # held high for 5 clocks
        await step(dut, 5)
        drive(dut, run=0, load=0)
        await step(dut, 1)
        expect_mem(dut, [0xA5] + [0x00] * 7)
        expect(dut, load_addr=1)

    async def test_load_sequential():
        await fresh(dut)
        for i in range(8):
            await write_word(dut, 0x10 + i, hold=3, gap=2)
        expect_mem(dut, [0x10 + i for i in range(8)])
        expect(dut, load_addr=0)

    async def test_load_wrap():
        await fresh(dut, [0x10 + i for i in range(8)])
        await write_word(dut, 0xEE)
        expect_mem(dut, [0xEE] + [0x10 + i for i in range(1, 8)])
        expect(dut, load_addr=1)

    async def test_load_min_pulse():
        await fresh(dut)
        for i in range(8):
            await write_word(dut, 0x20 + i, hold=1, gap=1)
        expect_mem(dut, [0x20 + i for i in range(8)])
        expect(dut, load_addr=0)

    async def test_load_data_patterns():
        patterns = [0x00, 0xFF, 0xAA, 0x55, 0x01, 0x80, 0x7F, 0xFE]
        await fresh(dut, patterns)
        expect_mem(dut, patterns)

    async def test_load_blocked_running():
        await fresh(dut, [JMP(0)] * 8)
        for _ in range(4):                            # four 1-clock pulses with run = 1
            await write_word(dut, 0xFF, run=1)
        await write_word(dut, 0xFF, hold=5, run=1)    # one 5-clock pulse
        expect_mem(dut, [JMP(0)] * 8)
        expect(dut, load_addr=0)
        await pause(dut, 1)
        await write_word(dut, 0x5A)                   # lands in mem[0] -> load_addr did not move
        assert mem(dut)[0] == 0x5A

    async def test_load_run_coincide():
        await fresh(dut, [0x00] * 8)
        drive(dut, run=1, load=1, data=0xCC)          # run and prog_load rise together
        await step(dut, 1)
        drive(dut, run=0, load=0)
        await step(dut, 1)
        expect_mem(dut, [0x00] * 8)
        expect(dut, load_addr=0)

    async def test_load_across_reset_release():
        await fresh(dut, [0x00] * 8)
        dut.rst_n.value = 0
        drive(dut, run=0, load=1, data=0xDD)          # prog_load high during reset
        await step(dut, 2)
        dut.rst_n.value = 1                           # released while prog_load stays high
        await step(dut, 4)
        drive(dut, run=0, load=0)
        await step(dut, 1)
        expect_mem(dut, [0x00] * 8)
        expect(dut, load_addr=0)

    async def test_load_while_halted():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        await pause(dut, 1)
        before = cpu_only(dut)
        la = state(dut)["load_addr"]
        await write_word(dut, 0x77)
        assert mem(dut)[0] == 0x77
        expect(dut, load_addr=(la + 1) & 7)
        assert cpu_only(dut) == before and before["halted"] == 1

    async def test_load_while_paused():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 3)
        await pause(dut, 1)
        before = cpu_only(dut)
        await write_word(dut, 0x7F)
        assert mem(dut)[0] == 0x7F
        assert cpu_only(dut) == before
        await run_edges(dut, 1)                       # continues from the held pc (3 = JZ)
        expect(dut, pc=4, ir=0xA5)

    await run_subs(dut, [
        test_load_edge_detect, test_load_sequential, test_load_wrap, test_load_min_pulse,
        test_load_data_patterns, test_load_blocked_running, test_load_run_coincide,
        test_load_across_reset_release, test_load_while_halted, test_load_while_paused,
    ])


# ============================================================================
# FEATURE 3: LOAD instruction
# ============================================================================
@cocotb.test()
async def feature_03_load_instruction(dut):
    await init(dut)

    async def test_load_imm():
        for imm in range(32):
            await fresh(dut, [LOAD(31), LOAD(imm)])
            await run_edges(dut, 1)
            expect(dut, acc=0x1F)
            await step(dut, 1)
            expect(dut, acc=imm)

    async def test_load_clears_upper_bits():
        await fresh(dut, [LOAD(0), SUB(1), LOAD(5)])
        await run_edges(dut, 2)
        expect(dut, acc=0xFF)
        await step(dut, 1)
        expect(dut, acc=0x05)

    async def test_load_no_side_effects():
        await fresh(dut, [LOAD(7)])
        await run_edges(dut, 1)
        expect(dut, pc=1, ir=0x07, acc=0x07, out_data=0x00, halted=0)

    await run_subs(dut, [test_load_imm, test_load_clears_upper_bits, test_load_no_side_effects])


# ============================================================================
# FEATURE 4: ADD instruction
# ============================================================================
@cocotb.test()
async def feature_04_add_instruction(dut):
    await init(dut)

    async def test_add():
        await fresh(dut, [LOAD(10), ADD(5), ADD(31)])
        await run_edges(dut, 2)
        expect(dut, acc=15)
        await step(dut, 1)
        expect(dut, acc=46)

    async def test_add_zero():
        await fresh(dut, [LOAD(20), ADD(0)])
        await run_edges(dut, 2)
        expect(dut, acc=20)

    async def test_add_max_imm():
        await fresh(dut, [LOAD(31), ADD(31)])
        await run_edges(dut, 2)
        expect(dut, acc=62)

    async def test_add_wrap():
        await fresh(dut, [LOAD(31)] + [ADD(31)] * 4 + [JMP(1)])
        await run_edges(dut, 9)                       # 7 additions done
        expect(dut, acc=248)
        await step(dut, 1)                            # 8th addition: 279 mod 256
        expect(dut, acc=23, out_data=0x00, halted=0)

    async def test_add_wrap_to_zero():
        await fresh(dut, [LOAD(0), SUB(1), ADD(1), JZ(5)])
        await run_edges(dut, 3)
        expect(dut, acc=0x00)
        await step(dut, 1)
        expect(dut, pc=5)

    async def test_add_keeps_output():
        await fresh(dut, [LOAD(9), STORE, ADD(5)])
        await run_edges(dut, 3)
        expect(dut, acc=0x0E, out_data=0x09)

    await run_subs(dut, [test_add, test_add_zero, test_add_max_imm, test_add_wrap,
                         test_add_wrap_to_zero, test_add_keeps_output])


# ============================================================================
# FEATURE 5: SUB instruction
# ============================================================================
@cocotb.test()
async def feature_05_sub_instruction(dut):
    await init(dut)

    async def test_sub():
        await fresh(dut, [LOAD(20), SUB(5), SUB(0)])
        await run_edges(dut, 2)
        expect(dut, acc=15)
        await step(dut, 1)
        expect(dut, acc=15)

    async def test_sub_wrap():
        await fresh(dut, [LOAD(0), SUB(1), LOAD(3), SUB(31)])
        await run_edges(dut, 2)
        expect(dut, acc=0xFF)
        await step(dut, 2)
        expect(dut, acc=0xE4)

    async def test_sub_to_zero():
        await fresh(dut, [LOAD(7), SUB(7)])
        await run_edges(dut, 2)
        expect(dut, acc=0x00)

    async def test_sub_max_imm():
        await fresh(dut, [LOAD(31), SUB(31), SUB(31)])
        await run_edges(dut, 2)
        expect(dut, acc=0x00)
        await step(dut, 1)
        expect(dut, acc=0xE1)

    await run_subs(dut, [test_sub, test_sub_wrap, test_sub_to_zero, test_sub_max_imm])


# ============================================================================
# FEATURE 6: STORE instruction and output
# ============================================================================
@cocotb.test()
async def feature_06_store_and_output(dut):
    await init(dut)

    async def test_store():
        await fresh(dut, [LOAD(9), STORE])
        await run_edges(dut, 1)
        expect(dut, out_data=0x00)
        await step(dut, 1)
        expect(dut, out_data=0x09, acc=0x09)

    async def test_store_output_hold():
        await fresh(dut, [LOAD(9), STORE, ADD(1), SUB(3), LOAD(31)])
        await run_edges(dut, 2)
        expect(dut, out_data=0x09)
        for acc in (0x0A, 0x07, 0x1F):
            await step(dut, 1)
            expect(dut, out_data=0x09, acc=acc)

    async def test_store_repeat_same_value():
        await fresh(dut, [LOAD(6), STORE, STORE])
        await run_edges(dut, 2)
        expect(dut, out_data=0x06)
        await step(dut, 1)
        expect(dut, out_data=0x06)

    async def test_store_zero():
        await fresh(dut, [LOAD(5), STORE, LOAD(0), STORE])
        await run_edges(dut, 2)
        expect(dut, out_data=0x05)
        await step(dut, 2)
        expect(dut, out_data=0x00)

    async def test_output_changes_only_at_store():
        await fresh(dut, COUNTDOWN)
        drive(dut, run=1)
        outs = []
        for _ in range(14):
            await step(dut, 1)
            outs.append(state(dut)["out_data"])
        changes = [i + 1 for i in range(14) if outs[i] != (outs[i - 1] if i else 0)]
        assert changes == [2, 6, 10], f"out_data changed at edges {changes}, outs {outs}"

    async def test_store_hold_in_pause():
        await fresh(dut, [LOAD(9), STORE])
        await run_edges(dut, 2)
        drive(dut, run=0)
        for _ in range(10):
            await step(dut, 1)
            expect(dut, out_data=0x09)

    await run_subs(dut, [test_store, test_store_output_hold, test_store_repeat_same_value,
                         test_store_zero, test_output_changes_only_at_store,
                         test_store_hold_in_pause])


# ============================================================================
# FEATURE 7: XOR instruction (replaces OUT)
# ============================================================================
@cocotb.test()
async def feature_07_xor_instruction(dut):
    await init(dut)

    async def test_xor():
        await fresh(dut, [LOAD(15), XOR(5)])
        await run_edges(dut, 2)
        expect(dut, acc=0x0A)

    async def test_xor_zero_imm():
        await fresh(dut, [LOAD(10), XOR(0)])
        await run_edges(dut, 2)
        expect(dut, acc=0x0A)

    async def test_xor_all_ones_imm():
        await fresh(dut, [LOAD(10), XOR(31)])
        await run_edges(dut, 2)
        expect(dut, acc=0x15)

    async def test_xor_reversible():
        await fresh(dut, [LOAD(10), XOR(31), XOR(31)])
        await run_edges(dut, 2)
        expect(dut, acc=0x15)
        await step(dut, 1)
        expect(dut, acc=0x0A)

    async def test_xor_upper_bits():
        await fresh(dut, [LOAD(0), SUB(1), XOR(31)])
        await run_edges(dut, 3)
        expect(dut, acc=0xE0)

    async def test_xor_equality_jz():
        await fresh(dut, [LOAD(9), XOR(9), JZ(5)])    # equal: jump taken
        await run_edges(dut, 2)
        expect(dut, acc=0x00)
        await step(dut, 1)
        expect(dut, pc=5)
        await fresh(dut, [LOAD(9), XOR(8), JZ(5)])    # different: not taken
        await run_edges(dut, 2)
        expect(dut, acc=0x01)
        await step(dut, 1)
        expect(dut, pc=3)

    async def test_xor_then_store():
        await fresh(dut, [LOAD(12), XOR(10), STORE])
        await run_edges(dut, 3)
        expect(dut, out_data=0x06)

    async def test_opcode_110_not_out():
        await fresh(dut, [LOAD(9), 0xC0])
        await run_edges(dut, 2)
        expect(dut, acc=0x09, out_data=0x00)

    await run_subs(dut, [test_xor, test_xor_zero_imm, test_xor_all_ones_imm, test_xor_reversible,
                         test_xor_upper_bits, test_xor_equality_jz, test_xor_then_store,
                         test_opcode_110_not_out])


# ============================================================================
# FEATURE 8: JMP instruction
# ============================================================================
@cocotb.test()
async def feature_08_jmp_instruction(dut):
    await init(dut)

    async def test_jmp_all_targets():
        for t in range(8):
            await fresh(dut, [JMP(t)] * 8)
            await run_edges(dut, 1)
            expect(dut, pc=t)

    async def test_jmp_self():
        await fresh(dut, [JMP(0)])
        drive(dut, run=1)
        for _ in range(10):
            await step(dut, 1)
            expect(dut, pc=0, acc=0)

    async def test_jmp_forward():
        await fresh(dut, [JMP(3), LOAD(1), LOAD(2), LOAD(7)])
        drive(dut, run=1)
        seen = []
        for _ in range(2):
            await step(dut, 1)
            seen.append(state(dut)["acc"])
        expect(dut, acc=0x07)
        assert 1 not in seen and 2 not in seen, f"skipped words executed, acc history {seen}"

    async def test_jmp_backward():
        await fresh(dut, [LOAD(1), ADD(1), JMP(1)])
        drive(dut, run=1)
        accs, pcs = [], []
        for _ in range(7):
            await step(dut, 1)
            accs.append(state(dut)["acc"])
            pcs.append(state(dut)["pc"])
        assert accs == [1, 2, 2, 3, 3, 4, 4], f"acc {accs}"
        assert pcs == [1, 2, 1, 2, 1, 2, 1], f"pc {pcs}"

    async def test_jmp_to_last_word():
        await fresh(dut, [JMP(7)] + [LOAD(i) for i in range(1, 8)])
        await run_edges(dut, 1)
        expect(dut, pc=7)
        await step(dut, 1)
        expect(dut, acc=0x07, pc=0)

    await run_subs(dut, [test_jmp_all_targets, test_jmp_self, test_jmp_forward,
                         test_jmp_backward, test_jmp_to_last_word])


# ============================================================================
# FEATURE 9: JZ instruction
# ============================================================================
@cocotb.test()
async def feature_09_jz_instruction(dut):
    await init(dut)

    async def test_jz_taken():
        for t in range(8):
            await fresh(dut, [JZ(t)])                 # acc = 0 after reset
            await run_edges(dut, 1)
            expect(dut, pc=t)

    async def test_jz_not_taken():
        await fresh(dut, [LOAD(1), JZ(5)])            # acc = 0x01
        await run_edges(dut, 2)
        expect(dut, pc=2)
        await fresh(dut, [LOAD(0), SUB(1), JZ(5)])    # acc = 0xFF
        await run_edges(dut, 3)
        expect(dut, pc=3)
        await fresh(dut, [LOAD(0)] + [SUB(31)] * 4 + [SUB(4), JZ(1)])   # acc = 0x80
        await run_edges(dut, 7)
        expect(dut, acc=0x80, pc=7)

    async def test_jz_sees_previous_result():
        await fresh(dut, [LOAD(1), SUB(1), JZ(5)])
        await run_edges(dut, 3)
        expect(dut, pc=5)
        await fresh(dut, [LOAD(2), SUB(1), JZ(5)])
        await run_edges(dut, 3)
        expect(dut, pc=3)

    async def test_jz_after_load_zero():
        await fresh(dut, [LOAD(7), LOAD(0), JZ(4)])
        await run_edges(dut, 3)
        expect(dut, pc=4)

    async def test_jz_after_wrap_to_zero():
        await fresh(dut, [LOAD(0), SUB(1), ADD(1), JZ(5)])
        await run_edges(dut, 3)
        expect(dut, acc=0x00)
        await step(dut, 1)
        expect(dut, pc=5)

    async def test_jz_keeps_acc():
        await fresh(dut, [LOAD(0), JZ(3)])            # taken
        await run_edges(dut, 1)
        before = state(dut)["acc"]
        await step(dut, 1)
        expect(dut, acc=before, pc=3)
        await fresh(dut, [LOAD(4), JZ(0)])            # not taken
        await run_edges(dut, 1)
        before = state(dut)["acc"]
        await step(dut, 1)
        expect(dut, acc=before, pc=2)

    await run_subs(dut, [test_jz_taken, test_jz_not_taken, test_jz_sees_previous_result,
                         test_jz_after_load_zero, test_jz_after_wrap_to_zero, test_jz_keeps_acc])


# ============================================================================
# FEATURE 10: HALT instruction
# ============================================================================
@cocotb.test()
async def feature_10_halt_instruction(dut):
    await init(dut)

    async def test_halt_freeze():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        expect(dut, pc=5, acc=0x00, ir=0xE0, out_data=0x01, halted=1)
        frozen = cpu_only(dut)
        await run_edges(dut, 10)
        assert cpu_only(dut) == frozen
        await pause(dut, 3)
        assert cpu_only(dut) == frozen
        await run_edges(dut, 3)
        assert cpu_only(dut) == frozen

    async def test_halt_sticky():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        frozen = cpu_only(dut)
        await pause(dut, 1)
        for w in (LOAD(1), LOAD(2), LOAD(3)):         # rewrite memory while halted
            await write_word(dut, w)
        await run_edges(dut, 8)
        for _ in range(3):                            # toggle run a few times
            await pause(dut, 1)
            await run_edges(dut, 2)
        assert cpu_only(dut) == frozen and frozen["halted"] == 1

    async def test_halt_first_word():
        await fresh(dut, [HALT] * 8)
        await run_edges(dut, 1)
        expect(dut, halted=1, pc=0, ir=0xE0, acc=0x00)

    async def test_halt_last_word():
        await fresh(dut, [LOAD(1)] + [ADD(1)] * 6 + [HALT])
        await run_edges(dut, 9)
        expect(dut, halted=1, pc=7, acc=0x07)

    async def test_halt_keeps_output():
        await fresh(dut, [LOAD(4), STORE, HALT])
        await run_edges(dut, 3)
        expect(dut, halted=1, out_data=0x04)
        drive(dut, run=1)
        for _ in range(10):
            await step(dut, 1)
            expect(dut, out_data=0x04)

    await run_subs(dut, [test_halt_freeze, test_halt_sticky, test_halt_first_word,
                         test_halt_last_word, test_halt_keeps_output])


# ============================================================================
# FEATURE 11: Run control (pause and resume)
# ============================================================================
@cocotb.test()
async def feature_11_run_control(dut):
    await init(dut)

    async def run_3_then_pause_10():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 3)
        expect(dut, pc=3, acc=0x02, ir=0x41, out_data=0x03)
        held = cpu_only(dut)
        drive(dut, run=0)
        for _ in range(10):
            await step(dut, 1)
            assert cpu_only(dut) == held, "state changed while paused"

    async def test_pause():
        await run_3_then_pause_10()

    async def test_resume():
        await run_3_then_pause_10()
        await run_edges(dut, 1)                       # JZ 5 executes, not taken
        expect(dut, pc=4, acc=0x02, ir=0xA5)

    async def test_idle_after_reset():
        await fresh(dut, COUNTDOWN)
        await pause(dut, 20)
        expect(dut, pc=0, acc=0, ir=0, out_data=0, halted=0)

    async def test_single_step():
        await fresh(dut, COUNTDOWN)
        model = Model(COUNTDOWN)
        for _ in range(14):
            await cycle(dut, model, run=1)            # run high for exactly one clock
            await cycle(dut, model, run=0)
            await cycle(dut, model, run=0)

    async def test_pause_on_jump():
        await fresh(dut, [LOAD(1), JMP(5)])
        await run_edges(dut, 1)
        drive(dut, run=0)
        for _ in range(5):
            await step(dut, 1)
            expect(dut, pc=1)
        await run_edges(dut, 1)
        expect(dut, pc=5)

    await run_subs(dut, [test_pause, test_resume, test_idle_after_reset,
                         test_single_step, test_pause_on_jump])


# ============================================================================
# FEATURE 12: Program counter
# ============================================================================
@cocotb.test()
async def feature_12_program_counter(dut):
    await init(dut)

    async def test_pc_increment():
        await fresh(dut, [LOAD(1)] + [ADD(1)] * 6)
        expect(dut, pc=0)
        drive(dut, run=1)
        for want in range(1, 8):
            await step(dut, 1)
            expect(dut, pc=want)

    async def test_pc_wrap():
        await fresh(dut, [LOAD(1)] + [ADD(1)] * 7)
        await run_edges(dut, 8)
        expect(dut, pc=0, acc=8, halted=0)
        await step(dut, 1)                            # word 0 runs again
        expect(dut, acc=1, pc=1)

    async def test_pc_jump_at_last_word():
        await fresh(dut, [LOAD(1)] * 7 + [JMP(2)])
        await run_edges(dut, 8)
        expect(dut, pc=2)

    await run_subs(dut, [test_pc_increment, test_pc_wrap, test_pc_jump_at_last_word])


# ============================================================================
# FEATURE 13: Single-cycle execution and IR
# ============================================================================
@cocotb.test()
async def feature_13_single_cycle_and_ir(dut):
    await init(dut)

    async def test_single_cycle_vs_model():
        await fresh(dut, COUNTDOWN)
        model = Model(COUNTDOWN)
        for _ in range(14):
            await cycle(dut, model, run=1)

    async def test_ir_content():
        await fresh(dut, COUNTDOWN)
        want = [0x03, 0x60, 0x41, 0xA5, 0x81, 0x60, 0x41, 0xA5, 0x81, 0x60, 0x41, 0xA5, 0xE0, 0xE0]
        drive(dut, run=1)
        got = []
        for _ in want:
            await step(dut, 1)
            got.append(state(dut)["ir"])
        assert got == want, f"ir {[hex(x) for x in got]}"

    async def test_ir_hold():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 3)
        drive(dut, run=0)
        for _ in range(10):
            await step(dut, 1)
            expect(dut, ir=0x41)
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        for _ in range(10):
            await step(dut, 1)
            expect(dut, ir=0xE0)

    await run_subs(dut, [test_single_cycle_vs_model, test_ir_content, test_ir_hold])


# ============================================================================
# FEATURE 14: Ignored operand fields
# ============================================================================
@cocotb.test()
async def feature_14_ignored_operand_fields(dut):
    await init(dut)

    async def test_ignored_jmp_bits():
        for t in range(8):
            for bits in range(4):
                await fresh(dut, [0x80 | (bits << 3) | t])
                await run_edges(dut, 1)
                expect(dut, pc=t)

    async def test_ignored_jz_bits():
        await fresh(dut, [0xA0 | (2 << 3) | 6])       # taken, acc = 0
        await run_edges(dut, 1)
        expect(dut, pc=6)
        await fresh(dut, [LOAD(1), 0xA0 | (3 << 3) | 6])   # not taken
        await run_edges(dut, 2)
        expect(dut, pc=2)

    async def test_ignored_store_operand():
        for byte in range(0x60, 0x80):
            await fresh(dut, [LOAD(7), byte])
            await run_edges(dut, 2)
            expect(dut, out_data=0x07, acc=0x07)

    async def test_ignored_halt_operand():
        for byte in range(0xE0, 0x100):
            await fresh(dut, [byte])
            await run_edges(dut, 1)
            expect(dut, halted=1, pc=0)

    await run_subs(dut, [test_ignored_jmp_bits, test_ignored_jz_bits,
                         test_ignored_store_operand, test_ignored_halt_operand])


# ============================================================================
# FEATURE 15: Cross-feature scenarios
# ============================================================================
@cocotb.test()
async def feature_15_cross_feature(dut):
    await init(dut)

    async def test_countdown_program():
        await fresh(dut, COUNTDOWN)
        drive(dut, run=1)
        outs, halted = [], []
        for _ in range(16):
            await step(dut, 1)
            outs.append(state(dut)["out_data"])
            halted.append(state(dut)["halted"])
        assert (outs[1], outs[5], outs[9]) == (3, 2, 1), f"outputs {outs}"
        assert outs[9:] == [1] * 7, "output must hold 0x01 after edge 10"
        assert halted.index(1) + 1 == 13, f"HALT at edge {halted.index(1) + 1}"
        expect(dut, pc=5)

    async def test_all_opcodes_program():
        await fresh(dut, [LOAD(5), XOR(3), STORE, ADD(2), SUB(8), JZ(7), JMP(0), HALT])
        drive(dut, run=1)
        accs = []
        for _ in range(7):
            await step(dut, 1)
            accs.append(state(dut)["acc"])
        assert accs[:5] == [5, 6, 6, 8, 0], f"acc {accs}"
        expect(dut, out_data=0x06, halted=1, pc=7, acc=0x00)

    async def test_reload_after_halt():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 13)
        expect(dut, halted=1)
        await fresh(dut, [LOAD(9), STORE, HALT])      # reset + new program
        await run_edges(dut, 3)
        expect(dut, out_data=0x09, halted=1, pc=2)

    async def test_pause_load_resume():
        await fresh(dut, COUNTDOWN)
        await run_edges(dut, 3)
        expect(dut, pc=3)
        drive(dut, run=0)
        await step(dut, 1)
        for w in (0x03, 0x60, 0x41, 0xE0):            # the 4th word replaces the JZ
            await write_word(dut, w)
        await run_edges(dut, 1)
        expect(dut, halted=1, ir=0xE0, pc=3, out_data=0x03)

    async def test_random_programs():
        rng = random.Random(1)
        dut._log.info(f"random seed 1, {RANDOM_PROGRAMS} programs x {RANDOM_EDGES} edges")
        for n in range(RANDOM_PROGRAMS):
            prog = [rng.randrange(256) for _ in range(8)]
            await fresh(dut, prog)
            model = Model(prog)
            for _ in range(RANDOM_EDGES):
                await cycle(dut, model,
                            run=int(rng.randrange(8) != 0),      # low 1 in 8
                            load=int(rng.randrange(8) == 0),     # high 1 in 8
                            data=rng.randrange(256),
                            rst_n=int(rng.randrange(64) != 0))   # low 1 in 64

    await run_subs(dut, [test_countdown_program, test_all_opcodes_program, test_reload_after_halt,
                         test_pause_load_resume, test_random_programs])
