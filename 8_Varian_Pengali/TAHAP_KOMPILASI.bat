@echo off
title Varian pengali - tahap KOMPILASI
cd /d "%~dp0.."
python 8_Varian_Pengali\jalankan_varian.py --kompilasi %*
pause
