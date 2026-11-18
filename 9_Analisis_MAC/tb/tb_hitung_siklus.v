`timescale 1 ps/1 ps
// ============================================================================
//  tb_hitung_siklus.v  --  Tugas 9: rincian 1.708 siklus inferensi top_papan
//
//  Meng-instansiasi top_papan TANPA mengubahnya dan hanya membaca sinyal
//  internal pengendali (dut.u_ctrl). Pewaktuan dan definisi jendela sama
//  dengan 6_Daya_FPGA/tb_jendela_os.v (Student B): jendela = siklus saat
//  sinyal sibuk = 1, dicuplik di tepi turun.
//
//  Setiap siklus jendela masuk tepat SATU kategori eksklusif:
//    L1   : beat MAC lapisan 1 (s_valid & semua s_ready, lapisan2 = 0)
//    L2   : beat MAC lapisan 2
//    ALIR : state S_ALIR tanpa beat (gelembung di dalam aliran)
//    EKOR : state S_HABIS (suku habis, menunggu pipa MAC + pengurasan terakhir)
//    LAIN : selain itu
//  Penghitung tumpang-tindih (berjalan sejajar dengan kategori di atas):
//    KURAS (menguras=1), EPI (epi_valid), AMAX (amax_valid), TULIS (wr_en)
// ============================================================================
module tb_hitung_siklus;
    reg clk = 0; always #10000 clk = ~clk;      // 50 MHz
    reg [3:0] key = 4'b1111;
    wire [3:0] led; wire [7:0] seg; wire [3:0] dig;
    top_papan dut(.clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));

    integer n = 0, mulai = -1, selesai = -1, cocok = -1;
    integer c_l1 = 0, c_l2 = 0, c_alir = 0, c_ekor = 0, c_lain = 0;
    integer c_kuras = 0, c_epi = 0, c_amax = 0, c_tulis = 0;
    integer awal_l2 = -1, akhir_beat = -1;
    wire beat = dut.u_ctrl.s_valid & (&dut.u_ctrl.s_ready_lajur);

    always @(posedge clk) n = n + 1;
    always @(negedge clk) begin
        if (mulai < 0 && dut.sibuk === 1'b1) mulai = n;
        if (mulai >= 0 && selesai < 0) begin
            if (dut.sibuk === 1'b0) selesai = n;
            else begin
                if (beat && !dut.u_ctrl.lapisan2) begin c_l1 = c_l1 + 1; akhir_beat = n; end
                else if (beat) begin c_l2 = c_l2 + 1; akhir_beat = n; if (awal_l2 < 0) awal_l2 = n; end
                else if (dut.u_ctrl.state == 2'd1) c_alir = c_alir + 1;
                else if (dut.u_ctrl.state == 2'd2) c_ekor = c_ekor + 1;
                else c_lain = c_lain + 1;
                if (dut.u_ctrl.menguras) c_kuras = c_kuras + 1;
                if (dut.u_ctrl.epi_valid) c_epi = c_epi + 1;
                if (dut.u_ctrl.amax_valid) c_amax = c_amax + 1;
                if (dut.u_ctrl.wr_en) c_tulis = c_tulis + 1;
            end
        end
        if (cocok < 0 && led[3] === 1'b0) cocok = n;
        if (selesai >= 0 && cocok >= 0) begin
            $display("SIKLUS total=%0d mulai=%0d selesai=%0d papan=%0d led_cocok=%0d",
                     selesai - mulai, mulai, selesai, dut.siklus_r, cocok);
            $display("EKSKLUSIF L1=%0d L2=%0d ALIR=%0d EKOR=%0d LAIN=%0d jumlah=%0d",
                     c_l1, c_l2, c_alir, c_ekor, c_lain, c_l1 + c_l2 + c_alir + c_ekor + c_lain);
            $display("SEJAJAR KURAS=%0d EPI=%0d AMAX=%0d TULIS=%0d", c_kuras, c_epi, c_amax, c_tulis);
            $display("WAKTU awal_beat_L2=%0d beat_terakhir=%0d ekor_setelah_beat_terakhir=%0d",
                     awal_l2 - mulai, akhir_beat - mulai, selesai - akhir_beat - 1);
            $finish;
        end
        if (n > 5000) begin $display("GAGAL: inferensi tidak selesai"); $finish; end
    end
endmodule
