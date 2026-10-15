import json
import os
import random
import time
import traceback

import vk_api
from FunPayAPI import Account, Runner
from FunPayAPI.updater.events import EventTypes

# ===== НАСТРОЙКИ =====
GOLDEN_KEY = os.environ.get("GOLDEN_KEY", "").strip()
VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
ADMIN_VK_ID = int(os.environ.get("ADMIN_VK_ID", "0") or 0)
STATE_FILE = "states.json"

print("Длина ключа:", len(GOLDEN_KEY), "(должно быть 32)", flush=True)
if len(GOLDEN_KEY) != 32:
    raise SystemExit("golden_key неверный: нужно значение куки golden_key ровно из 32 символов")

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
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
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
        print("Сообщение отправлено в ВК", flush=True)
    except Exception as e:
        print("Ошибка отправки в ВК:", e, flush=True)

# ===== FUNPAY =====
acc = Account(GOLDEN_KEY).get()
runner = Runner(acc)  # создаётся ОДИН раз
print(f"Бот запущен как {acc.username}", flush=True)

def handle_message(msg):
    chat_id = str(msg.chat_id)
    user_name = getattr(msg, "chat_name", None) or getattr(msg, "author", None) or "Пользователь"
    user_link = f"https://funpay.com/users/{msg.author_id}/"
    chat_link = f"https://funpay.com/chat/?node={msg.chat_id}"
    text = (msg.text or "").strip()
    low = text.lower()

    print(f"Сообщение от {msg.author_id} в чате {chat_id}: {text[:50]}", flush=True)

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
        print("Отправлено приветствие", flush=True)
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
def get_events():
    try:
        return runner.listen(requests_delay=6, ignore_exceptions=False)
    except TypeError:
        return runner.listen(requests_delay=6)

fails = 0
while True:
    try:
        for event in get_events():
            fails = 0
            print("СОБЫТИЕ:", event.type, flush=True)
            if event.type != EventTypes.NEW_MESSAGE:
                continue
            msg = event.message
            if msg.author_id == acc.id or msg.author_id == 0 or getattr(msg, "by_bot", False):
                continue
            try:
                handle_message(msg)
            except Exception:
                print("❌ Ошибка в обработке сообщения:", flush=True)
                traceback.print_exc()
    except Exception:
        fails += 1
        print(f"❌ Ошибка получения событий (попытка {fails}):", flush=True)
        traceback.print_exc()
        if fails >= 5:
            print("Слишком много ошибок подряд, остановка.", flush=True)
            break
        time.sleep(15)
        try:
            acc.get()  # обновляем сессию, Runner не пересоздаём
        except Exception:
            traceback.print_exc()
