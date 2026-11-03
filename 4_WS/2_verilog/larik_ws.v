// ============================================================================
//  larik_ws.v
//  Larik sistolik weight-stationary 4 baris x 2 kolom (8 PE).
//  Rincian rancangan: 4_WS/SPESIFIKASI_WS.md, bagian 4.
//
//            kata masukan (4 suku)          bias / FIFO jumlah parsial
//                   │                               │
//     suku 0 ──────►PE(0,0) ────────────────────► PE(0,1)
//                   │ psum                          │ psum
//     suku 1 ─[2]──►PE(1,0) ────────────────────► PE(1,1)
//                   │                               │
//     suku 2 ─[4]──►PE(2,0) ────────────────────► PE(2,1)
//                   │                               │
//     suku 3 ─[6]──►PE(3,0) ────────────────────► PE(3,1)
//                   ▼                               ▼
//            FIFO psum 8 tahap               FIFO psum 8 tahap
//
//  PE(r, c) = register bobot berpenyangga ganda + mac_unit.v TANPA diubah.
//  mac_unit dipakai dengan s_first = s_last = 1 di setiap beat, sehingga
//  keluarannya m_acc = s_init + x*w: menjumlahkan hasil kalinya ke jumlah
//  parsial dari PE di atasnya (Kung 1982, Design B1: "broadcast inputs,
//  move results, weights stay", sel y_out = y_in + w*x_in).
//
//  Suku ke-r disiarkan ke kedua kolom pada baris r, tertunda 2r siklus
//  karena tiap MAC di atasnya berlatensi 2 siklus.
//
//  FIFO JUMLAH PARSIAL
//  Hasil citra b keluar dari dasar kolom 8 siklus setelah beat baris 0,
//  dan dibutuhkan lagi di puncak kolom tepat 16 siklus setelah beat itu
//  (ubin berikutnya, citra yang sama). Register geser 8 tahap menutup
//  selisihnya: 8 (kolom) + 8 (FIFO) = 16 = B. Urutan citranya selalu tetap
//  (0..15 berulang), jadi FIFO tanpa alamat sudah cukup dan jumlah parsial
//  tidak pernah menyentuh M9K.
//
//  Bank bobot k melayani PE(r, c) dengan k = 2r + c.
// ============================================================================
`default_nettype none

module larik_ws #(
    parameter DW         = 8,
    parameter ACCW       = 32,
    parameter MULT_STYLE = "HARD"
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // ---- sejajar beat PE baris 0 ----
    input  wire                     in_valid,
    input  wire [4*DW-1:0]          in_kata,      // suku r di bit [8r +: 8]
    input  wire                     pakai_bias,
    input  wire signed [ACCW-1:0]   bias0,
    input  wire signed [ACCW-1:0]   bias1,

    // ---- bobot ----
    input  wire [8*DW-1:0]          bobot_bank,   // keluaran bank 7..0
    input  wire                     isi_bayangan,
    input  wire [3:0]               muat_aktif,   // per baris

    // ---- dasar kolom ----
    output wire                     out_valid,
    output wire signed [ACCW-1:0]   out0,
    output wire signed [ACCW-1:0]   out1
);

    integer k;

    // ------------------------------------------------------------------
    //  Register bobot berpenyangga ganda
    // ------------------------------------------------------------------
    reg signed [DW-1:0] bayangan [0:7];
    reg signed [DW-1:0] aktif    [0:7];

    always @(posedge clk) begin
        if (isi_bayangan)
            for (k = 0; k < 8; k = k + 1)
                bayangan[k] <= bobot_bank[k*DW +: DW];
        for (k = 0; k < 8; k = k + 1)
            if (muat_aktif[k/2])
                aktif[k] <= bayangan[k];
    end

    // ------------------------------------------------------------------
    //  Penunda baris: suku r ditunda 2r siklus
    // ------------------------------------------------------------------
    reg [DW-1:0] tunda1 [0:1];
    reg [DW-1:0] tunda2 [0:3];
    reg [DW-1:0] tunda3 [0:5];

    always @(posedge clk) begin
        tunda1[0] <= in_kata[1*DW +: DW];
        tunda2[0] <= in_kata[2*DW +: DW];
        tunda3[0] <= in_kata[3*DW +: DW];
        tunda1[1] <= tunda1[0];
        for (k = 1; k < 4; k = k + 1) tunda2[k] <= tunda2[k-1];
        for (k = 1; k < 6; k = k + 1) tunda3[k] <= tunda3[k-1];
    end

    wire signed [DW-1:0] x [0:3];
    assign x[0] = in_kata[0 +: DW];
    assign x[1] = tunda1[1];
    assign x[2] = tunda2[3];
    assign x[3] = tunda3[5];

    // ------------------------------------------------------------------
    //  FIFO jumlah parsial, 8 tahap per kolom
    // ------------------------------------------------------------------
    wire signed [ACCW-1:0] m_acc_pe   [0:7];
    wire        [7:0]      m_valid_pe;

    reg signed [ACCW-1:0] fifo0 [0:7];
    reg signed [ACCW-1:0] fifo1 [0:7];

    always @(posedge clk) begin
        fifo0[0] <= m_acc_pe[6];
        fifo1[0] <= m_acc_pe[7];
        for (k = 1; k < 8; k = k + 1) begin
            fifo0[k] <= fifo0[k-1];
            fifo1[k] <= fifo1[k-1];
        end
    end

    // puncak kolom: bias pada ubin pertama, selain itu jumlah parsial dari FIFO
    wire signed [ACCW-1:0] puncak0 = pakai_bias ? bias0 : fifo0[7];
    wire signed [ACCW-1:0] puncak1 = pakai_bias ? bias1 : fifo1[7];

    // ------------------------------------------------------------------
    //  8 PE
    // ------------------------------------------------------------------
    genvar r, c;
    generate
        for (r = 0; r < 4; r = r + 1) begin : g_baris
            for (c = 0; c < 2; c = c + 1) begin : g_kolom
                wire                   s_valid_pe;
                wire signed [ACCW-1:0] s_init_pe;

                if (r == 0) begin : g_puncak
                    assign s_valid_pe = in_valid;
                    assign s_init_pe  = (c == 0) ? puncak0 : puncak1;
                end else begin : g_bawah
                    assign s_valid_pe = m_valid_pe[2*(r-1) + c];
                    assign s_init_pe  = m_acc_pe[2*(r-1) + c];
                end

                mac_unit #(.DW(DW), .ACCW(ACCW), .MULT_STYLE(MULT_STYLE),
                           .PIPE_MULT(0), .HAS_EPILOG(0))
                u_mac (.clk(clk), .rst_n(rst_n),
                       .s_valid(s_valid_pe), .s_ready(),
                       .s_x(x[r]), .s_w(aktif[2*r + c]),
                       .s_first(1'b1), .s_last(1'b1),
                       .s_init(s_init_pe),
                       .cfg_shift(5'd0), .cfg_round(1'b0), .cfg_relu(1'b0),
                       .m_valid(m_valid_pe[2*r + c]), .m_ready(1'b1),
                       .m_acc(m_acc_pe[2*r + c]), .m_act(), .m_ovf());
            end
        end
    endgenerate

    assign out_valid = m_valid_pe[6];
    assign out0      = m_acc_pe[6];
    assign out1      = m_acc_pe[7];

endmodule

`default_nettype wire
