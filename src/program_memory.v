/* Program memory of the TCPU-8.
   Description : 8 x 8 flip-flop array with a combinational read port.
                 Written only by the loader. No reset: the contents are
                 undefined until written and persist across rst_n.
   Inputs      : clk, i_load_addr, i_pc, i_prog_data, i_load_pulse
   Outputs     : o_instr (= memory word at i_pc)
*/
module program_memory (
  input wire clk,
  input wire [2:0] i_load_addr,
  input wire [2:0] i_pc,
  input wire [7:0] i_prog_data,
  input wire i_load_pulse,
  output wire [7:0] o_instr
);

  // 8 words of 8 bits
  reg [7:0] ir_mem [0:7];

  // Combinational read at the current PC
  assign o_instr = ir_mem[i_pc];

  // Synchronous write, only when the load pulse is high
  always @(posedge clk) begin : memory_write
    if (i_load_pulse) begin : write_word
      ir_mem[i_load_addr] <= i_prog_data;
    end
  end

endmodule
