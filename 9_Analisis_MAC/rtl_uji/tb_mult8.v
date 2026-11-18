// ============================================================================
//  tb_mult8.v — pengujian MENYELURUH pengali 8 x 8 bertanda
//
//  Ruang masukan hanya 256 x 256 = 65.536 kombinasi, sehingga pengali ini
//  dapat diuji SELURUHNYA, bukan disampel. Ketiga varian diuji sekaligus.
//
//  Jalankan:  iverilog -g2012 -o sim tb_mult8.v mult_bw8_arith.v \
//                       mult_bw8_struct.v mult_hard8.v && vvp sim
// ============================================================================
`timescale 1ns/1ps

module tb_mult8;
    reg  signed [7:0]  a, b;
    wire signed [15:0] p_arith, p_struct, p_hard;
    integer i, j;
    integer salah_arith = 0, salah_struct = 0, salah_hard = 0;
    reg signed [15:0] benar;

    mult_bw8_arith  u_arith  (.a(a), .b(b), .p(p_arith));
    mult_bw8_struct u_struct (.a(a), .b(b), .p(p_struct));
    mult_hard8      u_hard   (.a(a), .b(b), .p(p_hard));

    initial begin
        $display("=== Pengujian menyeluruh pengali 8x8 bertanda ===");
        for (i = -128; i <= 127; i = i + 1) begin
            for (j = -128; j <= 127; j = j + 1) begin
                a = i[7:0];
                b = j[7:0];
                #1;
                benar = i * j;
                if (p_arith  !== benar) begin
                    if (salah_arith < 5)
                        $display("  ARITH  meleset: %0d x %0d = %0d, seharusnya %0d",
                                 i, j, p_arith, benar);
                    salah_arith = salah_arith + 1;
                end
                if (p_struct !== benar) begin
                    if (salah_struct < 5)
                        $display("  STRUCT meleset: %0d x %0d = %0d, seharusnya %0d",
                                 i, j, p_struct, benar);
                    salah_struct = salah_struct + 1;
                end
                if (p_hard   !== benar) begin
                    if (salah_hard < 5)
                        $display("  HARD   meleset: %0d x %0d = %0d, seharusnya %0d",
                                 i, j, p_hard, benar);
                    salah_hard = salah_hard + 1;
                end
            end
        end

        $display("");
        $display("  mult_bw8_arith  : %0d / 65536 benar, meleset %0d", 65536-salah_arith,  salah_arith);
        $display("  mult_bw8_struct : %0d / 65536 benar, meleset %0d", 65536-salah_struct, salah_struct);
        $display("  mult_hard8      : %0d / 65536 benar, meleset %0d", 65536-salah_hard,   salah_hard);
        $display("");

        // nilai batas yang wajib diperiksa terpisah
        a = -8'sd128; b = -8'sd128; #1;
        $display("  batas  -128 x -128 = %0d  (seharusnya  16384)  %s",
                 p_arith, (p_arith == 16384)  ? "OK" : "GAGAL");
        a = -8'sd128; b =  8'sd127; #1;
        $display("  batas  -128 x  127 = %0d  (seharusnya -16256)  %s",
                 p_arith, (p_arith == -16256) ? "OK" : "GAGAL");
        a =  8'sd127; b =  8'sd127; #1;
        $display("  batas   127 x  127 = %0d  (seharusnya  16129)  %s",
                 p_arith, (p_arith == 16129)  ? "OK" : "GAGAL");

        $display("");
        if (salah_arith == 0 && salah_struct == 0 && salah_hard == 0)
            $display("HASIL: LULUS — ketiga varian benar pada seluruh 65.536 kombinasi");
        else
            $display("HASIL: GAGAL");
        $finish;
    end
endmodule
