# ============================================================================
#  laporan_tahap.tcl — Tugas 4: delay per tahap unit MAC (tanpa kompilasi ulang)
#
#  Dijalankan oleh LAPORAN_TAHAP.bat:
#     quartus_sta -t laporan_tahap.tcl <revisi> <folder_keluaran>
#  dari folder 8_Varian_Pengali (basis data hasil kompilasi 3 Nov).
#
#  Untuk tiap model timing (Slow 85C, Slow 0C, Fast 0C) ditulis:
#     fmax_<model>.rpt        ringkasan Fmax
#     terburuk_<model>.rpt    10 jalur setup terburuk, rincian penuh
#     tahap1_<model>.rpt      memori -> pengali -> p_q (register di dalam u_mac)
#     tahap2_<model>.rpt      p_q -> MUX -> penjumlah -> acc/m_acc
#     epilog_<model>.rpt      jalur yang berakhir di epilog_unit
#     argmax_<model>.rpt      jalur yang berakhir di argmax10 (konteks, milik Student B)
#  Setiap laporan memakai -detail full_path, jadi delay sel (CELL) dan
#  interkoneksi (IC) terlihat per simpul.
# ============================================================================
set rev  [lindex $argv 0]
set out  [lindex $argv 1]
file mkdir $out

project_open $rev -revision $rev
create_timing_netlist
read_sdc
update_timing_netlist

proc lapor {nama dari ke file} {
    # Koleksi kosong tidak menghentikan skrip; dicatat di berkas.
    if {[catch {
        set f [get_registers $dari]
        set t [get_registers $ke]
        if {[get_collection_size $f] == 0 || [get_collection_size $t] == 0} {
            set h [open $file w]
            puts $h "TIDAK ADA REGISTER COCOK: dari={$dari} ([get_collection_size $f]) ke={$ke} ([get_collection_size $t])"
            close $h
            return
        }
        report_timing -setup -npaths 5 -detail full_path -from $f -to $t \
            -panel_name $nama -file $file
    } err]} {
        set h [open $file w]; puts $h "GALAT: $err"; close $h
    }
}

foreach kondisi {{slow 85 1200 slow85} {slow 0 1200 slow0} {fast 0 1200 fast0}} {
    lassign $kondisi model suhu tegangan tag
    if {[catch {set_operating_conditions -model $model -temperature $suhu -voltage $tegangan} err]} {
        set h [open "$out/kondisi_$tag.txt" w]; puts $h "GALAT kondisi: $err"; close $h
        continue
    }
    update_timing_netlist
    report_clock_fmax_summary -file "$out/fmax_$tag.rpt"
    report_timing -setup -npaths 10 -detail full_path -file "$out/terburuk_$tag.rpt"

    # Tahap 1: dari register memori ke register mana pun di u_mac.
    # Pada HARD, p_q bisa terkemas ke register keluaran blok pengali,
    # jadi tujuan dibuat lebar (*u_mac*) lalu dibaca di rincian jalurnya.
    lapor "tahap1_$tag" {*u_mem_d* *u_mem_w*} {*u_mac*p_q*} "$out/tahap1_$tag.rpt"
    lapor "tahap1lebar_$tag" {*u_mem_d* *u_mem_w*} {*u_mac*} "$out/tahap1lebar_$tag.rpt"
    # Tahap 2: dari p_q (atau register keluaran blok pengali pada HARD) ke akumulator.
    lapor "tahap2_$tag" {*u_mac*p_q* *u_mac*mac_out*} {*u_mac*acc*} "$out/tahap2_$tag.rpt"
    lapor "epilog_$tag" {*} {*u_epi*} "$out/epilog_$tag.rpt"
    lapor "argmax_$tag" {*} {*u_amax*} "$out/argmax_$tag.rpt"
}

delete_timing_netlist
project_close
