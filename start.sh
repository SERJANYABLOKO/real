#!/bin/bash

# Устанавливаем переменную окружения
export TOKEN_BOT=${TOKEN_BOT}

# Проверяем наличие токена
if [ -z "$TOKEN_BOT" ]; then
    echo "❌ Ошибка: TOKEN_BOT не установлен!"
    echo "Добавьте переменную окружения TOKEN_BOT в настройках Render"
    exit 1
fi

echo "✅ Токен найден: ${TOKEN_BOT:0:10}..."
echo "🚀 Запускаем бота..."

# Запускаем бота
python3 bot.py
