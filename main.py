import re
import logging
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils import executor
from functools import wraps

API_TOKEN = "8747503624:AAGkCWH0rtrZ-87y4vIGvJohi6n7PE2Y8lA"
CHANNEL_ID = "-1003843717383"

# --- Белый список пользователей ---
ALLOWED_USERS = [8666734115, 7479868225, 8169407131]  # замените на реальные ID

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_data = {}
user_limits = {}  # для лимита жалоб

# --- Кнопки ---
reasons_kb = ReplyKeyboardMarkup(resize_keyboard=True)
reasons = [
    "I don't like it",
    "Child sexual explanation material",
    "Grooming of children",
    "Pro-terror material",
    "Extreme crime and violence material",
    "Other crime and violence material",
    "Non-consensual intimate image sharing",
    "Sexual extortion",
    "Drug-related material",
    "Other",
    "It's not illegal but it must be taken down"
]
for r in reasons:
    reasons_kb.add(KeyboardButton(r))

doc_kb = ReplyKeyboardMarkup(resize_keyboard=True)
doc_kb.add(KeyboardButton("Proceed without documentation"))

confirm_kb = ReplyKeyboardMarkup(resize_keyboard=True)
confirm_kb.add(KeyboardButton("Confirm"), KeyboardButton("Start Again"))

# --- Проверка ссылки ---
def is_valid_link(text):
    return re.match(r"^(https?://)?t\.me/.+", text)

# --- Декоратор для доступа по белому списку ---
def only_allowed(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ALLOWED_USERS:
            await message.answer(
                "You don't have access to the bot, you can get it here - @id8666734115",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        return await func(message, *args, **kwargs)
    return wrapper

# --- Проверка лимита ---
def can_send(user_id):
    now = datetime.datetime.now()
    if user_id not in user_limits:
        user_limits[user_id] = []
    # Убираем жалобы старше часа
    user_limits[user_id] = [t for t in user_limits[user_id] if (now - t).seconds < 3600]
    if len(user_limits[user_id]) >= 5:
        next_available = 60 - int((now - user_limits[user_id][0]).seconds / 60)
        return False, next_available
    return True, 0

def record_sent(user_id):
    user_limits[user_id].append(datetime.datetime.now())

# --- START ---
@dp.message_handler(commands=['start'])
@only_allowed
async def start(message: types.Message):
    user_data[message.from_user.id] = {}
    await message.answer(
        "If you believe that content accessible on our platform is illegal, you can report it through this bot under the process provided for in the Industry Standards applicable to online services in Australia.\n\n"
        "We may have to dismiss your report if we have reasonable grounds to believe that it is unfounded, fraudulent or otherwise not made in good faith.\n\n"
        "To start, please enter a t.me/... link to the Telegram content you want to report:"
    )

# --- Получение ссылки ---
@dp.message_handler(lambda message: 'link' not in user_data.get(message.from_user.id, {}))
@only_allowed
async def get_link(message: types.Message):
    can_send_flag, wait_minutes = can_send(message.from_user.id)
    if not can_send_flag:
        await message.answer(f"Too many requests, please wait {wait_minutes}m before sending a new report.")
        return

    if not message.text or not is_valid_link(message.text):
        await message.answer("Please enter a valid link to the content you want to report.")
        return

    user_data[message.from_user.id]['link'] = message.text
    await message.answer("Select the reason of your report:", reply_markup=reasons_kb)

# --- Причина ---
@dp.message_handler(lambda message: 'reason' not in user_data.get(message.from_user.id, {}) and message.text in reasons)
@only_allowed
async def get_reason(message: types.Message):
    user_data[message.from_user.id]['reason'] = message.text

    await message.answer(
        "Please provide a description specifying why the content is illegal and state any other relevant information or context.",
        reply_markup=ReplyKeyboardRemove()
    )

# --- Описание ---
@dp.message_handler(lambda message: 'reason' in user_data.get(message.from_user.id, {}) and 'description' not in user_data.get(message.from_user.id, {}))
@only_allowed
async def get_description(message: types.Message):
    user_data[message.from_user.id]['description'] = message.text

    await message.answer(
        "If applicable, please attach documentation showing precedent that supports your claim.",
        reply_markup=doc_kb
    )

# --- Документы ---
@dp.message_handler(
    lambda message: 'description' in user_data.get(message.from_user.id, {}) and 'docs' not in user_data.get(message.from_user.id, {}),
    content_types=['photo', 'text']
)
@only_allowed
async def get_docs(message: types.Message):
    data = user_data.get(message.from_user.id)

    if message.text == "Proceed without documentation":
        data['docs'] = "No"

    elif message.photo:
        data['docs'] = "Photo attached"
        data['photo_id'] = message.photo[-1].file_id

    else:
        return

    await message.answer(
        "By submitting this report, you agree that all the information you provided is accurate and truthful, and that you believe in good faith that the content you reported is illegal for the reasons you described.\n\n"
        "In case that you are unsure in any of the above, please click ‘Start Again’ to resubmit your report.",
        reply_markup=confirm_kb
    )

# --- Подтверждение ---
@dp.message_handler(lambda message: message.text in ["Confirm", "Start Again"])
@only_allowed
async def final_step(message: types.Message):
    if message.text == "Start Again":
        user_data[message.from_user.id] = {}
        await message.answer("Restarting...", reply_markup=ReplyKeyboardRemove())
        await start(message)
        return

    data = user_data.get(message.from_user.id)
    record_sent(message.from_user.id)  # сохраняем факт отправки

    username = f"@{message.from_user.username}" if message.from_user.username else "Нет username"

    text = (
        f"Имя пользователя: {message.from_user.full_name}\n"
        f"Айди пользователя: {message.from_user.id}\n"
        f"Юз пользователя: {username}\n"
        f"Текст: {data.get('description')}\n"
        f"Причина: {reason}\n
        f"Ссылка: {data.get('link')}\n"
        f"Доказательства: {data.get('docs')}"
    )

    await bot.send_message(CHANNEL_ID, text)

    if data.get("photo_id"):
        await bot.send_photo(CHANNEL_ID, data["photo_id"])

    await message.answer(
        "Thank you for your report!\n\n"
        "It will be reviewed by our team as soon as possible. Please note that submitting duplicate reports for the same content will not expedite the moderation process.",
        reply_markup=ReplyKeyboardRemove()
    )

    user_data[message.from_user.id] = {}

# --- Запуск ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
