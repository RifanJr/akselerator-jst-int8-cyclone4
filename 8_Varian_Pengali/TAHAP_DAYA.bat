@echo off
title Varian pengali - tahap DAYA
cd /d "%~dp0.."
python 8_Varian_Pengali\jalankan_varian.py --daya %*
pause
