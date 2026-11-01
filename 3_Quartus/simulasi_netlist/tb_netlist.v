`timescale 1 ps/1 ps
module tb_netlist;
  reg clk = 0; always #10000 clk = ~clk;      // 50 MHz
  reg [3:0] key = 4'b1111;
  wire [3:0] led; wire [7:0] seg; wire [3:0] dig;
  top_papan dut(.clk(clk), .key(key), .led(led), .seg(seg), .dig(dig));
  integer n = 0, t_cocok = -1, t_beda = -1;
  always @(posedge clk) begin
    n = n + 1;
    if (t_cocok < 0 && led[3] === 1'b0) begin t_cocok = n; $display("LED cocok menyala pada siklus %0d", n); end
    if (t_beda  < 0 && led[2] === 1'b0) begin t_beda  = n; $display("LED beda menyala pada siklus %0d", n); end
  end
  initial begin
`ifdef VCD
    $dumpfile("papan_netlist.vcd"); $dumpvars(1, dut);
`endif
    repeat (`SIKLUS) @(posedge clk);
    $display("SELESAI siklus=%0d led=%b cocok=%0d beda=%0d", n, led, t_cocok, t_beda);
    $finish;
  end
endmodule
