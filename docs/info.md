<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

TCPU_8 is a small 8-bit CPU with one working register, the accumulator (ACC). It finishes one instruction on every rising clock edge while `run` is high.
 
Inside there are three pieces of state you can think about:
 
- a program memory of 8 words, 8 bits each, built from flip-flops
- a 3-bit program counter (PC) that points at the next word to run
- the accumulator and an output register, both 8 bits
Each instruction is one byte. The top 3 bits are the opcode and the low 5 bits are the operand. For LOAD, ADD, SUB and XOR the operand is a number from 0 to 31 (`imm`). For JMP and JZ only the low 3 bits are used, as the address to jump to.
 
| Opcode | Instruction | What it does |
| --- | --- | --- |
| 000 | LOAD imm | ACC = imm |
| 001 | ADD imm | ACC = ACC + imm (wraps at 256) |
| 010 | SUB imm | ACC = ACC - imm (wraps at 256) |
| 011 | STORE | out_data = ACC |
| 100 | JMP addr | PC = addr |
| 101 | JZ addr | if ACC is 0 then PC = addr, else PC + 1 |
| 110 | XOR imm | ACC = ACC xor imm |
| 111 | HALT | stop; PC, ACC and the output stay as they are until reset |
 
Things worth knowing:
 
- There are no flags. JZ looks at ACC directly, so it sees the result of the instruction just before it. `SUB 1` followed by `JZ` tests the result of the SUB.
- `out_data` only changes when a STORE runs. It keeps its value until the next STORE or a reset.
- After word 7 the PC wraps back to word 0. That is not a halt.
- Opcode 110 is XOR here. The original specification had an OUT instruction that did the same thing as STORE, so we replaced it with XOR.
The design is split into small blocks: a program loader (turns pulses on `prog_load` into memory writes), the program memory, a decoding unit (splits the instruction byte), an ALU (works out the next ACC), an execution unit (decides if an instruction runs and remembers a HALT), and a program counter. Reset is synchronous and active low. The clock is used as given, with no input synchronizers.

## How to test

Pins used:
 
| Pin | Name | Direction | Meaning |
| --- | --- | --- | --- |
| `ui[7:0]` | prog_data | input | the program word to write |
| `uio[0]` | run | input | 1 = execute, 0 = pause or load |
| `uio[1]` | prog_load | input | pulse to write one word |
| `uo[7:0]` | out_data | output | the output register |
 
The `uio` pins are used as inputs only. Reset is the normal `rst_n` pin of the board.
 
To load and run a program:
 
1. Hold `rst_n` low for at least one clock with `run = 0`, then release it. Keep `run` low.
2. For each of the 8 words, in order: put the word on `ui[7:0]`, set `prog_load` high for at least one clock, then set it low for at least one clock. Each pulse writes exactly one word into the next address, starting at address 0, even if `prog_load` stays high for several clocks.
3. Set `run` high. The CPU starts at word 0 and runs one instruction per clock.
All 8 words must be loaded, even if the program is shorter. Fill the rest with HALT (0xE0). A word that was never loaded has an unknown value.
 
Example: count down from 3. Load these 8 bytes in order:
 
| Address | Instruction | Byte |
| --- | --- | --- |
| 0 | LOAD 3 | 0x03 |
| 1 | STORE | 0x60 |
| 2 | SUB 1 | 0x41 |
| 3 | JZ 5 | 0xA5 |
| 4 | JMP 1 | 0x81 |
| 5 | HALT | 0xE0 |
| 6 | HALT | 0xE0 |
| 7 | HALT | 0xE0 |
 
After `run` goes high, `uo[7:0]` shows 0x03 after the 2nd clock, 0x02 after the 6th, and 0x01 after the 10th, and then stays at 0x01. The CPU halts on the 13th clock. To run again, pull `rst_n` low. Reset clears the PC, ACC and output but keeps the program in memory, so you can run it again without loading it.
 
Other behaviour you can check:
 
- `run = 0` pauses the CPU. Setting `run` high again continues from the same instruction.
- A pulse on `prog_load` while `run = 1` is ignored.
- Writing a 9th word replaces word 0.


## External hardware

None. The inputs can be driven from switches or a microcontroller, and the output can be read on LEDs or a logic analyser.
