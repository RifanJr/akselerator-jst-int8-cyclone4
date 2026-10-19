// ============================================================================
//  argmax10.v
//  Memilih indeks dengan akumulator terbesar dari sepuluh keluaran.
//
//  Nilai masuk SATU PER SATU seiring lapisan 2 menyelesaikan tiap neuron,
//  jadi tidak ada pembanding 10 arah dan tidak ada penyangga 10 x 32 bit.
//  Cukup satu pembanding dan satu register nilai terbesar.
//
//  Masukannya akumulator 32 bit LANGSUNG dari unit MAC, bukan keluaran
//  epilog. Epilog menyaturasi ke 8 bit, sedangkan akumulator keluaran
//  berkisar -5163..2063 -- kalau disaturasi lebih dulu, urutannya rusak.
//
//  Aturan seri: yang LEBIH DULU menang, karena pembandingnya memakai ">"
//  dan bukan ">=". Ini menyamakan perilakunya dengan np.argmax pada acuan
//  Python, sehingga perbandingan bit-exact tetap sah bila ada nilai kembar.
// ============================================================================
`default_nettype none

module argmax10 #(
    parameter ACCW = 32,
    parameter IW   = 4
)(
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    mulai,        // kosongkan sebelum lapisan 2
    input  wire                    in_valid,
    input  wire signed [ACCW-1:0]  in_acc,
    input  wire [IW-1:0]           in_idx,
    output reg  [IW-1:0]           idx_maks,
    output reg  signed [ACCW-1:0]  nilai_maks,
    output reg                     ada                 // sudah ada isinya
);

    always @(posedge clk) begin
        if (!rst_n) begin
            idx_maks   <= {IW{1'b0}};
            nilai_maks <= {ACCW{1'b0}};
            ada        <= 1'b0;
        end else if (mulai) begin
            ada        <= 1'b0;
            idx_maks   <= {IW{1'b0}};
            nilai_maks <= {ACCW{1'b0}};
        end else if (in_valid) begin
            if (!ada || (in_acc > nilai_maks)) begin
                idx_maks   <= in_idx;
                nilai_maks <= in_acc;
            end
            ada <= 1'b1;
        end
    end

endmodule

`default_nettype wire
