import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ==========================================
# 1. МИНИ-СЕРВЕР 
# ==========================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Alive')

class ReusableServer(HTTPServer):
    allow_reuse_address = True

def keep_alive():
    port = int(os.environ.get('PORT', 8080))
    server = ReusableServer(('0.0.0.0', port), PingHandler)
    server.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ==========================================
# 2. НАСТРОЙКА API
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. ЛОГИКА - СКАНЕР МОДЕЛЕЙ
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Спрашиваю у Google список доступных моделей... ⏳")
    
    try:
        available_models = []
        # Запрашиваем все модели и фильтруем те, что умеют писать текст
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        if available_models:
            models_str = "\n".join(available_models)
            await message.answer(
                f"✅ **Успешно! Вот модели, которые работают с твоим ключом:**\n\n`{models_str}`\n\nСкопируй самое короткое и понятное название (например, models/gemini-1.5-flash) и пришли сюда!", 
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Твой ключ рабочий, но Google не выдал ни одной текстовой модели. Возможно, дело в регионе или ограничениях аккаунта.")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при запросе списка:\n`{e}`", parse_mode="Markdown")

@dp.message(F.text)
async def handle_text(message: types.Message):
    await message.reply("Сначала нажми /start, чтобы мы узнали правильное имя модели!")

# ==========================================
# 4. ЗАПУСК
# ==========================================
async def main():
    print("Бот-сканер успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
