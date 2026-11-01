// ============================================================================
//  ctrl_ws.v
//  Pengendali orkestrasi memori untuk larik weight-stationary (WS) 4 x 2,
//  batch B = 16. Rincian rancangan: 4_WS/SPESIFIKASI_WS.md.
//
//  ---------------------------------------------------------------------
//  1. URUTAN KERJA (loop nest)
//
//      lapisan 1, lalu lapisan 2
//        g = pasangan neuron (2g, 2g+1)          32 pasang / 5 pasang
//          t = ubin 4 suku masukan               49 ubin  / 16 ubin
//            b = citra 0..15                     bobot DIAM 16 siklus
//
//  Setiap siklus pengendali mengeluarkan satu "token" (lapisan, g, t, b).
//  Tidak pernah ada jeda: semua memori selalu siap dan MAC tidak pernah
//  ditahan, jadi token keluar berturut-turut dari awal sampai akhir.
//
//  ---------------------------------------------------------------------
//  2. PEWAKTUAN TOKEN (siklus setelah token dikeluarkan)
//
//      +0   alamat masukan t*16 + b ke ROM citra / buffer aktivasi
//      +2   kata masukan tiba = beat PE baris 0 (latensi memori 2 siklus)
//      +2+2r beat PE baris r (tiap MAC berlatensi 2 siklus)
//      +10  hasil keluar dari dasar kolom (PE baris 3)
//      +12  argmax (3 tahap pipa) selesai memperbarui citra token itu
//
//  Penanda token (valid, lapisan, ubin pertama/terakhir, g, b) dialirkan
//  lewat register geser 10 tahap supaya tiba bersama datanya.
//
//  ---------------------------------------------------------------------
//  3. BOBOT BERPENYANGGA GANDA
//
//  Bobot satu ubin dibaca dari 8 bank SEKALI saja, lalu dipakai 16 citra.
//  Bank bobot hanya diaktifkan (en_w) satu siklus per ubin, supaya blok
//  M9K memang membaca sekali per ubin, bukan setiap siklus.
//
//  mem_w.v (dipakai tanpa diubah) punya dua tahap register dengan satu
//  clock-enable. Satu pulsa en_w sekaligus membaca kata baru ke tahap 1 dan
//  menggeser kata sebelumnya ke keluaran q. Karena itu alamat bobot berjalan
//  DUA ubin di depan (prefetch):
//      PRA        en_w dua kali (alamat 0 dan 1); q = ubin 0
//      ubin k, b = 8   en_w dengan alamat k+2;   q = ubin k+1
//      ubin k, b = 10  q disalin ke register BAYANGAN
//      ubin k, b = 1 + 2r  register AKTIF baris r disalin dari bayangan,
//                      satu siklus sebelum beat pertama baris r di ubin k
//  Bayangan berganti isi (b = 10) hanya setelah baris 3 menyalin (b = 7)
//  dan sebelum baris 0 menyalin lagi (b = 1 ubin berikutnya).
//
//  Jumlah pembacaan bank per batch = 2 (PRA) + 1647 = 1649: 1648 kata unik
//  ditambah satu baca ulang kata terakhir, karena alamat berhenti di 1647
//  sementara q masih perlu digeser sekali lagi.
//
//  Pencacah alamat bobot SATU untuk kedelapan bank dan tidak pernah
//  di-reset di antara lapisan: 0..1567 lapisan 1, 1568..1647 lapisan 2.
// ============================================================================
`default_nettype none

module ctrl_ws #(
    parameter DW   = 8,
    parameter ACCW = 32,
    parameter AW_W = 11,
    parameter GESER_BIAS_1 = 4,
    parameter GESER_BIAS_2 = 1
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     start,

    // ---- ke 8 bank bobot dan register bobot larik ----
    output wire [AW_W-1:0]          addr_w,
    output wire                     en_w,           // aktifkan bank bobot
    output wire                     isi_bayangan,
    output wire [3:0]               muat_aktif,     // satu bit per baris

    // ---- ke ROM citra dan buffer aktivasi ----
    output wire [9:0]               addr_in,        // t*16 + b
    output wire                     en_in,          // baca masukan hanya saat ada token
    output wire                     lap_token,      // lapisan token yang sedang keluar

    // ---- sejajar beat PE baris 0 (token + 2) ----
    output wire                     in_valid,
    output wire                     pilih_l2,       // 1 = masukan dari buffer aktivasi
    output wire                     pakai_bias,     // ubin pertama
    output wire signed [ACCW-1:0]   bias0,
    output wire signed [ACCW-1:0]   bias1,

    // ---- sejajar keluaran dasar kolom (token + 10) ----
    output wire                     akhir_l1,       // hasil akhir lapisan 1 -> epilog
    output wire                     akhir_l2,       // hasil akhir lapisan 2 -> argmax
    output wire [4:0]               g_dasar,
    output wire [3:0]               b_dasar,

    // ---- konfigurasi epilog, hanya lapisan 1 ----
    output wire [4:0]               cfg_shift,
    output wire                     cfg_round,
    output wire                     cfg_relu,

    // ---- status ----
    output reg                      done,
    output wire                     sibuk
);

    localparam [2:0] S_IDLE    = 3'd0,
                     S_PRA     = 3'd1,    // isi bobot ubin pertama
                     S_ALIR    = 3'd2,    // token keluar tanpa henti
                     S_HABIS   = 3'd3,    // token habis, tunggu yang terakhir tiba di dasar
                     S_SELESAI = 3'd4;

    reg [2:0]      state;
    reg [1:0]      pra;

    // ---- pencacah token ----
    reg            lap;        // 0 = lapisan 1, 1 = lapisan 2
    reg [4:0]      g;
    reg [5:0]      t;
    reg [3:0]      b;
    reg [AW_W-1:0] wa;         // alamat bobot = nomor ubin global

    // indeks terakhir tiap pencacah: lapisan 1 (49 ubin, 32 pasang),
    // lapisan 2 (16 ubin, 5 pasang)
    wire [5:0] t_terakhir = lap ? 6'd15 : 6'd48;
    wire [4:0] g_terakhir = lap ? 5'd4  : 5'd31;

    wire b_akhir     = (b == 4'd15);
    wire t_akhir     = (t == t_terakhir);
    wire g_akhir     = (g == g_terakhir);
    wire ubin_akhir  = lap & g_akhir & t_akhir;   // ubin terakhir seluruh batch
    wire token_akhir = ubin_akhir & b_akhir;

    wire alir = (state == S_ALIR);

    // ------------------------------------------------------------------
    //  Alamat
    // ------------------------------------------------------------------
    assign addr_in = {t, b};                      // t*16 + b
    assign en_in   = alir;
    assign lap_token = lap;
    assign addr_w  = wa;

    localparam [AW_W-1:0] WA_AKHIR = 11'd1647;    // kata terakhir bank bobot

    assign en_w = ((state == S_PRA) && (pra != 2'd2)) ||
                  (alir && (b == 4'd8) && !ubin_akhir);

    assign isi_bayangan = ((state == S_PRA) && (pra == 2'd2)) ||
                          (alir && (b == 4'd10) && !ubin_akhir);

    assign muat_aktif[0] = alir && (b == 4'd1);
    assign muat_aktif[1] = alir && (b == 4'd3);
    assign muat_aktif[2] = alir && (b == 4'd5);
    assign muat_aktif[3] = alir && (b == 4'd7);

    // ------------------------------------------------------------------
    //  Penanda token, dialirkan 12 tahap
    //  {valid, lapisan, ubin_pertama, ubin_terakhir, akhir_batch, g, b}
    // ------------------------------------------------------------------
    localparam TW = 1 + 1 + 1 + 1 + 1 + 5 + 4;
    wire [TW-1:0] token = {alir, lap, (t == 6'd0), t_akhir, token_akhir, g, b};

    reg [TW-1:0] pipa [1:12];
    integer s;
    always @(posedge clk) begin
        if (!rst_n) begin
            for (s = 1; s <= 12; s = s + 1) pipa[s] <= {TW{1'b0}};
        end else begin
            pipa[1] <= token;
            for (s = 2; s <= 12; s = s + 1) pipa[s] <= pipa[s-1];
        end
    end

    // tahap 2: beat PE baris 0
    wire       v2     = pipa[2][TW-1];
    wire       lap2   = pipa[2][TW-2];
    wire       awal2  = pipa[2][TW-3];
    wire [4:0] g2     = pipa[2][8:4];

    // tahap 10: dasar kolom
    wire       v10     = pipa[10][TW-1];
    wire       lap10   = pipa[10][TW-2];
    wire       akhir10 = pipa[10][TW-4];

    // tahap 12: argmax selesai memperbarui citra token ini
    wire       v12     = pipa[12][TW-1];
    wire       batch12 = pipa[12][TW-5];

    assign in_valid   = v2;
    assign pilih_l2   = lap2;
    assign pakai_bias = v2 & awal2;

    assign akhir_l1 = v10 & akhir10 & ~lap10;
    assign akhir_l2 = v10 & akhir10 &  lap10;
    assign g_dasar  = pipa[10][8:4];
    assign b_dasar  = pipa[10][3:0];

    // ------------------------------------------------------------------
    //  Bias pasangan neuron (2g, 2g+1), dari rom_bias8 tanpa diubah.
    //  rom_bias8 mengeluarkan 8 bias per kelompok 8 neuron berurutan:
    //  kelompok g/4 (lapisan 1) atau 8 + g/4 (lapisan 2), lajur 2*(g mod 4).
    // ------------------------------------------------------------------
    wire [3:0]  kelompok = lap2 ? (4'd8 + {1'b0, g2[4:2]}) : {1'b0, g2[4:2]};
    wire [63:0] bias8;
    rom_bias8 u_bias (.kelompok(kelompok), .dout(bias8));

    wire signed [DW-1:0] bias_a = bias8[{g2[1:0], 1'b0, 3'b000} +: DW];
    wire signed [DW-1:0] bias_b = bias8[{g2[1:0], 1'b1, 3'b000} +: DW];
    wire signed [ACCW-1:0] bias_a_ext = {{(ACCW-DW){bias_a[DW-1]}}, bias_a};
    wire signed [ACCW-1:0] bias_b_ext = {{(ACCW-DW){bias_b[DW-1]}}, bias_b};

    assign bias0 = lap2 ? (bias_a_ext <<< GESER_BIAS_2) : (bias_a_ext <<< GESER_BIAS_1);
    assign bias1 = lap2 ? (bias_b_ext <<< GESER_BIAS_2) : (bias_b_ext <<< GESER_BIAS_1);

    // ------------------------------------------------------------------
    //  Epilog: konfigurasi tetap, sama dengan rancangan OS
    // ------------------------------------------------------------------
    assign cfg_shift = 5'd8;
    assign cfg_round = 1'b0;
    assign cfg_relu  = 1'b1;

    assign sibuk = (state != S_IDLE) && (state != S_SELESAI);

    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            pra   <= 2'd0;
            lap   <= 1'b0;
            g     <= 5'd0;
            t     <= 6'd0;
            b     <= 4'd0;
            wa    <= {AW_W{1'b0}};
            done  <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        state <= S_PRA;
                        pra   <= 2'd0;
                        lap   <= 1'b0;
                        g     <= 5'd0;
                        t     <= 6'd0;
                        b     <= 4'd0;
                        wa    <= {AW_W{1'b0}};
                    end
                end

                // pra 0, 1: bank membaca alamat 0 dan 1; pra 2: ubin 0 ke bayangan
                S_PRA: begin
                    if (pra == 2'd2) begin
                        state <= S_ALIR;
                    end else begin
                        pra <= pra + 2'd1;
                        wa  <= wa + 1'b1;
                    end
                end

                S_ALIR: begin
                    // prefetch: setelah dibaca pada b = 8, alamat maju satu
                    if (en_w && (wa != WA_AKHIR))
                        wa <= wa + 1'b1;

                    // pencacah bersarang: b -> t -> g -> lapisan
                    if (b_akhir) begin
                        b <= 4'd0;
                        if (t_akhir) begin
                            t <= 6'd0;
                            if (g_akhir) begin
                                g <= 5'd0;
                                if (lap) state <= S_HABIS;
                                else     lap   <= 1'b1;
                            end else begin
                                g <= g + 5'd1;
                            end
                        end else begin
                            t <= t + 6'd1;
                        end
                    end else begin
                        b <= b + 4'd1;
                    end
                end

                // token terakhir sudah melewati dasar kolom dan argmax
                // (3 tahap pipa) -> selesai
                S_HABIS: if (v12 && batch12) begin
                    state <= S_SELESAI;
                    done  <= 1'b1;
                end

                S_SELESAI: if (start) state <= S_IDLE;

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule

`default_nettype wire
