import os
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.session.aiohttp import AiohttpSession

from app.db import SessionLocal, init_db
from app.models import Expense

BOT_TOKEN = os.getenv("BOT_TOKEN")
session = AiohttpSession(proxy="socks5://127.0.0.1:1080")
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

# --- Машина состояний (FSM) ---
class ExpenseForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()

# Паттерн для поиска суммы в тексте (например, "250" или "250.50")
PATTERN = re.compile(r"(?P<amount>\d+(?:[.,]\d{1,2})?)")

# Кнопки категорий
def get_categories_keyboard():
    kb = [
        [InlineKeyboardButton(text="🍔 Еда", callback_data="cat_food"),
         InlineKeyboardButton(text="🚕 Транспорт", callback_data="cat_transport")],
        [InlineKeyboardButton(text="🎮 Развлечения", callback_data="cat_fun"),
         InlineKeyboardButton(text="📦 Другое", callback_data="cat_other")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я помогу вести учёт расходов.\n\n"
        "Просто отправь мне сумму траты (например, `250` или `250.50`), "
        "а я предложу выбрать категорию.\n\n"
        "Команды:\n"
        "/stats — статистика за сегодня\n"
        "/month — статистика за месяц"
    )

# --- Обработка ввода суммы ---
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_amount(message: Message, state: FSMContext):
    match = PATTERN.search(message.text)
    if not match:
        await message.answer("Не понял 🤔 Отправь просто число, например: `250` или `250.50`")
        return

    amount = float(match.group("amount").replace(",", "."))
    await state.update_data(amount=amount)
    
    await message.answer(
        f"Записываю {amount:.2f} руб.\nВыбери категорию:",
        reply_markup=get_categories_keyboard()
    )
    await state.set_state(ExpenseForm.waiting_for_category)

# --- Обработка выбора категории ---
@dp.callback_query(ExpenseForm.waiting_for_category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await state.clear()
        await callback.message.edit_text("Отменено. Отправь новую сумму.")
        return

    category_map = {
        "cat_food": "Еда",
        "cat_transport": "Транспорт",
        "cat_fun": "Развлечения",
        "cat_other": "Другое"
    }
    category = category_map.get(callback.data, "Другое")
    
    data = await state.get_data()
    amount = data.get("amount")

    # Сохраняем в БД
    db = SessionLocal()
    try:
        expense = Expense(
            user_id=callback.from_user.id, 
            amount=amount, 
            category=category,
            description=""
        )
        db.add(expense)
        db.commit()
        await callback.message.edit_text(f"✅ Записано: {amount:.2f} руб. в категорию «{category}»")
    finally:
        db.close()
        await state.clear()

# --- Статистика за сегодня ---
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
        if not expenses:
            await message.answer("Сегодня трат ещё нет 🙂")
            return
            
        total = sum(e.amount for e in expenses)
        # Группировка по категориям
        by_cat = {}
        for e in expenses:
            by_cat[e.category] = by_cat.get(e.category, 0) + e.amount
            
        text = f"📊 <b>Траты за сегодня:</b>\n\n"
        for cat, amt in by_cat.items():
            text += f"• {cat}: {amt:.2f} руб.\n"
        text += f"\n<b>Итого: {total:.2f} руб.</b>"
        
        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()

# --- Статистика за месяц ---
@dp.message(Command("month"))
async def cmd_month(message: Message):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        start = datetime(now.year, now.month, 1)
        expenses = (
            db.query(Expense)
            .filter(Expense.user_id == message.from_user.id, Expense.created_at >= start)
            .all()
        )
        if not expenses:
            await message.answer("В этом месяце трат ещё нет 🙂")
            return
            
        total = sum(e.amount for e in expenses)
        by_cat = {}
        for e in expenses:
            by_cat[e.category] = by_cat.get(e.category, 0) + e.amount
            
        text = f"📈 <b>Траты за этот месяц:</b>\n\n"
        for cat, amt in by_cat.items():
            text += f"• {cat}: {amt:.2f} руб.\n"
        text += f"\n<b>Итого: {total:.2f} руб.</b>"
        
        await message.answer(text, parse_mode="HTML")
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