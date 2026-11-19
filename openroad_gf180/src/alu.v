/* 8-bit ALU of the TCPU-8.
   Description : computes the next ACC value from the opcode.
                 LOAD passes the immediate, ADD and SUB work modulo 256
                 with no flags, XOR toggles the ACC bits selected by the
                 immediate, every other opcode leaves ACC unchanged.
   Notes       : XOR (opcode 110) replaces the spec's OUT opcode, which
                 duplicated STORE. This is a documented deviation.
   Inputs      : i_op, i_imm (already zero-extended to 8 bits), i_acc
   Outputs     : o_alu_out (next ACC value)
*/
module alu (
  input wire [2:0] i_op,
  input wire [7:0] i_imm,
  input wire [7:0] i_acc,
  output reg [7:0] o_alu_out
);

  // Opcodes used by the ALU (spec 6.2)
  localparam [2:0] OP_LOAD = 3'b000;
  localparam [2:0] OP_ADD  = 3'b001;
  localparam [2:0] OP_SUB  = 3'b010;
  localparam [2:0] OP_XOR  = 3'b110;

  // Combinational ALU: default is hold, so no latch is inferred
  always @* begin : alu_select
    o_alu_out = i_acc;
    case (i_op)
      OP_LOAD : begin : alu_load
        o_alu_out = i_imm;
      end
      OP_ADD : begin : alu_add
        o_alu_out = i_acc + i_imm;
      end
      OP_SUB : begin : alu_sub
        o_alu_out = i_acc - i_imm;
      end
      OP_XOR : begin : alu_xor
        o_alu_out = i_acc ^ i_imm;
      end
      default : begin : alu_hold
        o_alu_out = i_acc;
      end
    endcase
  end

endmodule
