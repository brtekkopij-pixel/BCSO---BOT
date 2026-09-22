@echo off
title BCSO BOT
cd /d "%~dp0"

echo ======================================
echo              BCSO BOT v12
echo ======================================
echo.
py -m pip install -r requirements.txt

:RUN
echo.
echo [START] Uruchamiam bota...
py bot.py
set CODE=%ERRORLEVEL%

if "%CODE%"=="75" (
    echo [RESTART] Ponowne uruchomienie za 3 sekundy...
    timeout /t 3 /nobreak >nul
    goto RUN
)

echo.
echo [STOP] Bot zakonczyl prace. Kod: %CODE%
pause
