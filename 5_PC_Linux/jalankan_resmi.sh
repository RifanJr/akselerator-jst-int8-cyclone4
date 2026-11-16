#!/usr/bin/env bash
# Pengukuran resmi pembanding PC di Linux (inti terisolasi), satu perintah.
#
# Jalankan dari mode teks (TTY, tanpa desktop), di folder Alur_Utama:
#     sudo bash 5_PC_Linux/jalankan_resmi.sh
#
# Urutan (total sekitar 33 menit):
#   1. waktu --inti 2                       latensi + throughput, satu inti terisolasi
#   2. waktu                                tanpa kunci inti (mode 1 thread dan bawaan)
#   3. ulang --kali 5 --detik 60 --inti 2   sesi daya penuh, INT8 dan FP32 bergantian
#
# Seluruh keluaran layar juga disimpan ke 5_PC_Linux/hasil/log_resmi_<tanggal>.txt.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$REPO/../.venv/bin/python}"
SKRIP="$REPO/5_PC_Linux/ukur_pc_linux.py"
HASIL="$REPO/5_PC_Linux/hasil"
INTI=2
CPU_UJI="$((2 * INTI))-$((2 * INTI + 1))"

gagal() { echo "BERHENTI: $*" >&2; exit 1; }

# --- Pengecekan awal ---------------------------------------------------------
[ "$(id -u)" -eq 0 ] || gagal "harus dijalankan dengan sudo: sudo bash 5_PC_Linux/jalankan_resmi.sh"
[ -x "$PY" ] || gagal "Python venv tidak ditemukan di $PY"

isolasi="$(cat /sys/devices/system/cpu/isolated)"
[ "$isolasi" = "$CPU_UJI" ] || gagal "isolasi CPU $CPU_UJI tidak aktif (isolated='$isolasi'). Cek GRUB lalu reboot."
nohz="$(cat /sys/devices/system/cpu/nohz_full)"
[ "$nohz" = "$CPU_UJI" ] || gagal "nohz_full CPU $CPU_UJI tidak aktif (nohz_full='$nohz')."

listrik=0
for d in /sys/class/power_supply/*; do
    if [ "$(cat "$d/type" 2>/dev/null)" = "Mains" ] && [ "$(cat "$d/online" 2>/dev/null)" = "1" ]; then
        listrik=1
    fi
done
[ "$listrik" -eq 1 ] || gagal "charger tidak tersambung. Colokkan charger dulu."

profil="$(powerprofilesctl get 2>/dev/null || cat /sys/firmware/acpi/platform_profile)"
[ "$profil" = "balanced" ] || gagal "mode daya bukan Balanced (sekarang: '$profil')."

mkdir -p "$HASIL"
CAP="$(date +%Y%m%d_%H%M%S)"
LOG="$HASIL/log_resmi_$CAP.txt"
exec > >(tee -a "$LOG") 2>&1

echo "=== Pengukuran resmi PC Linux, mulai $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "isolated=$isolasi  nohz_full=$nohz  charger=tersambung  mode daya=$profil"
echo "cmdline: $(cat /proc/cmdline)"
if systemctl is-active --quiet graphical.target; then
    echo "PERINGATAN: desktop (graphical.target) masih aktif. Untuk data resmi, jalankan dari mode teks."
else
    echo "desktop: tidak aktif (mode teks)"
fi
echo "Perkiraan selesai: $(date -d '+33 min' '+%H:%M'). Jangan memakai laptop sampai selesai."
echo

cd "$REPO"

echo "### 1/3  waktu --inti $INTI   ($(date '+%H:%M:%S'))"
"$PY" -u "$SKRIP" waktu --inti "$INTI"
echo

echo "### 2/3  waktu (tanpa kunci inti)   ($(date '+%H:%M:%S'))"
"$PY" -u "$SKRIP" waktu
echo

echo "### 3/3  ulang --kali 5 --detik 60 --inti $INTI   ($(date '+%H:%M:%S'))"
"$PY" -u "$SKRIP" ulang --kali 5 --detik 60 --inti "$INTI"
echo

echo "=== SELESAI $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Log lengkap: $LOG"
echo "Kembali ke desktop: sudo systemctl isolate graphical.target   (atau: sudo reboot)"

# kembalikan kepemilikan berkas ke pengguna asli
if [ -n "${SUDO_USER:-}" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$HASIL"
fi
