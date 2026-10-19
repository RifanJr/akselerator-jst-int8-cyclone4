// ============================================================================
//  seg7_dec.v
//  Dekoder satu digit heksadesimal menjadi pola tujuh segmen.
//
//  Urutan bit keluaran mengikuti kebiasaan papan ini:
//
//      seg[0]=a  seg[1]=b  seg[2]=c  seg[3]=d
//      seg[4]=e  seg[5]=f  seg[6]=g  seg[7]=titik desimal
//
//              a
//            -----
//         f |     | b
//           |  g  |
//            -----
//         e |     | c
//           |     |
//            -----   . dp
//              d
//
//  Keluaran modul ini selalu AKTIF-TINGGI: bit bernilai 1 berarti segmen
//  itu ingin menyala. Penyesuaian ke polaritas papan (common anode lawan
//  common cathode) dilakukan di luar, oleh uji_papan.v, supaya modul ini
//  tetap netral dan bisa dipakai ulang di rancangan penuh.
//
//  Heksadesimal 0..F didukung penuh meskipun akselerator hanya memakai 0..9,
//  supaya modul ini juga berguna untuk menampilkan kode status saat mendebug.
// ============================================================================
`default_nettype none

module seg7_dec (
    input  wire [3:0] nilai,
    input  wire       titik,      // nyalakan titik desimal
    output reg  [7:0] seg         // aktif-tinggi, {dp,g,f,e,d,c,b,a}
);

    always @(*) begin
        case (nilai)
            //                   dp g f e d c b a
            4'h0:    seg[6:0] = 7'b0111111;
            4'h1:    seg[6:0] = 7'b0000110;
            4'h2:    seg[6:0] = 7'b1011011;
            4'h3:    seg[6:0] = 7'b1001111;
            4'h4:    seg[6:0] = 7'b1100110;
            4'h5:    seg[6:0] = 7'b1101101;
            4'h6:    seg[6:0] = 7'b1111101;
            4'h7:    seg[6:0] = 7'b0000111;
            4'h8:    seg[6:0] = 7'b1111111;
            4'h9:    seg[6:0] = 7'b1101111;
            4'hA:    seg[6:0] = 7'b1110111;
            4'hB:    seg[6:0] = 7'b1111100;
            4'hC:    seg[6:0] = 7'b0111001;
            4'hD:    seg[6:0] = 7'b1011110;
            4'hE:    seg[6:0] = 7'b1111001;
            default: seg[6:0] = 7'b1110001;   // F
        endcase
        seg[7] = titik;
    end

endmodule

`default_nettype wire
