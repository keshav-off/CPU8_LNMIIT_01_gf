# Verification and implementation status

This page records how to run the project tests and what they verify. It is separate from `info.md`, which holds the Tiny Tapeout project datasheet. The full test plan is in `test/TCPU8_Test_Plan.xlsx`.

## RTL simulation

The RTL test configuration is in `test/Makefile`. The tests are in `test/testcases/`, one folder per feature.

From the repository root:

```
cd test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
make clean
make
python -m cocotb_tools.check_results results.xml
```

`COCOTB_TEST_MODULES` in the Makefile lists the tests to run, separated by commas and without spaces or `.py`, for example `testcases.reset_feature.test_reset_values`. To run one test only:

```
make COCOTB_TEST_MODULES=testcases.reset_feature.test_reset_values
```

The test CI workflow installs Icarus Verilog and the packages in `test/requirements.txt`, runs the same suite, and checks `results.xml`, so a failed cocotb test fails CI.

## What the tests check

The tests drive the wrapper pins: `ui_in` = `prog_data`, `uio_in[0]` = `run`, `uio_in[1]` = `prog_load`, `uo_out` = `out_data`. Internal registers (`pc`, `acc`, `ir`, `halted`, `out_r`) are read hierarchically in RTL simulation only.

### Feature 1: Reset (spec 7.3, F01 to F04, F34)

| Test | What it asserts | Status |
|---|---|---|
| `test_reset_values` | After a reset from a dirty state, `pc`, `acc`, `ir`, `out_r`, `halted` and `out_data` are all 0. | |
| `test_reset_keeps_program` | After a mid-run reset, the program is re-run without reloading and the 20-edge trace is identical. | |
| `test_reset_clears_load_addr` | After reset the next loaded word goes to address 0. | |
| `test_reset_clears_halt` | A halted CPU runs again after reset (`acc` = 3, `pc` = 1). | |
| `test_reset_clears_output` | Reset clears `out_data` and `acc` after a STORE. | |
| `test_reset_during_load` | A reset in the middle of loading keeps the words already written and restarts at address 0. | |
| `test_reset_priority_over_load` | A load pulse while `rst_n = 0` is ignored. | |

Fill the Status column from your latest local and CI results (pass, fail or not run). Add the other features of the test plan in the same format as they are completed: program loading, LOAD, ADD, SUB, STORE, XOR, JMP, JZ, HALT, run control, program counter, single-cycle and IR, ignored operand fields and cross-feature scenarios.

## Gate-level simulation

After hardening, the gate-level test uses the powered netlist and the GF180 standard-cell models:

```
cd test
cp ../runs/wokwi/final/pnl/<top_module>.pnl.v gate_level_netlist.v
make clean
make GATES=yes PDK_ROOT=/path/to/pdk
python -m cocotb_tools.check_results results.xml
```

`<top_module>` is the top module name in `info.yaml`. In CI the GDS workflow copies the netlist in automatically. Gate-level netlists do not keep the RTL hierarchy, so gate-level tests may only check top-level pins (`uo_out`) and must not read `pc`, `acc`, `ir` or `halted`. Allow time for standard-cell delays before sampling outputs.

## CI workflows

- `test` runs the RTL test suite on pushes, validates `results.xml`, and uploads the results.
- `gds` runs the Tiny Tapeout GF180 GDS flow, precheck and the gate-level test.
- `docs` builds the Tiny Tapeout documentation.
- `fpga` is the template's FPGA build workflow.

The local commands above are useful for iteration. For the status of a particular commit, check the CI run and its artifacts.

## Waveforms

The simulator writes `tb.fst` in `test/` by default. Open it with GTKWave (`gtkwave tb.fst`) or Surfer (`surfer tb.fst`). Saved waveforms are kept in `test/waveforms/<feature>/`.

## Hardening snapshot

Not filled in yet. After running the hardening flow, record here the source commit, whether the flow completed, the DRC and LVS results, and the worst setup and hold slack with the clock period and constraints that were used. Rerun the flow for the current source before quoting any of these numbers as current results.
