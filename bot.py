# -*- coding: utf-8 -*-
"""
NFT Access Bot — Telegram-бот проверки NFT-доступа к закрытому каналу.
Стек: Python 3.11 + aiogram 3 + SQLite. Опционально pytoniq/tonutils для
on-chain проверки владения NFT.

Команды:
  /start        — приветствие, кнопка проверки
  /check EQ...  — проверка доступа по адресу кошелька
  /revoke EQ... — отзыв доступа (только админ)

Запуск:
  pip install aiogram
  export BOT_TOKEN=123456:AA...
  export ADMIN_CHANNEL_ID=-1001234567890
  export NFT_CONTRACT=EQ...
  export COLLECTION_NAME="Access Keys"
  export KEY_TTL_DAYS=30
  python bot.py
"""
import asyncio
import os
import sqlite3
import logging

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
logging.getLogger("aiogram").setLevel(logging.WARNING)
log = logging.getLogger("access")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHANNEL_ID = int(os.environ.get("ADMIN_CHANNEL_ID", "0"))
NFT_CONTRACT = os.environ.get("NFT_CONTRACT", "")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "Access Keys")
KEY_TTL_DAYS = int(os.environ.get("KEY_TTL_DAYS", "30"))
DEMO_WALLET = os.environ.get("DEMO_WALLET", "0QDD5oX4cPlW5ecZp2JUnJkllw1UejzjM5kXUJVyd87O9pKV")

db = sqlite3.connect("access.db")
db.execute(
    """CREATE TABLE IF NOT EXISTS keys(
         addr TEXT PRIMARY KEY,
         item INTEGER,
         tier TEXT,
         expires_at INTEGER,
         granted INTEGER DEFAULT 0)"""
)
db.commit()

router = Router()

TIERS = {
    "month": {"label": "Месяц", "days": 30},
    "year": {"label": "Год", "days": 365},
    "lifetime": {"label": "Навсегда", "days": 36500},
}


async def check_ownership(addr: str):
    """Проверка владения NFT-ключом.

    ДЕМО: whitelist в SQLite.
    БОЙ:  запрос к NFT-контракту — item index по адресу владельца,
          либо сверка с таблицей продаж вашего магазина.
    """
    row = db.execute(
        "SELECT item, tier, expires_at FROM keys WHERE addr=?", (addr,)
    ).fetchone()
    if not row:
        return None
    item, tier, expires = row
    if expires and expires < int(asyncio.get_event_loop().time()):
        return {"expired": True, "item": item, "tier": tier}
    return {"expired": False, "item": item, "tier": tier}


async def grant_access(user_id: int, addr: str):
    """Выдача доступа: одноразовая инвайт-ссылка в закрытый канал."""
    db.execute("UPDATE keys SET granted=1 WHERE addr=?", (addr,))
    db.commit()
    # БОЙ: bot.invite_link(chat_id=ADMIN_CHANNEL_ID, expire_date=...)
    return "https://t.me/+example_invite_link"


@router.message(Command("start"))
async def start(m: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Проверить мой доступ", callback_data="check")],
            [InlineKeyboardButton(text="🛒 Купить ключ", url="https://t.me/your_shop")],
        ]
    )
    await m.answer(
        f"<b>{COLLECTION_NAME}</b>\n\n"
        "Это бот проверки доступа к закрытому контенту.\n"
        "Пришлите адрес своего TON-кошелька — проверю, есть ли у вас ключ.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@router.callback_query(F.data == "check")
async def ask_addr(cb: types.CallbackQuery):
    await cb.message.answer("Пришлите адрес кошелька, например <code>EQ...</code>")
    await cb.answer()


@router.message(Command("check"))
async def cmd_check(m: types.Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.answer("Формат: <code>/check EQ...</code>")
        return
    await handle_addr(m, parts[1].strip())


@router.message(F.text.regexp(r"^(EQ|UQ)[A-Za-z0-9:_-]{40,}$"))
async def any_addr(m: types.Message):
    await handle_addr(m, m.text.strip())


async def handle_addr(m: types.Message, addr: str):
    res = await check_ownership(addr)
    if res is None:
        await m.answer(
            "❌ <b>Доступ закрыт</b>\n\n"
            f"По адресу <code>{addr}</code> ключ не найден.\n"
            "Купить ключ — в магазине канала.",
            parse_mode=ParseMode.HTML,
        )
        log.info("DENY user=%s addr=%s", m.from_user.id, addr)
        return
    if res["expired"]:
        await m.answer(
            "⚠️ <b>Срок ключа истёк</b>\n\n"
            f"Ключ #{res['item']} ({TIERS[res['tier']]['label']}) больше не активен.\n"
            "Продлите подписку в магазине.",
            parse_mode=ParseMode.HTML,
        )
        return
    link = await grant_access(m.from_user.id, addr)
    await m.answer(
        "✅ <b>Доступ открыт</b>\n\n"
        f"Ключ #{res['item']} · {TIERS[res['tier']]['label']}\n\n"
        f"Ссылка в закрытый канал (одноразовая):\n{link}",
        parse_mode=ParseMode.HTML,
    )
    log.info("GRANT user=%s addr=%s item=%s", m.from_user.id, addr, res["item"])


@router.message(Command("revoke"))
async def revoke(m: types.Message):
    if m.from_user.id != ADMIN_CHANNEL_ID:
        return
    parts = m.text.split()
    if len(parts) < 2:
        await m.answer("Формат: <code>/revoke EQ...</code>")
        return
    db.execute("UPDATE keys SET granted=0 WHERE addr=?", (parts[1].strip(),))
    db.commit()
    await m.answer("Доступ отозван.")


async def main():
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
