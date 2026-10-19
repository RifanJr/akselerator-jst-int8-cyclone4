// ============================================================================
//  mult_bw8_arith.v
//  Pengali Baugh-Wooley 8 x 8 bertanda — deskripsi ARITMETIKA
//
//  Partial product dibangkitkan sesuai Baugh-Wooley (AND untuk suku positif,
//  NAND untuk suku silang bertanda), lalu delapan barisnya dijumlahkan dengan
//  operator '+' agar Quartus memakai rantai carry Cyclone IV.
//
//  Murni kombinasional, tanpa clock.
// ============================================================================
`default_nettype none

module mult_bw8_arith (
    input  wire signed [7:0] a,
    input  wire signed [7:0] b,
    output wire signed [15:0] p
);
    wire [7:0] ua = a;
    wire [7:0] ub = b;

    wire [7:0] row [0:7];
    genvar i, j;
    generate
        // Baris 0..6 : AND pada bit 0..6, NAND pada bit 7
        for (i = 0; i < 7; i = i + 1) begin : g_row
            for (j = 0; j < 7; j = j + 1) begin : g_col
                assign row[i][j] = ua[i] & ub[j];
            end
            assign row[i][7] = ~(ua[i] & ub[7]);
        end
        // Baris 7 : NAND pada bit 0..6, AND pada bit 7
        for (j = 0; j < 7; j = j + 1) begin : g_row7
            assign row[7][j] = ~(ua[7] & ub[j]);
        end
    endgenerate
    assign row[7][7] = ua[7] & ub[7];

    // Penjumlahan delapan baris tergeser + konstanta koreksi Baugh-Wooley
    // (bit 15 dan bit 8). Operator '+' membuat Quartus memakai rantai carry.
    wire [15:0] sum = {8'b0, row[0]}
                    + ({8'b0, row[1]} << 1)
                    + ({8'b0, row[2]} << 2)
                    + ({8'b0, row[3]} << 3)
                    + ({8'b0, row[4]} << 4)
                    + ({8'b0, row[5]} << 5)
                    + ({8'b0, row[6]} << 6)
                    + ({8'b0, row[7]} << 7)
                    + 16'h8100;

    assign p = sum;
endmodule

`default_nettype wire
