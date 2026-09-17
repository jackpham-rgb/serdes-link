`timescale 1ns/1ps
// dfe: N-tap sign-sign LMS decision-feedback equalizer, fixed-point.
//
// Mirrors src/serdeslink/dfe.py's run_dfe() exactly, in Q(WIDTH-1-FRAC).FRAC
// fixed point (default Q1.14: 16 bits, 1 integer bit including sign, 14
// fractional bits -> range +-2.0, resolution ~6.1e-5).
//
// Both `past` decisions and the sign-sign update multiply only by +-1, so
// this design uses conditional add/subtract instead of real multipliers -
// the same simplification sign-sign LMS is normally chosen FOR in hardware.
// That is a real, intentional design point, not an approximation.
module dfe #(
    parameter int WIDTH   = 16,
    parameter int FRAC    = 14,
    parameter int N_TAPS  = 4,
    parameter signed [WIDTH-1:0] MU = 16'sd82   // default: dfe.py's mu=5e-3 in Q1.14 (round(5e-3*16384)=82)
) (
    input  logic                   clk,
    input  logic                   rst_n,
    input  logic                   en,
    input  logic signed [WIDTH-1:0] sample_in,
    output logic                    decision_out,       // 1 = +1, 0 = -1 (matches dfe.py's {-1,+1} via this bit)
    output logic signed [WIDTH-1:0] residual_out,
    output logic signed [WIDTH-1:0] tap0_out             // tap[0] exposed for the cosim/observability (settled-value checks)
);
    localparam signed [WIDTH-1:0] ONE = (1 <<< FRAC);  // +1.0 in this Q format

    logic signed [WIDTH-1:0] taps   [N_TAPS];
    logic signed [WIDTH-1:0] past   [N_TAPS];   // past[0] = most recent decision, as +-ONE
    logic signed [WIDTH-1:0] feedback;
    logic signed [WIDTH-1:0] residual;
    logic                    decision;
    logic                    error_sign;      // 1 = error>=0, matches np.sign(error)>=0 branch

    // Combinational: feedback, residual, decision, error sign (all pure
    // function of current state + sample_in, matching one iteration of
    // dfe.py's run_dfe() loop body before the state update).
    always_comb begin
        feedback = '0;
        for (int k = 0; k < N_TAPS; k++)
            feedback += past[k][WIDTH-1] ? -taps[k] : taps[k];  // past[k] sign selects +-taps[k]

        residual = sample_in - feedback;
        decision = (residual >= 0);
        // error = d - r ; d is +-ONE. error>=0 <=> (decision? ONE : -ONE) >= residual
        error_sign = decision ? (ONE >= residual) : (-ONE >= residual);
    end

    assign decision_out = decision;
    assign residual_out = residual;
    assign tap0_out      = taps[0];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int k = 0; k < N_TAPS; k++) begin
                taps[k] <= '0;
                past[k] <= '0;
            end
        end else if (en) begin
            // Tap update: taps[k] += MU * sign(error) * sign(past[k]), with
            // past[k]==0 (only possible at reset) treated as "no update",
            // matching np.sign(0)==0 in dfe.py.
            // sign(error)*sign(past[k]): same sign -> subtract MU, opposite
            // sign -> add MU (derived from taps -= MU*sign(error)*sign(past)
            // in dfe.py; error_sign==~past_sign_bit exactly when the two
            // signs agree, since past_sign_bit=1 means past was negative).
            for (int k = 0; k < N_TAPS; k++) begin
                if (past[k] == 0)
                    taps[k] <= taps[k];
                else if (error_sign == ~past[k][WIDTH-1])
                    taps[k] <= taps[k] - MU;
                else
                    taps[k] <= taps[k] + MU;
            end

            // Shift the decision history: past[0] <- new decision, others shift down.
            for (int k = N_TAPS - 1; k > 0; k--)
                past[k] <= past[k-1];
            past[0] <= decision ? ONE : -ONE;
        end
    end
endmodule
