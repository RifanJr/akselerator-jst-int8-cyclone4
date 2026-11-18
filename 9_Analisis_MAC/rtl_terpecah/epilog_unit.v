// ============================================================================
//  epilog_unit.v
//  Epilog bersama — geser, bulatkan, ReLU, saturasi.
//
//  Logika di dalamnya DISALIN PERSIS dari blok g_epilog pada mac_unit.v,
//  supaya hasilnya bit-exact sama dengan varian HAS_EPILOG = 1. Bedanya
//  hanya letak: di sini ia berdiri sendiri dan dipakai bersama oleh seluruh
//  lajur MAC, bukan disalin ke tiap lajur.
//
//  Alasan dipisah: epilog hanya bekerja sekali tiap 196 siklus (saat satu
//  neuron selesai), sementara ongkosnya lebih besar daripada pengalinya
//  sendiri — terutama penggeser variabel 32 bit lima tingkat akibat
//  cfg_shift selebar 5 bit. Menyalinnya P kali adalah pemborosan.
//
//  Keluarannya diregister, jadi latensi 1 siklus. Bagi pengendali, hasil
//  satu neuron kini siap pada siklus berikutnya setelah m_valid lajur.
//
//  Antrean: P lajur selesai berbarengan, lalu masuk ke sini satu per satu.
//  P siklus untuk menguras, sedangkan jeda antarneuron 196 siklus — muat
//  dengan sangat longgar. Pemilih (mux) antarlajur BUKAN bagian modul ini;
//  itu milik pengendali orkestrasi memori di Fase 6.
// ============================================================================
`default_nettype none

module epilog_unit #(
    parameter DW   = 8,
    parameter ACCW = 32
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // ---- masukan: satu akumulator neuron yang sudah selesai ----
    input  wire                     in_valid,
    input  wire signed [ACCW-1:0]   in_acc,

    // ---- konfigurasi, stabil selama satu lapisan ----
    input  wire [4:0]               cfg_shift,
    input  wire                     cfg_round,
    input  wire                     cfg_relu,

    // ---- keluaran teregister ----
    output wire                     out_valid,
    output wire signed [DW-1:0]     out_act,
    output wire                     out_ovf
);

    //  Dipisah menjadi submodul per komponen (9_Analisis_MAC, Tugas 5).
    //  Fungsi identik dengan versi datar.
    wire signed [ACCW-1:0] rnd_sum;     // [E1] in_acc + setengah LSB (opsional)
    wire signed [ACCW-1:0] shifted;     // [E2] geser kanan aritmetik
    wire signed [ACCW-1:0] relued;      // [E3] ReLU
    wire signed [DW-1:0]   act_c;       // [E4] saturasi 8 bit
    wire                   ovf_c;

    epi_round #(.ACCW(ACCW)) u_round (
        .in_acc(in_acc), .cfg_shift(cfg_shift), .cfg_round(cfg_round), .rnd_sum(rnd_sum)
    );
    epi_shift #(.ACCW(ACCW)) u_shift (
        .rnd_sum(rnd_sum), .cfg_shift(cfg_shift), .shifted(shifted)
    );
    epi_relu #(.ACCW(ACCW)) u_relu (
        .shifted(shifted), .cfg_relu(cfg_relu), .relued(relued)
    );
    epi_sat #(.DW(DW), .ACCW(ACCW)) u_sat (
        .relued(relued), .act_c(act_c), .ovf_c(ovf_c)
    );
    epi_reg_out #(.DW(DW)) u_out (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .act_c(act_c), .ovf_c(ovf_c),
        .out_valid(out_valid), .out_act(out_act), .out_ovf(out_ovf)
    );

endmodule

// ============================================================================
//  Submodul komponen epilog — dipisah HANYA untuk analisis per komponen.
//  Logika disalin persis dari versi datar.
// ============================================================================

// [E1] Pembulatan opsional: tambah setengah LSB sebelum digeser
module epi_round #(
    parameter ACCW = 32
)(
    input  wire signed [ACCW-1:0] in_acc,
    input  wire [4:0]             cfg_shift,
    input  wire                   cfg_round,
    output wire signed [ACCW-1:0] rnd_sum
);
    wire signed [ACCW-1:0] rnd_add =
        (cfg_round && (cfg_shift != 5'd0))
            ? ({{(ACCW-1){1'b0}}, 1'b1} <<< (cfg_shift - 5'd1))
            : {ACCW{1'b0}};
    assign rnd_sum = in_acc + rnd_add;
endmodule

// [E2] Geser kanan aritmetik
module epi_shift #(
    parameter ACCW = 32
)(
    input  wire signed [ACCW-1:0] rnd_sum,
    input  wire [4:0]             cfg_shift,
    output wire signed [ACCW-1:0] shifted
);
    assign shifted = rnd_sum >>> cfg_shift;
endmodule

// [E3] ReLU
module epi_relu #(
    parameter ACCW = 32
)(
    input  wire signed [ACCW-1:0] shifted,
    input  wire                   cfg_relu,
    output wire signed [ACCW-1:0] relued
);
    assign relued = (cfg_relu && shifted[ACCW-1]) ? {ACCW{1'b0}} : shifted;
endmodule

// [E4] Saturasi ke 8 bit bertanda
module epi_sat #(
    parameter DW   = 8,
    parameter ACCW = 32
)(
    input  wire signed [ACCW-1:0] relued,
    output wire signed [DW-1:0]   act_c,
    output wire                   ovf_c
);
    //  Batasnya ditulis sebagai pola bit, bukan bilangan desimal bertanda,
    //  supaya tidak ada konstanta yang melampaui lebarnya sendiri.
    localparam signed [ACCW-1:0] SAT_MAX = {{(ACCW-DW+1){1'b0}}, {(DW-1){1'b1}}};
    localparam signed [ACCW-1:0] SAT_MIN = ~SAT_MAX;
    wire sat_hi = (relued > SAT_MAX);
    wire sat_lo = (relued < SAT_MIN);
    assign act_c = sat_hi ? SAT_MAX[DW-1:0] :
                   sat_lo ? SAT_MIN[DW-1:0] : relued[DW-1:0];
    assign ovf_c = sat_hi | sat_lo;
endmodule

// [E5] Register keluaran epilog
module epi_reg_out #(
    parameter DW = 8
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 in_valid,
    input  wire signed [DW-1:0] act_c,
    input  wire                 ovf_c,
    output reg                  out_valid,
    output reg  signed [DW-1:0] out_act,
    output reg                  out_ovf
);
    always @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_act   <= {DW{1'b0}};
            out_ovf   <= 1'b0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                out_act <= act_c;
                out_ovf <= ovf_c;
            end
        end
    end
endmodule

`default_nettype wire
