@echo off
title Renta Wall Street - Localhost 8150
color 0B

:: 1. Ir a la carpeta del proyecto
cd /d "%~dp0"

:: 2. Instalar dependencias necesarias
echo Verificando dependencias...
python -m pip install flask pandas openpyxl pdfplumber --quiet

:: 3. Lanzar comprobador asincrono para abrir el navegador cuando este listo
echo Preparando apertura automatica del navegador...
start powershell -WindowStyle Hidden -Command "while(!(Test-NetConnection 127.0.0.1 -Port 8150 -WarningAction SilentlyContinue).TcpTestSucceeded) { Start-Sleep -Seconds 1 }; Start-Process 'http://127.0.0.1:8150'"

:: 4. Iniciar Watchdog (Bucle infinito en esta ventana)
echo Iniciando servidor en modo persistente (Watchdog activo)...
echo ATENCION: No cierres esta ventana para mantener el servicio activo.

:watchdog
python main.py
echo.
echo [CRITICO] El proceso de Python ha finalizado o fallado.
echo [WATCHDOG] Relanzando servicio automaticamente en 3 segundos...
timeout /t 3 /nobreak >nul
goto watchdog