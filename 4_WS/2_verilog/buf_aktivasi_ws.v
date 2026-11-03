// ============================================================================
//  buf_aktivasi_ws.v
//  Buffer aktivasi lapisan 1 untuk 16 citra, dibaca lapisan 2 sebagai
//  kata 32 bit (4 suku per kata).
//
//      alamat kata = (n div 4) * 16 + b      n = neuron 0..63, b = citra
//      lajur byte  = n mod 4
//
//  Pasangan neuron (2g, 2g+1) selalu jatuh di kata yang sama, di lajur
//  {0,1} bila g genap atau {2,3} bila g ganjil. Karena itu buffer dibagi
//  dua RAM 16 bit (lajur 0-1 dan lajur 2-3): satu tulis selalu mengisi
//  satu separuh penuh, tanpa perlu byte enable.
//
//  Port baca: latensi 2 siklus, sama dengan mem_d.v dan mem_w.v.
// ============================================================================
`default_nettype none

module buf_aktivasi_ws #(
    parameter DW = 8
)(
    input  wire           clk,

    // ---- tulis: satu pasangan neuron ----
    input  wire           wr_en,
    input  wire           wr_separuh_atas,   // 1 = lajur 2-3 (g ganjil)
    input  wire [7:0]     wr_addr,           // (g div 2) * 16 + b
    input  wire [2*DW-1:0] wr_data,          // {aktivasi 2g+1, aktivasi 2g}

    // ---- baca: satu kata 4 suku ----
    input  wire           rd_en,             // larik memori dibaca hanya saat aktif
    input  wire [7:0]     rd_addr,           // t * 16 + b
    output reg  [4*DW-1:0] rd_q
);

    // no_rw_check: baca dan tulis tidak pernah ke alamat yang sama pada
    // siklus yang sama (lapisan 1 hanya menulis, lapisan 2 hanya membaca),
    // jadi Quartus tidak perlu menambah logika penerus baca-saat-tulis.
    (* ramstyle = "M9K, no_rw_check" *) reg [2*DW-1:0] bawah [0:255];   // lajur 0-1
    (* ramstyle = "M9K, no_rw_check" *) reg [2*DW-1:0] atas  [0:255];   // lajur 2-3

    reg [4*DW-1:0] rd_larik;

    always @(posedge clk) begin
        if (wr_en &  wr_separuh_atas) atas [wr_addr] <= wr_data;
        if (wr_en & ~wr_separuh_atas) bawah[wr_addr] <= wr_data;
        if (rd_en) rd_larik <= {atas[rd_addr], bawah[rd_addr]};
        rd_q <= rd_larik;
    end

endmodule

`default_nettype wire
