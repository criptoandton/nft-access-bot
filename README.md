# NFT Access Bot

Telegram-бот проверки NFT-доступа к закрытому каналу: пользователь отправляет
адрес кошелька, бот сверяет владение NFT-ключом и выдаёт одноразовую инвайт-ссылку.
Есть отзыв доступа и админ-статистика.

**Стек:** Python 3.11, aiogram 3, SQLite, Tonutils / TonCenter API.

## Что делает

- проверка владения NFT по адресу кошелька
- автовыдача одноразовой ссылки в закрытый канал
- журнал действий в SQLite (выдано / отозвано)
- `/revoke <кошелёк>` — отзыв доступа администратором
- `/admin` — статистика по ключам

## Запуск

```bash
pip install aiogram tonutils
export BOT_TOKEN=123456:AA...
export ADMIN_ID=123456789
export CHANNEL_ID=-1001234567890
export COLLECTION_ADDRESS=EQ...
python bot.py
```

## Что заменить в бою

1. `check_nft_ownership()` — сейчас демо-режим по тестовым адресам. В бою:
   запрос item index коллекции (TonCenter / tonutils), поиск предмета
   с владельцем == переданный кошелёк.
2. `grant_access()` — возвращается тестовая ссылка. В бою:
   `bot.invite_link(chat_id=CHANNEL_ID, member_limit=1)`.
3. `COLLECTION_ADDRESS` — адрес вашей NFT-коллекции.

## Демо-кошелёк (testnet)

`0QDD5oX4cPlW5ecZp2JUnJkllw1UejzjM5kXUJVyd87O9pKV` — тестовый TON-кошелёк,
монеты не имеют реальной ценности.

## Отличие от второго кейса

Здесь покупатель **уже имеет** NFT-ключ, бот только проверяет владение.
В `ton-pay-shop-bot` ключ **продаётся** за крипту с автопродлением.

## Лицензия

MIT
