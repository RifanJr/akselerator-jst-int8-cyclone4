// ============================================================================
//  wrap_komponen.v  --  Tugas 10: mengukur komponen unit MAC dan epilog SENDIRIAN
//
//  Pola sama dengan pembungkus register tim (mult_timing_wrap.v): komponen
//  dijepit di antara register masukan (d_q) dan register keluaran (q_o),
//  sehingga Timing Analyzer melaporkan jalur register-ke-register yang hanya
//  berisi komponen itu. Semua port data dijadikan pin maya (VIRTUAL_PIN) oleh
//  qsf supaya tidak memakan pin fisik.
//
//  Komponen diambil dari 9_Analisis_MAC/rtl_terpecah/mac_unit.v dan epilog_unit.v
//  (versi terpecah) TANPA diubah. Konfigurasi
//  epilog (cfg_shift, cfg_round, cfg_relu) di sini VARIABEL (ikut register
//  masukan), berbeda dengan sistem yang memakai konstanta.
//
//  Top-level yang tersedia:
//    wrap_dasar      : register -> register tanpa logika (ongkos pembungkus)
//    wrap_m3_mux     : mac_mux_init   (M3)
//    wrap_m4_add     : mac_add32      (M4)
//    wrap_e1_round   : epi_round      (E1)
//    wrap_e2_shift   : epi_shift      (E2)
//    wrap_e3_relu    : epi_relu       (E3)
//    wrap_e4_sat     : epi_sat        (E4)
//    wrap_epi_rantai : E1 -> E2 -> E3 -> E4 berurutan (logika kombinasional epilog utuh)
// ============================================================================
`default_nettype none

module wrap_dasar (input wire clk, input wire [31:0] d_i, output reg [31:0] q_o);
    reg [31:0] d_q;
    always @(posedge clk) begin d_q <= d_i; q_o <= d_q; end
endmodule

module wrap_m3_mux (input wire clk, input wire [64:0] d_i, output reg [31:0] q_o);
    reg [64:0] d_q; wire [31:0] y;
    mac_mux_init #(.ACCW(32)) u_dut (.f_use(d_q[64]), .init_use(d_q[63:32]), .acc(d_q[31:0]), .acc_base(y));
    always @(posedge clk) begin d_q <= d_i; q_o <= y; end
endmodule

module wrap_m4_add (input wire clk, input wire [47:0] d_i, output reg [31:0] q_o);
    reg [47:0] d_q; wire [31:0] y;
    mac_add32 #(.PW(16), .ACCW(32)) u_dut (.acc_base(d_q[47:16]), .p_use(d_q[15:0]), .acc_next(y));
    always @(posedge clk) begin d_q <= d_i; q_o <= y; end
endmodule

module wrap_e1_round (input wire clk, input wire [37:0] d_i, output reg [31:0] q_o);
    reg [37:0] d_q; wire [31:0] y;
    epi_round #(.ACCW(32)) u_dut (.in_acc(d_q[31:0]), .cfg_shift(d_q[36:32]), .cfg_round(d_q[37]), .rnd_sum(y));
    always @(posedge clk) begin d_q <= d_i; q_o <= y; end
endmodule

module wrap_e2_shift (input wire clk, input wire [36:0] d_i, output reg [31:0] q_o);
    reg [36:0] d_q; wire [31:0] y;
    epi_shift #(.ACCW(32)) u_dut (.rnd_sum(d_q[31:0]), .cfg_shift(d_q[36:32]), .shifted(y));
    always @(posedge clk) begin d_q <= d_i; q_o <= y; end
endmodule

module wrap_e3_relu (input wire clk, input wire [32:0] d_i, output reg [31:0] q_o);
    reg [32:0] d_q; wire [31:0] y;
    epi_relu #(.ACCW(32)) u_dut (.shifted(d_q[31:0]), .cfg_relu(d_q[32]), .relued(y));
    always @(posedge clk) begin d_q <= d_i; q_o <= y; end
endmodule

module wrap_e4_sat (input wire clk, input wire [31:0] d_i, output reg [8:0] q_o);
    reg [31:0] d_q; wire [7:0] act; wire ovf;
    epi_sat #(.DW(8), .ACCW(32)) u_dut (.relued(d_q), .act_c(act), .ovf_c(ovf));
    always @(posedge clk) begin d_q <= d_i; q_o <= {ovf, act}; end
endmodule

module wrap_epi_rantai (input wire clk, input wire [38:0] d_i, output reg [8:0] q_o);
    reg [38:0] d_q; wire [31:0] r, s, z; wire [7:0] act; wire ovf;
    epi_round #(.ACCW(32)) u_round (.in_acc(d_q[31:0]), .cfg_shift(d_q[36:32]), .cfg_round(d_q[37]), .rnd_sum(r));
    epi_shift #(.ACCW(32)) u_shift (.rnd_sum(r), .cfg_shift(d_q[36:32]), .shifted(s));
    epi_relu  #(.ACCW(32)) u_relu  (.shifted(s), .cfg_relu(d_q[38]), .relued(z));
    epi_sat   #(.DW(8), .ACCW(32)) u_sat (.relued(z), .act_c(act), .ovf_c(ovf));
    always @(posedge clk) begin d_q <= d_i; q_o <= {ovf, act}; end
endmodule

`default_nettype wire
