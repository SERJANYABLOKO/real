import os
import logging
import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_BOT = os.environ.get("TOKEN_BOT")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")

REAL_MADRID_ID = 541

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "📌 **Команды:**\n"
        "/matches - показать ближайшие матчи Real Madrid\n"
        "/start - показать это сообщение",
        parse_mode='Markdown'
    )

async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loading_msg = await update.message.reply_text("⚽ Загружаю расписание матчей Real Madrid...")
    
    if not API_FOOTBALL_KEY:
        await loading_msg.edit_text(
            "❌ **API ключ не настроен!**\n\n"
            "Добавьте переменную API_FOOTBALL_KEY в настройках Render",
            parse_mode='Markdown'
        )
        return
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = "https://v3.football.api-sports.io/fixtures"
            headers = {"x-apisports-key": API_FOOTBALL_KEY}
            
            # Пробуем найти матчи в разных сезонах
            current_year = datetime.now(timezone.utc).year
            seasons = [current_year, current_year + 1, 2025, 2024, 2023]
            
            all_fixtures = []
            for season in seasons:
                params = {
                    "team": REAL_MADRID_ID,
                    "season": str(season),
                    "status": "NS"  # Not Started
                }
                
                logger.info(f"Проверяем сезон {season}")
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("response"):
                            all_fixtures = data["response"]
                            logger.info(f"Найдено {len(all_fixtures)} матчей в сезоне {season}")
                            break
            
            if not all_fixtures:
                await loading_msg.edit_text(
                    "❌ **Нет ближайших матчей**\n\n"
                    "Возможные причины:\n"
                    "• Межсезонье\n"
                    "• Расписание еще не опубликовано\n"
                    "• Проверьте API ключ",
                    parse_mode='Markdown'
                )
                return
            
            # Фильтруем будущие матчи
            now = datetime.now(timezone.utc)
            future_matches = []
            
            for match in all_fixtures:
                match_date_str = match['fixture']['date'].replace('Z', '+00:00')
                match_date = datetime.fromisoformat(match_date_str)
                if match_date > now:
                    future_matches.append(match)
            
            future_matches = future_matches[:5]  # Берем 5 ближайших
            
            if not future_matches:
                await loading_msg.edit_text(
                    "📊 **Нет предстоящих матчей**\n\n"
                    "Все матчи на текущий сезон уже сыграны.\n"
                    "Следите за обновлениями!",
                    parse_mode='Markdown'
                )
                return
            
            # Формируем сообщение
            message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
            message += f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n\n"
            
            for i, match in enumerate(future_matches, 1):
                match_date = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                is_home = (home == "Real Madrid")
                
                location = "🏠 ДОМА" if is_home else "✈️ ГОСТИ"
                opponent = away if is_home else home
                league = match['league']['name']
                venue = match['fixture']['venue']['name']
                
                message += f"**{i}. {league}**\n"
                message += f"📅 {match_date.strftime('%d %B %Y, %H:%M')}\n"
                message += f"{location}: **{opponent}**\n"
                message += f"📍 {venue}\n\n"
            
            message += "💪 **¡HALA MADRID!**"
            
            await loading_msg.edit_text(message, parse_mode='Markdown')
            logger.info("✅ Матчи успешно отправлены")
            
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await loading_msg.edit_text(
            f"❌ **Ошибка**\n\n"
            f"Не удалось загрузить данные.\n"
            f"Попробуйте позже.",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота Real Madrid Matches...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан!")
        return
    
    # Создаем приложение
    application = Application.builder().token(TOKEN_BOT).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("matches", matches_command))
    application.add_error_handler(error_handler)
    
    # Запускаем бота (синхронный способ)
    logger.info("🔄 Запуск polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
if __name__ == "__main__":
    main()
