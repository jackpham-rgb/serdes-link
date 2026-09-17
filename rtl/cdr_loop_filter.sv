`timescale 1ns/1ps
// cdr_loop_filter: the DIGITAL half of the bang-bang CDR loop only.
//
// Deliberately does NOT resample a waveform (src/serdeslink/cdr.py's
// run_cdr() does that in software to simulate an analog front end; real
// hardware's analog samplers/phase-interpolator are not digital RTL). This
// module takes a phase-detector reading each UI and produces the running
// phase-interpolator correction, in pure integer fixed-point arithmetic,
// matching serdeslink.cdr.loop_filter_step_fixed() instruction-for-
// instruction so the two can be compared bit-for-bit in cocotb.
//
// Units: KP_FIXED/KI_FIXED and the internal integrator are all in
// 1/PI_SUBSTEPS-ths of one phase-interpolator step (see cdr.py's
// PI_SUBSTEPS and loop_filter_gains_fixed()). correction_steps is the
// running total in WHOLE PI steps: the number a real phase interpolator
// would actually be commanded to.
module cdr_loop_filter #(
    parameter int PI_SUBSTEPS   = 256,   // must match serdeslink.cdr.PI_SUBSTEPS
    parameter int KP_FIXED      = 819,   // default: kp=0.05, pi_steps_per_ui=64 -> round(0.05*64*256)
    parameter int KI_FIXED      = 16,    // default: ki=0.001, pi_steps_per_ui=64 -> round(0.001*64*256)
    parameter int INTEG_WIDTH   = 32,
    parameter int STEPS_WIDTH   = 32
) (
    input  logic                            clk,
    input  logic                            rst_n,
    input  logic                            en,
    input  logic signed [7:0]               pd_in,             // -1, 0, or +1
    output logic signed [STEPS_WIDTH-1:0]   correction_steps,  // running PI position, in whole steps
    output logic signed [INTEG_WIDTH-1:0]   integrator_fixed   // exposed for the cosim, not needed by a real PI
);
    logic signed [INTEG_WIDTH-1:0] integrator_q, integrator_d;
    logic signed [STEPS_WIDTH-1:0] correction_q, correction_d;
    logic signed [INTEG_WIDTH-1:0] raw;
    logic signed [STEPS_WIDTH-1:0] delta_steps;

    always_comb begin
        integrator_d = integrator_q + KI_FIXED * (-pd_in);
        raw          = KP_FIXED * (-pd_in) + integrator_d;
        if (raw >= 0)
            delta_steps = (raw + (PI_SUBSTEPS / 2)) / PI_SUBSTEPS;
        else
            delta_steps = -((-raw + (PI_SUBSTEPS / 2)) / PI_SUBSTEPS);
        correction_d = correction_q + delta_steps;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            integrator_q <= '0;
            correction_q <= '0;
        end else if (en) begin
            integrator_q <= integrator_d;
            correction_q <= correction_d;
        end
    end

    assign correction_steps = correction_q;
    assign integrator_fixed = integrator_q;
endmodule
