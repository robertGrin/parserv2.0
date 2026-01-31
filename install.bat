@echo off
chcp 65001 >nul
cls
:menu
echo.
echo ==========================================
echo      УПРАВЛЕНИЕ ПАРСЕРОМ (DOCKER)
echo ==========================================
echo 1. Установить/Обновить (Build)
echo 2. Войти в аккаунт (Авторизация)
echo 3. Запустить парсер (Start)
echo 4. Смотреть логи (Logs)
echo 5. Остановить всё (Stop)
echo ==========================================
set /p choice="Выберите действие (1-5): "

if "%choice%"=="1" goto build
if "%choice%"=="2" goto auth
if "%choice%"=="3" goto start
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto stop
goto menu

:build
echo ⏳ Сборка контейнера...
docker-compose down -v
docker-compose build --no-cache app
echo ✅ Готово! Теперь выберите пункт 2.
pause
goto menu

:auth
echo 📱 Запуск скрипта входа...
echo Введите номер телефона (напр. +7999...) и код, когда попросят.
docker-compose run --rm app python src/add_account.py
echo.
echo Если вы видели "Успешный вход", выберите пункт 3.
pause
goto menu

:start
echo 🚀 Запуск бота...
docker-compose up -d
echo Бот работает в фоне.
pause
goto menu

:logs
docker-compose logs -f app
goto menu

:stop
docker-compose down
echo 🛑 Остановлено.
pause
goto menu