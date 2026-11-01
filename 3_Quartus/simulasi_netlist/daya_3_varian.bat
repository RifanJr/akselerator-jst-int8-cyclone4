@echo off
title Analisis daya 3 varian (HARD, ARITH, STRUCT)
cd /d "%~dp0.."
set "Q=C:\altera_lite\25.1std\quartus\bin64"
for %%R in (papan:papan_hard:output_papan papan_arith:papan_arith:output_arith papan_struct:papan_struct:output_struct) do (
  for /f "tokens=1-3 delims=:" %%a in ("%%R") do (
    echo Daya %%a ...
    "%Q%\quartus_pow.exe" --read_settings_files=on --write_settings_files=off papan -c %%a > "%~dp0log_daya_%%a.txt" 2>&1
    if errorlevel 1 (echo GAGAL %%a, lihat simulasi_netlist\log_daya_%%a.txt & pause & exit /b 1)
    if not exist "hasil_mentah\2026-11-01_daya_%%b" mkdir "hasil_mentah\2026-11-01_daya_%%b"
    copy /y %%c\%%a.pow.rpt "hasil_mentah\2026-11-01_daya_%%b\" >nul
    copy /y %%c\%%a.pow.summary "hasil_mentah\2026-11-01_daya_%%b\" >nul
    type %%c\%%a.pow.summary
  )
)
echo.
echo SELESAI analisis daya ketiga varian.
pause
