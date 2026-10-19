// ============================================================================
//  mac_unit.v
//  Unit Multiply-Accumulate 8 x 8 bertanda untuk akselerator JST pada
//  Cyclone IV EP4CE6E22C8N.
//
//  Ciri rancangan:
//    - Akumulator 32 bit (bukan 2N+1), cukup untuk 196 suku pada kasus terburuk
//    - Penanda first/last DIALIRKAN bersama data menyusuri pipa, sehingga
//      akumulator ditimpa nilai awal saat first, bukan dikosongkan terpisah.
//      Akibatnya tidak ada detak kosong di titik peralihan neuron.
//    - Bias dimuat lewat s_init saat first — tanpa penjumlah dan siklus tambahan
//    - Handshake VALID/READY penuh di kedua sisi; m_valid teregister sehingga
//      tidak ada lintasan kombinasional melingkar
//    - Epilog: geser kanan (dengan pembulatan opsional), ReLU, saturasi 8 bit
//    - Panjang akumulasi tidak dipatok, ditentukan first/last dari pengendali,
//      sehingga berlaku untuk lapisan terhubung penuh maupun kernel konvolusi
//
//  Latensi : 2 siklus bila PIPE_MULT = 0, 3 siklus bila PIPE_MULT = 1
//  Throughput : 1 beat per siklus, tanpa jeda antar neuron
// ============================================================================
`default_nettype none

module mac_unit #(
    parameter DW         = 8,
    parameter ACCW       = 32,
    parameter MULT_STYLE = "ARITH",   // "ARITH" | "STRUCT" | "HARD"
    parameter PIPE_MULT  = 0,         // 0 = latensi 2, 1 = latensi 3
    parameter HAS_EPILOG = 1          // 0 = hanya m_acc, epilog di luar
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // ---- sisi masukan ----
    input  wire                     s_valid,
    output wire                     s_ready,
    input  wire signed [DW-1:0]     s_x,
    input  wire signed [DW-1:0]     s_w,
    input  wire                     s_first,
    input  wire                     s_last,
    input  wire signed [ACCW-1:0]   s_init,

    // ---- konfigurasi, stabil selama satu lapisan ----
    input  wire [4:0]               cfg_shift,
    input  wire                     cfg_round,
    input  wire                     cfg_relu,

    // ---- sisi keluaran ----
    output reg                      m_valid,
    input  wire                     m_ready,
    output reg  signed [ACCW-1:0]   m_acc,
    output wire signed [DW-1:0]     m_act,
    output wire                     m_ovf
);

    localparam PW = 2*DW;             // lebar hasil kali

    // Batas saturasi 8 bit bertanda, dinyatakan pada lebar akumulator.
    // Ditulis sebagai pola bit, bukan sebagai bilangan desimal bertanda,
    // supaya tidak ada konstanta yang melampaui lebarnya sendiri
    // (-8'sd128 memicu peringatan "constant value overflow" di Quartus,
    //  karena 8'sd128 sendiri sudah di luar jangkauan 8 bit bertanda).
    localparam signed [ACCW-1:0] SAT_MAX = {{(ACCW-DW+1){1'b0}}, {(DW-1){1'b1}}};
    localparam signed [ACCW-1:0] SAT_MIN = ~SAT_MAX;

    // ------------------------------------------------------------------
    //  Kendali handshake
    // ------------------------------------------------------------------
    wire stall = m_valid & ~m_ready;
    assign s_ready = ~stall;
    wire beat = s_valid & s_ready;

    // ------------------------------------------------------------------
    //  Tahap 1 — pengali kombinasional
    // ------------------------------------------------------------------
    wire signed [PW-1:0] prod;

    generate
        if (MULT_STYLE == "HARD") begin : g_hard
            mult_hard8 u_mul (.a(s_x), .b(s_w), .p(prod));
        end else if (MULT_STYLE == "STRUCT") begin : g_struct
            mult_bw8_struct u_mul (.a(s_x), .b(s_w), .p(prod));
        end else begin : g_arith
            mult_bw8_arith u_mul (.a(s_x), .b(s_w), .p(prod));
        end
    endgenerate

    // ------------------------------------------------------------------
    //  Register pipa — data DAN penanda disimpan bersamaan
    // ------------------------------------------------------------------
    reg signed [PW-1:0]   p_q;
    reg signed [ACCW-1:0] init1;
    reg                   f1, l1, v1;

    always @(posedge clk) begin
        if (!rst_n) begin
            v1 <= 1'b0;  f1 <= 1'b0;  l1 <= 1'b0;
            p_q <= {PW{1'b0}};  init1 <= {ACCW{1'b0}};
        end else if (!stall) begin
            p_q   <= prod;
            init1 <= s_init;
            f1    <= s_first;
            l1    <= s_last;
            v1    <= beat;
        end
    end

    // ---- tahap pipa opsional, dipakai bila pengali gagal timing ----
    wire signed [PW-1:0]   p_use;
    wire signed [ACCW-1:0] init_use;
    wire                   f_use, l_use, v_use;

    generate
        if (PIPE_MULT == 1) begin : g_pipe
            reg signed [PW-1:0]   p_q2;
            reg signed [ACCW-1:0] init2;
            reg                   f2, l2, v2;
            always @(posedge clk) begin
                if (!rst_n) begin
                    v2 <= 1'b0;  f2 <= 1'b0;  l2 <= 1'b0;
                    p_q2 <= {PW{1'b0}};  init2 <= {ACCW{1'b0}};
                end else if (!stall) begin
                    p_q2 <= p_q;  init2 <= init1;
                    f2   <= f1;   l2    <= l1;   v2 <= v1;
                end
            end
            assign p_use = p_q2;  assign init_use = init2;
            assign f_use = f2;    assign l_use = l2;  assign v_use = v2;
        end else begin : g_nopipe
            assign p_use = p_q;   assign init_use = init1;
            assign f_use = f1;    assign l_use = l1;  assign v_use = v1;
        end
    endgenerate

    // ------------------------------------------------------------------
    //  Tahap 2 — pemilihan dasar akumulasi dan penjumlahan
    // ------------------------------------------------------------------
    reg signed [ACCW-1:0] acc;

    // MUX acc_base : nilai awal saat first, atau akumulator berjalan
    wire signed [ACCW-1:0] acc_base = f_use ? init_use : acc;
    wire signed [ACCW-1:0] prod_ext = {{(ACCW-PW){p_use[PW-1]}}, p_use};
    wire signed [ACCW-1:0] acc_next = acc_base + prod_ext;

    always @(posedge clk) begin
        if (!rst_n) begin
            acc     <= {ACCW{1'b0}};
            m_acc   <= {ACCW{1'b0}};
            m_valid <= 1'b0;
        end else begin
            if (m_valid & m_ready)
                m_valid <= 1'b0;                 // hasil sudah diambil

            if (!stall & v_use) begin
                acc <= acc_next;
                if (l_use) begin
                    m_acc   <= acc_next;         // nilai BARU, bukan acc teregister
                    m_valid <= 1'b1;
                end
            end
        end
    end

    // ------------------------------------------------------------------
    //  Tahap 3 — epilog: geser, bulatkan, ReLU, saturasi
    // ------------------------------------------------------------------
    generate
        if (HAS_EPILOG == 1) begin : g_epilog
            wire signed [ACCW-1:0] rnd_add =
                (cfg_round && (cfg_shift != 5'd0))
                    ? ({{(ACCW-1){1'b0}}, 1'b1} <<< (cfg_shift - 5'd1))
                    : {ACCW{1'b0}};

            wire signed [ACCW-1:0] shifted = (m_acc + rnd_add) >>> cfg_shift;
            wire signed [ACCW-1:0] relued  =
                (cfg_relu && shifted[ACCW-1]) ? {ACCW{1'b0}} : shifted;

            wire sat_hi = (relued > SAT_MAX);
            wire sat_lo = (relued < SAT_MIN);

            assign m_act = sat_hi ? SAT_MAX[DW-1:0] :
                           sat_lo ? SAT_MIN[DW-1:0] : relued[DW-1:0];
            assign m_ovf = sat_hi | sat_lo;
        end else begin : g_no_epilog
            assign m_act = {DW{1'b0}};
            assign m_ovf = 1'b0;
        end
    endgenerate

endmodule

`default_nettype wire
