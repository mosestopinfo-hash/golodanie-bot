#!/usr/bin/env python3
"""
ЛЕЧЕБНОЕ ГОЛОДАНИЕ — Telegram Bot (личное использование)
"""

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from typing import Optional
from dotenv import load_dotenv

import db
from content import STEPS, Step

# ─── Настройка ────────────────────────────────────────────────────────────────

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PHOTOS_DIR = Path(__file__).parent / "photos"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан! Укажи его в файле .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ─── Вспомогательные функции ──────────────────────────────────────────────────

def make_keyboard(step: Step) -> Optional[InlineKeyboardMarkup]:
    if not step.buttons:
        return None
    rows = [[InlineKeyboardButton(text=btn.label, callback_data=f"step:{btn.next_step}")]
            for btn in step.buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_photo(chat_id: int, filename: str):
    cached = db.get_photo_id(filename)
    if cached:
        await bot.send_photo(chat_id, cached)
        return cached
    photo_path = PHOTOS_DIR / filename
    if not photo_path.exists():
        logger.warning(f"Фото не найдено: {photo_path}")
        return None
    msg = await bot.send_photo(chat_id, FSInputFile(str(photo_path)))
    file_id = msg.photo[-1].file_id
    db.cache_photo(filename, file_id)
    return file_id


async def send_photo_with_caption(chat_id, filename, caption, keyboard=None):
    cached = db.get_photo_id(filename)
    if cached:
        await bot.send_photo(chat_id, cached, caption=caption[:1024], reply_markup=keyboard)
        return
    photo_path = PHOTOS_DIR / filename
    if not photo_path.exists():
        await bot.send_message(chat_id, caption, reply_markup=keyboard)
        return
    msg = await bot.send_photo(
        chat_id, FSInputFile(str(photo_path)),
        caption=caption[:1024], reply_markup=keyboard
    )
    db.cache_photo(filename, msg.photo[-1].file_id)


async def send_step(chat_id: int, step: Step, user_name: str):
    keyboard = make_keyboard(step)
    last_idx = len(step.messages) - 1

    for i, msg in enumerate(step.messages):
        is_last = (i == last_idx)
        kb = keyboard if is_last else None

        if msg.photo and msg.text:
            await send_photo_with_caption(chat_id, msg.photo, msg.text.replace("{name}", user_name), kb)
        elif msg.photo:
            await send_photo(chat_id, msg.photo)
            if is_last and kb:
                await bot.send_message(chat_id, "👇", reply_markup=kb)
        else:
            text = msg.text.replace("{name}", user_name)
            await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=msg.parse_mode)

        if not is_last:
            await asyncio.sleep(0.3)


async def go_to_step(chat_id: int, user_id: int, step_id: str, user_name: str):
    step = STEPS.get(step_id)
    if not step:
        await bot.send_message(chat_id, f"⚠️ Шаг '{step_id}' не найден. Напишите /start")
        return
    db.set_step(user_id, step_id)
    await send_step(chat_id, step, user_name)


# ─── Команды ─────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    db.upsert_user(user.id, user.username or "", user.first_name or "", user.last_name or "")
    db.set_paid(user.id, True)  # личное использование — доступ открыт сразу
    user_name = user.first_name or user.username or "друг"
    await go_to_step(message.chat.id, user.id, "course_welcome", user_name)


@dp.message(Command("continue"))
async def cmd_continue(message: Message):
    user = message.from_user
    user_data = db.get_user(user.id)
    if not user_data:
        await cmd_start(message)
        return
    step_id = user_data.get("step", "course_welcome")
    user_name = user.first_name or user.username or "друг"
    await go_to_step(message.chat.id, user.id, step_id, user_name)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    user_data = db.get_user(message.from_user.id)
    if not user_data:
        await message.answer("Нажми /start чтобы начать.")
        return
    step_id = user_data.get("step", "?")
    step = STEPS.get(step_id)
    step_num = list(STEPS.keys()).index(step_id) + 1 if step_id in STEPS else "?"
    total = len(STEPS)
    await message.answer(
        f"📊 Прогресс: шаг {step_num}/{total}\n"
        f"Текущий шаг: <b>{step_id}</b>\n\n"
        f"Нажми /continue чтобы продолжить."
    )


@dp.message(Command("goto"))
async def cmd_goto(message: Message):
    """Перейти к конкретному шагу. /goto stage3_start"""
    parts = message.text.split()
    if len(parts) < 2:
        steps_list = "\n".join(f"• {s}" for s in STEPS.keys())
        await message.answer(f"Использование: /goto [step_id]\n\nДоступные шаги:\n{steps_list}")
        return
    step_id = parts[1]
    if step_id not in STEPS:
        await message.answer(f"Шаг '{step_id}' не найден. Напиши /goto чтобы увидеть список.")
        return
    user = message.from_user
    user_name = user.first_name or user.username or "друг"
    await go_to_step(message.chat.id, user.id, step_id, user_name)


@dp.message(Command("steps"))
async def cmd_steps(message: Message):
    steps_list = "\n".join(f"• {s}" for s in STEPS.keys())
    await message.answer(f"📋 Все шаги курса:\n\n{steps_list}\n\nИспользуй /goto [шаг] для перехода.")


# ─── Callback кнопки ─────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("step:"))
async def handle_step_callback(callback: CallbackQuery):
    next_step_id = callback.data.split("step:", 1)[1]
    user = callback.from_user
    user_name = user.first_name or user.username or "друг"
    await callback.answer()
    await go_to_step(callback.message.chat.id, user.id, next_step_id, user_name)


@dp.message()
async def handle_other(message: Message):
    await message.answer(
        "Нажми /continue чтобы продолжить курс\n"
        "или /steps чтобы увидеть все шаги."
    )


# ─── Запуск ──────────────────────────────────────────────────────────────────

async def main():
    db.init_db()
    logger.info(f"Фото: {PHOTOS_DIR}")
    logger.info("Бот запущен!")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
