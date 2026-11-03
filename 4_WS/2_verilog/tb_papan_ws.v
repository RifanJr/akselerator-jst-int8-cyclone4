`timescale 1ns/1ps
// ============================================================================
//  tb_papan_ws.v  --  uji rancangan papan WS top_papan_ws.v
//
//  Meniru orang yang memakai papan:
//    1. batch 16 citra berjalan sendiri saat dinyalakan
//    2. key[0] ditekan 15 kali -> hasil citra 00..15 ditampilkan bergantian
//    3. key[2] sekali -> batch dijalankan ulang
//    4. key[3] ditahan -> tampilan berganti ke siklus per citra
//
//  Baris yang dicetak, diurai jalankan_papan_ws.py:
//    AKS     <batch> <citra> <neuron> <akumulator>   tiap keluaran lapisan 2
//    HASIL   <batch> <citra> <prediksi> <nilai maks> <siklus batch>
//    TAMPIL  <citra> <hasil di tampilan> <LED cocok> <LED beda>
//    TAMPIL_SIKLUS <tampilan BCD> LED1 <led mode siklus>
//
//  Pewaktuan tombol, pindai, dan kedip diperkecil supaya simulasi cepat.
// ============================================================================
module tb_papan_ws;

    reg clk = 0;
    always #10 clk = ~clk;          // 50 MHz

    reg  [3:0] key = 4'b1111;       // tombol aktif-rendah, dilepas
    wire [3:0] led;
    wire [7:0] seg;
    wire [3:0] dig;

    localparam SAMPEL = 16;

    top_papan_ws #(.SAMPEL_TOMBOL(SAMPEL), .SETENGAH_DETIK(200), .PINDAI(4)) u_top (
        .clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));

    // ---- setiap keluaran lapisan 2: dua neuron (2g, 2g+1) satu citra ----
    always @(posedge clk)
        if (u_top.akhir_l2) begin
            $display("AKS %0d %0d %0d %0d", u_top.jumlah_hasil + 1, u_top.b_dasar,
                     2 * u_top.g_dasar, u_top.out0);
            $display("AKS %0d %0d %0d %0d", u_top.jumlah_hasil + 1, u_top.b_dasar,
                     2 * u_top.g_dasar + 1, u_top.out1);
        end

    // ---- penghitung akses memori per batch (bukti bobot dipakai ulang) ----
    // baca_bobot  : siklus ketika blok M9K bobot aktif membaca (en_w)
    // muat_ubin   : salinan bobot satu ubin ke register bayangan
    // baca_masukan: kata masukan yang dipakai beat PE baris 0
    integer baca_bobot = 0, muat_ubin = 0, baca_masukan = 0;
    always @(posedge clk) begin
        if (u_top.start) begin
            baca_bobot   = 0;
            muat_ubin    = 0;
            baca_masukan = 0;
        end else begin
            if (u_top.en_w)         baca_bobot   = baca_bobot + 1;
            if (u_top.isi_bayangan) muat_ubin    = muat_ubin + 1;
            if (u_top.in_valid)     baca_masukan = baca_masukan + 1;
        end
    end

    task tekan(input integer n);
    begin
        key[n] = 1'b0;
        repeat (SAMPEL * 4) @(posedge clk);
        key[n] = 1'b1;
        repeat (SAMPEL * 4) @(posedge clk);
    end
    endtask

    task tunggu_batch(input integer ke);
        integer batas;
    begin
        batas = 0;
        while (u_top.jumlah_hasil < ke && batas < 100000) begin
            @(posedge clk); batas = batas + 1;
        end
        if (u_top.jumlah_hasil < ke) $display("GAGAL: batch %0d tidak pernah selesai", ke);
        @(posedge clk);
    end
    endtask

    task cetak_hasil(input integer ke);
        integer i;
    begin
        for (i = 0; i < 16; i = i + 1)
            $display("HASIL %0d %0d %0d %0d %0d", ke, i,
                     u_top.u_amax.idx[i], u_top.u_amax.nilai[i], u_top.siklus_r);
        $display("AKSES %0d %0d %0d %0d", ke, baca_bobot, muat_ubin, baca_masukan);
    end
    endtask

    integer n;
    initial begin
        // 1. batch pertama berjalan sendiri setelah reset internal lepas
        wait (u_top.rst_n === 1'b1);
        tunggu_batch(1);
        cetak_hasil(1);

        // 2. tampilkan hasil ke-16 citra satu per satu
        for (n = 0; n < 16; n = n + 1) begin
            repeat (8) @(posedge clk);
            // LED aktif-rendah: led[3] = cocok, led[2] = berbeda
            $display("TAMPIL %0d %0d %0d %0d", u_top.idx, u_top.hasil, ~led[3], ~led[2]);
            if (n < 15) tekan(0);
        end

        // 3. jalankan ulang batch
        tekan(2);
        tunggu_batch(2);
        cetak_hasil(2);

        // 4. mode siklus
        key[3] = 1'b0;
        repeat (SAMPEL * 4) @(posedge clk);
        $display("TAMPIL_SIKLUS %h LED1 %0d", u_top.tampil, ~led[1]);
        key[3] = 1'b1;
        repeat (SAMPEL * 4) @(posedge clk);

        $display("SELESAI");
        $finish;
    end

endmodule
