// ============================================================================
//  tb_mac_unit.v — pengujian unit MAC dengan data nyata lapisan 1
//
//  Mengalirkan 64 neuron x 196 suku = 12.544 beat SECARA MENERUS, tanpa jeda
//  satu detak pun di titik peralihan neuron, lalu membandingkan seluruh 64
//  akumulator dan 64 aktivasi terhadap acuan yang dihitung di Python.
//
//  Berkas vektor uji: tv_w.hex, tv_x.hex, tv_init.hex, exp_acc.hex, exp_act.hex
// ============================================================================
`timescale 1ns/1ps

module tb_mac_unit #(
    parameter STYLE = "ARITH",
    parameter PIPE  = 0
)(
);
    localparam N_NEURON = 64;
    localparam N_SUKU   = 196;
    localparam N_BEAT   = N_NEURON * N_SUKU;   // 12.544

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg                s_valid = 0;
    wire               s_ready;
    reg  signed [7:0]  s_x = 0, s_w = 0;
    reg                s_first = 0, s_last = 0;
    reg  signed [31:0] s_init = 0;
    reg  [4:0]         cfg_shift = 5'd8;
    reg                cfg_round = 1'b0, cfg_relu = 1'b1;
    wire               m_valid;
    reg                m_ready = 1;
    wire signed [31:0] m_acc;
    wire signed [7:0]  m_act;
    wire               m_ovf;

    mac_unit #(.MULT_STYLE(STYLE), .PIPE_MULT(PIPE)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_valid(s_valid), .s_ready(s_ready),
        .s_x(s_x), .s_w(s_w), .s_first(s_first), .s_last(s_last), .s_init(s_init),
        .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
        .m_valid(m_valid), .m_ready(m_ready),
        .m_acc(m_acc), .m_act(m_act), .m_ovf(m_ovf)
    );

    // ---- vektor uji ----
    reg [7:0]  W    [0:N_BEAT-1];
    reg [7:0]  X    [0:N_SUKU-1];
    reg [31:0] INIT [0:N_NEURON-1];
    reg [31:0] EACC [0:N_NEURON-1];
    reg [7:0]  EACT [0:N_NEURON-1];

    integer n_hasil = 0, n_salah = 0, n_stall = 0, n_beat = 0;
    reg cek_aktif = 1;
    integer k, errs;

    // ---- pencacah jeda tunggu dan perpindahan data ----
    always @(posedge clk) if (rst_n) begin
        if (s_valid & ~s_ready) n_stall = n_stall + 1;
        if (s_valid &  s_ready) n_beat  = n_beat  + 1;
    end

    // ---- pemeriksa keluaran ----
    always @(posedge clk) if (rst_n && cek_aktif && m_valid && m_ready) begin
        if (m_acc !== $signed(EACC[n_hasil])) begin
            if (n_salah < 5)
                $display("  neuron %0d: m_acc = %0d, seharusnya %0d",
                         n_hasil, m_acc, $signed(EACC[n_hasil]));
            n_salah = n_salah + 1;
        end
        if (m_act !== $signed(EACT[n_hasil])) begin
            if (n_salah < 5)
                $display("  neuron %0d: m_act = %0d, seharusnya %0d",
                         n_hasil, m_act, $signed(EACT[n_hasil]));
            n_salah = n_salah + 1;
        end
        n_hasil = n_hasil + 1;
    end

    integer nn, ii;
    initial begin
        $readmemh("tv_w.hex",    W);
        $readmemh("tv_x.hex",    X);
        $readmemh("tv_init.hex", INIT);
        $readmemh("exp_acc.hex", EACC);
        $readmemh("exp_act.hex", EACT);

        $display("=== varian %0s, PIPE_MULT = %0d ===", STYLE, PIPE);
        $display("=== Uji 1 : 64 neuron x 196 suku, menerus tanpa jeda ===");
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(negedge clk);

        for (nn = 0; nn < N_NEURON; nn = nn + 1) begin
            for (ii = 0; ii < N_SUKU; ii = ii + 1) begin
                s_valid = 1;
                s_x     = X[ii];
                s_w     = W[nn*N_SUKU + ii];
                s_first = (ii == 0);
                s_last  = (ii == N_SUKU-1);
                s_init  = INIT[nn];
                @(negedge clk);
                while (!s_ready) @(negedge clk);   // tidak pernah terjadi di sini
            end
        end
        s_valid = 0; s_first = 0; s_last = 0;
        repeat (10) @(posedge clk);

        $display("  beat terkirim      : %0d  (seharusnya %0d)", n_beat, N_BEAT);
        $display("  siklus jeda tunggu : %0d  (seharusnya 0)",   n_stall);
        $display("  hasil diterima     : %0d  (seharusnya %0d)", n_hasil, N_NEURON);
        $display("  ketidakcocokan     : %0d", n_salah);
        errs = n_salah + (n_beat != N_BEAT) + (n_stall != 0) + (n_hasil != N_NEURON);
        cek_aktif = 0;

        // ---------------------------------------------------------------
        $display("");
        $display("=== Uji 2 : first dan last bersamaan, akumulasi satu suku ===");
        n_hasil = 0;
        @(negedge clk);
        s_valid = 1; s_x = 8'sd5; s_w = 8'sd7; s_first = 1; s_last = 1; s_init = 32'sd100;
        @(negedge clk);
        s_valid = 0; s_first = 0; s_last = 0;
        repeat (5) @(posedge clk);
        $display("  m_acc = %0d  (seharusnya 135 = 100 + 5x7)  %s",
                 m_acc, (m_acc == 135) ? "OK" : "GAGAL");
        if (m_acc != 135) errs = errs + 1;

        // ---------------------------------------------------------------
        $display("");
        $display("=== Uji 3 : backpressure, m_ready ditahan rendah ===");
        m_ready = 0;
        @(negedge clk);
        s_valid = 1; s_x = 8'sd2; s_w = 8'sd3; s_first = 1; s_last = 1; s_init = 32'sd0;
        @(negedge clk);
        s_valid = 0; s_first = 0; s_last = 0;
        repeat (4) @(posedge clk);
        $display("  s_ready saat hasil menunggu = %0b  (seharusnya 0)  %s",
                 s_ready, (s_ready == 0) ? "OK" : "GAGAL");
        if (s_ready != 0) errs = errs + 1;
        m_ready = 1;
        @(posedge clk);
        $display("  m_acc setelah dilepas = %0d  (seharusnya 6)  %s",
                 m_acc, (m_acc == 6) ? "OK" : "GAGAL");
        if (m_acc != 6) errs = errs + 1;
        @(negedge clk);
        $display("  s_ready pulih = %0b  (seharusnya 1)  %s",
                 s_ready, (s_ready == 1) ? "OK" : "GAGAL");
        if (s_ready != 1) errs = errs + 1;

        // ---------------------------------------------------------------
        $display("");
        $display("=== Uji 4 : kasus terburuk 196 x (-128 x -128), tanpa meluap ===");
        @(negedge clk);
        for (ii = 0; ii < 196; ii = ii + 1) begin
            s_valid = 1; s_x = -8'sd128; s_w = -8'sd128;
            s_first = (ii == 0); s_last = (ii == 195); s_init = 0;
            @(negedge clk);
        end
        s_valid = 0; s_first = 0; s_last = 0;
        repeat (5) @(posedge clk);
        $display("  m_acc = %0d  (seharusnya 3211264)  %s",
                 m_acc, (m_acc == 3211264) ? "OK" : "GAGAL");
        if (m_acc != 3211264) errs = errs + 1;

        // ---------------------------------------------------------------
        $display("");
        $display("=== Uji 5 : saturasi keluaran ===");
        $display("  m_act = %0d, m_ovf = %0b  (seharusnya 127 dan 1)  %s",
                 m_act, m_ovf, (m_act == 127 && m_ovf == 1) ? "OK" : "GAGAL");
        if (!(m_act == 127 && m_ovf == 1)) errs = errs + 1;

        $display("");
        $display("========================================");
        if (errs == 0) $display("HASIL: LULUS — seluruh pengujian benar");
        else           $display("HASIL: GAGAL — %0d kesalahan", errs);
        $display("========================================");
        $finish;
    end
endmodule
