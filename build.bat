@echo off
chcp 65001 >nul
title DwarTools - Build

echo.
echo ========================================
echo          DwarTools EXE Builder
echo ========================================
echo.

echo [1/4] Проверка Python...
python --version

if errorlevel 1 (
    echo.
    echo ОШИБКА: Python не найден.
    echo Установите Python и попробуйте снова.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/4] Установка зависимостей...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ОШИБКА: не удалось установить зависимости.
    echo.
    pause
    exit /b 1
)

echo.
echo [3/4] Очистка предыдущей сборки...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DwarTools_v0.6.spec del /q DwarTools_v0.6.spec

echo.
echo [4/4] Создание DwarTools_v0.6.exe...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --name DwarTools_v0.6 ^
    DwarTools_v0.6.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo          ОШИБКА СБОРКИ
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo       СБОРКА УСПЕШНО ЗАВЕРШЕНА
echo ========================================
echo.
echo Готовый файл:
echo.
echo %cd%\dist\DwarTools_v0.6.exe
echo.

if exist "dist\DwarTools_v0.6.exe" (
    echo EXE успешно создан.
) else (
    echo ВНИМАНИЕ: EXE не найден.
)

echo.
pause
