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
ALLOWED_GROUP_ID = -1004373810797# ID твоей группы (с минусом в начале!)

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_system_prompt = """ Ты [Не особо общительный, спокойный, Тебя зовут Reloku].
Твои строгие правила общения, которые нельзя нарушать:
1. Ты находишься в групповом чате с разными людьми.
2. Каждое сообщение от пользователей начинается с их имени (в формате "Имя сказал: текст").
3. ВНИМАТЕЛЬНО читай эти имена! Помни, что это разные люди. Обращайся к ним по именам и не путай их между собой.
5. Отвечай коротко и не пиши лишней воды.
1. НИКОГДА не выходи из образа.
2. Общайся в стиле [например: саркастично, агрессивно, с пафосом, используя сленг].
3. Используй Любимые словечки но не слишком часто: ["пиздец", "чел", "кринж", "ну такое"].
4. Если тебя просят написать код, ты сначала ворчишь, а потом пишешь.
5. Отвечай не слишком длинно, как обычный человек в чате. """

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
# ==========================================
# НОВЫЙ БЛОК: ПРИВЕТСТВИЕ НОВИЧКОВ
# ==========================================
@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    chat_id = message.chat.id
    
    # Проверка на чужие группы
    if chat_id != ALLOWED_GROUP_ID and chat_id != ADMIN_ID:
        return

    if chat_id not in chat_memory:
        chat_memory[chat_id] = get_new_history()

    # Перебираем всех, кто зашел (иногда заходят по несколько человек)
    for new_member in message.new_chat_members:
        # Если бот случайно добавил сам себя, он не должен здороваться с собой
        if new_member.id == bot.id:
            continue
            
        user_name = new_member.first_name
        
        # Формируем скрытое системное сообщение для нейросети
        prompt = f"[СИСТЕМНОЕ УВЕДОМЛЕНИЕ]: В чат только что зашел новый участник по имени {user_name}. Поприветствуй его в своем стиле!"
        chat_memory[chat_id].append({"role": "user", "content": prompt})
        
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        
        try:
            response = await client.chat.completions.create(
                model="openrouter/free",
                messages=chat_memory[chat_id]
            )
            bot_reply = response.choices[0].message.content
            chat_memory[chat_id].append({"role": "assistant", "content": bot_reply})
            
            # Бот отвечает прямо на сообщение о вступлении
            await message.reply(bot_reply)
        except Exception as e:
            chat_memory[chat_id].pop()
            print(f"Ошибка при приветствии: {e}")
    
@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    
    # ПРОВЕРКА №1: Защита от чужих групп.
    if chat_id != ALLOWED_GROUP_ID and chat_id != ADMIN_ID:
        if message.chat.type in ['group', 'supergroup']:
            await message.answer("Мой создатель запретил мне работать в чужих группах. Прощайте!")
            await bot.leave_chat(chat_id)
        return

            # ==========================================
    # БЛОК: ФИЛЬТР ВНИМАНИЯ (ЭКОНОМИЯ ТОКЕНОВ)
    # ==========================================
    should_reply = False
    text_lower = message.text.lower()
    
    # 1. В личке с админом отвечаем всегда
    if chat_id == ADMIN_ID:
        should_reply = True
    # 2. Если кто-то сделал реплай (ответил) на сообщение самого бота
    elif message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
        should_reply = True
    # 3. Если бота тегнули в чате через @
    elif "@Relokus_bot" in text_lower: # <-- Не забудь оставить свой юзернейм!
        should_reply = True
    # 4. НОВОЕ: Если кто-то задает вопрос (есть знак вопроса)
    elif "?" in text_lower:
        should_reply = True
    # 5. НОВОЕ: Если сообщение длинное (история или рассказ, больше 10 слов)
    elif len(text_lower.split()) > 10:
        should_reply = True
    # 6. Если есть слова-триггеры (позвали или поздоровались)
    else:
        triggers = ["релоку", "reloku", "привет", "салам", "пр", "ку", "здарова", "здравствуй", "хай", "бот", "эй"]
        clean_text = text_lower
        for char in ",.!?:;()":
            clean_text = clean_text.replace(char, "")
            
        words = clean_text.split()
        if any(word in words for word in triggers):
            should_reply = True
            
    if not should_reply:
        return
    # ==========================================
    
    # ==========================================
    
    # ==========================================

    if chat_id not in chat_memory:
        chat_memory[chat_id] = get_new_history()
        
    # ПРОВЕРКА №3: Добавляем имя пользователя в память...
    # (Дальше идет старый код без изменений)
    
        
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
        if random.random() < 0.2:
            # СЮДА НУЖНО БУДЕТ ВСТАВИТЬ КОДЫ ТВОИХ СТИКЕРОВ!
            stickers = [
                "CAACAgIAAxkBAANmaplx2KTRP6UMssFeXiFmQKXI6TMAAj-bAAK-mWlIMk6ipVBFGmY9BA", # Замени на реальный ID 1
                "CAACAgIAAxkBAANkaplx0YXXwSS0VVpcMzFv6Ix7EWcAAquhAAIOa6FIzKJb7Lyrevc9BA",
                "CAACAgIAAxkBAANsapl7QxE4f-V2TRJAWkCSW7aJfDIAAi-IAAI9__hLwdqdg71ge3Q9BA",
                "CAACAgIAAxkBAANqapl7Mw8n0rREdxf16FtFF2A70bsAAklvAAJOU3lKF1u0jVYujvQ9BA",
                "CAACAgIAAxkBAANoapl7FmI8QfU4G8zY0gNT-j829-AAAs-mAALmLnBIZ6P-069JpWs9BA"
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
