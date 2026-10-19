// ==========================================================================
//  rom_bias8.v
//  ROM bias untuk konfigurasi P = 8, dibangkitkan dari
//  Training/export_final oleh notebook Training_MLP_PyTorch.ipynb (Tahap 7).
//
//  Pada P = 8, kedelapan lajur MAC membutuhkan bias DELAPAN neuron
//  BERURUTAN pada saat yang sama. Karena itu ROM ini dialamati per
//  KELOMPOK, bukan per neuron, dan mengeluarkan 8 x 8 bit sekaligus.
//
//  Cara ini jauh lebih murah daripada menyalin rom_bias 74 entri
//  sebanyak delapan kali: isinya hanya 10 entri x 64 bit.
//
//      kelompok 0..7 : lapisan 1, neuron 0..63
//      kelompok 8..9 : lapisan 2, neuron 0..9
//
//  Kelompok 9 hanya memuat 2 neuron yang sah (neuron 8 dan 9);
//  enam sisanya diisi nol dan hasilnya DIBUANG oleh pengendali,
//  bukan dipakai. Lihat topeng lajur di ctrl_fsm_p8.v.
// ==========================================================================
`default_nettype none

module rom_bias8 (
    input  wire [3:0]  kelompok,          // 0..9
    output reg  [63:0] dout               // {bias7, ..., bias0}
);

    always @(*) begin
        case (kelompok)
            4'd0 : dout = 64'h02F30F0D04FF03F2;   // L1 neuron 0..7  [-14, 3, -1, 4, 13, 15, -13, 2]
            4'd1 : dout = 64'hE00B0C28000BFFFC;   // L1 neuron 8..15  [-4, -1, 11, 0, 40, 12, 11, -32]
            4'd2 : dout = 64'h1A0E08E401DB440C;   // L1 neuron 16..23  [12, 68, -37, 1, -28, 8, 14, 26]
            4'd3 : dout = 64'h151D0E01140E1021;   // L1 neuron 24..31  [33, 16, 14, 20, 1, 14, 29, 21]
            4'd4 : dout = 64'h19141BFE121F1FF6;   // L1 neuron 32..39  [-10, 31, 31, 18, -2, 27, 20, 25]
            4'd5 : dout = 64'hF701110600254A24;   // L1 neuron 40..47  [36, 74, 37, 0, 6, 17, 1, -9]
            4'd6 : dout = 64'hFA2027181A19EA14;   // L1 neuron 48..55  [20, -22, 25, 26, 24, 39, 32, -6]
            4'd7 : dout = 64'hF7083100F91E20F3;   // L1 neuron 56..63  [-13, 32, 30, -7, 0, 49, 8, -9]
            4'd8 : dout = 64'hF4050E13F200F8E9;   // L2 neuron 0..7  [-23, -8, 0, -14, 19, 14, 5, -12]
            4'd9 : dout = 64'h000000000000F1FD;   // L2 neuron 8,9 + 6 pengisi  [-3, -15, 0, 0, 0, 0, 0, 0]
            default: dout = 64'h0000000000000000;
        endcase
    end

endmodule

`default_nettype wire
