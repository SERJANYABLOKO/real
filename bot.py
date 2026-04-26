import os
import logging
import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp

# --- НАСТРОЙКИ ---
# Токен вашего бота из переменных окружения
TOKEN_BOT = os.environ.get("TOKEN_BOT")
# ID лиги "La Liga" из базы OpenLigaDB
LA_LIGA_LEAGUE_ID = 10
# ID команды "Real Madrid" в этой лиге
REAL_MADRID_TEAM_ID = 30

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОМАНДЫ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение."""
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "Я бот, который покажет расписание ближайших матчей Real Madrid.\n"
        "Просто отправь команду /matches",
        parse_mode='Markdown'
    )

async def get_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает и отправляет список ближайших матчей."""
    chat_id = update.effective_chat.id
    loading_message = await update.message.reply_text("🔍 Ищу ближайшие матчи Real Madrid...")

    # 1. Формируем URL для запроса к OpenLigaDB
    # Эндпоинт возвращает все матчи для команды в указанном сезоне
    # Сезон 2024 - это сезон 2024/2025
    current_season = 2024
    url = f"https://www.openligadb.de/api/getmatchesbyteamandseason/{REAL_MADRID_TEAM_ID}/{current_seASON}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await loading_message.edit_text(f"❌ Ошибка при получении данных от API. Код ошибки: {resp.status}")
                    return

                all_matches = await resp.json()

    except aiohttp.ClientError as e:
        logger.error(f"Network error: {e}")
        await loading_message.edit_text("❌ Не удалось подключиться к серверу с расписанием. Попробуйте позже.")
        return
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await loading_message.edit_text("❌ Произошла неизвестная ошибка.")
        return

    if not all_matches:
        await loading_message.edit_text("❌ Не удалось найти расписание матчей для Real Madrid. Проверьте ID команды и лиги.")
        return

    # 2. Фильтруем и форматируем матчи
    today = datetime.now(timezone.utc).date()
    upcoming_matches = []

    for match in all_matches:
        # Парсим дату матча из строки формата "2025-05-04T16:15:00"
        match_date_str = match.get('MatchDateTimeUTC')
        if not match_date_str:
            continue

        try:
            # Преобразуем строку в объект datetime
            match_datetime = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
            match_date = match_datetime.date()
        except (ValueError, TypeError):
            logger.warning(f"Не удалось распарсить дату: {match_date_str}")
            continue

        # Оставляем только будущие матчи
        if match_date >= today:
            # Получаем названия команд
            team1_name = match['Team1']['TeamName']
            team2_name = match['Team2']['TeamName']

            # Определяем, где играет Реал Мадрид: дома или в гостях
            is_home = (team1_name == "Real Madrid")
            opponent = team2_name if is_home else team1_name
            location = "🏠 **ДОМА**" if is_home else "✈️ **В ГОСТЯХ**"

            # Формируем запись о матче
            match_info = {
                'date': match_datetime,
                'location': location,
                'opponent': opponent,
                'league': "La Liga",  # Название лиги, можно уточнить
                'venue': "Santiago Bernabéu" if is_home else "Стадион соперника"
            }
            upcoming_matches.append(match_info)

    # Берем только ближайшие 5 матчей
    upcoming_matches = upcoming_matches[:5]

    if not upcoming_matches:
        await loading_message.edit_text("📭 На данный момент нет запланированных ближайших матчей.")
        return

    # 3. Собираем итоговое сообщение
    result_message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"

    for i, match in enumerate(upcoming_matches, 1):
        match_date = match['date']
        location = match['location']
        opponent = match['opponent']
        league = match['league']
        venue = match['venue']

        result_message += f"**Матч #{i}**\n"
        result_message += f"🏆 {league}\n"
        result_message += f"📅 {match_date.strftime('%d %B %Y, %H:%M')} UTC\n"
        result_message += f"{location} vs **{opponent}**\n"
        result_message += f"📍 {venue}\n\n"

    result_message += "💪 **¡HALA MADRID!**"

    await loading_message.edit_text(result_message, parse_mode='Markdown')

# --- ЗАПУСК БОТА ---
def main():
    """Запускает бота."""
    if not TOKEN_BOT:
        logger.error("❌ Ошибка: переменная окружения TOKEN_BOT не установлена!")
        return

    # Создаем приложение
    application = Application.builder().token(TOKEN_BOT).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("matches", get_matches))

    # Запускаем бота
    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
