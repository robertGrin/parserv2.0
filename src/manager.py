# -*- coding: utf-8 -*-
import asyncio
import os
import logging
import io
import matplotlib
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

load_dotenv()
logging.basicConfig(level=logging.INFO)

ADMIN_ID = int(os.getenv("ADMIN_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
# Используем пул соединений для стабильности в Docker
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class ParsedMessage(Base):
    __tablename__ = "parsed_messages"
    id = Column(Integer, primary_key=True)
    channel_name = Column(String)
    text = Column(Text)
    date = Column(DateTime, default=datetime.now)

user_client = None

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
            if event.message.message:
                db = SessionLocal()
                db.add(ParsedMessage(channel_name=getattr(chat, 'title', 'Unknown'), text=event.message.message))
                db.commit()
                db.close()
        except: pass
    return client

# --- Команды /start, /join, /stats, /export (как в твоем исходнике) ---
#

async def main():
    global user_client
    print("⏳ Ожидание базы данных (10 сек)...")
    await asyncio.sleep(10)
    
    try:
        Base.metadata.create_all(engine)
        print("✅ База подключена!")
        user_client = await start_user_bot()
        print("🚀 Бот запущен!")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())