import os
import logging
import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_BOT = os.environ.get("TOKEN_BOT")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

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
            params = {
                "team": REAL_MADRID_ID,
                "next": 10,
                "season": "2025"  # Используем 2025 год, так как сейчас 2026
            }
            
            logger.info(f"Запрос к API с параметрами: {params}")
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("response", [])
                    
                    logger.info(f"Получено матчей: {len(fixtures)}")
                    
                    if not fixtures:
                        # Пробуем получить матчи за 2026 год
                        params["season"] = "2026"
                        async with session.get(url, headers=headers, params=params) as response2:
                            if response2.status == 200:
                                data2 = await response2.json()
                                fixtures = data2.get("response", [])
                                logger.info(f"Матчей за 2026: {len(fixtures)}")
                    
                    if not fixtures:
                        await loading_msg.edit_text(
                            "❌ **Нет ближайших матчей**\n\n"
                            "Возможные причины:\n"
                            "• Межсезонье\n"
                            "• Расписание еще не опубликовано\n"
                            "• Сезон 2025-2026 еще не начался",
                            parse_mode='Markdown'
                        )
                        return
                    
                    # Получаем текущую дату с часовым поясом UTC
                    today = datetime.now(timezone.utc)
                    
                    # Фильтруем только будущие матчи
                    future_fixtures = []
                    for fixture in fixtures:
                        match_date_str = fixture['fixture']['date'].replace('Z', '+00:00')
                        match_date = datetime.fromisoformat(match_date_str)
                        # Убеждаемся, что дата с часовым поясом
                        if match_date.tzinfo is None:
                            match_date = match_date.replace(tzinfo=timezone.utc)
                        
                        if match_date > today:
                            future_fixtures.append(fixture)
                    
                    fixtures = future_fixtures[:5]
                    
                    if not fixtures:
                        await loading_msg.edit_text(
                            "❌ **Нет предстоящих матчей**\n\n"
                            "Все матчи на текущий сезон уже сыграны.\n"
                            "Ожидайте начала нового сезона!",
                            parse_mode='Markdown'
                        )
                        return
                    
                    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
                    message += f"📅 Данные: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n\n"
                    
                    for i, fixture in enumerate(fixtures, 1):
                        match_date_str = fixture['fixture']['date'].replace('Z', '+00:00')
                        match_date = datetime.fromisoformat(match_date_str)
                        if match_date.tzinfo is None:
                            match_date = match_date.replace(tzinfo=timezone.utc)
                        
                        home_team = fixture['teams']['home']['name']
                        away_team = fixture['teams']['away']['name']
                        is_home = (home_team == "Real Madrid")
                        location = "🏠 ДОМА" if is_home else "✈️ В ГОСТЯХ"
                        opponent = away_team if is_home else home_team
                        
                        league = fixture['league']['name']
                        venue = fixture['fixture']['venue']['name']
                        
                        message += f"**Матч #{i}**\n"
                        message += f"🏆 {league}\n"
                        message += f"📅 {match_date.strftime('%d %B %Y %H:%M')} UTC\n"
                        message += f"{location} vs **{opponent}**\n"
                        message += f"📍 {venue}\n\n"
                    
                    message += "💪 **¡HALA MADRID!**"
                    
                    await loading_msg.edit_text(message, parse_mode='Markdown')
                    logger.info("✅ Матчи отправлены")
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка API: {response.status} - {error_text}")
                    await loading_msg.edit_text(f"❌ Ошибка API: {response.status}\n\nПроверьте ключ API")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await loading_msg.edit_text(
            f"❌ **Ошибка при получении данных**\n\n"
            f"```\n{str(e)[:150]}\n```",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def setup_application():
    app = Application.builder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("matches", matches_command))
    app.add_error_handler(error_handler)
    return app

async def main():
    logger.info("🚀 Запуск бота Real Madrid Matches...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан")
        return
    
    bot_app = setup_application()
    await bot_app.initialize()
    
    # Сбрасываем вебхук при запуске
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Вебхук сброшен")
    
    # Пауза для завершения всех предыдущих подключений
    await asyncio.sleep(2)
    
    # В Render используем только polling режим
    logger.info("🔄 Запуск в режиме polling")
    
    # Запускаем polling с правильными параметрами
    await bot_app.start()
    
    # Создаем updater вручную
    from telegram.ext import Updater
    updater = Updater(bot=bot_app.bot, update_queue=bot_app.update_queue)
    updater.start_polling(drop_pending_updates=True)
    
    logger.info("✅ Бот успешно запущен в режиме polling")
    
    # Держим бота активным
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    finally:
        await updater.stop()
        await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
