# ============================================================================
#  papan.sdc -- rancangan papan top_papan.v
#  Clock papan 50 MHz. Tombol ditekan manusia, LED dan seven-segment dilihat
#  manusia, jadi jalur masuk-keluarnya tidak perlu dianalisis pewaktuannya.
# ============================================================================

create_clock -name clk -period 20.000 [get_ports clk]
derive_clock_uncertainty

set_false_path -from [get_ports {key[*]}]
set_false_path -to   [get_ports {led[*]}]
set_false_path -to   [get_ports {seg[*]}]
set_false_path -to   [get_ports {dig[*]}]
