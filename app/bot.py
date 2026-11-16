import os
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from aiogram.client.session.aiohttp import AiohttpSession

from app.db import SessionLocal, init_db
from app.models import Expense

BOT_TOKEN = os.getenv("BOT_TOKEN")

session = AiohttpSession(proxy="socks5://127.0.0.1:1080")

bot = Bot(token=BOT_TOKEN, session=session)

dp = Dispatcher()

# Простейший парсер: "кофе 250" → (description="кофе", amount=250.0)
PATTERN = re.compile(r"^(?P<desc>.+?)\s+(?P<amount>\d+(?:[.,]\d{1,2})?)$")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Пиши траты в формате:\n"
        "<описание> <сумма>\n\n"
        "Например: `кофе 250`\n\n"
        "Команды: /stats — статистика за сегодня"
    )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        start = datetime.combine(today, datetime.min.time())
        expenses = (
            db.query(Expense)
            .filter(Expense.user_id == message.from_user.id, Expense.created_at >= start)
            .all()
        )
        total = sum(e.amount for e in expenses)
        if not expenses:
            await message.answer("Сегодня трат ещё нет 🙂")
            return
        lines = [f"• {e.description}: {e.amount:.2f}" for e in expenses]
        await message.answer(
            "Траты за сегодня:\n" + "\n".join(lines) + f"\n\n<b>Итого: {total:.2f}</b>",
            parse_mode="HTML",
        )
    finally:
        db.close()


@dp.message(F.text)
async def handle_expense(message: Message):
    match = PATTERN.match(message.text.strip())
    if not match:
        await message.answer("Не понял 🤔 Формат: `<описание> <сумма>`", parse_mode="HTML")
        return

    desc = match.group("desc").strip()
    amount = float(match.group("amount").replace(",", "."))

    db = SessionLocal()
    try:
        expense = Expense(user_id=message.from_user.id, amount=amount, description=desc)
        db.add(expense)
        db.commit()
        await message.answer(f"✅ Записал: {desc} — {amount:.2f}")
    finally:
        db.close()


async def main():
    init_db()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())