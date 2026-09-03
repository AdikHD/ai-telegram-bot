import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ==========================================
# 1. МИНИ-СЕРВЕР (ЗАЩИТА ОТ СНА ДЛЯ RENDER)
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

# Подключаем твою рабочую модель
model = genai.GenerativeModel('models/gemini-2.5-flash')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. ДОЛГОВРЕМЕННАЯ ПАМЯТЬ БОТА
# ==========================================
# Словарь для хранения историй переписок разных пользователей
user_chats = {}

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    # Создаем или сбрасываем память пользователя при команде /start
    user_chats[user_id] = model.start_chat(history=[])
    await message.answer("Привет! Я обновленный ИИ-бот с долговременной памятью. Давай общаться!")

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    
    # Если пользователь пишет впервые (без /start), создаем для него новую сессию памяти
    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])
        
    chat_session = user_chats[user_id]
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Отправляем сообщение не просто модели, а в конкретную сессию с контекстом
        response = chat_session.send_message(message.text)
        await message.reply(response.text)
        
    except Exception as e:
        await message.reply(f"Произошла ошибка:\n`{e}`", parse_mode="Markdown")

# ==========================================
# 4. ЗАПУСК
# ==========================================
async def main():
    print("ИИ-бот с памятью успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
