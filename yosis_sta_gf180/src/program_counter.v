/* Program counter of the TCPU-8.
   Description : 3-bit PC. Next PC is pc + 1 by default, target for JMP,
                 target for JZ when the zero flag is set, and pc (hold)
                 for HALT. Updates only when i_exec = 1.
   Inputs      : clk, rst_n, i_exec, i_op, i_target, i_zero
   Outputs     : o_pc
*/
module program_counter (
  input wire clk,
  input wire rst_n,
  input wire i_exec,
  input wire [2:0] i_op,
  input wire [2:0] i_target,
  input wire i_zero,
  output reg [2:0] o_pc
);

  // Opcodes that change the PC (spec 6.2)
  localparam [2:0] OP_JMP  = 3'b100;
  localparam [2:0] OP_JZ   = 3'b101;
  localparam [2:0] OP_HALT = 3'b111;

  // Next-state value of the PC
  reg [2:0] ir_pc_nxt;

  // Combinational next-PC logic: default first, then case on the opcode
  always @* begin : next_pc
    ir_pc_nxt = o_pc + 3'd1;
    case (i_op)
      OP_JMP : begin : pc_jump
        ir_pc_nxt = i_target;
      end
      OP_JZ : begin : pc_jump_zero
        if (i_zero) begin : jz_taken
          ir_pc_nxt = i_target;
        end
      end
      OP_HALT : begin : pc_halt
        ir_pc_nxt = o_pc;
      end
      default : begin : pc_increment
        ir_pc_nxt = o_pc + 3'd1;
      end
    endcase
  end

  // PC register: synchronous active-low reset, update only when i_exec = 1
  always @(posedge clk) begin : pc_register
    if (!rst_n) begin : pc_reset
      o_pc <= 3'd0;
    end else if (i_exec) begin : pc_update
      o_pc <= ir_pc_nxt;
    end
  end

endmodule
