import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class PingHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'Alive')


def keep_alive():
  port = int(os.environ.get('PORT', 8080))
  server = HTTPServer(('', port), PingHandler)
  server.serve_forever()


threading.Thread(target=keep_alive, daemon=True).start()

import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ==========================================
# 1. МИНИ-СЕРВЕР ДЛЯ RENDER (ЗАЩИТА ОТ СНА)
# ==========================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Alive')

def keep_alive():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), PingHandler)
    server.serve_forever()

# Запускаем сервер в фоновом потоке
threading.Thread(target=keep_alive, daemon=True).start()

# ==========================================
# 2. НАСТРОЙКА API И ТОКЕНОВ
# ==========================================
# Ключи берутся из настроек Render (Environment Variables)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Ошибка: Не указан BOT_TOKEN или GEMINI_API_KEY в переменных окружения!")

# Настраиваем ИИ-модель (используем быструю и современную версию)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Настраиваем Telegram-бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. ЛОГИКА РАБОТЫ БОТА
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я ИИ-бот на базе Gemini. Напиши мне что-нибудь!")

@dp.message(F.text)
async def handle_text(message: types.Message):
    # Показываем статус "печатает...", пока нейросеть думает
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Отправляем текст пользователя в Gemini
        response = model.generate_content(message.text)
        
        # Отправляем ответ нейросети обратно в Telegram
        await message.reply(response.text)
        
    except Exception as e:
        await message.reply("Произошла ошибка при обращении к нейросети. Попробуй позже.")
        print(f"Ошибка Gemini API: {e}")

# ==========================================
# 4. ЗАПУСК БОТА
# ==========================================
async def main():
    print("Бот успешно запущен и готов к работе!")
    # Запускаем постоянный опрос серверов Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
