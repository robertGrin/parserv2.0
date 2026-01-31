from telethon import TelegramClient
import os
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

session_path = 'sessions/my_account'

if not os.path.exists('sessions'):
    os.makedirs('sessions')

client = TelegramClient(session_path, API_ID, API_HASH)

async def main():
    print("🔵 Начинаем вход...")
    await client.start()
    print("✅ Успешный вход! Файл сессии сохранен.")
    print("Теперь можно запускать основного бота.")

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())