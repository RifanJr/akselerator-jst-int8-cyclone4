// ============================================================================
//  top_papan.v
//  Akselerator JST INT8 P = 8 pada papan Cyclone IV — rancangan demonstrasi.
//
//  ---------------------------------------------------------------------
//  HUBUNGAN DENGAN top_akselerator_p8.v
//
//  Jalur data di berkas ini SAMA PERSIS dengan top_akselerator_p8.v: modul
//  yang sama (mem_w, mem_d, mac_unit, epilog_unit, argmax10, rom_bias8,
//  ctrl_fsm_p8), parameter yang sama, sambungan yang sama. top_akselerator_p8
//  sengaja TIDAK diubah, karena itulah rancangan yang sudah diukur dan angka
//  sintesisnya sudah dilaporkan.
//
//  Tambahannya hanya SATU: mux pada port tulis mem_d, supaya citra uji dapat
//  dimuat ke alamat piksel 0..195 sebelum inferensi dimulai. Saat akselerator
//  berjalan, mux itu selalu memilih jalur tulis aktivasi milik pengendali.
//  Kesetaraannya dibuktikan oleh tb_papan.v: 16 citra, hasil identik.
//
//  ---------------------------------------------------------------------
//  CARA PAKAI DI PAPAN
//
//  Saat dinyalakan, citra 00 langsung dimuat dan dijalankan.
//
//    key[0]  citra berikutnya, lalu jalankan
//    key[1]  citra sebelumnya, lalu jalankan
//    key[2]  jalankan ulang citra yang sama
//    key[3]  DITAHAN: tampilkan jumlah siklus inferensi terakhir (harus 1816)
//
//  Tampilan normal, dari kiri ke kanan:
//
//      [puluhan][satuan.][prediksi Python][hasil papan]
//
//  contoh "00.77": citra 00, Python menebak 7, papan menebak 7.
//  Dua digit kanan harus selalu sama.
//
//    led[3]  menyala bila hasil papan = prediksi Python
//    led[2]  menyala bila berbeda
//    led[1]  menyala selama mode siklus (key[3] ditahan)
//    led[0]  berkedip 1 Hz, tanda rancangan hidup
//
//  Hasil uji papan 30 September 2026: urutan nomor LED di papan TERBALIK
//  dari indeks di sini (LED paling kiri = led[3]). Urutan fisik tombol belum
//  diketahui, jadi cukup coba satu per satu.
//
//  Polaritas default di bawah sudah terbukti benar oleh uji_papan.v.
// ============================================================================
`default_nettype none

module top_papan #(
    parameter LED_AKTIF_RENDAH = 1,
    parameter SEG_AKTIF_RENDAH = 1,
    parameter DIG_AKTIF_RENDAH = 1,
    parameter KEY_AKTIF_RENDAH = 1,

    parameter MULT_STYLE   = "HARD",
    parameter DIR_W        = "../1_Python_PC/mem/P8",
    parameter BERKAS_D     = "../1_Python_PC/mem/mem_d.hex",
    parameter BERKAS_CITRA = "../1_Python_PC/uji/citra_papan.hex",

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

    // ---- ukuran rancangan, sama dengan top_akselerator_p8 ----
    localparam P        = 8;
    localparam N_INPUT  = 196;
    localparam N_HIDDEN = 64;
    localparam N_OUTPUT = 10;
    localparam DW       = 8;
    localparam ACCW     = 32;
    localparam AW_W     = 11;
    localparam AW_D     = 9;
    localparam DEPTH_W  = 1696;

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
    //  Jalur data akselerator — salinan sambungan top_akselerator_p8
    // ==================================================================
    wire [AW_W-1:0] addr_w;
    wire [AW_D-1:0] addr_d;
    wire            mem_en;
    wire [3:0]      kel_bias;
    wire [P*DW-1:0] bias8;

    wire signed [DW-1:0] d_q;

    wire            s_valid, s_first, s_last;
    wire [P-1:0]    s_ready_lajur, m_valid_lajur, m_ready_lajur;
    wire [P*ACCW-1:0] s_init;
    wire [2:0]      pilih_lajur;

    wire            epi_valid, epi_out_valid;
    wire signed [DW-1:0] epi_act;
    wire [4:0]      cfg_shift;
    wire            cfg_round, cfg_relu;
    wire            wr_en;
    wire [AW_D-1:0] wr_addr;
    wire            amax_valid;
    wire [3:0]      amax_idx;

    wire            start;
    wire            done, sibuk;
    wire [3:0]      hasil;
    wire signed [ACCW-1:0] hasil_nilai;

    // ---- SATU-SATUNYA TAMBAHAN: mux port tulis mem_d untuk memuat citra ----
    wire            muat_we;
    wire [AW_D-1:0] muat_addr;
    wire [DW-1:0]   muat_data;

    mem_d #(.DW(DW), .DEPTH(N_INPUT + N_HIDDEN), .AW(AW_D), .BERKAS(BERKAS_D))
    u_mem_d (.clk(clk),
             .rd_en(mem_en), .rd_addr(addr_d), .rd_q(d_q),
             .wr_en  (muat_we | wr_en),
             .wr_addr(muat_we ? muat_addr : wr_addr),
             .wr_data(muat_we ? muat_data : epi_act));

    rom_bias8 u_bias (.kelompok(kel_bias), .dout(bias8));

    wire signed [ACCW-1:0] m_acc_lajur [0:P-1];

    genvar j;
    generate
        for (j = 0; j < P; j = j + 1) begin : g_lajur
            wire signed [DW-1:0] w_q;

            localparam BERKAS_BANK =
                (j == 0) ? {DIR_W, "/mem_w_b0.hex"} :
                (j == 1) ? {DIR_W, "/mem_w_b1.hex"} :
                (j == 2) ? {DIR_W, "/mem_w_b2.hex"} :
                (j == 3) ? {DIR_W, "/mem_w_b3.hex"} :
                (j == 4) ? {DIR_W, "/mem_w_b4.hex"} :
                (j == 5) ? {DIR_W, "/mem_w_b5.hex"} :
                (j == 6) ? {DIR_W, "/mem_w_b6.hex"} :
                           {DIR_W, "/mem_w_b7.hex"};

            mem_w #(.DW(DW), .DEPTH(DEPTH_W), .AW(AW_W), .BERKAS(BERKAS_BANK))
            u_mem_w (.clk(clk), .en(mem_en), .addr(addr_w), .q(w_q));

            mac_unit #(.DW(DW), .ACCW(ACCW), .MULT_STYLE(MULT_STYLE),
                       .PIPE_MULT(0), .HAS_EPILOG(0))
            u_mac (.clk(clk), .rst_n(rst_n),
                   .s_valid(s_valid), .s_ready(s_ready_lajur[j]),
                   .s_x(d_q), .s_w(w_q),
                   .s_first(s_first), .s_last(s_last),
                   .s_init(s_init[j*ACCW +: ACCW]),
                   .cfg_shift(5'd0), .cfg_round(1'b0), .cfg_relu(1'b0),
                   .m_valid(m_valid_lajur[j]), .m_ready(m_ready_lajur[j]),
                   .m_acc(m_acc_lajur[j]), .m_act(), .m_ovf());
        end
    endgenerate

    reg signed [ACCW-1:0] acc_terpilih;
    integer t;
    always @(*) begin
        acc_terpilih = m_acc_lajur[0];
        for (t = 0; t < P; t = t + 1)
            if (pilih_lajur == t[2:0]) acc_terpilih = m_acc_lajur[t];
    end

    epilog_unit #(.DW(DW), .ACCW(ACCW))
    u_epi (.clk(clk), .rst_n(rst_n),
           .in_valid(epi_valid), .in_acc(acc_terpilih),
           .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
           .out_valid(epi_out_valid), .out_act(epi_act), .out_ovf());

    argmax10 #(.ACCW(ACCW), .IW(4))
    u_amax (.clk(clk), .rst_n(rst_n), .mulai(start),
            .in_valid(amax_valid), .in_acc(acc_terpilih), .in_idx(amax_idx),
            .idx_maks(hasil), .nilai_maks(hasil_nilai), .ada());

    ctrl_fsm_p8 #(.P(P), .N_INPUT(N_INPUT), .N_HIDDEN(N_HIDDEN),
                  .N_OUTPUT(N_OUTPUT), .DW(DW), .ACCW(ACCW),
                  .AW_W(AW_W), .AW_D(AW_D))
    u_ctrl (.clk(clk), .rst_n(rst_n), .start(start),
            .addr_w(addr_w), .addr_d(addr_d), .mem_en(mem_en),
            .kel_bias(kel_bias), .bias8(bias8),
            .s_valid(s_valid), .s_ready_lajur(s_ready_lajur),
            .s_first(s_first), .s_last(s_last), .s_init(s_init),
            .m_valid_lajur(m_valid_lajur), .m_ready_lajur(m_ready_lajur),
            .pilih_lajur(pilih_lajur),
            .epi_valid(epi_valid),
            .cfg_shift(cfg_shift), .cfg_round(cfg_round), .cfg_relu(cfg_relu),
            .epi_out_valid(epi_out_valid), .wr_en(wr_en), .wr_addr(wr_addr),
            .amax_valid(amax_valid), .amax_idx(amax_idx),
            .done(done), .sibuk(sibuk));

    // ==================================================================
    //  Tombol: penyelaras dua flip-flop, lalu dicuplik tiap 10 ms.
    //  Pantulan kontak mekanis jauh lebih singkat dari selang cuplikan,
    //  sehingga cuplikan itu sendiri sudah berfungsi sebagai peredam.
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
    // denyut satu siklus tepat saat sebuah tombol mulai ditekan
    wire [3:0] tekan = {4{cuplik_d}} & k_stabil & ~k_lalu;
    wire       mode_siklus = k_stabil[3];

    // ==================================================================
    //  ROM 16 citra uji, masing-masing 256 alamat (196 piksel dipakai)
    // ==================================================================
    (* ramstyle = "M9K" *) reg [7:0] citra [0:4095];
    initial $readmemh(BERKAS_CITRA, citra);

    reg  [3:0] idx;          // citra yang sedang dipakai
    reg  [7:0] p;            // indeks piksel yang sedang dibaca dari ROM
    reg  [7:0] citra_q;
    always @(posedge clk) citra_q <= citra[{idx, p}];

    // ==================================================================
    //  Pengurut: muat citra -> jalankan -> simpan hasil
    // ==================================================================
    localparam [2:0] F_DIAM     = 3'd0,
                     F_MUAT     = 3'd1,
                     F_TUNTAS   = 3'd2,
                     F_BANGUN   = 3'd3,
                     F_KE_DIAM  = 3'd4,
                     F_JALAN    = 3'd5,
                     F_SIMPAN   = 3'd6;

    reg [2:0]  fase;
    reg        start_r;
    reg        awal;              // jalankan citra 00 sekali saat dinyalakan
    reg        tulis_d;           // penunda satu siklus, sejajar dengan citra_q
    reg [7:0]  p_d;

    reg [15:0] cacah_siklus;
    reg [3:0]  hasil_r;
    reg signed [ACCW-1:0] nilai_r;
    reg [15:0] siklus_r;
    reg        ada_hasil;
    reg [15:0] jumlah_hasil;      // bertambah tiap inferensi selesai (untuk testbench)

    assign start     = start_r;
    assign muat_we   = tulis_d;
    assign muat_addr = {{(AW_D-8){1'b0}}, p_d};
    assign muat_data = citra_q;

    always @(posedge clk) begin
        if (!rst_n) begin
            fase         <= F_DIAM;
            start_r      <= 1'b0;
            awal         <= 1'b1;
            idx          <= 4'd0;
            p            <= 8'd0;
            tulis_d      <= 1'b0;
            p_d          <= 8'd0;
            cacah_siklus <= 16'd0;
            hasil_r      <= 4'd0;
            nilai_r      <= {ACCW{1'b0}};
            siklus_r     <= 16'd0;
            ada_hasil    <= 1'b0;
            jumlah_hasil <= 16'd0;
        end else begin
            // data ROM keluar satu siklus setelah alamatnya, jadi alamat
            // tulis dan izin tulis ikut ditunda satu siklus
            tulis_d <= (fase == F_MUAT);
            p_d     <= p;

            // jumlah siklus dihitung persis seperti di testbench:
            // setiap detak ketika pengendali sibuk
            if (fase == F_BANGUN)  cacah_siklus <= 16'd0;
            else if (sibuk)        cacah_siklus <= cacah_siklus + 16'd1;

            case (fase)
                F_DIAM: begin
                    start_r <= 1'b0;
                    p       <= 8'd0;
                    if (awal) begin
                        awal <= 1'b0;
                        idx  <= 4'd0;
                        fase <= F_MUAT;
                    end else if (tekan[0]) begin
                        idx  <= idx + 4'd1;
                        fase <= F_MUAT;
                    end else if (tekan[1]) begin
                        idx  <= idx - 4'd1;
                        fase <= F_MUAT;
                    end else if (tekan[2]) begin
                        fase <= F_MUAT;
                    end
                end

                // 196 piksel disalin dari ROM ke mem_d alamat 0..195
                F_MUAT: begin
                    if (p == N_INPUT[7:0] - 8'd1) fase <= F_TUNTAS;
                    else                          p    <= p + 8'd1;
                end

                // piksel terakhir tertulis pada akhir siklus ini
                F_TUNTAS: fase <= F_BANGUN;

                // Pengendali yang baru selesai berada di keadaan SELESAI dan
                // butuh satu denyut start untuk kembali ke IDLE, baru denyut
                // berikutnya menjalankan inferensi. Setelah dinyalakan ia
                // sudah di IDLE, jadi cukup satu denyut.
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
                    hasil_r      <= hasil;
                    nilai_r      <= hasil_nilai;
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

    wire cocok = ada_hasil && (hasil_r == harap);

    // ==================================================================
    //  Tampilan
    // ==================================================================
    // biner 14 bit ke empat digit BCD (double dabble), dibatasi 9999
    function [15:0] ke_bcd;
        input [13:0] b;
        integer i;
        reg [29:0] s;
        begin
            s = {16'd0, b};
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

    wire [13:0] siklus_tampil = (siklus_r > 16'd9999) ? 14'd9999 : siklus_r[13:0];

    wire [3:0] idx_puluh  = (idx >= 4'd10) ? 4'd1 : 4'd0;
    wire [3:0] idx_satuan = (idx >= 4'd10) ? (idx - 4'd10) : idx;

    wire [15:0] tampil = mode_siklus ? ke_bcd(siklus_tampil)
                                     : {idx_puluh, idx_satuan, harap, hasil_r};
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
