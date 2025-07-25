import telebot
from telebot import types
import config
from datetime import datetime
import time
from tinydb import TinyDB, Query

bot = telebot.TeleBot(config.TOKEN)
db = TinyDB('stars.json')
users = db.table('users')
promocodes = db.table('promocodes')
channels = db.table('channels')
requests = db.table('requests')
meta = db.table('meta')
tasks = db.table('tasks')
completed_tasks = db.table('completed_tasks')

start_time = time.time()
if not meta.get(doc_id=1):
    meta.insert({'request_counter': 0})
request_counter = meta.get(doc_id=1)['request_counter']

def check_subscription(user_id):
    if not channels.all():
        return True
    for channel in channels.all():
        try:
            status = bot.get_chat_member(channel['id'], user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("👤 Заработать")
    btn2 = types.KeyboardButton("🍀 Промокоды")
    btn3 = types.KeyboardButton("🏦 Личный кабинет")
    btn4 = types.KeyboardButton("📋 Задания")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    return markup

def generate_task_message(user_id, page=0):
    available_tasks = [task for task in tasks.all() if not completed_tasks.get((Query().user_id == user_id) & (Query().task_id == task['task_id']))]
    if not available_tasks:
        return "<b>Нет доступных заданий!</b>", None
    page = max(0, min(page, len(available_tasks) - 1))
    task = available_tasks[page]
    text = f"""<b>Новое задание</b>

<b>Ссылка:</b> <a href='{task['link']}'>{task['link']}</a>
<b>Награда:</b> {task['stars']} ⭐️

<i>Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней.</i>
<i>Нажмите 'Проверить'</i>"""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("⬅️", callback_data=f"task_prev_{page}"),
        types.InlineKeyboardButton(f"{page + 1}/{len(available_tasks)}", callback_data="task_page"),
        types.InlineKeyboardButton("➡️", callback_data=f"task_next_{page}")
    )
    markup.add(types.InlineKeyboardButton("Проверить", callback_data=f"check_task_{task['task_id']}_{page}"))
    return text, markup

@bot.message_handler(commands=['start', 'admin'])
def handle_commands(message):
    user_id = message.from_user.id

    if message.text.startswith('/start'):
        if not check_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            for channel in channels.all():
                btn = types.InlineKeyboardButton("Подписаться", url=channel['link'])
                markup.add(btn)
            bot.send_message(message.chat.id, "<b>🚀 Подпишитесь на каналы, затем отправьте /start</b>", reply_markup=markup, parse_mode='HTML')
            return

        if not users.get(Query().user_id == user_id):
            users.insert({
                'user_id': user_id,
                'join_date': datetime.now().isoformat(),
                'refs': 0,
                'balance': 0.0,
                'withdrawn': 0.0,
                'username': message.from_user.username or "NoUsername",
                'referrer_id': None
            })

        args = message.text.split()
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id != user_id and users.get(Query().user_id == ref_id) and not users.get(Query().user_id == user_id)['referrer_id']:
                    users.update({'referrer_id': ref_id}, Query().user_id == user_id)
                    referrer = users.get(Query().user_id == ref_id)
                    users.update({'refs': referrer['refs'] + 1, 'balance': referrer['balance'] + 1.0}, Query().user_id == ref_id)
                    bot.send_message(ref_id, f"<b>Пользователь @{message.from_user.username or 'NoUsername'} перешел по вашей реферальной ссылке!</b>\nВам начислено <b>1.0 ⭐</b>", parse_mode='HTML')
            except ValueError:
                pass

        text = """<b>Приветствуем вас в нашем боте!</b>

<b>Что нужно делать?</b>
1. Приглашать людей по своей реферальной ссылке (она находится в разделе <b>"Заработать"</b>)
2. Когда сумма на вывод станет доступна, выводите и получайте ⭐"""
        bot.send_message(message.chat.id, text, reply_markup=main_menu(), parse_mode='HTML')

    elif message.text.startswith('/admin'):
        if user_id != config.ADMIN_ID:
            bot.send_message(message.chat.id, f"<b>Доступ запрещен!</b>\nВаш ID: {user_id}\nТребуемый ADMIN_ID: {config.ADMIN_ID}", parse_mode='HTML')
            return
        
        all_users = len(users.all())
        day_users = sum(1 for u in users.all() if (datetime.now() - datetime.fromisoformat(u['join_date'])).days < 1)
        
        text = f"""<b>Статистика системы:</b>

<b>👥 Пользователей:</b> {all_users}
<b>🆕 Новых пользователей сегодня:</b> {day_users}"""
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("Добавить канал", callback_data="add_channel")
        btn2 = types.InlineKeyboardButton("Убрать канал", callback_data="remove_channel")
        btn3 = types.InlineKeyboardButton("Добавить промокод", callback_data="add_promo")
        btn4 = types.InlineKeyboardButton("Удалить промокод", callback_data="remove_promo")
        btn5 = types.InlineKeyboardButton("Добавить задание", callback_data="add_task")
        btn6 = types.InlineKeyboardButton("Удалить задание", callback_data="remove_task")
        markup.add(btn1, btn2)
        markup.add(btn3, btn4)
        markup.add(btn5, btn6)
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        return
    
    if message.text == "👤 Заработать":
        user = users.get(Query().user_id == user_id)
        count_ref = user['refs']
        bot_username = bot.get_me().username
        text = f"""<b>👤 Реферальная программа</b>
<b>Вы пригласили:</b> {count_ref}
<b>🔗 Реф. ссылка:</b> <a href='https://t.me/{bot_username}?start={user_id}'>https://t.me/{bot_username}?start={user_id}</a>"""
        bot.send_message(message.chat.id, text, reply_markup=main_menu(), parse_mode='HTML')
        
    elif message.text == "🍀 Промокоды":
        bot.send_message(message.chat.id, "<b>🍀 Введите промокод для активации:</b>", parse_mode='HTML')
        bot.register_next_step_handler(message, process_promo)
        
    elif message.text == "🏦 Личный кабинет":
        user = users.get(Query().user_id == user_id)
        days = (datetime.now() - datetime.fromisoformat(user['join_date'])).days
        text = f"""<b>📱 Ваш кабинет:</b>

<b>👤 Имя:</b> {message.from_user.first_name} {message.from_user.last_name or ''}
<b>🔑 Ваш ID:</b> {user_id}
<b>🕜 Дней в боте:</b> {days}

<b>💳 Баланс:</b>
<b>● Основной:</b> {user['balance']:.1f} ⭐
<b>● Выведено:</b> {user['withdrawn']:.1f} ⭐"""
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("Вывести", callback_data="withdraw")
        markup.add(btn)
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')
    
    elif message.text == "📋 Задания":
        text, markup = generate_task_message(user_id)
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def process_promo(message):
    user_id = message.from_user.id
    code = message.text.upper()
    promo = promocodes.get(Query().code == code)
    if promo:
        used_by = set(promo.get('used_by', []))
        if user_id in used_by:
            bot.send_message(message.chat.id, "<b>Вы уже использовали этот промокод!</b>", reply_markup=main_menu(), parse_mode='HTML')
        elif promo['activations'] > 0:
            used_by.add(user_id)
            promocodes.update({'activations': promo['activations'] - 1, 'used_by': list(used_by)}, Query().code == code)
            user = users.get(Query().user_id == user_id)
            users.update({'balance': user['balance'] + promo['stars']}, Query().user_id == user_id)
            bot.send_message(message.chat.id, f"<b>Промокод активирован!</b>\nВы получили <b>{promo['stars']:.1f} ⭐</b>", reply_markup=main_menu(), parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "<b>Промокод исчерпал лимит активаций!</b>", reply_markup=main_menu(), parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "<b>Неверный промокод!</b>", reply_markup=main_menu(), parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    global request_counter
    
    if call.data == "withdraw":
        user_id = call.from_user.id
        if requests.get(Query().user_id == user_id):
            bot.edit_message_text("<b>У вас уже есть активная заявка! Дождитесь её завершения.</b>", call.message.chat.id, call.message.message_id, parse_mode='HTML')
            return
        user = users.get(Query().user_id == user_id)
        balance = user['balance']
        text = f"<b>Заработано:</b> {balance:.1f} ⭐️\n\n<b>🔻 Выбери, подарок за сколько звёзд хочешь получить:</b>"
        markup = types.InlineKeyboardMarkup()
        btns = [
            ("15 ⭐️", "withdraw_15"), ("25 ⭐️", "withdraw_25"),
            ("50 ⭐️", "withdraw_50"), ("100 ⭐️", "withdraw_100"),
            ("150 ⭐️", "withdraw_150"), ("350 ⭐️", "withdraw_350"),
            ("500 ⭐️", "withdraw_500")
        ]
        for btn_text, btn_data in btns:
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=btn_data))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        
    elif call.data.startswith("withdraw_"):
        stars = float(call.data.split("_")[1])
        user_id = call.from_user.id
        if requests.get(Query().user_id == user_id):
            bot.edit_message_text("<b>У вас уже есть активная заявка! Дождитесь её завершения.</b>", call.message.chat.id, call.message.message_id, parse_mode='HTML')
            return
        user = users.get(Query().user_id == user_id)
        if user['balance'] >= stars:
            request_counter += 1
            meta.update({'request_counter': request_counter}, doc_ids=[1])
            users.update({'balance': user['balance'] - stars}, Query().user_id == user_id)
            requests.insert({'request_id': request_counter, 'user_id': user_id, 'stars': stars})
            text = f"""<b>Заявка №{request_counter} на вывод {stars:.1f} ⭐️ создана.</b>

<i>В течение 72 часов заявка будет рассмотрена администраторами и вам будет отправлен подарок, из которого вы получите звёзды.</i>
<i>Не меняйте username, иначе мы не сможем отправить подарок, а заявка будет отклонена.</i>"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
            chat_text = f"<b>Новая заявка №{request_counter}</b> на получение подарка за <b>{stars:.1f} ⭐</b> от пользователя <b>{call.from_user.first_name} {call.from_user.last_name or ''}</b>"
            chat_msg = bot.send_message(config.CHAT_ID, chat_text, parse_mode='HTML')
            requests.update({'chat_msg_id': chat_msg.message_id}, Query().request_id == request_counter)
            channel_text = f"""<b>Заявка от пользователя</b> <a href="tg://user?id={user_id}">{call.from_user.first_name} {call.from_user.last_name or ''}</a>

<b>Username:</b> @{user['username']}
<b>Выбрал:</b> {stars:.1f} ⭐"""
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("Завершить", callback_data=f"complete_{request_counter}"),
                types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{request_counter}")
            )
            channel_msg = bot.send_message(config.CHANNEL_ID, channel_text, parse_mode='HTML', reply_markup=markup)
            requests.update({'channel_msg_id': channel_msg.message_id}, Query().request_id == request_counter)
            
    elif call.data.startswith("complete_"):
        req_id = int(call.data.split("_")[1])
        req = requests.get(Query().request_id == req_id)
        if req and call.from_user.id == config.ADMIN_ID:
            stars = req['stars']
            user_id = req['user_id']
            user = users.get(Query().user_id == user_id)
            channel_text = f"""<b>Заявка от пользователя</b> <a href="tg://user?id={user_id}">{call.from_user.first_name} {call.from_user.last_name or ''}</a>

<b>Username:</b> @{user['username']}
<b>Выбрал:</b> {stars:.1f} ⭐"""
            bot.edit_message_text(f"{channel_text}\n\n<b>Завершено</b>", config.CHANNEL_ID, req['channel_msg_id'], parse_mode='HTML')
            bot.send_message(config.CHAT_ID, f"<b>Заявка №{req_id} выполнена</b>, отправили подарок за <b>{stars:.1f} ⭐</b>", parse_mode='HTML')
            users.update({'withdrawn': user['withdrawn'] + stars}, Query().user_id == user_id)
            requests.remove(Query().request_id == req_id)
            
    elif call.data.startswith("reject_"):
        req_id = int(call.data.split("_")[1])
        req = requests.get(Query().request_id == req_id)
        if req and call.from_user.id == config.ADMIN_ID:
            stars = req['stars']
            user = users.get(Query().user_id == req['user_id'])
            channel_text = f"""<b>Заявка от пользователя</b> <a href="tg://user?id={req['user_id']}">{call.from_user.first_name} {call.from_user.last_name or ''}</a>

<b>Username:</b> @{user['username']}
<b>Выбрал:</b> {stars:.1f} ⭐"""
            bot.edit_message_text(f"{channel_text}\n\n<b>Отклонено</b>", config.CHANNEL_ID, req['channel_msg_id'], parse_mode='HTML')
            users.update({'balance': user['balance'] + stars}, Query().user_id == req['user_id'])
            requests.remove(Query().request_id == req_id)
            
    elif call.data == "add_channel" and call.from_user.id == config.ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "<b>Введите ID канала:</b>", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_channel_id)
        
    elif call.data == "remove_channel" and call.from_user.id == config.ADMIN_ID:
        text = "<b>Список каналов:</b>\n"
        for i, channel in enumerate(channels.all(), 1):
            text += f"{i}. <a href='{channel['link']}'>{channel['link']}</a> | {channel['id']}\n"
        text += "\n<b>Введите номер канала, который хотите удалить из списка:</b>"
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_channel_remove)
        
    elif call.data == "add_promo" and call.from_user.id == config.ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "<b>Введите промокод:</b>", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_promo_code)
        
    elif call.data == "remove_promo" and call.from_user.id == config.ADMIN_ID:
        text = "<b>Список промокодов:</b>\n"
        for i, promo in enumerate(promocodes.all(), 1):
            text += f"{i}. <b>{promo['code']}</b> | {promo['activations']} | {promo['stars']:.1f} ⭐\n"
        text += "\n<b>Введите номер промокода, который хотите удалить:</b>"
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_promo_remove)
    
    elif call.data == "add_task" and call.from_user.id == config.ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "<b>Введите ID канала:</b>", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_task_id)
    
    elif call.data == "remove_task" and call.from_user.id == config.ADMIN_ID:
        text = "<b>Список заданий:</b>\n"
        for i, task in enumerate(tasks.all(), 1):
            text += f"{i}. <a href='{task['link']}'>{task['link']}</a> | {task['id']} | {task['stars']} ⭐️\n"
        text += "\n<b>Введите номер задания, которое хотите удалить:</b>"
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_task_remove)
    
    elif call.data.startswith("task_prev_"):
        page = int(call.data.split("_")[2])
        new_page = max(0, page - 1)
        text, markup = generate_task_message(call.from_user.id, new_page)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    
    elif call.data.startswith("task_next_"):
        page = int(call.data.split("_")[2])
        available_tasks = [task for task in tasks.all() if not completed_tasks.get((Query().user_id == call.from_user.id) & (Query().task_id == task['task_id']))]
        new_page = min(len(available_tasks) - 1, page + 1)
        text, markup = generate_task_message(call.from_user.id, new_page)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    
    elif call.data.startswith("check_task_"):
        parts = call.data.split("_")
        task_id = int(parts[2])
        page = int(parts[3])
        user_id = call.from_user.id
        task = tasks.get(Query().task_id == task_id)
        if not task:
            bot.answer_callback_query(call.id, "Задание не найдено!")
            return
        if completed_tasks.get((Query().user_id == user_id) & (Query().task_id == task_id)):
            bot.answer_callback_query(call.id, "Вы уже выполнили это задание!")
            return
        try:
            chat_member = bot.get_chat_member(task['id'], user_id)
            if chat_member.status in ['member', 'administrator', 'creator']:
                user = users.get(Query().user_id == user_id)
                if user:
                    users.update({'balance': user['balance'] + task['stars']}, Query().user_id == user_id)
                    completed_tasks.insert({'user_id': user_id, 'task_id': task_id})
                    bot.answer_callback_query(call.id, f"Задание выполнено! Вы получили {task['stars']} ⭐️")
                    text, markup = generate_task_message(user_id, page)
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
                else:
                    bot.answer_callback_query(call.id, "Ошибка: пользователь не найден!")
            else:
                bot.answer_callback_query(call.id, "Вы не подписаны на канал!")
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 400 and "chat not found" in e.description.lower():
                bot.answer_callback_query(call.id, "Канал не найден! Обратитесь к администратору.")
            elif e.error_code == 403:
                bot.answer_callback_query(call.id, "Боту не хватает прав для проверки подписки!")
            else:
                bot.answer_callback_query(call.id, f"Ошибка проверки: {e.description}")
            bot.send_message(config.ADMIN_ID, f"<b>Ошибка проверки подписки</b> для task_id {task_id}, канал {task['id']}: {str(e)}", parse_mode='HTML')
    
    elif call.data == "back_to_menu":
        bot.edit_message_text("<b>Вы вернулись в главное меню</b>", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode='HTML')

def process_channel_id(message):
    channel_id = message.text
    msg = bot.send_message(message.chat.id, "<b>Введите ссылку на канал:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_channel_link(m, channel_id))

def process_channel_link(message, channel_id):
    channel_link = message.text
    channels.insert({'id': channel_id, 'link': channel_link})
    bot.send_message(message.chat.id, "<b>Канал добавлен в обязательные подписки</b>", parse_mode='HTML')

def process_channel_remove(message):
    try:
        index = int(message.text) - 1
        if 0 <= index < len(channels.all()):
            channels.remove(doc_ids=[channels.all()[index].doc_id])
            bot.send_message(message.chat.id, "<b>Канал удален из списка</b>", parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "<b>Неверный номер канала</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число</b>", parse_mode='HTML')

def process_promo_code(message):
    code = message.text.upper()
    promocodes.insert({'code': code, 'activations': 0, 'stars': 0.0, 'used_by': []})
    msg = bot.send_message(message.chat.id, "<b>Введите количество активаций:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_promo_activations(m, code))

def process_promo_activations(message, code):
    try:
        activations = int(message.text)
        promocodes.update({'activations': activations}, Query().code == code)
        msg = bot.send_message(message.chat.id, "<b>Введите сколько промокод даст звезд:</b>", parse_mode='HTML')
        bot.register_next_step_handler(msg, lambda m: process_promo_stars(m, code))
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число!</b>", parse_mode='HTML')

def process_promo_stars(message, code):
    try:
        stars = float(message.text)
        promocodes.update({'stars': stars}, Query().code == code)
        bot.send_message(message.chat.id, "<b>Промокод добавлен!</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число!</b>", parse_mode='HTML')

def process_promo_remove(message):
    try:
        index = int(message.text) - 1
        if 0 <= index < len(promocodes.all()):
            promocodes.remove(doc_ids=[promocodes.all()[index].doc_id])
            bot.send_message(message.chat.id, "<b>Промокод удален!</b>", parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "<b>Неверный номер!</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число!</b>", parse_mode='HTML')

def process_task_id(message):
    task_id = message.text
    msg = bot.send_message(message.chat.id, "<b>Введите ссылку на канал:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_task_link(m, task_id))

def process_task_link(message, task_id):
    task_link = message.text
    msg = bot.send_message(message.chat.id, "<b>Введите сколько будет за задание даваться звёзд:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_task_stars(m, task_id, task_link))

def process_task_stars(message, task_id, task_link):
    try:
        stars = float(message.text)
        task_count = len(tasks.all()) + 1
        tasks.insert({'task_id': task_count, 'id': task_id, 'link': task_link, 'stars': stars})
        bot.send_message(message.chat.id, "<b>Задание создано!</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число!</b>", parse_mode='HTML')

def process_task_remove(message):
    try:
        index = int(message.text) - 1
        if 0 <= index < len(tasks.all()):
            tasks.remove(doc_ids=[tasks.all()[index].doc_id])
            bot.send_message(message.chat.id, "<b>Задание удалено!</b>", parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "<b>Неверный номер!</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Введите число!</b>", parse_mode='HTML')

if __name__ == '__main__':
    bot.polling(none_stop=True)