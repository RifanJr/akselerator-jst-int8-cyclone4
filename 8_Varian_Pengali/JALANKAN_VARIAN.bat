@echo off
title Ukur ulang tiga varian pengali (rancangan OS terbaru)
cd /d "%~dp0.."
where iverilog >nul 2>&1
if errorlevel 1 if exist "C:\iverilog\bin\iverilog.exe" set "PATH=C:\iverilog\bin;%PATH%"
python 8_Varian_Pengali\jalankan_varian.py %*
pause
