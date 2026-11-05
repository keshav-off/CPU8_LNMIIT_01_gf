![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# TCPU-8

TCPU-8 is a small, single-cycle 8-bit accumulator CPU designed for a 1x1 Tiny Tapeout tile using the GF180MCU process. It has a 1-byte instruction format, an 8-word program memory built from flip-flops, and a pulse-based program-loading interface. One instruction finishes on every clock edge while `run` is high.

The CPU implements `LOAD`, `ADD`, `SUB`, `STORE`, `JMP`, `JZ`, `XOR` and `HALT`. The 8-bit accumulator is copied to the output pins by `STORE`. Opcode `110` is `XOR`, which replaces the `OUT` instruction of the original specification, because `OUT` did the same thing as `STORE`.

See the [project datasheet](docs/info.md) for the architecture, instruction set, pin mapping and a programming example.

## Project status

The repository includes the RTL, the Tiny Tapeout wrapper, a cocotb testbench organised by feature, and the Tiny Tapeout workflows for testing, GF180 hardening, precheck, gate-level testing and the documentation page. Tests are being added feature by feature following the test plan in `test/TCPU8_Test_Plan.xlsx`. See [verification and implementation status](docs/verification.md) for what is tested so far and how to run it.

## Pin mapping

| Pins | Name | Direction | Meaning |
| --- | --- | --- | --- |
| `ui[7:0]` | `prog_data[7:0]` | input | program word to write |
| `uio[0]` | `run` | input | 1 = execute, 0 = pause or load |
| `uio[1]` | `prog_load` | input | pulse to write one word |
| `uo[7:0]` | `out_data[7:0]` | output | output register |

The bidirectional pins are used as inputs only (`uio_oe = 0`). `rst_n` is the standard Tiny Tapeout reset, active low.

## Run the tests

Install Icarus Verilog and the Python packages in `test/requirements.txt`, then run:

```
cd test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
make clean
make
python -m cocotb_tools.check_results results.xml
```

The tests are in `test/testcases/`, one folder per feature. The `COCOTB_TEST_MODULES` line in `test/Makefile` selects which ones run, and you can run a single test from the command line:

```
make COCOTB_TEST_MODULES=testcases.reset_feature.test_reset_values
```

`make` writes the waveform file `tb.fst`, which you can open with GTKWave (`gtkwave tb.fst`) or Surfer (`surfer tb.fst`). Saved waveforms are kept in `test/waveforms/<feature>/`.

The `gds` workflow hardens the design and repeats the test on the gate-level netlist, so a test used there may only check the chip pins. Details are in the [test README](test/README.md) and [docs/verification.md](docs/verification.md).

## Repository map

* `src/` - CPU RTL and the Tiny Tapeout wrapper:
  * `project.v` - wrapper, top module `tt_um_CPU8_LNMIIT`, maps the CPU to the Tiny Tapeout pins
  * `TCPU_8.v` - CPU top level (accumulator, output register, wiring)
  * `program_loader.v` - turns `prog_load` pulses into memory writes
  * `program_memory.v` - 8 x 8 flip-flop program memory
  * `decoding_unit.v` - splits the instruction byte into opcode, immediate and target
  * `alu.v` - LOAD, ADD, SUB and XOR
  * `execution_unit.v` - run enable and the halted flag
  * `program_counter.v` - 3-bit PC with JMP, JZ and HALT handling
  * `config.json` - Tiny Tapeout hardening settings
* `test/` - cocotb testbench:
  * `testcases/` - one folder per feature, one file per test
  * `waveforms/` - saved waveforms, one folder per feature
  * `tb.v` and `Makefile` - simulation top and flow (RTL and gate level)
  * `TCPU8_Test_Plan.xlsx` - the test plan
  * `README.md` - testbench instructions
* `docs/info.md` - datasheet content used by Tiny Tapeout.
* `docs/verification.md` - how to run the tests, what they check, CI workflows and hardening status.
* `info.yaml` - project settings: top module, source files, pin names and clock.
* `.github/workflows/` - Tiny Tapeout workflows for `gds`, `docs`, `test` and `fpga`.

## Tiny Tapeout resources

* [Tiny Tapeout](https://tinytapeout.com/)
* [Local hardening guide](https://www.tinytapeout.com/guides/local-hardening/)
* [Digital design lessons](https://tinytapeout.com/digital_design/)
