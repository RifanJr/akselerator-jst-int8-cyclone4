// ============================================================================
//  mem_d.v
//  Memori data — BACA DAN TULIS, port baca dan tulis terpisah.
//
//  Berbeda dari mem_w yang hanya-baca, memori ini menampung dua hal:
//
//      alamat    0 .. 195   piksel citra masukan 14x14, Q2.6
//      alamat  196 .. 259   aktivasi lapisan 1, Q5.3  <- DITULIS saat berjalan
//
//  Aktivasi lapisan 1 ditulis balik ke sini oleh epilog begitu satu neuron
//  selesai, lalu dibaca lagi sebagai masukan lapisan 2. Karena itu modul ini
//  wajib punya port tulis; memakai ROM di sini adalah kesalahan.
//
//  Port baca dan tulis dipisah (simple dual-port) supaya penulisan aktivasi
//  tidak perlu menghentikan aliran pembacaan piksel. Cyclone IV M9K
//  mendukungnya langsung.
//
//  Tabrakan baca-tulis pada alamat yang sama TIDAK PERNAH TERJADI dalam
//  rancangan ini: saat lapisan 1 berjalan, yang dibaca hanya 0..195
//  sedangkan yang ditulis hanya 196..259. Karena itu perilaku
//  read-during-write tidak perlu ditentukan.
//
//  Latensi baca: 2 siklus, sama seperti mem_w. Tahap kedua dipetakan ke
//  register keluaran bawaan M9K sehingga ongkosnya nol logic element.
//  Lihat penjelasan panjangnya di mem_w.v.
//
//  Port TULIS tidak terpengaruh: penulisan tetap satu siklus.
// ============================================================================
`default_nettype none

module mem_d #(
    parameter DW     = 8,
    parameter DEPTH  = 260,        // 196 piksel + 64 aktivasi
    parameter AW     = 9,          // 2^9 = 512, cukup untuk 260
    parameter BERKAS = "../1_Python_PC/mem/mem_d.hex"
)(
    input  wire           clk,

    // ---- port baca ----
    input  wire           rd_en,
    input  wire [AW-1:0]  rd_addr,
    output reg  [DW-1:0]  rd_q,

    // ---- port tulis ----
    input  wire           wr_en,
    input  wire [AW-1:0]  wr_addr,
    input  wire [DW-1:0]  wr_data
);

    // Batas wilayah, disediakan agar pengendali tidak menulis angka ajaib
    localparam [AW-1:0] ALAMAT_PIKSEL   = 9'd0;     // 0..195
    localparam [AW-1:0] ALAMAT_AKTIVASI = 9'd196;   // 196..259

    (* ramstyle = "M9K" *) reg [DW-1:0] isi [0:DEPTH-1];

    reg [DW-1:0] rd_larik;     // tahap 1: keluaran larik memori
                               // tahap 2: rd_q, register keluaran M9K

    initial begin
        $readmemh(BERKAS, isi);
    end

    always @(posedge clk) begin
        if (wr_en) isi[wr_addr] <= wr_data;
        if (rd_en) begin
            rd_larik <= isi[rd_addr];
            rd_q     <= rd_larik;
        end
    end

endmodule

`default_nettype wire
