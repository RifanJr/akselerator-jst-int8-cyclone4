// ============================================================================
//  ctrl_nlr.v
//  Pengendali rancangan TANPA STATIONARY (No Local Reuse, NLR) untuk
//  akselerator JST 196-64-10, 8 lajur MAC. Rincian: 7_NLR/SPESIFIKASI_NLR.md.
//
//  Prinsip (Sze dkk., 2017, hlm. 15): tidak ada data yang ditahan di unit MAC.
//  Setiap operasi mengambil bobot, masukan, DAN jumlah parsial dari memori,
//  lalu mengembalikan jumlah parsial yang baru ke memori:
//
//      psum[n] = psum[n] (dari memori) + x_i * w[n][i]   -> ditulis ke memori
//
//  mac_unit.v dipakai TANPA diubah dengan s_first = s_last = 1 pada setiap
//  operasi, sehingga akumulatornya tidak pernah membawa nilai dari satu
//  operasi ke operasi berikutnya. Nilai awalnya (s_init) adalah jumlah parsial
//  dari memori, atau bias pada suku pertama.
//
//  ---------------------------------------------------------------------
//  URUTAN DAN JARAK BACA-SETELAH-TULIS
//
//  Lajur j mengerjakan neuron j, j+8, j+16, ... (sama dengan OS). Pada setiap
//  masukan i, lajur bergantian mengerjakan K neuronnya, satu per siklus:
//
//      untuk i: untuk k = 0..K-1:   lajur j: neuron j + 8k
//
//  Jumlah parsial neuron yang sama baru dibaca lagi K siklus kemudian.
//  Pewaktuannya:
//      t    : alamat bobot, masukan, dan jumlah parsial diberikan
//      t+2  : ketiganya tiba di MAC (latensi memori 2)
//      t+4  : hasil MAC keluar dan ditulis ke memori (latensi MAC 2)
//      t+5  : paling cepat nilai baru boleh dibaca lagi
//  Jadi K harus >= 5.
//      Lapisan 1: 64 neuron / 8 lajur -> K = 8, tanpa slot kosong.
//      Lapisan 2: 10 neuron           -> K2 = 5, slot k = 2..4 kosong.
//
//  ---------------------------------------------------------------------
//  HASIL AKHIR KE MEMORI, LALU DIKURAS
//
//  Suku terakhir pun ditulis ke memori jumlah parsial seperti suku lain
//  ("output activations are then put back to the global buffer"). Setelah
//  seluruh suku satu lapisan selesai, isi memori dikuras satu per satu:
//      lapisan 1: 64 nilai -> epilog (ReLU, geser 8) -> mem_d alamat 196..259
//      lapisan 2: 10 nilai -> argmax
//
//  Alamat bobot memakai berkas bank OS (P8) tanpa diubah:
//      lapisan 1: k*196 + i         lapisan 2: 1568 + k*64 + i
// ============================================================================
`default_nettype none

module ctrl_nlr #(
    parameter P        = 8,
    parameter N_INPUT  = 196,
    parameter N_HIDDEN = 64,
    parameter N_OUTPUT = 10,
    parameter DW       = 8,
    parameter ACCW     = 32,
    parameter AW_W     = 11,
    parameter AW_D     = 9,
    parameter AW_P     = 3,           // memori jumlah parsial: 8 kata per lajur
    parameter K1       = 8,           // slot per masukan, lapisan 1
    parameter K2       = 5,           // slot per masukan, lapisan 2 (jarak aman)
    parameter GESER_BIAS_1 = 4,
    parameter GESER_BIAS_2 = 1
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     start,

    // ---- memori bobot (sama untuk kedelapan bank) dan memori data ----
    output wire [AW_W-1:0]          addr_w,
    output wire [AW_D-1:0]          addr_d,
    output wire                     mem_en,

    // ---- ROM bias berkelompok ----
    output wire [3:0]               kel_bias,
    input  wire [P*DW-1:0]          bias8,

    // ---- memori jumlah parsial, satu per lajur ----
    output wire [P-1:0]             ps_rd_en,
    output wire [AW_P-1:0]          ps_rd_addr,
    input  wire [P*ACCW-1:0]        ps_q,
    output wire [P-1:0]             ps_wr_en,
    output wire [AW_P-1:0]          ps_wr_addr,

    // ---- lajur MAC ----
    output wire [P-1:0]             s_valid,
    output wire [P*ACCW-1:0]        s_init,
    input  wire [P-1:0]             m_valid,

    // ---- pengurasan ----
    output wire signed [ACCW-1:0]   acc_kuras,
    output wire                     epi_valid,
    output wire [4:0]               cfg_shift,
    output wire                     cfg_round,
    output wire                     cfg_relu,
    input  wire                     epi_out_valid,
    output wire                     wr_en,
    output wire [AW_D-1:0]          wr_addr,
    output wire                     amax_valid,
    output wire [3:0]               amax_idx,

    // ---- status ----
    output reg                      done,
    output wire                     sibuk
);

    localparam N_A    = N_HIDDEN / P;          // 8 kelompok lapisan 1
    localparam AWAL_2 = N_A * N_INPUT;         // 1568, awal bobot lapisan 2

    localparam [2:0] S_IDLE    = 3'd0,
                     S_HITUNG  = 3'd1,         // suku dialirkan, satu slot per siklus
                     S_KURAS   = 3'd2,         // hasil akhir dibaca dari memori
                     S_AKHIR   = 3'd3,         // tunggu argmax menerima hasil terakhir
                     S_SELESAI = 3'd4;

    reg [2:0] state;
    reg       lapisan2;
    reg [7:0] i;               // indeks masukan
    reg [2:0] k;               // slot (neuron ke-k milik lajur)
    reg [6:0] n;               // neuron yang sedang dikuras
    reg [1:0] tunggu;

    wire [7:0] n_suku = lapisan2 ? N_HIDDEN[7:0] : N_INPUT[7:0];
    wire [2:0] k_maks = lapisan2 ? (K2[2:0] - 3'd1) : (K1[2:0] - 3'd1);
    wire [6:0] n_maks = lapisan2 ? (N_OUTPUT[6:0] - 7'd1) : (N_HIDDEN[6:0] - 7'd1);

    wire hitung = (state == S_HITUNG);
    wire kuras  = (state == S_KURAS);
    wire slot_akhir  = (k == k_maks);
    wire suku_akhir  = (i == n_suku - 8'd1);

    // ------------------------------------------------------------------
    //  Lajur yang sah pada slot ini: neuron j + 8k harus ada
    // ------------------------------------------------------------------
    wire [P-1:0] topeng;
    genvar gj;
    generate
        for (gj = 0; gj < P; gj = gj + 1) begin : g_topeng
            wire [6:0] neuron = {1'b0, k, 3'b000} + gj;
            assign topeng[gj] = hitung &
                (lapisan2 ? (neuron < N_OUTPUT[6:0]) : 1'b1);
        end
    endgenerate
    wire ada_lajur = |topeng;

    // ------------------------------------------------------------------
    //  Alamat (tahap t)
    // ------------------------------------------------------------------
    // slot kosong pada lapisan 2 diarahkan ke alamat slot 0 supaya tetap di
    // dalam bank; datanya tidak pernah dipakai
    wire [2:0]      k_alamat = ada_lajur ? k : 3'd0;
    wire [AW_W-1:0] i_w      = {{(AW_W-8){1'b0}}, i};
    wire [AW_W-1:0] k_w      = {{(AW_W-3){1'b0}}, k_alamat};
    assign addr_w = lapisan2 ? (AWAL_2[AW_W-1:0] + (k_w << 6) + i_w)          // k*64
                             : ((k_w << 7) + (k_w << 6) + (k_w << 2) + i_w);  // k*196
    assign addr_d = lapisan2 ? (N_INPUT[AW_D-1:0] + {{(AW_D-8){1'b0}}, i})
                             : {{(AW_D-8){1'b0}}, i};
    assign kel_bias = lapisan2 ? (N_A[3:0] + {1'b0, k_alamat}) : {1'b0, k};

    // memori bobot dan data menahan pipanya saat en rendah, jadi en dibiarkan
    // menyala dua siklus setelah slot terakhir agar data terakhir sempat keluar
    reg hitung_d1, hitung_d2;
    assign mem_en = hitung | hitung_d1 | hitung_d2;

    // ------------------------------------------------------------------
    //  Memori jumlah parsial
    // ------------------------------------------------------------------
    wire [AW_P-1:0] n_kata  = n[5:3];          // neuron n: lajur n%8, kata n/8
    wire [2:0]      n_lajur = n[2:0];
    assign ps_rd_addr = kuras ? n_kata : k;

    genvar gr;
    generate
        for (gr = 0; gr < P; gr = gr + 1) begin : g_baca
            // suku pertama memakai bias, tidak membaca memori
            assign ps_rd_en[gr] = (topeng[gr] & (i != 8'd0))
                                | (kuras & (n_lajur == gr));
        end
    endgenerate

    // ------------------------------------------------------------------
    //  Pipa penanda: tahap t -> t+2 (MAC) -> t+4 (tulis)
    // ------------------------------------------------------------------
    reg [P-1:0]    top_d1, top_d2;
    reg            awal_d1, awal_d2;           // suku pertama: pakai bias
    reg            lap2_d1, lap2_d2;
    reg [2:0]      k_d1, k_d2, k_d3, k_d4;
    reg [P*DW-1:0] bias_d1, bias_d2;
    reg            kuras_d1, kuras_d2;
    reg [6:0]      n_d1, n_d2, n_d3;
    reg            lap2k_d1, lap2k_d2;

    assign s_valid = top_d2;

    genvar gi;
    generate
        for (gi = 0; gi < P; gi = gi + 1) begin : g_init
            wire signed [DW-1:0]   b     = bias_d2[gi*DW +: DW];
            wire signed [ACCW-1:0] b_ext = {{(ACCW-DW){b[DW-1]}}, b};
            wire signed [ACCW-1:0] b_sel = lap2_d2 ? (b_ext <<< GESER_BIAS_2)
                                                  : (b_ext <<< GESER_BIAS_1);
            assign s_init[gi*ACCW +: ACCW] = awal_d2 ? b_sel : ps_q[gi*ACCW +: ACCW];
        end
    endgenerate

    // setiap hasil MAC (termasuk suku terakhir) kembali ke memori
    assign ps_wr_en   = m_valid;
    assign ps_wr_addr = k_d4;

    // ------------------------------------------------------------------
    //  Pengurasan: data tiba dua siklus setelah alamat
    // ------------------------------------------------------------------
    reg signed [ACCW-1:0] kuras_pilih;
    integer t;
    always @(*) begin
        kuras_pilih = ps_q[0 +: ACCW];
        for (t = 0; t < P; t = t + 1)
            if (n_d2[2:0] == t[2:0]) kuras_pilih = ps_q[t*ACCW +: ACCW];
    end
    assign acc_kuras = kuras_pilih;

    assign epi_valid  = kuras_d2 & ~lap2k_d2;
    assign amax_valid = kuras_d2 &  lap2k_d2;
    assign amax_idx   = n_d2[3:0];
    assign cfg_shift  = 5'd8;
    assign cfg_round  = 1'b0;
    assign cfg_relu   = 1'b1;

    // tulis aktivasi menyusul keluaran epilog satu siklus
    assign wr_en   = epi_out_valid;
    assign wr_addr = N_INPUT[AW_D-1:0] + {{(AW_D-7){1'b0}}, n_d3};

    assign sibuk = (state != S_IDLE) && (state != S_SELESAI);

    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            hitung_d1 <= 1'b0;  hitung_d2 <= 1'b0;
            top_d1 <= {P{1'b0}};  top_d2 <= {P{1'b0}};
            awal_d1 <= 1'b0;  awal_d2 <= 1'b0;
            lap2_d1 <= 1'b0;  lap2_d2 <= 1'b0;
            k_d1 <= 3'd0;  k_d2 <= 3'd0;  k_d3 <= 3'd0;  k_d4 <= 3'd0;
            bias_d1 <= {(P*DW){1'b0}};  bias_d2 <= {(P*DW){1'b0}};
            kuras_d1 <= 1'b0;  kuras_d2 <= 1'b0;
            n_d1 <= 7'd0;  n_d2 <= 7'd0;  n_d3 <= 7'd0;
            lap2k_d1 <= 1'b0;  lap2k_d2 <= 1'b0;
        end else begin
            hitung_d1 <= hitung;            hitung_d2 <= hitung_d1;
            top_d1    <= topeng;            top_d2    <= top_d1;
            awal_d1   <= (i == 8'd0);       awal_d2   <= awal_d1;
            lap2_d1   <= lapisan2;          lap2_d2   <= lap2_d1;
            k_d1      <= k;   k_d2 <= k_d1; k_d3 <= k_d2;  k_d4 <= k_d3;
            bias_d1   <= bias8;             bias_d2   <= bias_d1;
            kuras_d1  <= kuras;             kuras_d2  <= kuras_d1;
            n_d1      <= n;   n_d2 <= n_d1; n_d3 <= n_d2;
            lap2k_d1  <= lapisan2;          lap2k_d2  <= lap2k_d1;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            lapisan2 <= 1'b0;
            i        <= 8'd0;
            k        <= 3'd0;
            n        <= 7'd0;
            tunggu   <= 2'd0;
            done     <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        state    <= S_HITUNG;
                        lapisan2 <= 1'b0;
                        i        <= 8'd0;
                        k        <= 3'd0;
                    end
                end

                S_HITUNG: begin
                    if (slot_akhir) begin
                        k <= 3'd0;
                        if (suku_akhir) begin
                            i     <= 8'd0;
                            n     <= 7'd0;
                            state <= S_KURAS;
                        end else begin
                            i <= i + 8'd1;
                        end
                    end else begin
                        k <= k + 3'd1;
                    end
                end

                // Hasil akhir lapisan dikuras satu per siklus. Kata yang dikuras
                // pertama (kata 0) sudah selesai ditulis sebelum dibaca; kata
                // berikutnya dibaca jauh setelah penulisan terakhirnya.
                S_KURAS: begin
                    if (n == n_maks) begin
                        if (lapisan2) begin
                            state  <= S_AKHIR;
                            tunggu <= 2'd0;
                        end else begin
                            lapisan2 <= 1'b1;
                            i        <= 8'd0;
                            k        <= 3'd0;
                            state    <= S_HITUNG;
                        end
                    end else begin
                        n <= n + 7'd1;
                    end
                end

                // nilai terakhir tiba di argmax dua siklus setelah dibaca
                S_AKHIR: begin
                    if (tunggu == 2'd2) begin
                        state <= S_SELESAI;
                        done  <= 1'b1;
                    end else begin
                        tunggu <= tunggu + 2'd1;
                    end
                end

                S_SELESAI: if (start) state <= S_IDLE;

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule

`default_nettype wire
