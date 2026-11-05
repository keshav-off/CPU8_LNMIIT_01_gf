# TCPU-8 testbench

The cocotb testbench drives the TCPU-8 Tiny Tapeout wrapper for RTL and gate-level simulation. For general cocotb guidance, see the [Tiny Tapeout testing guide](https://tinytapeout.com/hdl/testing/).

For the design description, see [docs/info.md](../docs/info.md). The test plan is in `TCPU8_Test_Plan.xlsx`.

## Prerequisites

Install Icarus Verilog (12.0 is used in CI), GTKWave and Python 3.9 or newer. Then install the Python packages from `requirements.txt`:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Folder layout

```
test/
  Makefile          cocotb + Icarus flow (RTL and gate level)
  tb.v              Verilog top used by cocotb, dumps the waveform
  testcases/        one folder per feature, one .py file per test
  waveforms/        saved .fst files, one folder per feature
```

## Pin mapping

| Wrapper pin    | Meaning                            |
|----------------|------------------------------------|
| `ui_in[7:0]`   | `prog_data`, instruction byte      |
| `uio_in[0]`    | `run`                              |
| `uio_in[1]`    | `prog_load`, rising-edge strobe    |
| `uo_out[7:0]`  | `out_data`, output register        |

## RTL simulation

Run from this directory:

```
make clean
make
python -m cocotb_tools.check_results results.xml
```

The Makefile selects the tests listed in `COCOTB_TEST_MODULES`, separated by commas and without spaces or `.py`. They are imported from `testcases/`, for example `testcases.reset_feature.test_reset_values`. To run one test only:

```
make COCOTB_TEST_MODULES=testcases.reset_feature.test_reset_values
```

## Gate-level simulation

First harden the design. The Tiny Tapeout flow writes the powered netlist to `runs/wokwi/final/pnl/<top_module>.pnl.v`. The top module name is in `info.yaml`. From this directory, copy the netlist and run the test:

```
cp ../runs/wokwi/final/pnl/tt_um_CPU8_LNMIIT.pnl.v gate_level_netlist.v
make clean
make GATES=yes PDK_ROOT=/path/to/pdk
python -m cocotb_tools.check_results results.xml
```

In the GDS workflow the netlist is copied in automatically. Gate-level netlists do not keep the RTL hierarchy, so gate-level tests must check the top-level pins only (`uo_out`), and must not read `pc`, `acc`, `ir` or `halted`. Allow time for standard-cell delays before sampling outputs.

## View the waveform

The simulator writes `tb.fst` by default. Open it with GTKWave:

```
gtkwave tb.fst
```

Or use Surfer:

```
surfer tb.fst
```

## Notes

- `out_data` changes only when a STORE executes, so sample `uo_out` after the STORE edge.
- Hold `run`, `prog_load` and `rst_n` for several clocks. A word is written on the first edge where `prog_load` is high while `run = 0`.
- On old Icarus versions (10.x), single-bit writes like `dut.uio_in[1].value = 1` fail. Write the whole vector: `dut.uio_in.value = 0b10`.
- Opcode 110 is XOR in this design. In the specification it was OUT.
