/* Decoding unit of the TCPU-8.
   Description : splits the instruction byte into opcode, immediate and
                 jump target. The 5-bit immediate is zero-extended to
                 8 bits. Purely combinational, so it has no clock.
   Inputs      : i_instr (instruction byte from program memory)
   Outputs     : o_op, o_imm, o_target, o_halt
   Note        : instr[4:3] is ignored by JMP and JZ (target uses
                 instr[2:0] only), and STORE and HALT ignore the whole
                 operand (spec 6.3). XOR (opcode 110) uses the immediate.
*/
module decoding_unit (
  input wire [7:0] i_instr,
  output wire [2:0] o_op,
  output wire [7:0] o_imm,
  output wire [2:0] o_target,
  output wire o_halt
);

  // Opcode used for the halt decode (spec 6.2)
  localparam [2:0] OP_HALT = 3'b111;

  assign o_op     = i_instr[7:5];
  assign o_imm    = {3'b000, i_instr[4:0]};  // explicit zero-extension
  assign o_target = i_instr[2:0];
  assign o_halt   = (i_instr[7:5] == OP_HALT);

endmodule
