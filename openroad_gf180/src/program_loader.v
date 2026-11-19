/* Program loader of the TCPU-8.
   Description : detects a rising edge of i_prog_load while i_run = 0 and
                 produces a one-edge load pulse. o_load_addr selects the
                 program memory word to write and increments after each
                 load (3-bit, wraps 7 -> 0).
   Inputs      : clk, rst_n, i_prog_load, i_run
   Outputs     : o_load_addr, o_load_pulse (memory write enable)
   Notes       : ir_pl_q samples i_prog_load at every edge, including
                 during reset. Reset clears o_load_addr. The top level
                 blocks the memory write during reset (spec 4.2, 7.3).
*/
module program_loader (
  input wire clk,
  input wire rst_n,
  input wire i_prog_load,
  input wire i_run,
  output reg [2:0] o_load_addr,
  output wire o_load_pulse
);

  // Previous sample of i_prog_load (for edge detection)
  reg ir_prev_prog_load;

  // Rising edge of i_prog_load, only while i_run = 0
  assign o_load_pulse = i_prog_load & ~ir_prev_prog_load & ~i_run;

  // ir_pl_q follows i_prog_load every edge, o_load_addr has a
  // synchronous reset
  always @(posedge clk) begin : loader_registers
    ir_prev_prog_load <= i_prog_load;
    if (!rst_n) begin : reset_load_addr
      o_load_addr <= 3'd0;
    end else if (o_load_pulse) begin : step_load_addr
      o_load_addr <= o_load_addr + 3'd1;
    end
  end

endmodule
