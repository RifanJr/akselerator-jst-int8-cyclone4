`timescale 1 ps/1 ps
// ============================================================================
//  tb_jendela_ws.v  --  cari jendela inferensi batch di simulasi RTL
//
//  Setelah dinyalakan, top_papan_ws menjalankan ke-16 citra uji sekaligus
//  (satu batch) tanpa perlu menekan tombol. Testbench ini mencatat nomor
//  siklus saat pengendali mulai sibuk dan saat selesai, supaya simulasi
//  netlist (tb_netlist_ws.v) merekam VCD HANYA selama inferensi.
//
//  Pewaktuan clock dan penomoran siklus SAMA dengan tb_netlist_ws.v dan
//  dengan 6_Daya_FPGA/tb_jendela_os.v (rancangan OS).
// ============================================================================
module tb_jendela_ws;
    reg clk = 0; always #10000 clk = ~clk;      // 50 MHz
    reg [3:0] key = 4'b1111;                    // tombol dilepas
    wire [3:0] led; wire [7:0] seg; wire [3:0] dig;
    top_papan_ws dut(.clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));

    // n = jumlah tepi naik sejak awal; dicuplik di tepi turun supaya bebas balapan
    integer n = 0, mulai = -1, selesai = -1, cocok = -1;
    always @(posedge clk) n = n + 1;
    always @(negedge clk) begin
        if (mulai < 0 && dut.sibuk === 1'b1) mulai = n;
        if (mulai >= 0 && selesai < 0 && dut.sibuk === 1'b0) selesai = n;
        if (cocok < 0 && led[3] === 1'b0) cocok = n;
        if (cocok >= 0) begin
            $display("JENDELA mulai=%0d selesai=%0d siklus=%0d led_cocok=%0d siklus_papan=%0d",
                     mulai, selesai, selesai - mulai, cocok, dut.siklus_r);
            $finish;
        end
        if (n > 40000) begin $display("GAGAL: inferensi tidak selesai"); $finish; end
    end
endmodule
