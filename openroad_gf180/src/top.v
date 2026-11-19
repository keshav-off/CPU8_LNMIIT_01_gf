/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_CPU8_LNMIIT (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    wire  [7:0] prog_data = ui_in;
    wire  prog_load = uio_in[1];
    wire  run = uio_in[0];
    wire  [7:0] out_data;

    assign uio_out  = 8'b0; //not used 
    assign uio_oe  = 0;
    
    TCPU_8 u_tcpu(
        .clk        (clk),
        .rst_n      (rst_n),
        .prog_data  (prog_data),
        .prog_load  (prog_load),
        .run        (run),
        .out_data   (out_data)
    );
    
  // All output pins must be assigned. If not used, assign to 0.
  assign uo_out  = out_data;  
  
    
  // List all unused inputs to prevent warnings
    wire _unused = &{ena, uio_in[7:2], 1'b0};

endmodule
