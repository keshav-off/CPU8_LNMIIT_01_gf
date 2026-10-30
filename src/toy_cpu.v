/* TCPU-8 top level: 8-bit single-cycle accumulator CPU.
   Description : one instruction is fetched, decoded, executed and
                 committed at each rising edge of clk while run = 1.
                 Clocking mode: host-generated clock (Mode H,
                 SYNC_STAGES = 0), so there are no input synchronizers.
   Inputs      : clk, rst_n, prog_data, prog_load, run
   Outputs     : out_data (registered, = out_r)
   Notes       : the port names (spec 3.1) and the names pc, acc, ir,
                 halted and out_r (spec 3.3) are fixed by the spec and
                 are declared in this scope. pc and halted are driven by
                 submodules. All other internal wires start with is_ and
                 internal registers with ir_ (RTL coding guideline).
*/
module toy_cpu (
  input wire clk,
  input wire rst_n,
  input wire [7:0] prog_data,
  input wire prog_load,
  input wire run,
  output wire [7:0] out_data
);

  // Opcode used by the top level (spec 6.2). Opcode 110 is XOR in this
  // design (the spec's OUT duplicated STORE), so only STORE writes out_r.
  localparam [2:0] OP_STORE = 3'b011;

  // Architectural state (names fixed by the spec)
  wire [2:0] pc;
  /* verilator lint_off UNUSEDSIGNAL */
  // halted is read only by the testbench (hierarchically)
  wire halted;
  // ir is for simulation visibility only; it has no fanout by design
  reg [7:0] ir;
  /* verilator lint_on UNUSEDSIGNAL */
  reg [7:0] acc;
  reg [7:0] out_r;

  // Next-state value of the OUT register
  reg [7:0] ir_out_r_nxt;

  // Loader and memory connections
  wire [2:0] is_load_addr;
  wire is_load_pulse;
  wire is_mem_write_en;
  wire [7:0] is_instr;

  // Decoder outputs
  wire [2:0] is_op;
  wire [7:0] is_imm;
  wire [2:0] is_target;
  wire is_halt;

  // ALU and control signals
  wire [7:0] is_alu_out;
  wire is_zero;
  wire is_exec;

  // Zero detect on the pre-edge ACC (used only by JZ)
  assign is_zero = (acc == 8'h00);

  // Reset has priority over a load pulse, so block the memory write
  assign is_mem_write_en = is_load_pulse & rst_n;

  // Program loader
  program_loader U_program_loader (
    .clk          (clk),
    .rst_n        (rst_n),
    .i_prog_load  (prog_load),
    .i_run        (run),
    .o_load_addr  (is_load_addr),
    .o_load_pulse (is_load_pulse)
  );

  // Program memory
  program_memory U_program_memory (
    .clk          (clk),
    .i_load_addr  (is_load_addr),
    .i_pc         (pc),
    .i_prog_data  (prog_data),
    .i_load_pulse (is_mem_write_en),
    .o_instr      (is_instr)
  );

  // Decoding unit
  decoding_unit U_decoding_unit (
    .i_instr  (is_instr),
    .o_op     (is_op),
    .o_imm    (is_imm),
    .o_target (is_target),
    .o_halt   (is_halt)
  );

  // ALU
  alu U_alu (
    .i_op      (is_op),
    .i_imm     (is_imm),
    .i_acc     (acc),
    .o_alu_out (is_alu_out)
  );

  // Execution unit (execute enable and halted flag)
  execution_unit U_execution_unit (
    .clk      (clk),
    .rst_n    (rst_n),
    .i_run    (run),
    .i_halt   (is_halt),
    .o_exec   (is_exec),
    .o_halted (halted)
  );

  // Program counter
  program_counter U_program_counter (
    .clk      (clk),
    .rst_n    (rst_n),
    .i_exec   (is_exec),
    .i_op     (is_op),
    .i_target (is_target),
    .i_zero   (is_zero),
    .o_pc     (pc)
  );

  // Next OUT value: STORE copies the pre-edge ACC
  always @* begin : next_out
    ir_out_r_nxt = out_r;
    if (is_op == OP_STORE) begin : out_write
      ir_out_r_nxt = acc;
    end
  end

  // ACC, IR and OUT registers: synchronous active-low reset (priority),
  // one instruction committed per edge when is_exec = 1
  always @(posedge clk) begin : datapath_registers
    if (!rst_n) begin : reset_state
      acc   <= 8'h00;
      ir    <= 8'h00;
      out_r <= 8'h00;
    end else if (is_exec) begin : commit_instruction
      acc   <= is_alu_out;
      ir    <= is_instr;
      out_r <= ir_out_r_nxt;
    end
  end

  // Registered output, no logic between the flops and the port
  assign out_data = out_r;

endmodule
