// ============================================================================
//  mult_bw8_struct.v
//  Pengali Baugh-Wooley 8 x 8 bertanda — deskripsi STRUKTURAL
//
//  Setia pada gambar arsitektur array multiplier: gerbang AND/NAND untuk
//  partial product, dan larik full adder untuk reduksinya. Dipakai sebagai
//  pembanding terhadap mult_bw8_arith.v — algoritmanya sama persis, yang
//  berbeda hanya cara mendeskripsikannya.
//
//  Catatan Cyclone IV: full adder yang di-instantiate manual umumnya TIDAK
//  memakai rantai carry, sehingga versi ini diperkirakan lebih besar dan
//  lebih lambat daripada versi aritmetika. Selisih itulah yang dilaporkan.
// ============================================================================
`default_nettype none

module full_adder (
    input  wire a, b, cin,
    output wire sum, cout
);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module mult_bw8_struct (
    input  wire signed [7:0] a,
    input  wire signed [7:0] b,
    output wire signed [15:0] p
);
    wire [7:0] ua = a;
    wire [7:0] ub = b;

    // ---- partial product, sesuai Baugh-Wooley ----
    wire [7:0] row [0:7];
    genvar i, j;
    generate
        for (i = 0; i < 7; i = i + 1) begin : g_row
            for (j = 0; j < 7; j = j + 1) begin : g_col
                assign row[i][j] = ua[i] & ub[j];
            end
            assign row[i][7] = ~(ua[i] & ub[7]);
        end
        for (j = 0; j < 7; j = j + 1) begin : g_row7
            assign row[7][j] = ~(ua[7] & ub[j]);
        end
    endgenerate
    assign row[7][7] = ua[7] & ub[7];

    // ---- konstanta koreksi sebagai baris tambahan (bit 15 dan bit 8) ----
    wire [15:0] konst = 16'h8100;

    // ---- reduksi bertingkat dengan larik full adder ----
    // acc[k] = jumlah parsial setelah menyerap baris ke-k
    wire [15:0] acc [0:8];
    assign acc[0] = konst;

    generate
        for (i = 0; i < 8; i = i + 1) begin : g_stage
            // baris ke-i digeser ke kiri sebanyak i
            wire [15:0] addend = {8'b0, row[i]} << i;
            wire [16:0] carry;
            assign carry[0] = 1'b0;
            for (j = 0; j < 16; j = j + 1) begin : g_bit
                full_adder fa (
                    .a    (acc[i][j]),
                    .b    (addend[j]),
                    .cin  (carry[j]),
                    .sum  (acc[i+1][j]),
                    .cout (carry[j+1])
                );
            end
        end
    endgenerate

    assign p = acc[8];
endmodule

`default_nettype wire
