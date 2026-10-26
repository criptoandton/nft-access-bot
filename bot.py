# -*- coding: utf-8 -*-
"""
Access Keys Bot — проверка NFT-доступа к закрытому каналу.

Пользователь подключает кошелёк, бот сверяет владение NFT-ключом по whitelist
и выдаёт одноразовую инвайт-ссылку в закрытый канал. Есть отзыв доступа.

Стек: Python 3.11 + aiogram 3 + SQLite.

Запуск:
  pip install aiogram tonutils
  export BOT_TOKEN=123456:AA...
  export ADMIN_ID=123456789
  export CHANNEL_ID=-1001234567890
  export COLLECTION_ADDRESS=EQ...
  python bot.py
"""
import asyncio
import os
import time
import logging
import sqlite3

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("access")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
COLLECTION_ADDRESS = os.environ.get("COLLECTION_ADDRESS", "")
TESTNET_WALLET = "0QDD5oX4cPlW5ecZp2JUnJkllw1UejzjM5kXUJVyd87O9pKV"

db = sqlite3.connect("access.db")
db.execute("""CREATE TABLE IF NOT EXISTS keys(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT UNIQUE NOT NULL,
    nft_index INTEGER,
    granted_at INTEGER,
    revoked INTEGER DEFAULT 0)""")
db.execute("""CREATE TABLE IF NOT EXISTS log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT, action TEXT, created_at INTEGER)""")
db.commit()

router = Router()


def now():
    return int(time.time())


def write_log(wallet: str, action: str):
    db.execute("INSERT INTO log (wallet, action, created_at) VALUES (?,?,?)",
               (wallet, action, now()))
    db.commit()


def find_key(wallet: str):
    return db.execute(
        "SELECT id, nft_index, granted_at, revoked FROM keys WHERE wallet=?",
        (wallet.strip().lower(),)).fetchone()


async def check_nft_ownership(wallet: str):
    """Проверка владения NFT.

    БОЙ:  запрос item index коллекции (TonCenter / tonutils) и поиск
         предмета с владельцем == wallet.
    ДЕМО: тестовые адреса из DEMO_KEYS.
    """
    w = wallet.strip()
    demo = {
        "EQDemo_Owner_0000000000000000000000": (4821, "demo-owner"),
        "EQDemo_User_1111111111111111111111": (3907, "demo-user"),
    }
    if w in demo:
        return {"ok": True, "index": demo[w][0], "demo": True}
    return {"ok": False, "demo": True}


async def grant_access(wallet: str, nft_index: int):
    db.execute(
        "INSERT OR REPLACE INTO keys (wallet, nft_index, granted_at, revoked)"
        " VALUES (?,?,?,0)", (wallet.strip().lower(), nft_index, now()))
    db.commit()
    write_log(wallet, "granted")
    # БОЙ: bot.invite_link(chat_id=CHANNEL_ID, member_limit=1)
    return "https://t.me/+example_private_channel_invite"


@router.message(Command("start"))
async def start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Проверить доступ", callback_data="check")],
        [InlineKeyboardButton(text="ℹ️ Как это работает", callback_data="how")],
    ])
    await m.answer(
        "🔑 <b>Access Keys</b>\n\n"
        "Проверю ваш доступ по адресу кошелька и, если NFT-ключ найден, "
        "открою вход в закрытый канал.\n\n"
        "Пришлите адрес кошелька (EQ… или UQ…).",
        parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "how")
async def how(cb: types.CallbackQuery):
    await cb.message.edit_text(
        "ℹ️ <b>Как это работает</b>\n\n"
        "1. Вы отправляете адрес кошелька\n"
        "2. Бот сверяет владение NFT-ключом\n"
        "3. При успехе вы получаете одноразовую ссылку в закрытый канал\n"
        "4. При отзыве или возврате NFT доступ снимается автоматически",
        parse_mode=ParseMode.HTML)
    await cb.answer()


@router.message(F.text)
async def check_wallet(m: types.Message):
    wallet = (m.text or "").strip()
    if not wallet:
        return
    res = await check_nft_ownership(wallet)
    if not res["ok"]:
        await m.answer(
            "❌ <b>Доступ закрыт</b>\n\n"
            "NFT-ключ для этого адреса не найден. "
            "Купите ключ в магазине канала.",
            parse_mode=ParseMode.HTML)
        return
    existing = find_key(wallet)
    if existing and existing[3]:
        await m.answer(
            "🚫 <b>Доступ отозван</b>\n\n"
            "Ключ по этому адресу больше не действует. Обратитесь в поддержку.",
            parse_mode=ParseMode.HTML)
        return
    invite = await grant_access(wallet, res["index"])
    await m.answer(
        "✅ <b>Доступ открыт</b>\n\n"
        f"NFT-ключ #{res['index']} найден в коллекции.\n"
        "Добавлен в закрытый канал.\n\n"
        f"Ссылка (одноразовая):\n{invite}",
        parse_mode=ParseMode.HTML)


@router.message(Command("revoke"))
async def revoke(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    parts = (m.text or "").split()
    if len(parts) < 2:
        await m.answer("Формат: /revoke <кошелёк>")
        return
    wallet = parts[1].strip().lower()
    db.execute("UPDATE keys SET revoked=1 WHERE wallet=?", (wallet,))
    db.commit()
    write_log(wallet, "revoked")
    await m.answer(f"Доступ отозван: <code>{wallet}</code>", parse_mode=ParseMode.HTML)


@router.message(Command("admin"))
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    total = db.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
    alive = db.execute("SELECT COUNT(*) FROM keys WHERE revoked=0").fetchone()[0]
    await m.answer(
        "📊 <b>Статистика</b>\n\n"
        f"Всего ключей: {total}\n"
        f"Активных: {alive}",
        parse_mode=ParseMode.HTML)


async def main():
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
