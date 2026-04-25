import os
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiohttp import web
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN_BOT = os.environ.get("TOKEN_BOT")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ID команды Real Madrid в API-Football
REAL_MADRID_ID = 541

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственная команда"""
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "Я бот, который показывает расписание матчей Real Madrid.\n\n"
        "📌 **Команды:**\n"
        "/matches - показать ближайшие матчи Real Madrid\n"
        "/start - показать это сообщение\n\n"
        "🏆 **¡Vamos Real!**",
        parse_mode='Markdown'
    )

async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ближайшие матчи Real Madrid"""
    # Отправляем сообщение о загрузке
    loading_msg = await update.message.reply_text("⚽ Загружаю расписание матчей Real Madrid...")
    
    if not API_FOOTBALL_KEY:
        await loading_msg.edit_text(
            "❌ **API ключ не настроен!**\n\n"
            "Добавьте переменную окружения `API_FOOTBALL_KEY` на Render.\n\n"
            "📝 **Как получить бесплатный ключ:**\n"
            "1. Зарегистрируйтесь на [dashboard.api-football.com](https://dashboard.api-football.com/register)\n"
            "2. Подтвердите email\n"
            "3. Скопируйте API ключ из личного кабинета\n\n"
            "Бесплатный тариф: 100 запросов/день",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            # Формируем запрос к API-Football
            url = "https://v3.football.api-sports.io/fixtures"
            headers = {
                "x-apisports-key": API_FOOTBALL_KEY
            }
            params = {
                "team": REAL_MADRID_ID,
                "next": 5,  # Следующие 5 матчей
                "season": str(datetime.now().year)
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("response", [])
                    
                    if not fixtures:
                        await loading_msg.edit_text(
                            "❌ **Не найдено ближайших матчей**\n\n"
                            "Возможные причины:\n"
                            "• Сезон закончился\n"
                            "• Данные ещё не обновились\n"
                            "• Нет запланированных матчей"
                        )
                        return
                    
                    # Формируем красивое сообщение
                    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
                    message += f"📅 *Данные: {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n"
                    message += f"🏆 *API-Football (бесплатный тариф)*\n\n"
                    message += "─" * 30 + "\n\n"
                    
                    for i, fixture in enumerate(fixtures, 1):
                        match_date = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
                        
                        # Определяем, где играет Реал
                        home_team = fixture['teams']['home']['name']
                        away_team = fixture['teams']['away']['name']
                        is_home = (home_team == "Real Madrid")
                        
                        if is_home:
                            location = "🏠 **ДОМА**"
                            opponent = away_team
                        else:
                            location = "✈️ **В ГОСТЯХ**"
                            opponent = home_team
                        
                        # Турнир и иконка
                        league = fixture['league']['name']
                        league_icons = {
                            "La Liga": "🇪🇸",
                            "UEFA Champions League": "🏆",
                            "Copa del Rey": "👑",
                            "Supercopa de España": "🏆",
                            "UEFA Super Cup": "⭐",
                            "FIFA Club World Cup": "🌍"
                        }
                        league_icon = league_icons.get(league, "⚽")
                        
                        # Стадион
                        venue = fixture['fixture']['venue']['name']
                        
                        message += f"**Матч #{i}**\n"
                        message += f"📅 {match_date.strftime('%d %B %Y')}\n"
                        message += f"⏰ {match_date.strftime('%H:%M')} UTC\n"
                        message += f"🏟️ {location}\n"
                        message += f"🆚 **Против:** {opponent}\n"
                        message += f"🏆 {league_icon} **Турнир:** {league}\n"
                        message += f"📍 **Стадион:** {venue}\n"
                        
                        # Статус матча
                        status = fixture['fixture']['status']['short']
                        status_texts = {
                            "NS": "⏳ Ещё не начался",
                            "TBD": "❓ Время будет определено",
                            "1H": "🔥 ИДЁТ ПЕРВЫЙ ТАЙМ! 🔥",
                            "2H": "🔥 ИДЁТ ВТОРОЙ ТАЙМ! 🔥",
                            "HT": "⏸️ Перерыв",
                            "FT": "✅ Завершён",
                            "AET": "⏱️ Дополнительное время",
                            "PEN": "⚽ Серия пенальти",
                            "SUSP": "⏸️ Отложен",
                            "INT": "🚫 Прерван",
                            "PST": "📅 Перенесён",
                            "CANC": "❌ Отменён",
                            "ABD": "🚫 Прерван досрочно",
                            "AWD": "🏆 Техническая победа",
                            "WO": "🚫 Неявка"
                        }
                        
                        if status in ["1H", "2H", "HT"]:
                            # Показываем текущий счёт, если матч идёт
                            score_home = fixture['goals']['home'] or 0
                            score_away = fixture['goals']['away'] or 0
                            message += f"📊 **ТЕКУЩИЙ СЧЁТ:** {score_home} : {score_away}\n"
                        
                        message += f"📌 {status_texts.get(status, '⏳ Статус неизвестен')}\n"
                        message += "\n" + "─" * 30 + "\n\n"
                    
                    # Добавляем информацию о лиге
                    message += "📊 **ПОСЛЕДНИЕ РЕЗУЛЬТАТЫ:**\n"
                    message += "• La Liga: Мадрид борется за чемпионство 🏆\n"
                    message += "• Champions League: Команда в погоне за победой ⭐\n\n"
                    message += "💪 **¡HALA MADRID Y NADA MÁS!** ⚽🤍"
                    
                    await loading_msg.edit_text(message, parse_mode='Markdown')
                    logger.info(f"✅ Показаны матчи Real Madrid для чата {update.effective_chat.id}")
                    
                elif response.status == 429:
                    await loading_msg.edit_text(
                        "⚠️ **Превышен лимит запросов!**\n\n"
                        "Бесплатный тариф API-Football: 100 запросов/день.\n"
                        "Пожалуйста, попробуйте завтра.\n\n"
                        "💡 *Совет: Используйте команду реже, чтобы не превышать лимит.*"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка API: {response.status} - {error_text}")
                    await loading_msg.edit_text(
                        f"❌ **Ошибка API** (Код: {response.status})\n\n"
                        "Пожалуйста, попробуйте позже.\n\n"
                        "Если ошибка повторяется:\n"
                        "• Проверьте API ключ\n"
                        "• Убедитесь, что ключ активен\n"
                        "• Свяжитесь с поддержкой API-Football"
                    )
                    
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка сети: {e}")
        await loading_msg.edit_text(
            "❌ **Ошибка сети**\n\n"
            "Не удалось连接到 API-Football.\n"
            "Пожалуйста, проверьте интернет-соединение и попробуйте позже."
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await loading_msg.edit_text(
            "❌ **Произошла ошибка**\n\n"
            "Пожалуйста, попробуйте позже.\n\n"
            f"Ошибка: {str(e)[:100]}"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже."
        )

def setup_application():
    """Настройка приложения бота"""
    app = Application.builder().token(TOKEN_BOT).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("matches", matches_command))
    
    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)
    
    return app

# Webhook обработчики для aiohttp
async def webhook_handler(request):
    """Обработчик вебхуков от Telegram"""
    try:
        data = await request.json()
        bot_app = request.app['bot_app']
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return web.Response(text="Error", status=500)

async def health_handler(request):
    """Health check handler для Render"""
    return web.Response(text="OK", status=200)

async def main():
    """Главная функция запуска бота"""
    logger.info("🚀 Запуск бота Real Madrid Matches...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан в переменных окружения")
        return
    
    bot_app = setup_application()
    await bot_app.initialize()
    
    # Проверяем наличие API ключа
    if not API_FOOTBALL_KEY:
        logger.warning("⚠️ API_FOOTBALL_KEY не задан! Команда /matches не будет работать.")
    
    if WEBHOOK_URL:
        # Режим вебхука (для Render)
        logger.info(f"🌐 Запуск в режиме вебхука на порту {PORT}")
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Устанавливаем вебхук
        result = await bot_app.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
        if result:
            logger.info(f"✅ Вебхук успешно установлен: {webhook_url}")
        else:
            logger.error("❌ Не удалось установить вебхук")
            return
        
        # Создаем aiohttp приложение
        app = web.Application()
        app['bot_app'] = bot_app
        app.router.add_post('/webhook', webhook_handler)
        app.router.add_get('/health', health_handler)
        app.router.add_get('/', health_handler)
        
        # Запускаем сервер
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        logger.info(f"✅ Бот успешно запущен на порту {PORT}")
        
        # Держим сервер запущенным
        await asyncio.Event().wait()
        
    else:
        # Режим polling (для локальной разработки)
        logger.info("🔄 Запуск в режиме polling")
        await bot_app.start()
        await bot_app.updater.start_polling()
        
        logger.info("✅ Бот успешно запущен")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен пользователем")
            await bot_app.updater.stop()
            await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
