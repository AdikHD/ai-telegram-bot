import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ==========================================
# 1. МИНИ-СЕРВЕР (УСИЛЕННЫЙ ОТ ОШИБОК)
# ==========================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Alive')

# Добавляем класс, который умеет переиспользовать занятый порт
class ReusableServer(HTTPServer):
    allow_reuse_address = True

def keep_alive():
    port = int(os.environ.get('PORT', 8080))
    # Слушаем все адреса (0.0.0.0), чтобы Render точно был доволен
    server = ReusableServer(('0.0.0.0', port), PingHandler)
    server.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ==========================================
# 2. НАСТРОЙКА API
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
# Используем самую актуальную версию Flash
model = genai.GenerativeModel('gemini-1.5-flash-latest')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. ЛОГИКА И ОТЛОВ ОШИБОК
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я ИИ-бот на базе Gemini. Напиши мне что-нибудь!")

@dp.message(F.text)
async def handle_text(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = model.generate_content(message.text)
        await message.reply(response.text)
        
    except Exception as e:
        # ТЕПЕРЬ БОТ ПРИШЛЕТ ТЕКСТ ОШИБКИ ПРЯМО В ЧАТ!
        await message.reply(f"Произошла ошибка API:\n`{e}`", parse_mode="Markdown")

# ==========================================
# 4. ЗАПУСК
# ==========================================
async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
