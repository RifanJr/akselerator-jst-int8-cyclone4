// ============================================================================
//  mem_w.v
//  Memori bobot — hanya-baca, satu port, keluaran teregister.
//
//  Isinya diambil dari citra memori hasil gen_mem.py. Untuk P = 1 seluruh
//  13.184 bobot berada dalam satu bank kontigu:
//
//      alamat       0 ..  12.543   bobot lapisan 1  (64 neuron x 196 masukan)
//      alamat  12.544 ..  13.183   bobot lapisan 2  (10 neuron x  64 masukan)
//
//  Peta alamat umumnya (berlaku untuk P berapa pun):
//      lapisan 1 : g*196 + i           g = 0..nA-1, i = 0..195
//      lapisan 2 : nA*196 + g*64 + i   g = 0..nB-1, i = 0..63
//  dengan nA = ceil(64/P) dan nB = ceil(10/P). P = 1 memberi nA = 64, nB = 10.
//
//  KELUARAN TEREGISTER — ini keharusan, bukan pilihan gaya.
//  Clock-to-output M9K sekitar 2-3 ns. Bila keluaran memori langsung
//  disodorkan ke pengali Baugh-Wooley (delay terukur 15,31 ns), jalur
//  kritisnya membengkak menjadi kira-kira 18 ns dan margin terhadap anggaran
//  20 ns tinggal 2 ns. Dengan register di keluaran memori, jalur pengali
//  kembali berdiri sendiri seperti yang terukur saat sintesis.
//
//  Latensi baca: 1 siklus. Data alamat A muncul di q pada siklus berikutnya.
//
//  Memori disimpulkan (inferred), bukan dari IP wizard. Alasannya, berkas
//  hasil wizard terikat versi Quartus dan menyulitkan orang lain mengulang
//  sintesisnya.
// ============================================================================
`default_nettype none

module mem_w #(
    parameter DW     = 8,
    parameter DEPTH  = 13184,
    parameter AW     = 14,
    // Jalur relatif ini sengaja dipilih agar berlaku di DUA lingkungan:
    //   simulasi Icarus dijalankan dari folder 2_Verilog/ -> ../1_Python_PC/mem/...
    //   sintesis Quartus proyeknya di folder 3_Quartus/  -> ../1_Python_PC/mem/...
    // Testbench tetap boleh menimpanya lewat parameter.
    parameter BERKAS = "../1_Python_PC/mem/P8/mem_w_b0.hex"
)(
    input  wire           clk,
    input  wire           en,      // clock enable; q bertahan saat en rendah
    input  wire [AW-1:0]  addr,
    output reg  [DW-1:0]  q
);

    (* ramstyle = "M9K" *) reg [DW-1:0] isi [0:DEPTH-1];

    reg [DW-1:0] q_larik;      // tahap 1: keluaran larik memori
                               // tahap 2: q, register keluaran M9K

    initial begin
        $readmemh(BERKAS, isi);
    end

    // Tanpa reset: register di dalam blok memori Cyclone IV tidak boleh
    // punya reset asinkron, kalau dipaksa Quartus gagal menyimpulkan M9K
    // dan membangunnya dari logic element.
    always @(posedge clk) begin
        if (en) begin
            q_larik <= isi[addr];
            q       <= q_larik;
        end
    end

endmodule

`default_nettype wire
