# -*- coding: utf-8 -*-
import asyncio
import os
import logging
import io
import matplotlib
# Устанавливаем бэкенд 'Agg' для работы без монитора
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import google.generativeai as genai

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

ADMIN_ID = int(os.getenv("ADMIN_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- ИНИЦИАЛИЗАЦИЯ ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
# pool_pre_ping помогает не терять связь с БД
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class ParsedMessage(Base):
    __tablename__ = "parsed_messages"
    id = Column(Integer, primary_key=True)
    channel_name = Column(String)
    text = Column(Text)
    date = Column(DateTime, default=datetime.now)

Base.metadata.create_all(engine)
user_client = None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def fetch_history(client, channel_entity, limit=100):
    """Скачивает последние сообщения из канала в базу"""
    db = SessionLocal()
    count = 0
    try:
        chat_title = getattr(channel_entity, 'title', 'Unknown')
        async for message in client.iter_messages(channel_entity, limit=limit):
            if message.text:
                msg = ParsedMessage(
                    channel_name=chat_title,
                    text=message.text,
                    date=message.date.replace(tzinfo=None)
                )
                db.add(msg)
                count += 1
        db.commit()
        return count
    except Exception as e:
        logging.error(f"Ошибка истории: {e}")
        return 0
    finally:
        db.close()

def generate_plot(df):
    """Рисует график"""
    if df.empty: return None
    counts = df['channel_name'].value_counts().head(10)
    
    plt.figure(figsize=(10, 6))
    counts.plot(kind='bar', color='skyblue')
    plt.title('Топ каналов')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

async def get_ai_analysis(df):
    """Аналитика от Gemini"""
    if not ai_model: return "⚠️ ИИ выключен (нет ключа)."
    top_channels = df['channel_name'].value_counts().head(5).to_string()
    prompt = (
        f"Проанализируй {len(df)} сообщений из Telegram.\n"
        f"Топ источников:\n{top_channels}\n\n"
        f"Напиши краткий отчет на русском: что это за данные и дай совет по парсингу."
    )
    try:
        response = await ai_model.generate_content_async(prompt)
        return response.text
    except: return "Ошибка генерации отчета."

# --- ЮЗЕР-БОТ ---
async def start_user_bot():
    global user_client
    session_dir = "sessions"
    if not os.path.exists(session_dir): os.makedirs(session_dir)
    
    files = [f for f in os.listdir(session_dir) if f.endswith('.session')]
    if not files: return None

    session_path = os.path.join(session_dir, files[0].replace('.session', ''))
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized(): return None

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        try:
            chat = await event.get_chat()
            if event.message.text:
                db = SessionLocal()
                db.add(ParsedMessage(
                    channel_name=getattr(chat, 'title', 'Unknown'), 
                    text=event.message.text
                ))
                db.commit()
                db.close()
        except: pass
    
    print("✅ Юзер-бот активен!")
    return client

# --- КОМАНДЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "🤖 **AI Parser v4.0**\n\n"
        "📡 **Управление:**\n"
        "`/list` - Мои каналы\n"
        "`/join <ссылка>` - Вступить + История\n"
        "`/sync` - Скачать историю всех каналов\n\n"
        "📊 **Аналитика:**\n"
        "`/stats` - График + AI отчет\n"
        "`/export` - Excel файл",
        parse_mode="Markdown"
    )

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    if message.from_user.id != ADMIN_ID or not user_client: return
    status = await message.answer("⏳ Загружаю список...")
    text = "<b>Ваши каналы:</b>\n\n"
    async for dialog in user_client.iter_dialogs():
        if dialog.is_channel:
            text += f"• {dialog.name}\n"
    await status.edit_text(text[:4096], parse_mode="HTML")

@dp.message(Command("sync"))
async def cmd_sync(message: types.Message):
    if message.from_user.id != ADMIN_ID or not user_client: return
    status = await message.answer("⏳ Синхронизация истории (это может занять время)...")
    total = 0
    async for dialog in user_client.iter_dialogs():
        if dialog.is_channel:
            total += await fetch_history(user_client, dialog.entity, limit=50)
    await status.edit_text(f"✅ Готово! Загружено сообщений: {total}")

@dp.message(Command("join"))
async def cmd_join(message: types.Message):
    if message.from_user.id != ADMIN_ID or not user_client: return
    link = message.text.replace("/join", "").strip()
    status = await message.answer("⏳ Вступаю...")
    try:
        if "+" in link:
            updates = await user_client(ImportChatInviteRequest(link.split('+')[-1]))
            target = updates.chats[0]
        else:
            target = await user_client.get_entity(link)
            await user_client(JoinChannelRequest(target))
        
        count = await fetch_history(user_client, target, limit=100)
        await status.edit_text(f"✅ Подписан на {getattr(target, 'title', link)}!\nСкачано постов: {count}")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    status = await message.answer("🎨 Рисую график и думаю...")
    db = SessionLocal()
    try:
        df = pd.read_sql(db.query(ParsedMessage).statement, engine)
        if df.empty: 
            await status.edit_text("Пусто.")
            return
        
        plot_buf = generate_plot(df)
        ai_text = await get_ai_analysis(df)
        
        if plot_buf:
            photo = BufferedInputFile(plot_buf.read(), filename="stats.png")
            await message.answer_photo(photo=photo, caption=f"🧠 **Анализ:**\n{ai_text}", parse_mode="Markdown")
            await status.delete()
    finally: db.close()

@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    db = SessionLocal()
    df = pd.read_sql(db.query(ParsedMessage).statement, engine)
    db.close()
    df.to_excel("data.xlsx", index=False)
    await message.answer_document(types.FSInputFile("data.xlsx"))
    os.remove("data.xlsx")

async def main():
    global user_client
    print("⏳ Подключение к БД...")
    await asyncio.sleep(5)
    user_client = await start_user_bot()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())