@echo off
title Kompilasi varian ARITH dan STRUCT
cd /d "%~dp0.."
set "Q=C:\altera_lite\25.1std\quartus\bin64"
for %%V in (arith struct) do (
  echo Mengompilasi papan_%%V ... (beberapa menit^)
  "%Q%\quartus_sh.exe" --flow compile papan -c papan_%%V > "%~dp0log_kompilasi_%%V.txt" 2>&1
  if errorlevel 1 (echo GAGAL papan_%%V, lihat simulasi_netlist\log_kompilasi_%%V.txt & pause & exit /b 1)
  if not exist "hasil_mentah\2026-11-01_papan_%%V" mkdir "hasil_mentah\2026-11-01_papan_%%V"
  copy /y output_%%V\*.rpt "hasil_mentah\2026-11-01_papan_%%V\" >nul
  copy /y output_%%V\*.summary "hasil_mentah\2026-11-01_papan_%%V\" >nul
  type output_%%V\papan_%%V.fit.summary
)
echo.
echo SELESAI kompilasi kedua varian.
pause
