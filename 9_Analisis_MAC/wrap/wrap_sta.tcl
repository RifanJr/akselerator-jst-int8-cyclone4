# quartus_sta -t wrap_sta.tcl <revisi>
# Jalur setup terburuk reg -> reg pada model bawaan Slow 1200mV 85C.
set rev [lindex $argv 0]
project_open $rev -revision $rev
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -npaths 1 -detail full_path -file "hasil_sta/${rev}_slow85.rpt"
delete_timing_netlist
project_close
