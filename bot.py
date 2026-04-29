import os
import logging
import sys
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp

# Настройки
TOKEN_BOT = os.environ.get("TOKEN_BOT")
REAL_MADRID_TEAM_ID = 30

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "Я покажу расписание ближайших матчей Real Madrid!\n"
        "Просто отправь команду /matches\n\n"
        "Доступные команды:\n"
        "/start - Приветствие\n"
        "/matches - Ближайшие матчи\n"
        "/help - Помощь",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    await update.message.reply_text(
        "📋 **Доступные команды:**\n\n"
        "/start - Приветствие\n"
        "/matches - Ближайшие матчи Real Madrid\n"
        "/help - Эта справка",
        parse_mode='Markdown'
    )

async def get_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и отправка матчей"""
    loading_msg = await update.message.reply_text("🔍 Ищу ближайшие матчи Real Madrid...")
    
    # Пробуем получить данные за последние годы
    current_year = datetime.now().year
    seasons = [2025, 2026, 2024, current_year]
    all_matches = None
    
    for season in seasons:
        url = f"https://www.openligadb.de/api/getmatchesbyteamandseason/{REAL_MADRID_TEAM_ID}/{season}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        matches = await resp.json()
                        if matches and len(matches) > 0:
                            all_matches = matches
                            logger.info(f"✅ Найдено {len(matches)} матчей за {season} год")
                            break
                    else:
                        logger.warning(f"Сезон {season}: статус {resp.status}")
        except Exception as e:
            logger.error(f"Ошибка при запросе {season}: {e}")
            continue
    
    if not all_matches:
        await loading_msg.edit_text(
            "❌ Не удалось найти матчи Real Madrid.\n\n"
            "Возможные причины:\n"
            "• Сейчас межсезонье (июнь-июль)\n"
            "• API временно недоступен\n"
            "• Расписание еще не опубликовано\n\n"
            "Попробуйте позже или через /matches"
        )
        return
    
    # Фильтруем будущие матчи (на 90 дней вперед)
    now = datetime.now(timezone.utc)
    upcoming_matches = []
    
    for match in all_matches:
        match_date_str = match.get('MatchDateTimeUTC')
        if not match_date_str:
            continue
            
        try:
            match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
            # Показываем матчи на 60 дней вперед
            if match_date > now and match_date < now + timedelta(days=60):
                team1 = match['Team1']['TeamName']
                team2 = match['Team2']['TeamName']
                is_home = (team1 == "Real Madrid")
                
                league_name = match.get('LeagueName', 'La Liga')
                
                upcoming_matches.append({
                    'date': match_date,
                    'is_home': is_home,
                    'opponent': team2 if is_home else team1,
                    'league': league_name,
                    'venue': "Santiago Bernabéu" if is_home else "В гостях"
                })
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {e}")
            continue
    
    if not upcoming_matches:
        await loading_msg.edit_text(
            "📭 На данный момент нет запланированных матчей.\n\n"
            "Возможно, сейчас межсезонье. Расписание появится ближе к августу!"
        )
        return
    
    # Сортируем по дате и берем 5 ближайших
    upcoming_matches.sort(key=lambda x: x['date'])
    upcoming_matches = upcoming_matches[:5]
    
    # Формируем сообщение
    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
    message += f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n\n"
    
    for i, match in enumerate(upcoming_matches, 1):
        location_icon = "🏠" if match['is_home'] else "✈️"
        location_text = "**ДОМА**" if match['is_home'] else "**В ГОСТЯХ**"
        date_str = match['date'].strftime('%d %B %Y, %H:%M')
        
        message += f"{location_icon} **Матч #{i}**\n"
        message += f"🏆 {match['league']}\n"
        message += f"📅 {date_str} UTC\n"
        message += f"{location_text} vs **{match['opponent']}**\n"
        message += f"📍 {match['venue']}\n\n"
    
    message += "💪 **¡HALA MADRID Y NADA MÁS!**"
    
    await loading_msg.edit_text(message, parse_mode='Markdown')
    logger.info("✅ Матчи успешно отправлены")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
        )

def main():
    """Запуск бота"""
    if not TOKEN_BOT:
        logger.error("❌ Токен бота не найден!")
        sys.exit(1)
    
    logger.info("🚀 Запуск бота...")
    logger.info(f"Токен: {TOKEN_BOT[:10]}...")
    
    try:
        # Создаем приложение
        application = Application.builder().token(TOKEN_BOT).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("matches", get_matches))
        application.add_handler(CommandHandler("help", help_command))
        application.add_error_handler(error_handler)
        
        logger.info("✅ Бот успешно запущен!")
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=None
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
