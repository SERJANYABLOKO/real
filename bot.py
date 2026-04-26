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

# Разные возможные ID для Real Madrid
REAL_MADRID_IDS = [541, 282, 555]  # 541 - основной, 282 - возможно для лиги, 555 - резервный

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ **Hala Madrid!** ⚽\n\n"
        "📌 **Команды:**\n"
        "/matches - показать ближайшие матчи Real Madrid\n"
        "/start - показать это сообщение",
        parse_mode='Markdown'
    )

async def find_real_madrid_id(session):
    """Найти правильный ID Real Madrid в API"""
    url = "https://v3.football.api-sports.io/teams"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"search": "Real Madrid"}
    
    try:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                teams = data.get("response", [])
                for team in teams:
                    if "Real Madrid" in team['team']['name']:
                        logger.info(f"Найден Real Madrid: ID={team['team']['id']}, Name={team['team']['name']}")
                        return team['team']['id']
    except Exception as e:
        logger.error(f"Ошибка поиска ID: {e}")
    return REAL_MADRID_IDS[0]  # возвращаем ID по умолчанию

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
            # Найдем правильный ID Real Madrid
            real_madrid_id = await find_real_madrid_id(session)
            
            # Получаем текущую дату
            today = datetime.now().date()
            
            # Пробуем разные подходы для получения матчей
            fixtures = []
            
            # Способ 1: через параметр next
            url = "https://v3.football.api-sports.io/fixtures"
            headers = {"x-apisports-key": API_FOOTBALL_KEY}
            
            # Пробуем разные параметры
            params_list = [
                {"team": real_madrid_id, "next": "10"},  # следующий 10 матчей
                {"team": real_madrid_id, "season": "2024"},  # сезон 2024
                {"team": real_madrid_id, "season": "2025"},  # сезон 2025
                {"team": real_madrid_id, "from": today.isoformat()},  # с сегодняшней даты
                {"team": real_madrid_id},  # все матчи
            ]
            
            for params in params_list:
                logger.info(f"Пробуем параметры: {params}")
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("response"):
                            fixtures = data["response"]
                            logger.info(f"Найдено {len(fixtures)} матчей с параметрами {params}")
                            break
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API ({params}): {response.status} - {error_text}")
            
            # Фильтруем только будущие матчи
            today = datetime.now()
            future_fixtures = []
            for fixture in fixtures:
                match_date_str = fixture['fixture']['date'].replace('Z', '+00:00')
                match_date = datetime.fromisoformat(match_date_str)
                if match_date > today:
                    future_fixtures.append(fixture)
            
            fixtures = future_fixtures[:5]  # берем только 5 ближайших
            
            if not fixtures:
                # Если матчей нет, показываем последние результаты
                params = {"team": real_madrid_id, "last": "5"}
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("response"):
                            await show_last_matches(loading_msg, data["response"])
                            return
                    else:
                        await loading_msg.edit_text(
                            "❌ **Нет ближайших матчей**\n\n"
                            "Возможные причины:\n"
                            "• Межсезонье\n"
                            "• Расписание еще не опубликовано\n"
                            "• Проблемы с API\n\n"
                            f"ID Real Madrid в API: {real_madrid_id}",
                            parse_mode='Markdown'
                        )
                        return
            
            # Формируем сообщение с матчами
            message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
            message += f"📅 Данные: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            
            for i, fixture in enumerate(fixtures, 1):
                match_date = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
                
                home_team = fixture['teams']['home']['name']
                away_team = fixture['teams']['away']['name']
                is_home = (home_team == "Real Madrid")
                location = "🏠 **ДОМА**" if is_home else "✈️ **В ГОСТЯХ**"
                opponent = away_team if is_home else home_team
                
                league = fixture['league']['name']
                venue = fixture['fixture']['venue']['name']
                status = fixture['fixture']['status']['long']
                
                message += f"**Матч #{i}**\n"
                message += f"🏆 {league}\n"
                message += f"📅 {match_date.strftime('%d %B %Y %H:%M')} UTC\n"
                message += f"{location} vs **{opponent}**\n"
                message += f"📍 {venue}\n"
                if status != "Not Started":
                    message += f"📊 Статус: {status}\n"
                message += "\n"
            
            message += "💪 **¡HALA MADRID!**"
            
            await loading_msg.edit_text(message, parse_mode='Markdown')
            logger.info("✅ Матчи отправлены")
            
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await loading_msg.edit_text(
            f"❌ **Ошибка при получении данных**\n\n"
            f"Текст ошибки: {str(e)[:200]}\n\n"
            f"Проверьте логи для деталей.",
            parse_mode='Markdown'
        )

async def show_last_matches(loading_msg, fixtures):
    """Показать последние матчи, если нет будущих"""
    message = "📊 **ПОСЛЕДНИЕ МАТЧИ REAL MADRID** 📊\n\n"
    message += f"📅 Данные: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    
    for i, fixture in enumerate(fixtures[:5], 1):
        match_date = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
        
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        goals_home = fixture['goals']['home']
        goals_away = fixture['goals']['away']
        
        is_home = (home_team == "Real Madrid")
        opponent = away_team if is_home else home_team
        location = "🏠 дома" if is_home else "✈️ в гостях"
        
        result = f"{goals_home} - {goals_away}"
        if is_home:
            madrid_goals = goals_home
            opponent_goals = goals_away
        else:
            madrid_goals = goals_away
            opponent_goals = goals_home
        
        if madrid_goals > opponent_goals:
            emoji = "✅ **ПОБЕДА**"
        elif madrid_goals < opponent_goals:
            emoji = "❌ **ПОРАЖЕНИЕ**"
        else:
            emoji = "🤝 **НИЧЬЯ**"
        
        message += f"**Матч #{i}** - {emoji}\n"
        message += f"📅 {match_date.strftime('%d %B %Y')}\n"
        message += f"{location} vs **{opponent}**\n"
        message += f"📊 Счет: **{result}**\n\n"
    
    message += "\n⚠️ **Нет запланированных матчей**\n"
    message += "Показаны последние результаты.\n\n"
    message += "💪 **¡HALA MADRID!**"
    
    await loading_msg.edit_text(message, parse_mode='Markdown')

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
            web_app = web.Application()
            
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
            
            web_app.router.add_post('/webhook', webhook_handler)
            web_app.router.add_get('/health', health_handler)
            web_app.router.add_get('/', health_handler)
            
            runner = web.AppRunner(web_app)
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
