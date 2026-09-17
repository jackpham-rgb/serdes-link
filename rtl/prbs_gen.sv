`timescale 1ns/1ps
// prbs_gen: maximal-length PRBS generator (Fibonacci LFSR).
//
// Bit-for-bit match to src/serdeslink/prbs.py's `prbs()` function: same
// seed (1), same left-shift-and-mask update, same two-tap feedback
// polynomial (x^ORDER + x^(ORDER-TAP2+1)... in practice just TAP1/TAP2 as
// 1-indexed bit positions counted from the LSB, exactly as in prbs.py).
//
// out_bit is the CURRENT register's LSB, sampled BEFORE the shift, matching
// prbs.py's `out[i] = reg & 1` happening before `reg = (reg << 1 | fb) & mask`.
module prbs_gen #(
    parameter int ORDER = 15,
    parameter int TAP1  = 15,   // 1-indexed, matches serdeslink.prbs._TAPS
    parameter int TAP2  = 14
) (
    input  logic clk,
    input  logic rst_n,
    input  logic en,
    output logic out_bit
);
    logic [ORDER-1:0] lfsr;
    logic fb;

    assign fb      = lfsr[TAP1-1] ^ lfsr[TAP2-1];
    assign out_bit = lfsr[0];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= {{(ORDER-1){1'b0}}, 1'b1};  // seed = 1, matches prbs.py default
        else if (en)
            lfsr <= {lfsr[ORDER-2:0], fb};
    end
endmodule
