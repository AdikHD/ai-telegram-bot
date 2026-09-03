import os
import asyncio
import threading
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

from openai import AsyncOpenAI
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

# ==========================================
# 2. НАСТРОЙКИ (ВСТАВЬ СВОИ ДАННЫЕ!)
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

ADMIN_ID = 8503497111           # Твой ID из Телеграма
ALLOWED_GROUP_ID = -1003970909380# ID твоей группы (с минусом в начале!)

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_system_prompt = "Ты участник чата. Отвечай коротко и естественно."
# Теперь память привязана к чатам (группе), а не к отдельным юзерам
chat_memory = {}

def get_new_history():
    return [{"role": "system", "content": current_system_prompt}]

# ==========================================
# 3. ЛОГИКА АДМИНА
# ==========================================
@dp.message(Command("setrole"))
async def cmd_setrole(message: types.Message):
    global current_system_prompt
    if message.from_user.id != ADMIN_ID:
        return
    new_role = message.text.replace("/setrole", "").strip()
    if not new_role:
        await message.reply("Напиши роль. Пример: /setrole Ты злой пират.")
        return
    current_system_prompt = new_role
    chat_memory.clear()
    await message.reply(f"Успешно! Моя новая базовая установка:\n{current_system_prompt}")

# СЕКРЕТНАЯ ФУНКЦИЯ: Узнаем ID стикеров
@dp.message(F.sticker)
async def handle_sticker(message: types.Message):
    if message.chat.id == ADMIN_ID:
        await message.reply(f"ID этого стикера:\n`{message.sticker.file_id}`", parse_mode="Markdown")

# ==========================================
# 4. ОБЩАЯ ЛОГИКА ГРУППЫ И ОТВЕТЫ
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    chat_memory[chat_id] = get_new_history()
    await message.answer("Бот запущен!")

@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    
    # ПРОВЕРКА №1: Защита от чужих групп. Бот работает только в выбранной группе и в личке с админом.
    if chat_id != ALLOWED_GROUP_ID and chat_id != ADMIN_ID:
        if message.chat.type in ['group', 'supergroup']:
            await message.answer("Мой создатель запретил мне работать в чужих группах. Прощайте!")
            await bot.leave_chat(chat_id)
        return

    if chat_id not in chat_memory:
        chat_memory[chat_id] = get_new_history()
        
    # ПРОВЕРКА №3: Добавляем имя пользователя в память, чтобы бот знал, с кем говорит
    formatted_text = f"{user_name} сказал: {message.text}"
    chat_memory[chat_id].append({"role": "user", "content": formatted_text})
    
    # Делаем вид, что печатаем (в группе это выглядит круто)
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=chat_memory[chat_id]
        )
        bot_reply = response.choices[0].message.content
        chat_memory[chat_id].append({"role": "assistant", "content": bot_reply})
        
        await message.reply(bot_reply)
        
        # ПРОВЕРКА №4: Шанс 10% кинуть стикер после ответа
        if random.random() < 0.1:
            # СЮДА НУЖНО БУДЕТ ВСТАВИТЬ КОДЫ ТВОИХ СТИКЕРОВ!
            stickers = [
                "CAACAgIAAxkBAAE...", # Замени на реальный ID 1
                "CAACAgIAAxkBAAE..."  # Замени на реальный ID 2
            ]
            # Выбираем случайный стикер из списка
            chosen_sticker = random.choice(stickers)
            if chosen_sticker != "CAACAgIAAxkBAAE...": # Проверка, что ты их заменил
                await message.answer_sticker(chosen_sticker)
            
    except Exception as e:
        chat_memory[chat_id].pop()
        error_msg = str(e).lower()
        
        # ПРОВЕРКА №2: Реакция на лимиты OpenRouter (ошибки 429, 402 или исчерпание квоты)
        if "402" in error_msg or "429" in error_msg or "limit" in error_msg or "quota" in error_msg:
            await message.reply("Я устал, пойду отдохну 💤")
        else:
            await message.reply(f"Произошла техническая ошибка:\n`{e}`", parse_mode="Markdown")

async def main():
    print("Групповой ИИ-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
