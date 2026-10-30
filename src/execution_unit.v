/* Execution unit of the TCPU-8.
   Description : generates the execute enable and holds the halted flag.
                 o_exec = i_run & ~o_halted gates the PC, ACC, OUT and IR
                 updates. o_halted is set when a HALT instruction commits
                 and is cleared only by reset.
   Inputs      : clk, rst_n, i_run, i_halt
   Outputs     : o_exec, o_halted
*/
module execution_unit (
  input wire clk,
  input wire rst_n,
  input wire i_run,
  input wire i_halt,
  output wire o_exec,
  output reg o_halted
);

  // Execute enable: run is high and the CPU has not halted
  assign o_exec = i_run & ~o_halted;

  // Halted flag: synchronous active-low reset, sticky once set
  always @(posedge clk) begin : halted_register
    if (!rst_n) begin : halted_reset
      o_halted <= 1'b0;
    end else if (o_exec && i_halt) begin : halted_set
      o_halted <= 1'b1;
    end
  end

endmodule
