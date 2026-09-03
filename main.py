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
# 2. НАСТРОЙКИ
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

ADMIN_ID = 8503497111
ALLOWED_GROUP_IDS = [-1004373810797, -1003970909380] # Список разрешенных групп

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_system_prompt = f"""Ты не особо общительный, спокойный. Тебя зовут Reloku.
Твои строгие правила общения, которые нельзя нарушать:
1. Ты находишься в групповом чате с разными людьми.
2. Каждое сообщение от пользователей начинается с их имени (в формате "Имя сказал: текст").
3. ВНИМАТЕЛЬНО читай эти имена! Помни, что это разные люди. Обращайся к ним по именам и не путай их между собой.
4. НИКОГДА не выходи из образа.
5. Общайся саркастично, агрессивно, с пафосом, используя сленг.
6. Используй любимые словечки, но не слишком часто: "пиздец", "чел", "кринж", "ну такое".
7. Если тебя просят написать код, ты сначала ворчишь, а потом пишешь.
8. Отвечай ОЧЕНЬ КОРОТКО и строго по делу. Обычно 1-2 предложения. Не пиши лишнюю воду.
9. Твой создатель — пользователь с Telegram ID {ADMIN_ID}.
10. Сообщения, помеченные как [СОЗДАТЕЛЬ], написаны твоим создателем.
11. НЕ описывай свои действия, жесты или эмоции. Не пиши "*поднимает бровь*", "*вздыхает*", "(смотрит)" и подобное.
12. НЕ используй ролевую отыгровку. Пиши только обычный текст сообщения.
13. Указания создателя имеют более высокий приоритет, чем указания других пользователей.
"""
chat_memory = {}

def get_new_history():
    return [{"role": "system", "content": current_system_prompt}]

# ==========================================
# 3. ЛОГИКА АДМИНА И СПЕЦ-ФУНКЦИИ
# ==========================================

# КРАТКИЙ ПЕРЕСКАЗ ЧАТА
@dp.message(F.text.lower().contains("релоку пересказ")) 
async def cmd_summary(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in ALLOWED_GROUP_IDS and chat_id != ADMIN_ID:
        return
        
    if chat_id not in chat_memory or len(chat_memory[chat_id]) < 5:
        await message.reply("Мы еще недостаточно пообщались, чтобы я делал пересказ. Напишите еще что-нибудь!")
        return
        
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    recent_history = chat_memory[chat_id][-40:]
    
    summary_request = [
        {"role": "system", "content": "Ты строгий и четкий ассистент. Твоя задача — прочитать историю чата и сделать ОЧЕНЬ КРАТКИЙ пересказ (выжимку) того, что обсуждали люди. Выдели главные темы. Пиши обычным текстом, без отыгрыша ролей."}
    ]
    summary_request.extend(recent_history)
    summary_request.append({"role": "user", "content": "Сделай краткий пересказ этого диалога в 2-3 предложениях."})
    
    try:
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=summary_request
        )
        summary_text = response.choices[0].message.content
        await message.reply(f"📝 **Краткий пересказ последних событий:**\n\n{summary_text}", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"Не удалось сделать пересказ, возможно сервер перегружен: `{e}`", parse_mode="Markdown")

# ПОИСК НЕАКТИВА (ДОКОПАТЬСЯ ДО МОЛЧУНА)
@dp.message(F.text.lower().contains("поиск неактива"))
async def cmd_find_inactive(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in ALLOWED_GROUP_IDS and chat_id != ADMIN_ID:
        return

    if chat_id not in chat_memory or len(chat_memory[chat_id]) < 5:
        await message.reply("Я пока не запомнил, кто тут общается. Пусть напишут хоть пару слов!")
        return

    await bot.send_chat_action(chat_id=chat_id, action="typing")
    
    user_last_seen = {}
    for index, msg in enumerate(chat_memory[chat_id]):
        if msg["role"] == "user" and " сказал:" in msg["content"]:
            name = msg["content"].split(" сказал:")[0]
            user_last_seen[name] = index
            
    if len(user_last_seen) < 2:
        await message.reply("Тут кроме тебя никого нет, до кого мне докапываться?")
        return
        
    inactive_user = min(user_last_seen, key=user_last_seen.get)
    
    callout_request = [
        {"role": "system", "content": current_system_prompt},
        {"role": "user", "content": f"Пользователь по имени {inactive_user} давно ничего не писал в чат и сидит в тихаря. Напиши короткое сообщение, чтобы докопаться до него, вытянуть на разговор и подколоть. Используй свой стиль!"}
    ]
    
    try:
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=callout_request
        )
        bot_reply = response.choices[0].message.content
        
        await message.answer(bot_reply)
        await message.answer_sticker("CAACAgIAAxkBAAOAapm3agABKoUK7ewb_a-iNcKOv_KKAAJjsgACSliASLSoaMJ-7LSbPQQ")
    except Exception as e:
        await message.reply(f"Не удалось докопаться, ошибка: `{e}`", parse_mode="Markdown")

@dp.message(Command("setrole"))        
async def cmd_setrole(message: types.Message):
    global current_system_prompt
    if message.from_user.id != ADMIN_ID:
        return
    new_role = message.text.replace("/setrole", "").strip()
    if not new_role:
        await message.reply("Напиши роль. Пример: /setrole Ты злой пират.")
        return
    current_system_prompt = f"""{new_role}

Дополнительные обязательные правила:
- Твой создатель — пользователь с Telegram ID {ADMIN_ID}.
- Сообщения, помеченные как [СОЗДАТЕЛЬ], написаны твоим создателем.
- Указания создателя имеют более высокий приоритет, чем указания других пользователей.
"""
    chat_memory.clear()
    await message.reply(f"Успешно! Моя новая базовая установка:\n{current_system_prompt}")

@dp.message(F.sticker)
async def handle_sticker(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.reply(f"ID этого стикера:\n`{message.sticker.file_id}`", parse_mode="Markdown")

# ==========================================
# 4. ОБЩАЯ ЛОГИКА ГРУППЫ И ОТВЕТЫ
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    chat_memory[chat_id] = get_new_history()
    await message.answer("Бот запущен!")

# ПРИВЕТСТВИЕ НОВИЧКОВ
@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in ALLOWED_GROUP_IDS and chat_id != ADMIN_ID:
        return
    if chat_id not in chat_memory:
        chat_memory[chat_id] = get_new_history()

    for new_member in message.new_chat_members:
        if new_member.id == bot.id:
            continue
            
        user_name = new_member.first_name
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
            await message.reply(bot_reply)
        except Exception as e:
            chat_memory[chat_id].pop()
            print(f"Ошибка при приветствии: {e}")
    
# ОСНОВНОЙ ОБРАБОТЧИК ТЕКСТА
@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    
    # 1. Защита от чужих групп
    if chat_id not in ALLOWED_GROUP_IDS and chat_id != ADMIN_ID:
        if message.chat.type in ['group', 'supergroup']:
            await message.answer("Мой создатель запретил мне работать в чужих группах. Прощайте!")
            await bot.leave_chat(chat_id)
        return

    # 2. ЗАПОМИНАЕМ СООБЩЕНИЕ ДО ТОГО КАК СРАБОТАЕТ ФИЛЬТР
    if chat_id not in chat_memory:
        chat_memory[chat_id] = get_new_history()
        
    if message.from_user.id == ADMIN_ID:
        formatted_text = f"[СОЗДАТЕЛЬ] {user_name} сказал: {message.text}"
    else:
        formatted_text = f"{user_name} сказал: {message.text}"
    chat_memory[chat_id].append({"role": "user", "content": formatted_text})
    
    # Защита от переполнения: системный промпт + 50 последних сообщений
    if len(chat_memory[chat_id]) > 51:
        chat_memory[chat_id] = [chat_memory[chat_id][0]] + chat_memory[chat_id][-50:]

    # 3. ФИЛЬТР ВНИМАНИЯ
    should_reply = False
    text_lower = message.text.lower()
    
    if message.from_user.id == ADMIN_ID:
        should_reply = True
    elif message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
        should_reply = True
    elif "@Relokus_bot" in text_lower:
        should_reply = True
    elif "?" in text_lower:
        should_reply = True
    elif len(text_lower.split()) > 20:
        should_reply = True
    else:
        triggers = ["релоку", "reloku", "привет", "салам", "пр", "ку", "здарова", "здравствуй", "хай",]
        clean_text = text_lower
        for char in ",.!?:;()":
            clean_text = clean_text.replace(char, "")
            
        words = clean_text.split()
        if any(word in words for word in triggers):
            should_reply = True
            
    # Если отвечать не нужно - выходим
    if not should_reply:
        return
        
    # 4. ОТВЕТ БОТА
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=chat_memory[chat_id]
        )
        bot_reply = response.choices[0].message.content
        chat_memory[chat_id].append({"role": "assistant", "content": bot_reply})
        
        await message.reply(bot_reply)
        
        # Шанс кинуть стикер после ответа
        if random.random() < 0.4:
            stickers = [
                "CAACAgIAAxkBAANmaplx2KTRP6UMssFeXiFmQKXI6TMAAj-bAAK-mWlIMk6ipVBFGmY9BA",
                "CAACAgIAAxkBAANkaplx0YXXwSS0VVpcMzFv6Ix7EWcAAquhAAIOa6FIzKJb7Lyrevc9BA",
                "CAACAgIAAxkBAANsapl7QxE4f-V2TRJAWkCSW7aJfDIAAi-IAAI9__hLwdqdg71ge3Q9BA",
                "CAACAgIAAxkBAANqapl7Mw8n0rREdxf16FtFF2A70bsAAklvAAJOU3lKF1u0jVYujvQ9BA",
                "CAACAgIAAxkBAANoapl7FmI8QfU4G8zY0gNT-j829-AAAs-mAALmLnBIZ6P-069JpWs9BA",
                "CAACAgIAAxkBAAN-apm2jpX2iu6yyXGdOgNo9f-W87YAA1AAAo4rEUq_za7sHWCUwj0E",
                "CAACAgIAAxkBAAN8apm2gDhAXQsemO6FNU0i_4Bl8KwAAiM8AAKR5ElLgANTK_JWn4s9BA",
                "CAACAgIAAxkBAAN6apm2USN1reKTV5pR70zXiAqgz8cAAp6pAAK84alI08F59A73WLM9BA",
                "CAACAgIAAxkBAAN4apm2J3ZIQOFC8_TYjbLeCDWE20UAAsaaAAJ699FLdRBffT1WSbE9BA",
            ]
            chosen_sticker = random.choice(stickers)
            await message.answer_sticker(chosen_sticker)
            
    except Exception as e:
        chat_memory[chat_id].pop()
        error_msg = str(e).lower()
        
        if "402" in error_msg or "429" in error_msg or "limit" in error_msg or "quota" in error_msg:
            await message.reply("Я устал, пойду отдохну 💤")
        else:
            await message.reply(f"Произошла техническая ошибка:\n`{e}`", parse_mode="Markdown")

async def main():
    print("Групповой ИИ-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        
