// ============================================================================
//  seg7_scan.v
//  Pemindai empat digit seven-segment.
//
//  Keempat digit berbagi delapan jalur segmen yang sama, jadi hanya satu
//  digit boleh menyala pada satu saat. Modul ini menyalakannya bergantian
//  cukup cepat sehingga mata melihat keempatnya menyala bersamaan.
//
//  Laju pindai: satu digit per PEMBAGI siklus. Dengan clock 50 MHz dan
//  PEMBAGI = 50.000, tiap digit berganti tiap 1 ms, sehingga satu putaran
//  penuh 4 ms -- setara 250 Hz, jauh di atas ambang kedip mata (sekitar
//  60 Hz) dan tidak terlihat berkedip pada kamera ponsel.
//
//  Polaritas keluaran diatur lewat parameter, karena papan ini tidak
//  terdokumentasi resmi dan polaritasnya harus dibuktikan dengan percobaan:
//
//      SEG_AKTIF_RENDAH = 1  -> segmen menyala saat jalurnya 0 (common anode)
//      DIG_AKTIF_RENDAH = 1  -> digit terpilih saat jalurnya 0
//
//  Dengan begitu, kalau tampilannya terbalik cukup ganti parameternya --
//  tidak perlu menyentuh logika.
// ============================================================================
`default_nettype none

module seg7_scan #(
    parameter PEMBAGI          = 50000,   // siklus per digit
    parameter SEG_AKTIF_RENDAH = 1,
    parameter DIG_AKTIF_RENDAH = 1
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] nilai,      // empat digit heksadesimal
    input  wire [3:0]  titik,      // titik desimal per digit
    output wire [7:0]  seg,        // ke pin SEG[7:0]
    output wire [3:0]  dig         // ke pin DIG[3:0]
);

    // ---- pencacah pembagi ----
    reg [31:0] cacah;
    reg [1:0]  pilih;

    always @(posedge clk) begin
        if (!rst_n) begin
            cacah <= 32'd0;
            pilih <= 2'd0;
        end else if (cacah >= PEMBAGI - 1) begin
            cacah <= 32'd0;
            pilih <= pilih + 2'd1;
        end else begin
            cacah <= cacah + 32'd1;
        end
    end

    // ---- pilih digit yang sedang ditampilkan ----
    reg [3:0] nibble;
    reg       dp;
    always @(*) begin
        case (pilih)
            2'd0: begin nibble = nilai[3:0];   dp = titik[0]; end
            2'd1: begin nibble = nilai[7:4];   dp = titik[1]; end
            2'd2: begin nibble = nilai[11:8];  dp = titik[2]; end
            2'd3: begin nibble = nilai[15:12]; dp = titik[3]; end
        endcase
    end

    wire [7:0] seg_tinggi;
    seg7_dec u_dec (.nilai(nibble), .titik(dp), .seg(seg_tinggi));

    // ---- satu digit aktif ----
    reg [3:0] dig_tinggi;
    always @(*) begin
        case (pilih)
            2'd0: dig_tinggi = 4'b0001;
            2'd1: dig_tinggi = 4'b0010;
            2'd2: dig_tinggi = 4'b0100;
            2'd3: dig_tinggi = 4'b1000;
        endcase
    end

    // ---- penyesuaian polaritas ----
    assign seg = SEG_AKTIF_RENDAH ? ~seg_tinggi : seg_tinggi;
    assign dig = DIG_AKTIF_RENDAH ? ~dig_tinggi : dig_tinggi;

endmodule

`default_nettype wire
