@echo off
title Tugas 4 - delay per tahap (quartus_sta, tanpa kompilasi ulang)
set STA=C:\altera_lite\25.1std\quartus\bin64\quartus_sta.exe
cd /d "%~dp0..\..\8_Varian_Pengali"
for %%v in (hard arith struct) do (
    echo.
    echo ===== %%v =====
    "%STA%" -t "%~dp0laporan_tahap.tcl" daya_%%v "%~dp0..\hasil\T4\%%v"
)
echo.
echo Selesai. Hasil ada di 9_Analisis_MAC\hasil\T4\
pause
