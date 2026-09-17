`timescale 1ns/1ps
// serdes_digital_top: flat-IO wrapper bundling the three Stage C blocks
// behind one clock, for a future Tiny Tapeout (P2) submission.
//
// This is deliberately NOT a full SerDes PHY: it's the digital control
// pieces (PRBS reference pattern, the DFE, and the CDR digital loop
// filter) with clean, few-pin IO, which is what a shuttle-scale tapeout
// can actually fit and bring up. See the honesty line in the repo README.
module serdes_digital_top #(
    parameter int PRBS_ORDER  = 15,
    parameter int PRBS_TAP1   = 15,
    parameter int PRBS_TAP2   = 14,
    parameter int DFE_WIDTH   = 16,
    parameter int DFE_FRAC    = 14,
    parameter int DFE_N_TAPS  = 4,
    parameter int PI_SUBSTEPS = 256,
    parameter int KP_FIXED    = 819,
    parameter int KI_FIXED    = 16
) (
    input  logic                          clk,
    input  logic                          rst_n,
    input  logic                          en,

    // PRBS reference generator (e.g. for a loopback self-test)
    output logic                          prbs_bit,

    // DFE: one fixed-point sample per UI in, decision + residual out
    input  logic signed [DFE_WIDTH-1:0]   dfe_sample_in,
    output logic                          dfe_decision_out,
    output logic signed [DFE_WIDTH-1:0]   dfe_residual_out,

    // CDR digital loop filter: one phase-detector reading per UI in,
    // running phase-interpolator position out
    input  logic signed [7:0]             cdr_pd_in,
    output logic signed [31:0]            cdr_correction_steps
);
    prbs_gen #(
        .ORDER (PRBS_ORDER),
        .TAP1  (PRBS_TAP1),
        .TAP2  (PRBS_TAP2)
    ) u_prbs (
        .clk     (clk),
        .rst_n   (rst_n),
        .en      (en),
        .out_bit (prbs_bit)
    );

    dfe #(
        .WIDTH  (DFE_WIDTH),
        .FRAC   (DFE_FRAC),
        .N_TAPS (DFE_N_TAPS)
    ) u_dfe (
        .clk          (clk),
        .rst_n        (rst_n),
        .en           (en),
        .sample_in    (dfe_sample_in),
        .decision_out (dfe_decision_out),
        .residual_out (dfe_residual_out),
        .tap0_out     ()
    );

    cdr_loop_filter #(
        .PI_SUBSTEPS (PI_SUBSTEPS),
        .KP_FIXED    (KP_FIXED),
        .KI_FIXED    (KI_FIXED)
    ) u_cdr (
        .clk               (clk),
        .rst_n             (rst_n),
        .en                (en),
        .pd_in             (cdr_pd_in),
        .correction_steps  (cdr_correction_steps),
        .integrator_fixed  ()
    );
endmodule
