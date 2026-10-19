// ============================================================================
//  mult_hard8.v
//  Pengali 8 x 8 bertanda memakai blok pengali embedded Cyclone IV.
//
//  Satu perkalian 8 x 8 bertanda memuat dalam satu elemen pengali 9 bit.
//  EP4CE6 menyediakan 30 elemen tersebut (15 blok 18x18, tiap blok dapat
//  dipecah menjadi dua 9x9).
//
//  Dipakai sebagai PEMBANDING bagi mult_bw8_*.v. Akumulator tetap dibangun
//  di logic element pada kedua varian, sehingga yang dibandingkan benar-benar
//  hanya cara perkalian dilakukan.
// ============================================================================
`default_nettype none

module mult_hard8 (
    input  wire signed [7:0] a,
    input  wire signed [7:0] b,
    output wire signed [15:0] p
);
    (* multstyle = "dsp" *) wire signed [15:0] hasil = a * b;
    assign p = hasil;
endmodule

`default_nettype wire
