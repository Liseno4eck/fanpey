import json
import os
import random
import time

import vk_api
from FunPayAPI import Account, Runner
from FunPayAPI.updater.events import EventTypes

# ===== НАСТРОЙКИ =====
GOLDEN_KEY = "v1.6d57ec1d80de8d249f76452b2de91ace144ace2d9fc8f8de1135807704a5d286.3c61f93daf390d7c4ab855e32ad54902.1792677695.k1.03dbc36ad89b0d64de51797fd1849f3c416d3f34b0efdeeb703ebf83cabb7cf2"
VK_TOKEN = "vk1.a.bh7sxx4bOc4oMKyzy1DGTlDzOT3qfOGQvB_lPDNZs5-kjmWD3YgY86XWT5nUzB30i_z8qPk1DdL7fYpGBPSwwoehKSfRdHV18MVFP2ttxIF-w0eQHF45p_IWxY1tjyDAcGi7WK_B5f_82WyrJfeKseJIPrwArE7ONifEm-5FJ9-7qlj2pVEBTxJ8ZCkk0RNoXJl5b5YIdXpWem711726WA"   # с правом на сообщения
ADMIN_VK_ID = 875762552            # твой VK ID (цифрами)
STATE_FILE = "states.json"

# ===== ТЕКСТЫ =====
MSG_1 = (
    "Привет! Для покупки бота, пожалуйста, напиши, какого именно бота тебе нужно "
    "и какие характеристики и пожелания у тебя есть. Также скажи, нужно ли прислать "
    "просто код или сделать уже полностью работающего бота.\n\n"
    "Для ответа введите: +ответ (ваше сообщение)\n"
    "Чтобы позвать продавца: +позвать продавца"
)
MSG_2 = (
    "Отлично! Теперь всё, что нужно, это оплатить услугу и дать мне свою ссылку на ВК, "
    "чтобы я мог выдать вам полный доступ и права.\n\n"
    "Для ответа введите: +ответ (ваше сообщение)\n"
    "Чтобы позвать продавца: +позвать продавца"
)
MSG_3 = (
    "Отлично, я получил всё, что нужно! Теперь просто оплати заказ и жди выполнения "
    "в течение 1-3 часов. Иногда я буду задавать вопросы, чтобы детализировать бота."
)

# Этапы: 1 = ждём описание бота, 2 = ждём оплату и ссылку ВК, 3 = завершено

# ===== СОСТОЯНИЯ =====
def load_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_states(states):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False)

states = load_states()

# ===== ВК =====
vk = vk_api.VkApi(token=VK_TOKEN).get_api()

def notify_admin(text):
    try:
        vk.messages.send(
            user_id=ADMIN_VK_ID,
            random_id=random.randint(1, 2**31),
            message=text,
        )
    except Exception as e:
        print("Ошибка отправки в ВК:", e)

# ===== FUNPAY =====
acc = Account(GOLDEN_KEY).get()
runner = Runner(acc)
print(f"Бот запущен как {acc.username}")

def handle_message(msg):
    chat_id = str(msg.chat_id)
    user_name = msg.chat_name or "Пользователь"
    user_link = f"https://funpay.com/users/{msg.author_id}/"
    chat_link = f"https://funpay.com/chat/?node={msg.chat_id}"
    text = (msg.text or "").strip()
    low = text.lower()

    # Вызов продавца
    if low.startswith("+позвать продавца"):
        notify_admin(f"🔔 Юзер вас вызвал!\n👤 {user_name} ({user_link})\n💬 Чат: {chat_link}")
        acc.send_message(msg.chat_id, "Продавец вызван, скоро с вами свяжутся ✅")
        return

    # Новый чат: приветствие
    if chat_id not in states:
        states[chat_id] = 1
        save_states(states)
        acc.send_message(msg.chat_id, MSG_1)
        return

    stage = states[chat_id]

    # Ответ пользователя через +ответ
    if low.startswith("+ответ"):
        answer = text[len("+ответ"):].strip()
        if not answer:
            acc.send_message(msg.chat_id, "Напишите сообщение после команды: +ответ (ваше сообщение)")
            return

        notify_admin(f"📩 Ответ от юзера\n👤 {user_name} ({user_link})\n💬 Чат: {chat_link}\n\n{answer}")

        if stage == 1:
            states[chat_id] = 2
            save_states(states)
            acc.send_message(msg.chat_id, MSG_2)
        elif stage == 2:
            states[chat_id] = 3
            save_states(states)
            acc.send_message(msg.chat_id, MSG_3)
        else:
            acc.send_message(msg.chat_id, "Сообщение передано продавцу ✅")

# ===== ГЛАВНЫЙ ЦИКЛ =====
while True:
    try:
        for event in runner.listen(requests_delay=4):
            if event.type != EventTypes.NEW_MESSAGE:
                continue
            msg = event.message
            if msg.author_id == acc.id or msg.author_id == 0 or msg.by_bot:
                continue  # свои и системные сообщения пропускаем
            handle_message(msg)
    except Exception as e:
        print("Ошибка, перезапуск через 10 сек:", e)
        time.sleep(10)
        try:
            acc.get()
            runner = Runner(acc)
        except Exception as e2:
            print("Не удалось обновить сессию:", e2)
