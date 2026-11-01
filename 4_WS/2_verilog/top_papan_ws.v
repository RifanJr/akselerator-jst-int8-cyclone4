// ============================================================================
//  top_papan_ws.v
//  Akselerator JST INT8 weight-stationary (WS) 4 x 2, batch 16, pada papan
//  Cyclone IV. Rincian rancangan: 4_WS/SPESIFIKASI_WS.md.
//
//  Modul bersama dari rancangan OS dipakai TANPA diubah: mac_unit, mult_*,
//  mem_w, epilog_unit, seg7_scan, seg7_dec (2_Verilog/) dan rom_bias8
//  (1_Python_PC/mem/). Yang khusus WS: ctrl_ws, larik_ws, buf_aktivasi_ws,
//  argmax_batch, serta isi memori di 4_WS/1_mem/.
//
//  ---------------------------------------------------------------------
//  CARA PAKAI DI PAPAN
//
//  Saat dinyalakan, ke-16 citra uji dijalankan sekaligus (satu batch) dan
//  hasilnya disimpan.
//
//    key[0]  tampilkan hasil citra berikutnya (tanpa menghitung ulang)
//    key[1]  tampilkan hasil citra sebelumnya
//    key[2]  jalankan ulang batch
//    key[3]  DITAHAN: tampilkan siklus per citra = siklus batch / 16
//            (dibulatkan), supaya sebanding dengan angka rancangan OS
//
//  Tampilan dan LED sama dengan rancangan OS:
//      [puluhan][satuan.][prediksi Python][hasil papan], misalnya "00.77"
//    led[3]  menyala bila hasil papan = prediksi Python
//    led[2]  menyala bila berbeda
//    led[1]  menyala selama mode siklus (key[3] ditahan)
//    led[0]  berkedip 1 Hz, tanda rancangan hidup
// ============================================================================
`default_nettype none

module top_papan_ws #(
    parameter LED_AKTIF_RENDAH = 1,
    parameter SEG_AKTIF_RENDAH = 1,
    parameter DIG_AKTIF_RENDAH = 1,
    parameter KEY_AKTIF_RENDAH = 1,

    parameter MULT_STYLE   = "HARD",
    // jalur relatif berlaku untuk simulasi (4_WS/2_verilog) dan Quartus
    // (4_WS/3_quartus), karena keduanya satu tingkat di bawah 4_WS
    parameter DIR_MEM      = "../1_mem",

    parameter SAMPEL_TOMBOL  = 500000,     // 10 ms pada 50 MHz
    parameter SETENGAH_DETIK = 25000000,
    parameter PINDAI         = 50000       // 1 ms per digit
)(
    input  wire        clk,
    input  wire [3:0]  key,
    output wire [3:0]  led,
    output wire [7:0]  seg,
    output wire [3:0]  dig
);

    localparam DW      = 8;
    localparam ACCW    = 32;
    localparam AW_W    = 11;
    localparam DEPTH_W = 1648;      // ubin: 32 x 49 + 5 x 16
    localparam N_KATA  = 784;       // ROM citra: 49 ubin x 16 citra

    // ==================================================================
    //  Reset internal saat dinyalakan
    // ==================================================================
    reg [3:0] cacah_reset = 4'd0;
    reg       rst_n       = 1'b0;
    always @(posedge clk) begin
        if (cacah_reset != 4'hF) begin
            cacah_reset <= cacah_reset + 4'd1;
            rst_n       <= 1'b0;
        end else begin
            rst_n <= 1'b1;
        end
    end

    // ==================================================================
    //  Pengendali
    // ==================================================================
    wire            start;
    wire            done, sibuk;
    wire [AW_W-1:0] addr_w;
    wire            en_w;
    wire            isi_bayangan;
    wire [3:0]      muat_aktif;
    wire [9:0]      addr_in;
    wire            en_in, lap_alir;
    wire            in_valid, pilih_l2, pakai_bias;
    wire signed [ACCW-1:0] bias0, bias1;
    wire            akhir_l1, akhir_l2;
    wire [4:0]      g_dasar;
    wire [3:0]      b_dasar;
    wire [4:0]      cfg_shift;
    wire            cfg_round, cfg_relu;

    ctrl_ws #(.DW(DW), .ACCW(ACCW), .AW_W(AW_W)) u_ctrl (
        .clk(clk), .rst_n(rst_n), .start(start),
        .addr_w(addr_w), .en_w(en_w), .isi_bayangan(isi_bayangan), .muat_aktif(muat_aktif),
        .addr_in(addr_in), .en_in(en_in), .lap_token(lap_alir),
        .in_valid(in_valid), .pilih_l2(pilih_l2), .pakai_bias(pakai_bias),
        .bias0(bias0), .bias1(bias1),
        .akhir_l1(akhir_l1), .akhir_l2(akhir_l2),
        .g_dasar(g_dasar), .b_dasar(b_dasar),
        .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
        .done(done), .sibuk(sibuk));

    // ==================================================================
    //  8 bank bobot (mem_w.v tanpa diubah), bank k untuk PE(r, c), k = 2r + c
    // ==================================================================
    wire [8*DW-1:0] bobot_bank;

    genvar k;
    generate
        for (k = 0; k < 8; k = k + 1) begin : g_bank
            localparam BERKAS_BANK =
                (k == 0) ? {DIR_MEM, "/mem_w_ws_b0.hex"} :
                (k == 1) ? {DIR_MEM, "/mem_w_ws_b1.hex"} :
                (k == 2) ? {DIR_MEM, "/mem_w_ws_b2.hex"} :
                (k == 3) ? {DIR_MEM, "/mem_w_ws_b3.hex"} :
                (k == 4) ? {DIR_MEM, "/mem_w_ws_b4.hex"} :
                (k == 5) ? {DIR_MEM, "/mem_w_ws_b5.hex"} :
                (k == 6) ? {DIR_MEM, "/mem_w_ws_b6.hex"} :
                           {DIR_MEM, "/mem_w_ws_b7.hex"};

            mem_w #(.DW(DW), .DEPTH(DEPTH_W), .AW(AW_W), .BERKAS(BERKAS_BANK))
            // en hanya satu siklus per ubin: bobot benar-benar dibaca sekali
            u_mem_w (.clk(clk), .en(en_w), .addr(addr_w), .q(bobot_bank[k*DW +: DW]));
        end
    endgenerate

    // ==================================================================
    //  ROM 16 citra uji, kata 32 bit = 4 piksel, alamat t*16 + b
    //  latensi 2 siklus, sama dengan mem_w
    // ==================================================================
    (* ramstyle = "M9K" *) reg [4*DW-1:0] rom_citra [0:N_KATA-1];
    initial $readmemh({DIR_MEM, "/citra_ws32.hex"}, rom_citra);

    // larik ROM dibaca hanya saat ada token (lapisan 1); tahap kedua hanya register
    reg [4*DW-1:0] rom_larik, rom_q;
    always @(posedge clk) begin
        if (en_in & ~lap_alir) rom_larik <= rom_citra[addr_in];
        rom_q <= rom_larik;
    end

    // ==================================================================
    //  Buffer aktivasi lapisan 1 (dibaca lapisan 2)
    // ==================================================================
    wire [4*DW-1:0] akt_q;
    wire            epi_out_valid0, epi_out_valid1;
    wire signed [DW-1:0] act0, act1;
    reg  [4:0]      g_epi;
    reg  [3:0]      b_epi;

    always @(posedge clk)
        if (akhir_l1) begin
            g_epi <= g_dasar;
            b_epi <= b_dasar;
        end

    buf_aktivasi_ws #(.DW(DW)) u_buf (
        .clk(clk),
        .wr_en(epi_out_valid0), .wr_separuh_atas(g_epi[0]),
        .wr_addr({g_epi[4:1], b_epi}),             // (g div 2) * 16 + b
        .wr_data({act1, act0}),
        .rd_en(en_in & lap_alir), .rd_addr(addr_in[7:0]), .rd_q(akt_q));

    // ==================================================================
    //  Larik WS 4 x 2
    // ==================================================================
    wire                   out_valid;
    wire signed [ACCW-1:0] out0, out1;

    larik_ws #(.DW(DW), .ACCW(ACCW), .MULT_STYLE(MULT_STYLE)) u_larik (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid),
        .in_kata(pilih_l2 ? akt_q : rom_q),
        .pakai_bias(pakai_bias), .bias0(bias0), .bias1(bias1),
        .bobot_bank(bobot_bank), .isi_bayangan(isi_bayangan), .muat_aktif(muat_aktif),
        .out_valid(out_valid), .out0(out0), .out1(out1));

    // ==================================================================
    //  Epilog lapisan 1 (epilog_unit.v tanpa diubah), satu per kolom
    // ==================================================================
    epilog_unit #(.DW(DW), .ACCW(ACCW)) u_epi0 (
        .clk(clk), .rst_n(rst_n), .in_valid(akhir_l1), .in_acc(out0),
        .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
        .out_valid(epi_out_valid0), .out_act(act0), .out_ovf());

    epilog_unit #(.DW(DW), .ACCW(ACCW)) u_epi1 (
        .clk(clk), .rst_n(rst_n), .in_valid(akhir_l1), .in_acc(out1),
        .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
        .out_valid(epi_out_valid1), .out_act(act1), .out_ovf());

    // ==================================================================
    //  Argmax lapisan 2 untuk 16 citra
    // ==================================================================
    reg  [3:0]             idx;              // citra yang sedang ditampilkan
    wire [3:0]             hasil;
    wire signed [ACCW-1:0] hasil_nilai;

    argmax_batch #(.ACCW(ACCW), .B(16)) u_amax (
        .clk(clk), .rst_n(rst_n), .mulai(start),
        .in_valid(akhir_l2), .in_b(b_dasar),
        .in_idx0({g_dasar[2:0], 1'b0}),           // neuron 2g
        .in_acc0(out0), .in_acc1(out1),
        .pilih_b(idx), .idx_maks(hasil), .nilai_maks(hasil_nilai));

    // ==================================================================
    //  Tombol: penyelaras dua flip-flop, lalu dicuplik tiap 10 ms
    //  (sama dengan top_papan.v)
    // ==================================================================
    reg [3:0] k1 = 4'd0, k2 = 4'd0;
    always @(posedge clk) begin
        k1 <= key;
        k2 <= k1;
    end
    wire [3:0] k_aktif = KEY_AKTIF_RENDAH ? ~k2 : k2;

    reg [31:0] cacah_sampel;
    reg        cuplik, cuplik_d;
    reg [3:0]  k_stabil, k_lalu;
    always @(posedge clk) begin
        if (!rst_n) begin
            cacah_sampel <= 32'd0;
            cuplik       <= 1'b0;
            cuplik_d     <= 1'b0;
            k_stabil     <= 4'd0;
            k_lalu       <= 4'd0;
        end else begin
            cuplik   <= 1'b0;
            cuplik_d <= cuplik;
            if (cacah_sampel >= SAMPEL_TOMBOL - 1) begin
                cacah_sampel <= 32'd0;
                cuplik       <= 1'b1;
            end else begin
                cacah_sampel <= cacah_sampel + 32'd1;
            end
            if (cuplik) begin
                k_lalu   <= k_stabil;
                k_stabil <= k_aktif;
            end
        end
    end
    wire [3:0] tekan = {4{cuplik_d}} & k_stabil & ~k_lalu;
    wire       mode_siklus = k_stabil[3];

    // ==================================================================
    //  Pengurut: jalankan batch -> simpan jumlah siklus
    // ==================================================================
    localparam [2:0] F_DIAM    = 3'd0,
                     F_BANGUN  = 3'd1,
                     F_KE_DIAM = 3'd2,
                     F_JALAN   = 3'd3,
                     F_SIMPAN  = 3'd4;

    reg [2:0]  fase;
    reg        start_r;
    reg        awal;              // jalankan batch sekali saat dinyalakan
    reg [15:0] cacah_siklus;
    reg [15:0] siklus_r;          // siklus satu batch
    reg        ada_hasil;
    reg [15:0] jumlah_hasil;      // bertambah tiap batch selesai (untuk testbench)

    assign start = start_r;

    always @(posedge clk) begin
        if (!rst_n) begin
            fase         <= F_DIAM;
            start_r      <= 1'b0;
            awal         <= 1'b1;
            idx          <= 4'd0;
            cacah_siklus <= 16'd0;
            siklus_r     <= 16'd0;
            ada_hasil    <= 1'b0;
            jumlah_hasil <= 16'd0;
        end else begin
            // dihitung setiap detak ketika pengendali sibuk
            if (fase == F_BANGUN)  cacah_siklus <= 16'd0;
            else if (sibuk)        cacah_siklus <= cacah_siklus + 16'd1;

            case (fase)
                F_DIAM: begin
                    start_r <= 1'b0;
                    if (awal) begin
                        awal <= 1'b0;
                        fase <= F_BANGUN;
                    end else if (tekan[0]) begin
                        idx <= idx + 4'd1;
                    end else if (tekan[1]) begin
                        idx <= idx - 4'd1;
                    end else if (tekan[2]) begin
                        fase <= F_BANGUN;
                    end
                end

                // Pengendali yang baru selesai berada di SELESAI dan butuh
                // satu denyut start untuk kembali ke IDLE (sama dengan OS).
                F_BANGUN: begin
                    start_r <= 1'b1;
                    fase    <= done ? F_KE_DIAM : F_JALAN;
                end

                F_KE_DIAM: begin
                    start_r <= 1'b0;
                    if (!done && !start_r) fase <= F_BANGUN;
                end

                F_JALAN: begin
                    start_r <= 1'b0;
                    if (done && !start_r) fase <= F_SIMPAN;
                end

                F_SIMPAN: begin
                    siklus_r     <= cacah_siklus;
                    ada_hasil    <= 1'b1;
                    jumlah_hasil <= jumlah_hasil + 16'd1;
                    fase         <= F_DIAM;
                end

                default: fase <= F_DIAM;
            endcase
        end
    end

    // ==================================================================
    //  Prediksi Python untuk ke-16 citra (dari uji/daftar_uji.txt)
    // ==================================================================
    reg [3:0] harap;
    always @(*) begin
        case (idx)
            4'd0:  harap = 4'd7;   4'd1:  harap = 4'd2;
            4'd2:  harap = 4'd1;   4'd3:  harap = 4'd0;
            4'd4:  harap = 4'd4;   4'd5:  harap = 4'd1;
            4'd6:  harap = 4'd4;   4'd7:  harap = 4'd9;
            4'd8:  harap = 4'd5;   4'd9:  harap = 4'd9;
            4'd10: harap = 4'd0;   4'd11: harap = 4'd6;
            4'd12: harap = 4'd9;   4'd13: harap = 4'd0;
            4'd14: harap = 4'd3;   default: harap = 4'd8;
        endcase
    end

    wire cocok = ada_hasil && (hasil == harap);

    // ==================================================================
    //  Tampilan
    // ==================================================================
    // biner 14 bit ke empat digit BCD (double dabble), dibatasi 9999
    function [15:0] ke_bcd;
        input [13:0] bin;
        integer i;
        reg [29:0] s;
        begin
            s = {16'd0, bin};
            for (i = 0; i < 14; i = i + 1) begin
                if (s[17:14] >= 4'd5) s[17:14] = s[17:14] + 4'd3;
                if (s[21:18] >= 4'd5) s[21:18] = s[21:18] + 4'd3;
                if (s[25:22] >= 4'd5) s[25:22] = s[25:22] + 4'd3;
                if (s[29:26] >= 4'd5) s[29:26] = s[29:26] + 4'd3;
                s = s << 1;
            end
            ke_bcd = s[29:14];
        end
    endfunction

    // siklus per citra = siklus batch / 16, dibulatkan
    wire [15:0] siklus_citra  = (siklus_r + 16'd8) >> 4;
    wire [13:0] siklus_tampil = (siklus_citra > 16'd9999) ? 14'd9999 : siklus_citra[13:0];

    wire [3:0] idx_puluh  = (idx >= 4'd10) ? 4'd1 : 4'd0;
    wire [3:0] idx_satuan = (idx >= 4'd10) ? (idx - 4'd10) : idx;

    wire [15:0] tampil = mode_siklus ? ke_bcd(siklus_tampil)
                                     : {idx_puluh, idx_satuan, harap, hasil};
    wire [3:0]  titik  = mode_siklus ? 4'b0000 : 4'b0100;

    seg7_scan #(.PEMBAGI(PINDAI),
                .SEG_AKTIF_RENDAH(SEG_AKTIF_RENDAH),
                .DIG_AKTIF_RENDAH(DIG_AKTIF_RENDAH))
    u_scan (.clk(clk), .rst_n(rst_n),
            .nilai(tampil), .titik(titik), .seg(seg), .dig(dig));

    // ---- LED: detak 1 Hz tanda hidup ----
    reg [31:0] cacah_detak;
    reg        detak;
    always @(posedge clk) begin
        if (!rst_n) begin
            cacah_detak <= 32'd0;
            detak       <= 1'b0;
        end else if (cacah_detak >= SETENGAH_DETIK - 1) begin
            cacah_detak <= 32'd0;
            detak       <= ~detak;
        end else begin
            cacah_detak <= cacah_detak + 32'd1;
        end
    end

    wire [3:0] led_tinggi = {cocok, ada_hasil & ~cocok, mode_siklus, detak};
    assign led = LED_AKTIF_RENDAH ? ~led_tinggi : led_tinggi;

endmodule

`default_nettype wire
