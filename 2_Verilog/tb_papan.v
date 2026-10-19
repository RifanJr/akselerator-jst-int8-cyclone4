`timescale 1ns/1ps
// ============================================================================
//  tb_papan.v  --  uji rancangan papan top_papan.v
//
//  Meniru orang yang menekan tombol di papan:
//    1. citra 00 berjalan sendiri saat dinyalakan
//    2. key[0] ditekan 15 kali -> citra 01 .. 15
//    3. key[1] sekali  -> kembali ke citra 14
//    4. key[2] sekali  -> citra 14 dijalankan ulang
//    5. key[3] ditahan -> tampilan harus berganti ke jumlah siklus
//
//  Tiap hasil dicetak dalam baris HASIL yang diurai jalankan_papan.py dan
//  dicocokkan ke uji/golden_uji.txt: digit terpilih DAN nilai akumulator
//  pemenangnya harus sama persis.
//
//  Pewaktuan tombol, pindai, dan kedip diperkecil supaya simulasi cepat.
//  Logikanya sama; hanya angka pembaginya yang berbeda.
// ============================================================================
module tb_papan;

    reg clk = 0;
    always #10 clk = ~clk;          // 50 MHz

    reg  [3:0] key = 4'b1111;       // tombol aktif-rendah, dilepas
    wire [3:0] led;
    wire [7:0] seg;
    wire [3:0] dig;

    localparam SAMPEL = 16;

    top_papan #(.SAMPEL_TOMBOL(SAMPEL), .SETENGAH_DETIK(200), .PINDAI(4)) u_top (
        .clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));

    integer salah = 0;

    task tekan(input integer n);
    begin
        key[n] = 1'b0;
        repeat (SAMPEL * 4) @(posedge clk);
        key[n] = 1'b1;
        repeat (SAMPEL * 4) @(posedge clk);
    end
    endtask

    task tunggu_hasil(input integer sebelum);
        integer batas;
    begin
        batas = 0;
        while (u_top.jumlah_hasil === sebelum && batas < 20000) begin
            @(posedge clk); batas = batas + 1;
        end
        if (u_top.jumlah_hasil === sebelum) begin
            $display("GAGAL: hasil tidak pernah keluar");
            salah = salah + 1;
        end
        @(posedge clk);
        // LED aktif-rendah: led[3] = cocok, led[2] = berbeda
        $display("HASIL %0d %0d %0d %0d %0d %0d",
                 u_top.idx, u_top.hasil_r, u_top.nilai_r, u_top.siklus_r,
                 ~led[3], ~led[2]);
    end
    endtask

    integer n, sebelum;
    initial begin
        // 1. citra 00 berjalan sendiri setelah reset internal lepas
        wait (u_top.rst_n === 1'b1);
        tunggu_hasil(0);

        // 2. citra 01 .. 15
        for (n = 1; n < 16; n = n + 1) begin
            sebelum = u_top.jumlah_hasil;
            tekan(0);
            tunggu_hasil(sebelum);
        end

        // 3. mundur satu
        sebelum = u_top.jumlah_hasil;
        tekan(1);
        tunggu_hasil(sebelum);

        // 4. ulangi citra yang sama
        sebelum = u_top.jumlah_hasil;
        tekan(2);
        tunggu_hasil(sebelum);

        // 5. mode siklus: tampilan harus 1816 dalam BCD
        key[3] = 1'b0;
        repeat (SAMPEL * 4) @(posedge clk);
        $display("TAMPIL_SIKLUS %h LED1 %0d", u_top.tampil, ~led[1]);
        key[3] = 1'b1;
        repeat (SAMPEL * 4) @(posedge clk);
        $display("TAMPIL_NORMAL %h", u_top.tampil);

        $display("SELESAI");
        $finish;
    end

endmodule
