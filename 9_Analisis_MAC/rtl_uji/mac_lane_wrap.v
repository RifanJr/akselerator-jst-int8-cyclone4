// ============================================================================
//  mac_lane_wrap.v
//  Pembungkus tipis untuk menyintesis satu lajur mac_unit secara berdiri
//  sendiri, guna mengukur pemakaian logic element dan Fmax per lajur.
//
//  Ada dua modul dengan daftar port yang PERSIS SAMA, hanya berbeda pada
//  parameter MULT_STYLE:
//
//      mac_lane_arith  -> MULT_STYLE = "ARITH"  (Baugh-Wooley, logika)
//      mac_lane_hard   -> MULT_STYLE = "HARD"   (pengali keras embedded)
//
//  Karena nama portnya sama, satu set penugasan VIRTUAL_PIN di dalam
//  mac_syn.qsf berlaku untuk keduanya. Mengganti varian cukup dengan
//  mengganti top-level entity, tanpa menyentuh berkas apa pun.
//
//  Pembungkus ini TIDAK menambah logika: seluruh port diteruskan langsung
//  ke mac_unit, sehingga angka LE yang terbaca adalah angka mac_unit murni.
// ============================================================================
`default_nettype none

// ---------------------------------------------------------------------------
//  Varian logika — pengali Baugh-Wooley dari gerbang dasar
// ---------------------------------------------------------------------------
module mac_lane_arith (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("ARITH"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (1)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule

// ---------------------------------------------------------------------------
//  Varian keras — pengali embedded 9 bit
// ---------------------------------------------------------------------------
module mac_lane_hard (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("HARD"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (1)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule

// ---------------------------------------------------------------------------
//  Varian struktural — Baugh-Wooley dengan full adder eksplisit
// ---------------------------------------------------------------------------
module mac_lane_struct (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("STRUCT"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (1)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule


// ===========================================================================
//  VARIAN TANPA EPILOG (HAS_EPILOG = 0)
//
//  Epilog dikeluarkan dari lajur dan dijadikan satu blok bersama
//  (epilog_unit.v). Daftar portnya sengaja dibuat PERSIS SAMA dengan varian
//  beregilog di atas — m_act dan m_ovf tetap ada, hanya diikat ke nol —
//  supaya penugasan VIRTUAL_PIN di mac_syn.qsf berlaku tanpa perubahan.
//
//  Selisih LE terhadap varian beregilog = ongkos epilog per lajur, yaitu
//  angka yang menentukan apakah P=16 dapat diselamatkan.
// ===========================================================================

// ---------------------------------------------------------------------------
//  mac_lane_arith_noepi
// ---------------------------------------------------------------------------
module mac_lane_arith_noepi (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("ARITH"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (0)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule

// ---------------------------------------------------------------------------
//  mac_lane_hard_noepi
// ---------------------------------------------------------------------------
module mac_lane_hard_noepi (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("HARD"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (0)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule

// ---------------------------------------------------------------------------
//  mac_lane_struct_noepi
// ---------------------------------------------------------------------------
module mac_lane_struct_noepi (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                s_valid,
    output wire                s_ready,
    input  wire signed [7:0]   s_x,
    input  wire signed [7:0]   s_w,
    input  wire                s_first,
    input  wire                s_last,
    input  wire signed [31:0]  s_init,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                m_valid,
    input  wire                m_ready,
    output wire signed [31:0]  m_acc,
    output wire signed [7:0]   m_act,
    output wire                m_ovf
);
    mac_unit #(
        .DW         (8),
        .ACCW       (32),
        .MULT_STYLE ("STRUCT"),
        .PIPE_MULT  (0),
        .HAS_EPILOG (0)
    ) u_lane (
        .clk (clk), .rst_n (rst_n),
        .s_valid (s_valid), .s_ready (s_ready),
        .s_x (s_x), .s_w (s_w),
        .s_first (s_first), .s_last (s_last), .s_init (s_init),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .m_valid (m_valid), .m_ready (m_ready),
        .m_acc (m_acc), .m_act (m_act), .m_ovf (m_ovf)
    );
endmodule

// ===========================================================================
//  Pembungkus untuk mengukur epilog bersama secara berdiri sendiri
// ===========================================================================
module epilog_wrap (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                in_valid,
    input  wire signed [31:0]  in_acc,
    input  wire        [4:0]   cfg_shift,
    input  wire                cfg_round,
    input  wire                cfg_relu,
    output wire                out_valid,
    output wire signed [7:0]   out_act,
    output wire                out_ovf
);
    epilog_unit #(.DW(8), .ACCW(32)) u_epi (
        .clk (clk), .rst_n (rst_n),
        .in_valid (in_valid), .in_acc (in_acc),
        .cfg_shift (cfg_shift), .cfg_round (cfg_round), .cfg_relu (cfg_relu),
        .out_valid (out_valid), .out_act (out_act), .out_ovf (out_ovf)
    );
endmodule

`default_nettype wire
