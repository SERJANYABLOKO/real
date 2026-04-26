import os
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp
import asyncio

# Настройки
TOKEN_BOT = os.environ.get("TOKEN_BOT")
LA_LIGA_LEAGUE_ID = 10
REAL_MADRID_TEAM_ID = 30

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "Я покажу расписание ближайших матчей Real Madrid!\n"
        "Просто отправь команду /matches",
        parse_mode='Markdown'
    )

async def get_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и отправка матчей"""
    loading_msg = await update.message.reply_text("🔍 Ищу ближайшие матчи Real Madrid...")
    
    # Пробуем разные сезоны (2024, 2025, 2026)
    seasons = [2026, 2025, 2024]
    all_matches = []
    
    for season in seasons:
        url = f"https://www.openligadb.de/api/getmatchesbyteamandseason/{REAL_MADRID_TEAM_ID}/{season}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        matches = await resp.json()
                        if matches:
                            all_matches = matches
                            logger.info(f"Найдено {len(matches)} матчей за сезон {season}")
                            break
                    else:
                        logger.warning(f"Сезон {season}: статус {resp.status}")
        except Exception as e:
            logger.error(f"Ошибка при запросе сезона {season}: {e}")
            continue
    
    if not all_matches:
        await loading_msg.edit_text("❌ Не удалось найти матчи Real Madrid. Попробуйте позже.")
        return
    
    # Фильтруем будущие матчи
    now = datetime.now(timezone.utc)
    upcoming_matches = []
    
    for match in all_matches:
        match_date_str = match.get('MatchDateTimeUTC')
        if not match_date_str:
            continue
            
        try:
            match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
            if match_date > now:
                # Определяем место проведения
                team1 = match['Team1']['TeamName']
                team2 = match['Team2']['TeamName']
                is_home = (team1 == "Real Madrid")
                
                upcoming_matches.append({
                    'date': match_date,
                    'is_home': is_home,
                    'opponent': team2 if is_home else team1,
                    'league': "La Liga",
                    'venue': "Santiago Bernabéu" if is_home else "В гостях"
                })
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {e}")
            continue
    
    upcoming_matches = upcoming_matches[:5]
    
    if not upcoming_matches:
        await loading_msg.edit_text("📭 На данный момент нет запланированных матчей.")
        return
    
    # Формируем сообщение
    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
    message += f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n\n"
    
    for i, match in enumerate(upcoming_matches, 1):
        location = "🏠 **ДОМА**" if match['is_home'] else "✈️ **В ГОСТЯХ**"
        date_str = match['date'].strftime('%d %B %Y, %H:%M')
        
        message += f"**Матч #{i}**\n"
        message += f"🏆 {match['league']}\n"
        message += f"📅 {date_str} UTC\n"
        message += f"{location} vs **{match['opponent']}**\n"
        message += f"📍 {match['venue']}\n\n"
    
    message += "💪 **¡HALA MADRID!**"
    
    await loading_msg.edit_text(message, parse_mode='Markdown')
    logger.info("✅ Матчи отправлены")

def main():
    """Запуск бота"""
    if not TOKEN_BOT:
        logger.error("❌ Токен бота не найден!")
        return
    
    # Создаем приложение
    application = Application.builder().token(TOKEN_BOT).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("matches", get_matches))
    
    # Запускаем бота с принудительным сбросом вебхука
    logger.info("🚀 Запуск бота...")
    application.run_polling(
        drop_pending_updates=True,  # Сбрасываем старые обновления
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
