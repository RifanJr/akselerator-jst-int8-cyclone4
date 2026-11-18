#!/bin/bash
# Gerbang perubahan RTL Student A. Dijalankan dari akar repo dengan Icarus Verilog.
#   gerbang.sh g1 datar|terpecah   (vektor uji dibangkitkan dulu oleh rtl_uji/buat_vektor_uji.py) tb_mac_unit.v x {ARITH,STRUCT,HARD} x PIPE {0,1}
#   gerbang.sh t2                  tb_mult8.v: 65.536 pasangan masukan untuk ketiga pengali
#   gerbang.sh g3                  2_Verilog/jalankan_papan.py (18/18, 1.708 siklus)
# versi datar   = 2_Verilog/mac_unit.v dan epilog_unit.v (dipakai OS, WS, NLR)
# versi terpecah = 9_Analisis_MAC/rtl_terpecah/ (hanya untuk pengukuran per komponen;
#                  jangan dikompilasi bersama berkas 2_Verilog karena nama modulnya sama)
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
UJI=$REPO/9_Analisis_MAC/rtl_uji
LOG=$REPO/9_Analisis_MAC/hasil/gerbang
mkdir -p "$LOG"
case "$1" in
g1)
  if [ "$2" = terpecah ]; then SRC=$REPO/9_Analisis_MAC/rtl_terpecah; else SRC=$REPO/2_Verilog; fi
  W=$(mktemp -d); python3 "$UJI/buat_vektor_uji.py" "$W" >/dev/null   # vektor uji dari 1_Python_PC/Training/export_final
  for s in ARITH STRUCT HARD; do for p in 0 1; do
    iverilog -g2012 -P tb_mac_unit.STYLE=\"$s\" -P tb_mac_unit.PIPE=$p -o "$W/sim_${s}_$p" \
      "$UJI/tb_mac_unit.v" "$SRC/mac_unit.v" "$SRC/epilog_unit.v" "$REPO/2_Verilog/mult_bw8_arith.v" \
      "$REPO/2_Verilog/mult_bw8_struct.v" "$REPO/2_Verilog/mult_hard8.v" 2>&1 | grep -v "Attributes are not supported"
    (cd "$W" && vvp "sim_${s}_$p") > "$LOG/G1_$2_${s}_pipe$p.txt"
    echo "G1 $2 $s PIPE=$p : $(grep HASIL "$LOG/G1_$2_${s}_pipe$p.txt")"
  done; done ;;
t2)
  W=$(mktemp -d)
  iverilog -g2012 -o "$W/t8" "$UJI/tb_mult8.v" "$REPO/2_Verilog/mult_bw8_arith.v" \
    "$REPO/2_Verilog/mult_bw8_struct.v" "$REPO/2_Verilog/mult_hard8.v" 2>&1 | grep -v "Attributes are not supported"
  vvp "$W/t8" | tee "$LOG/../T2_uji_tuntas_mult8.txt" | grep HASIL ;;
g3)
  (cd "$REPO/2_Verilog" && python3 jalankan_papan.py) | tail -5 ;;
esac
