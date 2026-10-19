@echo off
title Simulasi RTL rancangan papan
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ===========================================================
echo   SIMULASI RTL - top_papan.v (16 citra uji vs acuan Python)
echo ===========================================================
echo.

rem ---- cari Icarus Verilog ----
where iverilog >nul 2>&1
if errorlevel 1 (
  if exist "C:\iverilog\bin\iverilog.exe" (
    set "PATH=C:\iverilog\bin;%PATH%"
  ) else if exist "C:\Program Files\iverilog\bin\iverilog.exe" (
    set "PATH=C:\Program Files\iverilog\bin;%PATH%"
  ) else (
    echo   Icarus Verilog TIDAK DITEMUKAN.
    echo.
    echo   Pasang dari bleyer.org/icarus. Saat memasang, centang pilihan
    echo   Add executable folders to the user PATH, lalu jalankan berkas ini lagi.
    echo.
    pause
    exit /b 1
  )
)

rem ---- cari Python ----
set "PY="
python --version >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  py --version >nul 2>&1
  if not errorlevel 1 set "PY=py"
)
if not defined PY (
  echo   Python TIDAK DITEMUKAN.
  echo.
  pause
  exit /b 1
)

echo   Icarus Verilog dan Python ditemukan. Simulasi berjalan...
echo.
%PY% jalankan_papan.py
echo.
pause
