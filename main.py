import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Alive')
        
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
        

class ReusableServer(HTTPServer):
    allow_reuse_address = True

def keep_alive():
    port = int(os.environ.get('PORT', 8080))
    server = ReusableServer(('0.0.0.0', port), PingHandler)
    server.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

ADMIN_ID = 8503497111  # ВСТАВЬ СЮДА СВОЙ ID ИЗ ТЕЛЕГРАМА!

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_system_prompt = "Ты дружелюбный ИИ-ассистент."
user_chats = {}

def get_new_history():
    return [{"role": "system", "content": current_system_prompt}]

@dp.message(Command("setrole"))
async def cmd_setrole(message: types.Message):
    global current_system_prompt
    if message.from_user.id != ADMIN_ID:
        await message.reply("У тебя нет прав менять мою личность!")
        return
    new_role = message.text.replace("/setrole", "").strip()
    if not new_role:
        await message.reply("Напиши роль. Пример: /setrole Ты злой пират.")
        return
    current_system_prompt = new_role
    user_chats.clear()
    await message.reply(f"Успешно! Моя новая базовая установка:\n{current_system_prompt}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_chats[message.from_user.id] = get_new_history()
    await message.answer("Я сменил ядро на Llama 3.1 и готов к работе! Напиши мне.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_chats:
        user_chats[user_id] = get_new_history()
    user_chats[user_id].append({"role": "user", "content": message.text})
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=user_chats[user_id]
        )
        bot_reply = response.choices[0].message.content
        user_chats[user_id].append({"role": "assistant", "content": bot_reply})
        await message.reply(bot_reply)
    except Exception as e:
        user_chats[user_id].pop()
        await message.reply(f"Произошла ошибка:\n{e}")

async def main():
    print("Бот на OpenRouter успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
