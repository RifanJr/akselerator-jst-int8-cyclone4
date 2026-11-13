// ============================================================================
//  mem_psum.v
//  Memori jumlah parsial satu lajur untuk rancangan tanpa stationary (NLR).
//
//  Simple dual-port: satu port baca dan satu port tulis yang bekerja pada
//  siklus yang sama. Dipaksa ke blok M9K supaya setiap akses jumlah parsial
//  benar-benar menjadi akses memori (dan tercatat sebagai daya M9K oleh
//  Power Analyzer), bukan register.
//
//  Latensi baca 2 siklus, sama dengan mem_w dan mem_d, sehingga jumlah
//  parsial tiba di MAC bersamaan dengan bobot dan masukan.
//
//      siklus t   : rd_en dan rd_addr diberikan, larik dibaca pada akhir siklus
//      siklus t+1 : rd_larik
//      siklus t+2 : rd_q sah
//
//  rd_en hanya menyalakan pembacaan larik. Tahap kedua selalu maju, sehingga
//  pembacaan yang dimatikan per lajur tidak menggeser pewaktuan lajur lain.
//
//  Baca dan tulis ke alamat yang sama pada siklus yang sama menghasilkan NILAI
//  LAMA. Pengendali menjamin hal itu tidak pernah terjadi pada data yang masih
//  dibutuhkan (lihat jarak K pada ctrl_nlr.v).
// ============================================================================
`default_nettype none

module mem_psum #(
    parameter DW    = 32,
    parameter DEPTH = 8,
    parameter AW    = 3
)(
    input  wire           clk,

    input  wire           rd_en,
    input  wire [AW-1:0]  rd_addr,
    output reg  [DW-1:0]  rd_q,

    input  wire           wr_en,
    input  wire [AW-1:0]  wr_addr,
    input  wire [DW-1:0]  wr_data
);

    (* ramstyle = "M9K, no_rw_check" *) reg [DW-1:0] isi [0:DEPTH-1];

    reg [DW-1:0] rd_larik;

    // Tanpa reset: register di dalam blok M9K tidak boleh punya reset.
    always @(posedge clk) begin
        if (wr_en) isi[wr_addr] <= wr_data;
        if (rd_en) rd_larik <= isi[rd_addr];
        rd_q <= rd_larik;
    end

endmodule

`default_nettype wire
