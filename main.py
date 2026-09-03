import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command

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
# 2. НАСТРОЙКИ АДМИНА И API
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# ВСТАВЬ СЮДА ЦИФРЫ СВОЕГО ID!
ADMIN_ID = 123456789  

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Базовый стиль общения по умолчанию
current_system_prompt = "Ты дружелюбный и краткий ИИ-ассистент."
user_chats = {}

# Функция создания сессии с жестким системным промптом
def create_chat_session():
    model = genai.GenerativeModel(
        'models/gemini-3.6-flash',
        system_instruction=current_system_prompt
    )
    return model.start_chat(history=[])

# ==========================================
# 3. ЛОГИКА СМЕНЫ РОЛИ (ТОЛЬКО ДЛЯ АДМИНА)
# ==========================================
@dp.message(Command("setrole"))
async def cmd_setrole(message: types.Message):
    global current_system_prompt
    
    # Блокируем доступ всем, кроме тебя
    if message.from_user.id != ADMIN_ID:8503497111
        await message.reply("У тебя нет прав менять мою личность! 🚫")
        return
        
    # Вытаскиваем текст новой роли
    new_role = message.text.replace("/setrole", "").strip()
    
    if not new_role:
        await message.reply("Напиши роль. Пример: /setrole Ты злой пират.")
        return
        
    current_system_prompt = new_role
    # Очищаем всем память, чтобы новая личность загрузилась с чистого листа
    user_chats.clear() 
    
    await message.reply(f"✅ Успешно! Моя новая базовая установка:\n{current_system_prompt}")

# ==========================================
# 4. ОБЩАЯ ЛОГИКА
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_chats[message.from_user.id] = create_chat_session()
    await message.answer("Я готов к работе. Напиши мне что-нибудь!")

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_chats:
        user_chats[user_id] = create_chat_session()
        
    chat_session = user_chats[user_id]
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Обрати внимание, здесь уже добавлен _async, чтобы бот не "висел"!
        response = await chat_session.send_message_async(message.text)
        await message.reply(response.text)
    except Exception as e:
        await message.reply(f"Произошла ошибка:\n`{e}`", parse_mode="Markdown")

# ==========================================
# 5. ЗАПУСК
# ==========================================
async def main():
    print("Бот с управлением ролями запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
