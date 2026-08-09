@echo off
chcp 65001 >nul
cd /d %~dp0

REM 依次尝试 python / py / 常见安装路径，自动跳过微软商店的占位 stub
set "PYEXE="
python --version >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE (
    py -3 --version >nul 2>&1 && set "PYEXE=py -3"
)
if not defined PYEXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PYEXE (
    echo [错误] 未检测到可用的 Python。请先安装 Python 3.9 或更高版本：
    echo        https://www.python.org/downloads/  （安装时勾选 Add python.exe to PATH）
    echo.
    pause
    exit /b 1
)

echo 正在启动 LeetCode 刷题训练器，浏览器将自动打开 http://127.0.0.1:8000
echo 关闭本窗口即可停止服务。
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
%PYEXE% app.py
pause
