import os
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp
import asyncio

# Настройки
TOKEN_BOT = os.environ.get("TOKEN_BOT")
REAL_MADRID_TEAM_ID = 30

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "Я покажу расписание ближайших матчей Real Madrid!\n"
        "Просто отправь команду /matches\n\n"
        "🏆 Доступные команды:\n"
        "/matches - ближайшие матчи\n"
        "/help - помощь",
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
    
    # Используем текущий сезон (осень-весна)
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Определяем сезон (для футбола сезон начинается в августе)
    if current_month >= 8:
        season_start = current_year
        season_end = current_year + 1
        season = f"{season_start}"
    else:
        season_start = current_year - 1
        season_end = current_year
        season = f"{season_start}"
    
    # Пробуем разные форматы сезонов
    seasons_to_try = [season, str(season_start), str(current_year)]
    
    all_matches = None
    
    for season_try in seasons_to_try:
        # API для получения матчей по сезону
        url = f"https://www.openligadb.de/api/getmatchesbyteamandseason/{REAL_MADRID_TEAM_ID}/{season_try}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        matches = await resp.json()
                        if matches and len(matches) > 0:
                            all_matches = matches
                            logger.info(f"✅ Найдено {len(matches)} матчей за сезон {season_try}")
                            break
                    else:
                        logger.warning(f"Сезон {season_try}: статус {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"Таймаут для сезона {season_try}")
        except Exception as e:
            logger.error(f"Ошибка при запросе сезона {season_try}: {e}")
            continue
    
    # Если не нашли через API команды, пробуем API лиги Ла Лига
    if not all_matches:
        logger.info("Пробуем получить матчи через API лиги...")
        la_liga_league_id = 10
        url = f"https://www.openligadb.de/api/getmatchdata/laliga/{current_year}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        league_matches = await resp.json()
                        # Фильтруем матчи Реал Мадрида
                        real_matches = []
                        for match in league_matches:
                            if match.get('Team1', {}).get('TeamId') == REAL_MADRID_TEAM_ID or \
                               match.get('Team2', {}).get('TeamId') == REAL_MADRID_TEAM_ID:
                                real_matches.append(match)
                        
                        if real_matches:
                            all_matches = real_matches
                            logger.info(f"✅ Найдено {len(real_matches)} матчей Реала через лигу")
        except Exception as e:
            logger.error(f"Ошибка при запросе лиги: {e}")
    
    if not all_matches:
        await loading_msg.edit_text(
            "❌ Не удалось найти матчи Real Madrid.\n\n"
            "Возможные причины:\n"
            "• Сезон еще не начался\n"
            "• Проблемы с API (попробуйте позже)\n"
            "• Межсезонье\n\n"
            "Попробуйте повторить через /matches"
        )
        return
    
    # Фильтруем будущие матчи
    now = datetime.now(timezone.utc)
    upcoming_matches = []
    
    for match in all_matches:
        # Проверяем разные форматы даты
        match_date_str = match.get('MatchDateTimeUTC')
        if not match_date_str:
            match_date_str = match.get('MatchDateTime')
        
        if not match_date_str:
            continue
            
        try:
            # Обработка разных форматов даты
            if 'Z' in match_date_str:
                match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
            else:
                match_date = datetime.fromisoformat(match_date_str)
                if match_date.tzinfo is None:
                    match_date = match_date.replace(tzinfo=timezone.utc)
            
            # Показываем матчи на 60 дней вперед
            if match_date > now and match_date < now + timedelta(days=60):
                team1 = match['Team1']['TeamName']
                team2 = match['Team2']['TeamName']
                is_home = (team1 == "Real Madrid")
                
                # Название турнира
                league_name = match.get('LeagueName', 'La Liga')
                
                upcoming_matches.append({
                    'date': match_date,
                    'is_home': is_home,
                    'opponent': team2 if is_home else team1,
                    'league': league_name,
                    'venue': "Santiago Bernabéu" if is_home else "В гостях"
                })
        except Exception as e:
            logger.error(f"Ошибка парсинга даты {match_date_str}: {e}")
            continue
    
    # Сортируем по дате
    upcoming_matches.sort(key=lambda x: x['date'])
    upcoming_matches = upcoming_matches[:5]  # Показываем 5 ближайших
    
    if not upcoming_matches:
        await loading_msg.edit_text(
            "📭 На данный момент нет запланированных матчей.\n\n"
            "Возможно, сейчас межсезонье. Попробуйте позже, когда начнется новый сезон!"
        )
        return
    
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
    
    try:
        await loading_msg.edit_text(message, parse_mode='Markdown')
        logger.info("✅ Матчи успешно отправлены")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await loading_msg.edit_text("❌ Ошибка при форматировании сообщения. Попробуйте позже.")

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
        logger.error("❌ Токен бота не найден! Установите переменную окружения TOKEN_BOT")
        return
    
    logger.info("🚀 Запуск бота...")
    
    try:
        # Создаем приложение
        application = Application.builder().token(TOKEN_BOT).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("matches", get_matches))
        application.add_handler(CommandHandler("help", help_command))
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

if __name__ == '__main__':
    main()
