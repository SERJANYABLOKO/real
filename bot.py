import os
import logging
import asyncio
from datetime import datetime
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
                "next": 5,
                "season": str(datetime.now().year)
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("response", [])
                    
                    if not fixtures:
                        await loading_msg.edit_text("❌ Нет ближайших матчей")
                        return
                    
                    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
                    message += f"📅 Данные: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    
                    for i, fixture in enumerate(fixtures, 1):
                        match_date = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
                        
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
                    await loading_msg.edit_text(f"❌ Ошибка API: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await loading_msg.edit_text("❌ Ошибка при получении данных")

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
    
    # Режим работы
    if WEBHOOK_URL and WEBHOOK_URL != "":
        try:
            logger.info(f"🌐 Запуск в режиме вебхука на порту {PORT}")
            webhook_url = f"{WEBHOOK_URL}/webhook"
            await bot_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
            
            # Создаем веб-сервер
            app = web.Application()
            
            async def webhook_handler(request):
                try:
                    data = await request.json()
                    update = Update.de_json(data, bot_app.bot)
                    await bot_app.process_update(update)
                    return web.Response(text="OK")
                except Exception as e:
                    logger.error(f"Webhook error: {e}")
                    return web.Response(text="Error", status=500)
            
            async def health_handler(request):
                return web.Response(text="OK")
            
            app.router.add_post('/webhook', webhook_handler)
            app.router.add_get('/health', health_handler)
            app.router.add_get('/', health_handler)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', PORT)
            await site.start()
            
            logger.info(f"✅ Сервер запущен на порту {PORT}")
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"Ошибка при настройке вебхука: {e}")
            logger.info("🔄 Переключаюсь в режим polling...")
            await bot_app.start()
            await bot_app.updater.start_polling()
            await asyncio.Event().wait()
    else:
        logger.info("🔄 Запуск в режиме polling")
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
