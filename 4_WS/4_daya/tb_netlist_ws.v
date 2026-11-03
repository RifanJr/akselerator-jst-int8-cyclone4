`timescale 1 ps/1 ps
// ============================================================================
//  tb_netlist_ws.v  --  simulasi netlist pascasintesis untuk analisis daya
//
//  Menjalankan netlist simulation/questa/daya_ws.vo (batch 16 citra berjalan
//  sendiri setelah dinyalakan) dan merekam VCD mulai siklus MULAI.
//  siapkan_vcd.py memotongnya pada siklus SELESAI, sehingga Power Analyzer
//  hanya melihat aktivitas selama inferensi, tanpa reset.
//
//  MULAI dan LED_COCOK diambil dari tb_jendela_ws.v (RTL). Netlist dianggap
//  benar bila LED "cocok" menyala pada siklus yang SAMA dengan RTL.
//
//  Sama dengan 6_Daya_FPGA/tb_netlist_os.v (rancangan OS), yang diadaptasi
//  dari 3_Quartus/simulasi_netlist/tb_netlist.v (Student A).
// ============================================================================
module tb_netlist_ws;
    reg clk = 0; always #10000 clk = ~clk;      // 50 MHz
    reg [3:0] key = 4'b1111;
    wire [3:0] led; wire [7:0] seg; wire [3:0] dig;
    top_papan_ws dut(.clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));

    integer n = 0, cocok = -1;
    always @(posedge clk) begin
        n = n + 1;
        if (n == `MULAI) begin
            $dumpfile("build/ws_netlist.vcd");
            $dumpvars(1, dut);
        end
    end
    always @(negedge clk) begin
        if (cocok < 0 && led[3] === 1'b0) cocok = n;
        if (n == `LED_COCOK + 2) begin
            $display("NETLIST led_cocok=%0d harap=%0d %s", cocok, `LED_COCOK,
                     cocok == `LED_COCOK ? "COCOK" : "BEDA");
            $finish;
        end
    end
endmodule
