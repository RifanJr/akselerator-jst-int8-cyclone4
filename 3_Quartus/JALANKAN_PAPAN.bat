@echo off
title Akselerator di Papan - kompilasi dan pemrograman
cd /d "%~dp0"

echo.
echo ===========================================================
echo   AKSELERATOR P = 8 DI PAPAN
echo ===========================================================
echo.
echo   Langkah 1: kompilasi proyek papan (sekitar 2-5 menit)
echo   Langkah 2: program papan lewat USB Blaster
echo.
echo   Pastikan Quartus (GUI) sudah DITUTUP.
echo.
pause

set "QBIN="
if exist "C:\intelFPGA_lite\25.1std\quartus\bin64\quartus_sh.exe" set "QBIN=C:\intelFPGA_lite\25.1std\quartus\bin64"
if not defined QBIN if exist "C:\intelFPGA_lite\25.1\quartus\bin64\quartus_sh.exe" set "QBIN=C:\intelFPGA_lite\25.1\quartus\bin64"
if not defined QBIN if exist "C:\altera_lite\25.1std\quartus\bin64\quartus_sh.exe" set "QBIN=C:\altera_lite\25.1std\quartus\bin64"
if not defined QBIN if exist "D:\intelFPGA_lite\25.1std\quartus\bin64\quartus_sh.exe" set "QBIN=D:\intelFPGA_lite\25.1std\quartus\bin64"

if not defined QBIN (
  echo   Folder Quartus TIDAK DITEMUKAN.
  pause
  exit /b 1
)
echo   Quartus ditemukan: %QBIN%
echo.

echo ===========================================================
echo   LANGKAH 1 - KOMPILASI
echo ===========================================================
"%QBIN%\quartus_sh.exe" --flow compile papan
if errorlevel 1 (
  echo.
  echo   KOMPILASI GAGAL. Kirim isi jendela ini untuk diperiksa.
  pause
  exit /b 1
)

echo.
echo   Kompilasi selesai. Ringkasan:
type output_papan\papan.fit.summary
echo.
type output_papan\papan.sta.summary
echo.

echo ===========================================================
echo   LANGKAH 2 - PEMROGRAMAN PAPAN
echo ===========================================================
echo.
echo   Nyalakan papan dan pasang USB Blaster ke header JTAG.
echo.
pause
"%QBIN%\jtagconfig.exe"
echo.
"%QBIN%\quartus_pgm.exe" -c "USB-Blaster [USB-0]" -m JTAG -o "p;output_papan\papan.sof"

echo.
echo ===========================================================
echo   SELESAI
echo ===========================================================
echo.
pause
