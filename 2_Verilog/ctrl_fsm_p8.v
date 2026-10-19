// ============================================================================
//  ctrl_fsm_p8.v
//  Pengendali orkestrasi memori untuk konfigurasi P lajur paralel.
//
//  Turunan dari ctrl_fsm.v (P = 1) dengan tiga perubahan pokok:
//
//  ---------------------------------------------------------------------
//  1. SATU PENCACAH UNTUK SELURUH BANK
//
//  Bank ke-j memegang neuron j, j+P, j+2P, ... Karena polanya simetris,
//  kedelapan bank tetap dialamati oleh SATU pencacah yang sama. Alamatnya
//  pun tetap naik satu demi satu tanpa pernah direset, persis seperti P = 1.
//  Inilah buah dari tata letak berbank yang dirancang di Fase 1.
//
//      lapisan 1 : g*196 + i            g = 0..nA-1, i = 0..195
//      lapisan 2 : nA*196 + g*64 + i    g = 0..nB-1, i = 0..63
//      nA = ceil(64/P) = 8      nB = ceil(10/P) = 2
//
//  Memori data TIDAK dipecah: kedelapan lajur membaca piksel yang SAMA pada
//  saat yang sama, jadi satu mem_d melayani semuanya lewat satu port baca.
//
//  ---------------------------------------------------------------------
//  2. PENGURASAN HASIL
//
//  Kedelapan lajur menerima s_valid, s_first, dan s_last yang sama, sehingga
//  kedelapannya selesai pada siklus yang SAMA PERSIS. Sementara epilog dan
//  port tulis mem_d hanya satu. Karena itu hasilnya dikuras satu per satu
//  selama P siklus, dan selama itu lajur berhenti menerima masukan.
//
//  Ongkosnya P siklus per kelompok neuron: 10 kelompok x 8 = 80 siklus dari
//  total sekitar 1.776. Ini DILAPORKAN APA ADANYA, bukan disembunyikan --
//  percepatan nyatanya 7,4x, bukan 8x.
//
//  Menghilangkan 80 siklus itu bisa, dengan menambah register penangkap
//  32 bit di tiap lajur (8 x 32 = 256 register) supaya MAC tidak perlu
//  menunggu. Tidak dilakukan karena menukar 4,5 persen kecepatan dengan
//  9 persen logic element adalah pertukaran yang merugikan.
//
//  ---------------------------------------------------------------------
//  3. TOPENG LAJUR PADA LAPISAN 2
//
//  Lapisan 2 punya 10 neuron, tidak habis dibagi 8. Kelompok terakhir hanya
//  memuat 2 neuron yang sah; enam lajur sisanya tetap menghitung tetapi
//  hasilnya DIBUANG, tidak pernah sampai ke argmax.
//
//  Lapisan 1 tidak perlu topeng karena 64 habis dibagi 8.
// ============================================================================
`default_nettype none

module ctrl_fsm_p8 #(
    parameter P        = 8,
    parameter N_INPUT  = 196,
    parameter N_HIDDEN = 64,
    parameter N_OUTPUT = 10,
    parameter DW       = 8,
    parameter ACCW     = 32,
    parameter AW_W     = 11,          // 2^11 = 2048 >= 1696 per bank
    parameter AW_D     = 9,
    parameter GESER_BIAS_1 = 4,
    parameter GESER_BIAS_2 = 1
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     start,

    // ---- ke memori ----
    output wire [AW_W-1:0]          addr_w,       // sama untuk kedelapan bank
    output wire [AW_D-1:0]          addr_d,
    output wire                     mem_en,

    // ---- ke ROM bias berkelompok ----
    output wire [3:0]               kel_bias,
    input  wire [P*DW-1:0]          bias8,

    // ---- ke seluruh lajur MAC (disiarkan sama) ----
    output reg                      s_valid,
    input  wire [P-1:0]             s_ready_lajur,
    output reg                      s_first,
    output reg                      s_last,
    output reg  [P*ACCW-1:0]        s_init,

    // ---- dari lajur MAC ----
    input  wire [P-1:0]             m_valid_lajur,
    output wire [P-1:0]             m_ready_lajur,

    // ---- pemilih lajur yang sedang dikuras ----
    output wire [2:0]               pilih_lajur,

    // ---- ke epilog, hanya lapisan 1 ----
    output wire                     epi_valid,
    output wire [4:0]               cfg_shift,
    output wire                     cfg_round,
    output wire                     cfg_relu,

    // ---- tulis balik aktivasi ----
    input  wire                     epi_out_valid,
    output wire                     wr_en,
    output wire [AW_D-1:0]          wr_addr,

    // ---- ke argmax, hanya lapisan 2 ----
    output wire                     amax_valid,
    output wire [3:0]               amax_idx,

    // ---- status ----
    output reg                      done,
    output wire                     sibuk
);

    localparam N_A = (N_HIDDEN + P - 1) / P;      // 8 kelompok lapisan 1
    localparam N_B = (N_OUTPUT + P - 1) / P;      // 2 kelompok lapisan 2

    localparam [2:0] S_IDLE    = 3'd0,
                     S_ALIR    = 3'd1,
                     S_KURAS   = 3'd2,
                     S_TUNGGU  = 3'd3,
                     S_SELESAI = 3'd4;

    reg [2:0] state;
    reg       lapisan2;

    reg [AW_W-1:0] cnt_w;      // alamat bobot, tidak pernah direset
    reg [7:0]      i;          // indeks suku
    reg [3:0]      g;          // indeks kelompok neuron
    reg [2:0]      k;          // lajur yang sedang dikuras

    wire [7:0] n_suku = lapisan2 ? N_HIDDEN[7:0] : N_INPUT[7:0];
    wire [3:0] n_kel  = lapisan2 ? N_B[3:0]      : N_A[3:0];

    wire suku_akhir = (i == n_suku - 8'd1);
    wire kel_akhir  = (g == n_kel - 4'd1);

    // ---- seluruh lajur harus siap, karena alamatnya bersama ----
    wire semua_siap = &s_ready_lajur;
    wire semua_hasil = &m_valid_lajur;

    wire alir = (state == S_ALIR);
    wire maju = alir & semua_siap;

    // ------------------------------------------------------------------
    //  Alamat
    // ------------------------------------------------------------------
    wire [AW_D-1:0] i_ext = {{(AW_D-8){1'b0}}, i};
    assign addr_w   = cnt_w;
    assign addr_d   = lapisan2 ? (N_INPUT[AW_D-1:0] + i_ext) : i_ext;
    assign kel_bias = lapisan2 ? (N_A[3:0] + g) : g;     // 0..7 L1, 8..9 L2
    assign mem_en   = semua_siap;

    // ------------------------------------------------------------------
    //  Nilai awal akumulator tiap lajur
    // ------------------------------------------------------------------
    wire [ACCW-1:0] init_lajur [0:P-1];
    genvar gi;
    generate
        for (gi = 0; gi < P; gi = gi + 1) begin : g_init
            wire signed [DW-1:0] b = bias8[gi*DW +: DW];
            wire signed [ACCW-1:0] b_ext = {{(ACCW-DW){b[DW-1]}}, b};
            assign init_lajur[gi] =
                lapisan2 ? (b_ext <<< GESER_BIAS_2) : (b_ext <<< GESER_BIAS_1);
        end
    endgenerate

    // ------------------------------------------------------------------
    //  Epilog: konfigurasinya tetap, hanya melayani lapisan 1
    // ------------------------------------------------------------------
    assign cfg_shift = 5'd8;
    assign cfg_round = 1'b0;
    assign cfg_relu  = 1'b1;

    // ------------------------------------------------------------------
    //  Pengurasan
    // ------------------------------------------------------------------
    wire menguras = (state == S_KURAS);

    // neuron global yang sedang dikuras
    wire [6:0] neuron_kuras = {3'b0, g} * P[6:0] + {4'b0, k};
    // pada lapisan 2 hanya neuron < 10 yang sah
    wire lajur_sah = lapisan2 ? (neuron_kuras < N_OUTPUT[6:0]) : 1'b1;

    assign pilih_lajur = k;

    // hanya lajur yang sedang dikuras yang boleh melepas hasilnya
    genvar gj;
    generate
        for (gj = 0; gj < P; gj = gj + 1) begin : g_rdy
            assign m_ready_lajur[gj] = menguras && (k == gj[2:0]);
        end
    endgenerate

    assign epi_valid  = menguras & ~lapisan2;
    assign amax_valid = menguras &  lapisan2 & lajur_sah;
    assign amax_idx   = neuron_kuras[3:0];

    // penulisan aktivasi menyusul keluaran epilog satu siklus
    reg [6:0] neuron_epi;
    assign wr_en   = epi_out_valid;
    assign wr_addr = N_INPUT[AW_D-1:0] + {{(AW_D-7){1'b0}}, neuron_epi};

    assign sibuk = (state != S_IDLE) && (state != S_SELESAI);

    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            lapisan2 <= 1'b0;
            cnt_w    <= {AW_W{1'b0}};
            i        <= 8'd0;
            g        <= 4'd0;
            k        <= 3'd0;
            v1       <= 1'b0;  f1 <= 1'b0;  l1 <= 1'b0;
            s_valid  <= 1'b0;  s_first <= 1'b0;  s_last <= 1'b0;
            done     <= 1'b0;
        end else begin
            // --- pipa penanda dua tahap, sejajar latensi memori ---
            if (semua_siap) begin
                v1 <= maju;
                if (maju) begin
                    f1 <= (i == 8'd0);
                    l1 <= suku_akhir;
                end
                s_valid <= v1;
                if (v1) begin
                    s_first <= f1;
                    s_last  <= l1;
                end
            end

            if (maju) begin
                cnt_w <= cnt_w + 1'b1;
                if (suku_akhir) i <= 8'd0;
                else            i <= i + 1'b1;
            end

            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        state    <= S_ALIR;
                        lapisan2 <= 1'b0;
                        cnt_w    <= {AW_W{1'b0}};
                        i        <= 8'd0;
                        g        <= 4'd0;
                        k        <= 3'd0;
                    end
                end

                // Alamat kelompok ini habis -> tunggu hasilnya keluar,
                // baru dikuras. TIDAK menghitung siklus, menunggu m_valid.
                S_ALIR: if (maju && suku_akhir) begin
                    state <= S_TUNGGU;
                end

                S_TUNGGU: if (semua_hasil) begin
                    state <= S_KURAS;
                    k     <= 3'd0;
                end

                S_KURAS: begin
                    if (k == P[2:0] - 3'd1) begin
                        k <= 3'd0;
                        if (kel_akhir) begin
                            if (lapisan2) begin
                                state <= S_SELESAI;
                                done  <= 1'b1;
                            end else begin
                                // pindah ke lapisan 2; cnt_w SENGAJA tidak
                                // direset, nilainya sudah nA*196 = 1568
                                lapisan2 <= 1'b1;
                                g        <= 4'd0;
                                i        <= 8'd0;
                                state    <= S_ALIR;
                            end
                        end else begin
                            g     <= g + 4'd1;
                            state <= S_ALIR;
                        end
                    end else begin
                        k <= k + 3'd1;
                    end
                end

                S_SELESAI: if (start) state <= S_IDLE;

                default: state <= S_IDLE;
            endcase
        end
    end

    // tahap pertama pipa penanda
    reg v1, f1, l1;

    // ------------------------------------------------------------------
    //  Nilai awal disiarkan ke seluruh lajur, ikut pipa dua tahap
    // ------------------------------------------------------------------
    reg [P*ACCW-1:0] init1;
    integer t;
    always @(posedge clk) begin
        if (!rst_n) begin
            init1  <= {(P*ACCW){1'b0}};
            s_init <= {(P*ACCW){1'b0}};
        end else if (semua_siap) begin
            if (maju)
                for (t = 0; t < P; t = t + 1)
                    init1[t*ACCW +: ACCW] <= init_lajur[t];
            if (v1) s_init <= init1;
        end
    end

    // ------------------------------------------------------------------
    //  Indeks neuron untuk penulisan aktivasi, sejajar keluaran epilog
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) neuron_epi <= 7'd0;
        else if (epi_valid) neuron_epi <= neuron_kuras;
    end

endmodule

`default_nettype wire
