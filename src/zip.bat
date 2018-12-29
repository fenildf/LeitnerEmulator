@echo off
set ZIP=C:\PROGRA~1\7-Zip\7z.exe a -tzip -y -r
set REPO=plan0

%ZIP% %REPO%_20.zip plan0.py

%ZIP% %REPO%_21.zip *.py
