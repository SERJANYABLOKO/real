#!/bin/bash

# Устанавливаем переменную окружения
export TOKEN_BOT=${TOKEN_BOT}

# Проверяем наличие токена
if [ -z "$TOKEN_BOT" ]; then
    echo "❌ Ошибка: TOKEN_BOT не установлен!"
    exit 1
fi

echo "✅ Токен найден, запускаем бота..."
python bot.py
