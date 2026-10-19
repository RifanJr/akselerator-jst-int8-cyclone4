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
    output reg                      out_valid,
    output reg  signed [DW-1:0]     out_act,
    output reg                      out_ovf
);

    // ---- pembulatan opsional: tambah setengah LSB sebelum digeser ----
    wire signed [ACCW-1:0] rnd_add =
        (cfg_round && (cfg_shift != 5'd0))
            ? ({{(ACCW-1){1'b0}}, 1'b1} <<< (cfg_shift - 5'd1))
            : {ACCW{1'b0}};

    // ---- geser kanan aritmetik ----
    wire signed [ACCW-1:0] shifted = (in_acc + rnd_add) >>> cfg_shift;

    // ---- ReLU ----
    wire signed [ACCW-1:0] relued =
        (cfg_relu && shifted[ACCW-1]) ? {ACCW{1'b0}} : shifted;

    // ---- saturasi ke 8 bit bertanda ----
    //  Batasnya ditulis sebagai pola bit, bukan bilangan desimal bertanda,
    //  supaya tidak ada konstanta yang melampaui lebarnya sendiri.
    localparam signed [ACCW-1:0] SAT_MAX = {{(ACCW-DW+1){1'b0}}, {(DW-1){1'b1}}};
    localparam signed [ACCW-1:0] SAT_MIN = ~SAT_MAX;

    wire sat_hi = (relued > SAT_MAX);
    wire sat_lo = (relued < SAT_MIN);

    wire signed [DW-1:0] act_c = sat_hi ? SAT_MAX[DW-1:0] :
                                 sat_lo ? SAT_MIN[DW-1:0] : relued[DW-1:0];
    wire                 ovf_c = sat_hi | sat_lo;

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
