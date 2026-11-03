// ============================================================================
//  argmax_batch.v
//  Argmax lapisan keluaran untuk 16 citra sekaligus.
//
//  Hasil akhir lapisan 2 keluar dari dasar kolom sepasang-sepasang:
//  neuron 2g dan 2g+1 milik citra b, untuk g = 0..4 berurutan. Tiap citra
//  punya register nilai terbesar dan indeksnya sendiri.
//
//  Masukannya akumulator 32 bit, bukan keluaran epilog (sama dengan
//  argmax10.v pada rancangan OS). Pembandingnya ">" dan kandidat diperiksa
//  menurut urutan neuron (2g lalu 2g+1, g naik), sehingga bila ada nilai
//  kembar yang LEBIH DULU menang, sama dengan np.argmax pada acuan Python.
//
//  Tiga tahap pipa, supaya pemilih 16 citra dan dua pembanding 32 bit tidak
//  berantai dalam satu siklus (jalur itu sempat menjadi jalur terpanjang
//  seluruh rancangan, padahal bukan bagian dataflow WS):
//      tahap 1: tangkap masukan dan isi lama citra in_b
//      tahap 2: bandingkan kandidat neuron 2g
//      tahap 3: bandingkan kandidat neuron 2g+1, lalu tulis
//  Aman karena citra yang sama baru diperbarui lagi setelah 256 siklus
//  (sekali per pasangan neuron), jauh lebih lama dari 3 tahap pipa ini.
//  Hasil citra b siap 3 siklus setelah in_valid.
// ============================================================================
`default_nettype none

module argmax_batch #(
    parameter ACCW = 32,
    parameter B    = 16
)(
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    mulai,       // kosongkan sebelum batch baru

    input  wire                    in_valid,
    input  wire [3:0]              in_b,        // citra
    input  wire [3:0]              in_idx0,     // neuron 2g; kandidat kedua 2g+1
    input  wire signed [ACCW-1:0]  in_acc0,
    input  wire signed [ACCW-1:0]  in_acc1,

    // ---- pembacaan hasil satu citra ----
    input  wire [3:0]              pilih_b,
    output wire [3:0]              idx_maks,
    output wire signed [ACCW-1:0]  nilai_maks
);

    // Tetap register, bukan M9K: tampilan membaca idx secara asinkron, dan
    // keluaran M9K yang tidak diregister memperpanjang jalur pembanding.
    (* ramstyle = "logic" *) reg [3:0]             idx   [0:B-1];
    (* ramstyle = "logic" *) reg signed [ACCW-1:0] nilai [0:B-1];
    reg [B-1:0]           ada;

    // ------------------------------------------------------------------
    //  Tahap 1: tangkap masukan dan isi lama citra in_b
    // ------------------------------------------------------------------
    reg                   v1;
    reg [3:0]             b1, idx0_1;
    reg signed [ACCW-1:0] acc0_1, acc1_1;
    reg                   ada_lama;
    reg signed [ACCW-1:0] nilai_lama;
    reg [3:0]             idx_lama;

    always @(posedge clk) begin
        if (!rst_n) v1 <= 1'b0;
        else        v1 <= in_valid & ~mulai;
        b1         <= in_b;
        idx0_1     <= in_idx0;
        acc0_1     <= in_acc0;
        acc1_1     <= in_acc1;
        ada_lama   <= ada[in_b];
        nilai_lama <= nilai[in_b];
        idx_lama   <= idx[in_b];
    end

    // ------------------------------------------------------------------
    //  Tahap 2: kandidat neuron 2g
    // ------------------------------------------------------------------
    wire ambil0 = !ada_lama || (acc0_1 > nilai_lama);

    reg                   v2;
    reg [3:0]             b2, idx1_2, idx_a;
    reg signed [ACCW-1:0] acc1_2, nilai_a;

    always @(posedge clk) begin
        if (!rst_n) v2 <= 1'b0;
        else        v2 <= v1 & ~mulai;
        b2      <= b1;
        idx1_2  <= idx0_1 + 4'd1;
        acc1_2  <= acc1_1;
        nilai_a <= ambil0 ? acc0_1 : nilai_lama;
        idx_a   <= ambil0 ? idx0_1 : idx_lama;
    end

    // ------------------------------------------------------------------
    //  Tahap 3: kandidat neuron 2g+1, lalu tulis
    // ------------------------------------------------------------------
    wire ambil1 = (acc1_2 > nilai_a);

    always @(posedge clk) begin
        if (!rst_n) begin
            ada <= {B{1'b0}};
        end else if (mulai) begin
            ada <= {B{1'b0}};
        end else if (v2) begin
            nilai[b2] <= ambil1 ? acc1_2 : nilai_a;
            idx[b2]   <= ambil1 ? idx1_2 : idx_a;
            ada[b2]   <= 1'b1;
        end
    end

    assign idx_maks   = idx[pilih_b];
    assign nilai_maks = nilai[pilih_b];

endmodule

`default_nettype wire
