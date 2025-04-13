import telebot
import sqlite3
import random
import time
import threading
import os
import json
from PIL import Image, ImageDraw, ImageFont
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# إعدادات البوت
TOKEN = "7984622218:AAEhjLtLp2WFWLdYxcVxmxW-AQAf4nKShiI"  # ضع توكن البوت الصحيح هنا
ADMIN_ID = 7347225275      # ضع معرف الأدمن الصحيح هنا
SUPPORT_LINK = "https://t.me/Vuvuvuuu_bot"  # رابط الدعم لشحن الرصيد

# إعدادات الدعوات
INVITE_ENABLED = True  # تفعيل أو تعطيل نظام الدعوات
# تعريف القنوات المطلوبة
REQUIRED_CHANNELS = ["@ee44e4e","@Se_v_e_n7","@ZD_66","@S_0_P_E_R"]
broadcasting_active = False  # بداية الإذاعة متوقفة
INVITE_FRIENDS_ACTIVE = True  # للتحكم في حالة دعوة الأصدقاء
CHARGE_POINTS_ACTIVE = True  # للتحكم في حالة سحب الرصيد
DAILY_TASKS_ACTIVE = False  # لتحديد حالة المهام اليومية
BOT_ACTIVE = True  # لتحديد حالة البوت
entry_notification_enabled = True  # الحالة الافتراضية: مفعّل ✅
bot_running = True  # الحالة الافتراضية: البوت مفعّل
invite_link_enabled = True  # الحالة الافتراضية: رابط الدعوة مفعل ✅
TRANSFER_FEE_PERCENTAGE = 10  # نسبة رسوم التحويل (يمكن تعديلها من لوحة التحكم)
NOTIFICATIONS_ENABLED = True  # الافتراضي: إشعارات الدخول مفعلة
INVITE_POINTS = 10  # عدد النقاط المكتسبة عند دعوة صديق
BOT_ACTIVE = True  # الافتراضي: البوت يعمل
memory_games = {}  # ✅ تخزين حالة كل مستخدم في اختبار الذاكرة
user_invites = 0  # عدد الدعوات الخاصة بالمستخدم

bot = telebot.TeleBot(TOKEN)

# إنشاء اتصال بقاعدة البيانات
conn = sqlite3.connect("bets.db", check_same_thread=False)
cursor = conn.cursor()

# ✅ إنشاء جدول `users` إذا لم يكن موجودًا
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER
)''')

# ✅ التحقق من وجود العمود `invites` وإضافته إذا لم يكن موجودًا
try:
    cursor.execute("SELECT invites FROM users LIMIT 1;")
except sqlite3.OperationalError:
    cursor.execute("ALTER TABLE users ADD COLUMN invites INTEGER DEFAULT 0;")
    conn.commit()

# ✅ إنشاء جدول `referrals` إذا لم يكن موجودًا
cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
    inviter_id INTEGER,
    invited_id INTEGER,
    PRIMARY KEY (inviter_id, invited_id)
)''')

# ✅ إنشاء جدول `tasks` إذا لم يكن موجودًا
cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT,
    task_type TEXT,
    task_goal INTEGER,
    reward INTEGER
)''')

# ✅ إنشاء جدول `daily_tasks` إذا لم يكن موجودًا
cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        points INTEGER NOT NULL
    )
''')

# ✅ إنشاء جدول `user_tasks` إذا لم يكن موجودًا
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_tasks (
        user_id INTEGER,
        task_id INTEGER,
        completed BOOLEAN DEFAULT 0,
        UNIQUE(user_id, task_id)
    )
''')

conn.commit()  # حفظ التغييرات في قاعدة البيانات

# ملف تخزين أسعار الألعاب
PRICE_FILE = "game_prices.json"

# 🔄 تحميل أسعار الألعاب عند بدء تشغيل البوت
def load_game_prices():
    try:
        with open(PRICE_FILE, "r") as file:
            game_prices = json.load(file)
        print("✅ تم تحميل أسعار الألعاب من الملف بنجاح!")
        return game_prices
    except (FileNotFoundError, json.JSONDecodeError):
        print("⚠️ لم يتم العثور على ملف الأسعار، سيتم استخدام الإعدادات الافتراضية.")
        return {}  # إرجاع قاموس فارغ إذا لم يتم العثور على الملف

# تحميل الأسعار عند بدء تشغيل البوت
game_prices = load_game_prices()

# تحديث إعدادات الألعاب باستخدام الأسعار المحفوظة
GAME_SETTINGS = {
    "guess": {"entry": game_prices.get("guess", 5), "win": 10, "loss": 5},
    "trivia": {"entry": game_prices.get("trivia", 5), "win": 5, "loss": 5, "time": 10},
    "wheel": {"entry": game_prices.get("wheel", 5)}, 
    "memory": {"entry": game_prices.get("memory", 5), "win": 10, "loss": 5}
}

# 🔄 حفظ الأسعار في الملف عند التعديل
def save_price_changes():
    with open(PRICE_FILE, "w") as file:
        json.dump({game: GAME_SETTINGS[game]["entry"] for game in GAME_SETTINGS}, file, indent=4)
    print("💾 تم حفظ تغييرات الأسعار في الملف.")

# 📌 دالة تعديل الأسعار من لوحة الإدارة
def admin_edit_game_prices(message):
    try:
        game_name, new_price = message.text.split()
        new_price = int(new_price)
        if game_name in GAME_SETTINGS:
            GAME_SETTINGS[game_name]["entry"] = new_price
            save_price_changes()  # 🔄 حفظ التعديلات في `game_prices.json`
            bot.send_message(ADMIN_ID, f"✅ تم تعديل سعر اللعبة '{game_name}' إلى {new_price} نقطة وحفظه في الملف.")
        else:
            bot.send_message(ADMIN_ID, "❌ اسم اللعبة غير صحيح، الرجاء إدخال اسم لعبة موجود.")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ تنسيق غير صحيح، استخدم: game_name new_price")


# نصوص الأزرار (لوحة المستخدم)
button_names = {
    "guess": "🎲 تخمين الرقم",
    "trivia": "❓ أسئلة عامة",
    "wheel": "🎡 عجلة الحظ",
    "memory": "🧠 اختبار الذاكرة",
    "balance": "💰 معرفة الرصيد",
    "referral": "🎟 دعوة الأصدقاء",
    "sh_charge": "💳 شحن الرصيد",
    "admin_panel": "🛠️ لوحة الإدارة"
}

# دوال مساعدة لتعديل النقاط
def add_points(user_id, amount):
    cursor.execute("UPDATE users SET points = points + ? WHERE id=?", (amount, user_id))
    conn.commit()

def remove_points(user_id, amount):
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] >= amount:
        cursor.execute("UPDATE users SET points = points - ? WHERE id=?", (amount, user_id))
    else:
        cursor.execute("UPDATE users SET points = 0 WHERE id=?", (user_id,))
    conn.commit()

# لوحة المستخدم (ReplyKeyboardMarkup بأزرار عادية)
def get_user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(KeyboardButton("💰 معرفة الرصيد"), KeyboardButton("🎮 الألعاب"))
    markup.row(KeyboardButton("🔄 تحويل النقاط"), KeyboardButton("🎟 دعوة الأصدقاء"))
    markup.row(KeyboardButton("💳 سحب النقاط"), KeyboardButton("💳 شحن الرصيد"))
    markup.row(KeyboardButton("📅 المهام اليومية"))  # ✅ إضافة زر المهام اليومية هنا
    return markup

def get_games_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("🎲 تخمين الرقم"),
        KeyboardButton("❓ أسئلة عامة")
    )
    markup.add(
        KeyboardButton("🎡 عجلة الحظ"),
        KeyboardButton("✈️ لعبة الطيارة")  # ✅ زر لعبة الطيارة الجديد
    )
    markup.add(
        KeyboardButton("🧠 اختبار الذاكرة"),
        KeyboardButton("⬅ العودة")
    )
    return markup
    
# لوحة الإدارة (InlineKeyboardMarkup) تظهر فقط للأدمن
# دالة لإنشاء لوحة التحكم للأدمن
def get_admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)

    # مجموعة الأزرار الأساسية
    markup.add(
        InlineKeyboardButton("📦 قسم النسخ الاحتياطية", callback_data="backup_menu"),
        InlineKeyboardButton(f"إشعار الدخول: {'✅' if entry_notification_enabled else '❌'}", callback_data="toggle_notifications"),
        InlineKeyboardButton("⚙️ تشغيل/إيقاف البوت: " + ("✅" if bot_running else "❌"), callback_data="toggle_bot"),
        InlineKeyboardButton("🔗 تعيين قناة اشتراك", callback_data="set_channel"),  # زر تعيين قناة الاشتراك
    )

    # زر إعدادات البوت
    markup.add(InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="bot_settings"))

    return markup

# دالة لإنشاء قائمة إعدادات البوت
def get_bot_settings_menu():
    markup = InlineKeyboardMarkup(row_width=2)

    # مجموعة إعدادات البوت
    markup.add(
        InlineKeyboardButton("💰 إضافة نقاط", callback_data="admin_add_points"),
        InlineKeyboardButton("❌ خصم نقاط", callback_data="admin_remove_points"),
        InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="broadcast"),
        InlineKeyboardButton("📋 معلومات المستخدم", callback_data="get_user_info"),
        InlineKeyboardButton("⚙️ تعديل رسالة الترحيب", callback_data="edit_welcome"),
        InlineKeyboardButton("🔄 تعديل إعدادات الألعاب", callback_data="edit_game_settings"),
        InlineKeyboardButton("🔧 تعديل نقاط الألعاب", callback_data="edit_game_points"),
        InlineKeyboardButton("⏱ تعديل وقت الأسئلة", callback_data="edit_question_time"),
        InlineKeyboardButton("📅 إدارة المهام اليومية", callback_data="manage_tasks"),
        InlineKeyboardButton("🔗 تعيين نقاط الدعوة", callback_data="set_invite_points"),
        InlineKeyboardButton("➕ إضافة نقاط للجميع", callback_data="add_points_all"),
        InlineKeyboardButton("➖ خصم نقاط للجميع", callback_data="remove_points_all"),
        InlineKeyboardButton("⬅ العودة", callback_data="back_to_admin")  # زر العودة
    )

    return markup

# دالة لتحديث الرسائل المشتركة
def update_admin_message(chat_id, message_id, text, reply_markup):
    bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "toggle_notifications")
def toggle_entry_notification(call):
    global entry_notification_enabled
    entry_notification_enabled = not entry_notification_enabled  # تبديل الحالة

    # تحديث الرسالة لعرض الحالة الجديدة
    update_admin_message(call.message.chat.id, call.message.message_id, "🔧 **لوحة تحكم الأدمن:**", get_admin_menu())

# دالة لتبديل حالة تشغيل البوت
@bot.callback_query_handler(func=lambda call: call.data == "toggle_bot")
def toggle_bot(call):
    global bot_running
    bot_running = not bot_running  # تبديل حالة التشغيل

    # إرسال إشعار للأدمن حول حالة البوت
    status = "✅ البوت الآن قيد التشغيل." if bot_running else "❌ تم إيقاف البوت، لن يتمكن المستخدمون من التفاعل معه."
    bot.answer_callback_query(call.id, status, show_alert=True)

    # تحديث لوحة الأدمن
    update_admin_message(call.message.chat.id, call.message.message_id, "🔧 **لوحة تحكم الأدمن:**", get_admin_menu())

# دالة لإظهار إعدادات البوت
@bot.callback_query_handler(func=lambda call: call.data == "bot_settings")
def show_bot_settings(call):
    update_admin_message(call.message.chat.id, call.message.message_id, "🔧 **إعدادات البوت:**", get_bot_settings_menu())

# دالة لإعادة المستخدم إلى لوحة الإدارة عند الضغط على زر العودة
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username if message.from_user.username else "NoUsername"
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name if message.from_user.last_name else ""

    full_name = f"{first_name} {last_name}" if last_name else first_name

    # التحقق من الاشتراك في القناة
    for channel in REQUIRED_CHANNELS:  # تأكد من فحص جميع القنوات
        if not is_subscribed(user_id, channel):
            bot.send_message(user_id, f"🚸| عذراً عزيزي .🔰| عليك الاشتراك في قناة البوت لتتمكن من استخدامه\n\n- https://t.me/{channel[1:]}\n\n‼️| اشترك ثم ارسل /start")
            return

    # إذا كان مشتركًا في القناة، استمر في عرض الرسالة المعتادة
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "🛠️ لوحة الإدارة:", reply_markup=get_admin_menu())
        return

    # التحقق من وجود المستخدم في قاعدة البيانات
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if user is None:
        # إذا لم يكن المستخدم موجودًا، أضفه
        cursor.execute("INSERT INTO users (id, username, points) VALUES (?, ?, ?)", (user_id, username, 0))
        conn.commit()

        # إرسال إشعار إلى المطور
        cursor.execute("SELECT COUNT(*) FROM users")
        total_members = cursor.fetchone()[0]  # عدد الأعضاء في قاعدة البيانات
        message_text = f"""
        تم دخول شخص جديد إلى البوت الخاص بك 👾
        -----------------------
        • معلومات العضو الجديد :
        • الاسم : [{full_name}](tg://openmessage?user_id={user_id})
        • المعرف : @{username} 
        • الايدي : {user_id}
        -----------------------
        • عدد الأعضاء الكلي : {total_members}
        """
        bot.send_message(ADMIN_ID, message_text, parse_mode='Markdown')

        # رسالة ترحيب للمستخدم الجديد
        bot.send_message(user_id, "👋 هلا بيك حبيبي نورت البوت\n\nمعاك مطور البوت👈𝑩𝑳𝑨𝑪𝑲\n\nشرح البوت👇\n\n"
                                  "1👈شحن النقاط عن طريق الوكيل للعب الالعاب\n\n"
                                  "2👈بعد شحن النقاط يمكنك لعب الالعاب، كل لعبة لها سعر\n\n"
                                  "3👈بعد بدء العبة عند الإجابة الصحيحة تكسب نقاط، عند الإجابة الخاطئة تخسر نقاط\n\n"
                                  "4👈تجميع النقاط عبر الهدايا التي ستنزل في قناة البوت\n\n"
                                  "5👈تجميع النقاط عند مشاركة رابط الدعوة\n\n"
                                  "6👈يمكنك استبدال نقاط البوت بنقاط بوت تمويل، كل 10 نقاط في البوت = 100 نقطة", 
                                  reply_markup=get_user_menu())
    else:
        # إذا كان المستخدم موجودًا في قاعدة البيانات
        bot.send_message(user_id, f"🎉 مرحبا يا👈 {first_name} 👉نورت البوت\n\nرصيدك الحالي👈: {user[2]} نقطة.", 
                         reply_markup=get_user_menu())

# دالة back_to_admin: هذه الدالة تسمح بالرجوع إلى لوحة الإدارة
@bot.callback_query_handler(func=lambda call: call.data == "back_to_admin")
def back_to_admin(call):
    # تحديث الرسالة إلى لوحة الإدارة عند العودة
    bot.edit_message_text(
        "🔧 **لوحة تحكم الأدمن:**\n\nاختر القسم الذي تريد تعديل الإعدادات فيه.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=get_admin_menu()  # تأكد من أنك تستخدم لوحة الأدمن هنا
    )

@bot.message_handler(func=lambda m: m.text == "💳 شحن الرصيد")
def charge_points(message):
    user_id = message.chat.id  # ✅ تعريف user_id في بداية الدالة

    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا، لا يمكنك دعوة الأصدقاء الآن.")
        return

    if not CHARGE_POINTS_ACTIVE:  # تحقق من حالة سحب الرصيد
        bot.send_message(user_id, "⚠️ ميزة شحن الرصيد غير مفعلة حاليًا.")
        return

    # إنشاء زر شفاف يحتوي على رابط الوكيل
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 تواصل مع الوكيل", url=SUPPORT_LINK))

    # نص الرسالة مع التنسيق الجيد
    recharge_text = (
        "⚠️ للتواصل مع الدعم لشحن رصيدك:\n\n"
        "📌 الشروط:\n"
        "1️⃣ الشحن يتم عبر نقاط بوتات تمويل بدلًا من الأموال، أي يمكنك شحن حسابك باستخدام نقاط أخرى.\n\n"
        "2️⃣ عند سحب النقاط، يمكنك تحويل نقاط بوت المراهنات إلى نقاط بوت تمويل.\n\n"
        "3️⃣ كل 10 نقاط بوت مراهنات = 100 نقطة بوت تمويل.\n\n"
        "4️⃣ البوتات المسموحة للشحن والسحب:\n"
        "   - 📌 أسيا سيل\n"
        "   - 📌 مهدويون\n"
        "   - 📌 دعمكم\n"
        "   - 📌 اليمن\n"
        "   - 📌 أرقام فيك\n\n"
        "💰 لطلب الشحن أو السحب، راسل الوكيل عبر الزر أدناه👇"
    )

    # إرسال الرسالة مع الزر
    bot.send_message(user_id, recharge_text, reply_markup=markup, parse_mode="Markdown")

# ===================== قسم الألعاب =====================
@bot.message_handler(func=lambda m: m.text == "🎮 الألعاب")
def show_games(message):
    bot.send_message(message.chat.id, "🎮 اختر لعبة:", reply_markup=get_games_menu())

@bot.message_handler(commands=['plane'])
def start_plane(message):
    if game.running:
        return bot.send_message(message.chat.id, "🚀 الطيارة تحلق بالفعل!")
    
    bot.send_message(message.chat.id, "⌛️ الطيارة ستقلع بعد 3 ثوانٍ! استخدم /join_plane [المبلغ] للانضمام.")
    
    def launch_game():
        game.start_game()
        bot.send_message(message.chat.id, f"🔥 الطائرة انطلقت! المضاعف الآن {game.multiplier}x")
    
    threading.Thread(target=launch_game).start()

@bot.message_handler(commands=['join_plane'])
def join_plane(message):
    parts = message.text.split()
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❌ استخدم: /join_plane [الرهان]")
    bet = int(parts[1])
    bot.send_message(message.chat.id, game.join_game(message.chat.id, bet))

@bot.message_handler(commands=['cashout_plane'])
def cashout_plane(message):
    bot.send_message(message.chat.id, game.cashout(message.chat.id))

@bot.message_handler(commands=['stop_plane'])
def stop_plane(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, f"🛑 توقفت اللعبة! المضاعف: {game.stop_game()}x")

@bot.message_handler(func=lambda m: m.text == "🏆 تخمين مكان الكرة")
def play_guess_ball(message):
    user_id = message.chat.id
    if not bot_running:
        bot.send_message(message.chat.id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return
    # التحقق من رصيد اللاعب
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[0] < GAME_SETTINGS["guess"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['guess']['entry']} نقطة. يرجى شحن رصيدك عبر الوكيل.", reply_markup=get_user_menu())
        return

    # خصم تكلفة اللعبة
    remove_points(user_id, GAME_SETTINGS["guess"]["entry"])

    # تحديد مكان الكرة عشوائيًا
    ball_position = random.randint(1, 3)

    bot.send_message(user_id, "🎩 تحت أي كوب تعتقد أن الكرة موجودة؟\n\n🔢 اختر: 1, 2, 3")

    def check_guess(msg):
        try:
            user_guess = int(msg.text)
            if user_guess not in [1, 2, 3]:
                bot.send_message(user_id, "⚠️ يرجى اختيار رقم صحيح (1، 2، 3).")
                return
            
            if user_guess == ball_position:
                add_points(user_id, GAME_SETTINGS["guess"]["win"])
                bot.send_message(user_id, f"🎉 صحيح! الكرة كانت تحت الكوب {ball_position}. ربحت {GAME_SETTINGS['guess']['win']} نقطة! 🎊")
            else:
                remove_points(user_id, GAME_SETTINGS["guess"]["loss"])
                bot.send_message(user_id, f"❌ خطأ! الكرة كانت تحت الكوب {ball_position}. تم خصم {GAME_SETTINGS['guess']['loss']} نقطة. 😢")
        
        except ValueError:
            bot.send_message(user_id, "⚠️ الرجاء إدخال رقم صحيح.")
    
    bot.register_next_step_handler(message, check_guess)
    
@bot.message_handler(func=lambda m: m.text == "⬅ العودة")
def back_to_main(message):
    bot.send_message(message.chat.id, "🔙 عودة إلى القائمة الرئيسية", reply_markup=get_user_menu())

@bot.message_handler(func=lambda m: m.text == button_names["guess"])
def play_guess(message):
    user_id = message.chat.id
    if not bot_running:
        bot.send_message(message.chat.id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < GAME_SETTINGS["guess"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['guess']['entry']} نقطة.", reply_markup=get_user_menu())
        return

    secret_number = random.randint(1, 10)
    bot.send_message(user_id, "🔢 اختر رقمًا بين 1 و 10!")
    def check_guess(msg):
        try:
            guess = int(msg.text)
            if guess == secret_number:
                add_points(user_id, GAME_SETTINGS["guess"]["win"])
                bot.send_message(user_id, "🎉 صحيح! ربحت 10 نقطة.")
            else:
                remove_points(user_id, GAME_SETTINGS["guess"]["loss"])
                bot.send_message(user_id, f"❌ خطأ! \n\n تم خصم 5 نقطة.")
        except ValueError:
            bot.send_message(user_id, "⚠️ الرجاء إدخال رقم صحيح.")
    bot.register_next_step_handler(message, check_guess)

# --- لعبة الأسئلة العامة مع عد تنازلي ---
trivia_questions = [
    {"q": "ما هي عاصمة فرنسا؟", "a": "باريس"},
    {"q": "ما هو أكبر كوكب في المجموعة الشمسية؟", "a": "المشتري"},
    {"q": "كم عدد قارات العالم؟", "a": "7"},
    {"q": "ما هو الحيوان الذي يُلقب بملك الغابة؟", "a": "الأسد"},
    {"q": "كم عدد ألوان قوس قزح؟", "a": "7"},
    {"q": "من هو مؤلف رواية 'البؤساء'؟", "a": "فيكتور هوجو"},
    {"q": "ما هو البحر الذي يفصل بين أوروبا وأفريقيا؟", "a": "البحر المتوسط"},
    {"q": "ما هي العملة الرسمية في اليابان؟", "a": "الين"},
    {"q": "في أي عام هبط الإنسان على سطح القمر؟", "a": "1969"},
    {"q": "ما هو أسرع حيوان بري في العالم؟", "a": "الفهد"},
    {"q": "ما هو الغاز الذي تتنفسه الكائنات الحية للبقاء على قيد الحياة؟", "a": "الأكسجين"},
    {"q": "من هو النبي الذي ابتلعه الحوت؟", "a": "يونس"},
    {"q": "ما هي اللغة الرسمية في البرازيل؟", "a": "البرتغالية"},
    {"q": "كم عدد اللاعبين في فريق كرة القدم؟", "a": "11"},
    {"q": "ما هو الكوكب الذي يُعرف بالكوكب الأحمر؟", "a": "المريخ"},
    {"q": "ما هو العنصر الكيميائي الذي يرمز له بـ 'O'؟", "a": "الأكسجين"},
    {"q": "ما هو أطول نهر في العالم؟", "a": "النيل"},
    {"q": "من هو مؤسس شركة مايكروسوفت؟", "a": "بيل جيتس"},
    {"q": "ما هو الحيوان الذي يستطيع الطيران ولكنه ليس طائرًا؟", "a": "الخفاش"},
    {"q": "ما هي أكبر قارة في العالم؟", "a": "آسيا"},
    {"q": "ما هو الحيوان الذي يُعرف بأنه أسرع مخلوق بحري؟", "a": "سمك الشراع"},
    {"q": "من هو مخترع المصباح الكهربائي؟", "a": "توماس إديسون"},
    {"q": "ما هو اسم عاصمة إيطاليا؟", "a": "روما"},
    {"q": "كم عدد الكواكب في المجموعة الشمسية؟", "a": "8"},
    {"q": "ما هو اسم أطول جبل في العالم؟", "a": "إيفرست"},
    {"q": "ما هو الحيوان الذي لا يشرب الماء طوال حياته؟", "a": "الكنغر البري"},
    {"q": "ما هو اسم أكبر محيط في العالم؟", "a": "المحيط الهادئ"},
    {"q": "من هو أول رئيس للولايات المتحدة الأمريكية؟", "a": "جورج واشنطن"},
    {"q": "ما هو الذهب الأسود؟", "a": "البترول"},
    {"q": "من هو الشاعر الذي لُقّب بـ 'أمير الشعراء'؟", "a": "أحمد شوقي"},
    {"q": "ما هو الحيوان الذي يمتلك أطول عمر؟", "a": "السلحفاة"},
    {"q": "كم عدد أضلاع المثلث؟", "a": "3"},
    {"q": "ما هو العضو المسؤول عن ضخ الدم في الجسم؟", "a": "القلب"},
    {"q": "من هو العالم الذي وضع قانون الجاذبية؟", "a": "نيوتن"},
    {"q": "ما هي عاصمة السعودية؟", "a": "الرياض"},
    {"q": "ما هي أكبر دولة في العالم من حيث المساحة؟", "a": "روسيا"},
    {"q": "من هو النبي الذي كلمه الله مباشرة؟", "a": "موسى"},
    {"q": "ما هو أكثر عنصر كيميائي متوفر في جسم الإنسان؟", "a": "الأكسجين"},
    {"q": "ما هو الحيوان الذي يُلقب بسفينة الصحراء؟", "a": "الجمل"},
    {"q": "كم عدد الأسنان لدى الإنسان البالغ؟", "a": "32"},
    {"q": "من هو اللاعب الذي يُلقب بالظاهرة في كرة القدم؟", "a": "رونالدو نازاريو"},
    {"q": "ما هو الحيوان الذي يمكنه العيش في الماء واليابسة؟", "a": "الضفدع"},
    {"q": "ما هو عدد حروف اللغة الإنجليزية؟", "a": "26"},
    {"q": "ما هو أول مسجد بني في الإسلام؟", "a": "مسجد قباء"},
    {"q": "كم سنة في العقد الواحد؟", "a": "10"},
    {"q": "ما هي أكبر بحيرة في العالم؟", "a": "بحيرة قزوين"},
    {"q": "من هو الصحابي الذي لقب بـ 'الفاروق'؟", "a": "عمر بن الخطاب"},
    {"q": "ما هو العنصر الذي يوجد في جميع المركبات العضوية؟", "a": "الكربون"},
    {"q": "ما هو الحيوان الذي يستطيع تغيير لونه؟", "a": "الحرباء"},
    {"q": "ما هو أول عنصر في الجدول الدوري؟", "a": "الهيدروجين"}
]
    # يمكن إضافة المزيد حتى 50 سؤال

# قائمة معرفات الأدمن
ADMIN_IDS = [7347225275]  # استبدل بالـ ID الخاص بالأدمن الحقيقي

# ✅ دالة لعرض رصيد المستخدم عند الضغط على الزر
@bot.message_handler(func=lambda message: message.text == "💰 معرفة الرصيد")
def show_balance(message):
    user_id = message.from_user.id

    # استعلام لجلب رصيد المستخدم
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # تجهيز رسالة الرصيد
    user_balance_text = f"💰 رصيدك الحالي: {user[0]} نقطة." if user else "💸 ليس لديك نقاط حالياً."

    # إرسال الرسالة بدون إظهار رصيد الأدمن
    bot.send_message(message.chat.id, user_balance_text)

@bot.message_handler(func=lambda m: m.text == "🔄 تحويل النقاط")
def transfer_points(message):

    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا، لا يمكنك دعوة الأصدقاء الآن.")
        return

    bot.send_message(message.chat.id, "🔢 أرسل معرف المستخدم والمبلغ المراد تحويله بالشكل التالي:\n`user_id amount`", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_transfer)

def process_transfer(message):
    try:
        sender_id = message.chat.id

        if not BOT_ACTIVE:
            bot.send_message(sender_id, "⚠️ البوت متوقف حاليًا، لا يمكنك تحويل النقاط الآن.")
            return

        recipient_id, amount = map(int, message.text.split())

        if sender_id == recipient_id:
            bot.send_message(sender_id, "❌ لا يمكنك تحويل النقاط إلى نفسك!")
            return

        cursor.execute("SELECT points FROM users WHERE id=?", (sender_id,))
        sender_points = cursor.fetchone()
        if not sender_points or sender_points[0] < amount:
            bot.send_message(sender_id, "❌ رصيدك غير كافٍ لإتمام التحويل!")
            return

        # خصم النقاط من المرسل
        remove_points(sender_id, amount)

        # تطبيق العمولة
        fee = int(amount * TRANSFER_FEE_PERCENTAGE / 100)
        final_amount = amount - fee

        # إضافة النقاط إلى المستلم
        add_points(recipient_id, final_amount)

        bot.send_message(sender_id, f"✅ تم تحويل {final_amount} نقطة إلى المستخدم {recipient_id}. (تم خصم {fee} نقطة كعمولة)")
        bot.send_message(recipient_id, f"🎉 لقد استلمت {final_amount} نقطة من المستخدم {sender_id}!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ تنسيق غير صحيح، استخدم: `user_id amount`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💳 سحب النقاط")
def withdraw_points(message):
    user_id = message.chat.id
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()

    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا، لا يمكنك دعوة الأصدقاء الآن.")
        return

    user_points = row[0]
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_withdraw"))
    
    memory_games[user_id] = {"stage": "withdraw"}  # تحديد المرحلة
    msg = bot.send_message(
        user_id, 
        f"💰 لديك {user_points} نقطة.\n"
        "🔢 أدخل عدد النقاط التي ترغب في سحبها.\n"
        "📢 ملاحظة: كل 10 نقاط في هذا البوت = 100 نقطة في بوت التمويل!\n"
        "📌 مثال: 100",
        parse_mode="Markdown",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, ask_bot_username)

def ask_bot_username(message):
    user_id = message.chat.id
    if user_id not in memory_games or memory_games[user_id].get("stage") != "withdraw":
        return  # المستخدم ألغى العملية، لا تفعل شيئًا
    
    try:
        amount = int(message.text)
        if amount < 100 or amount % 100 != 0:
            bot.send_message(user_id, "❌ يجب أن يكون المبلغ مضاعفًا لـ 100.")
            bot.register_next_step_handler(message, ask_bot_username)
            return

        cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
        row = cursor.fetchone()
        if not row or row[0] < (amount // 100) * 10:
            bot.send_message(user_id, "❌ ليس لديك نقاط كافية للسحب.")
            bot.register_next_step_handler(message, ask_bot_username)
            return

        deducted_amount = (amount // 100) * 10
        memory_games[user_id] = {"stage": "process", "amount": amount, "deducted": deducted_amount}

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_withdraw"))

        msg = bot.send_message(
            user_id, 
            f"📢 سيتم خصم **{deducted_amount} نقطة** من رصيدك.\n"
            "🤖 أدخل يوزر البوت المراد السحب منه:\n"
            "✅ البوتات المسموح السحب منها:\n"
            "- @yynnurybot\n- @MHDN313bot\n- @srwry2bot",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_withdrawal)

    except ValueError:
        bot.send_message(user_id, "⚠️ يرجى إدخال رقم صحيح.")
        bot.register_next_step_handler(message, ask_bot_username)

def process_withdrawal(message):  
    user_id = message.chat.id
    if user_id not in memory_games or memory_games[user_id].get("stage") != "process":
        return  # المستخدم ألغى العملية، لا تفعل شيئًا

    bot_username = message.text.strip().lower()
    allowed_bots = ["@yynnurybot", "@MHDN313bot", "@srwry2bot"]
    if bot_username not in allowed_bots:
        msg = bot.send_message(user_id, "❌ البوت الذي أدخلته غير مسموح السحب منه.\n💬 تواصل مع المطور أو أدخل يوزر بوت آخر:")
        bot.register_next_step_handler(msg, process_withdrawal)
        return  

    amount = memory_games[user_id]["amount"]
    deducted_amount = memory_games[user_id]["deducted"]

    cursor.execute("UPDATE users SET points = points - ? WHERE id=?", (deducted_amount, user_id))
    conn.commit()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📩 إرسال رابط النقاط", callback_data=f"send_points:{user_id}"))

    bot.send_message(
        ADMIN_ID, 
        f"🔔 طلب جديد لسحب النقاط:\n"
        f"👤 المستخدم: @{message.from_user.username if message.from_user.username else 'لا يوجد يوزر'}\n"
        f"💰 النقاط المطلوبة: {amount} نقطة\n"
        f"❌ النقاط التي تم خصمها: {deducted_amount} نقطة\n"
        f"🤖 البوت المطلوب السحب منه: {bot_username}",
        reply_markup=markup
    )

    bot.send_message(user_id, "✅ تم خصم النقاط من رصيدك.\n⏳ عندما يكون المطور متصلًا بالإنترنت، سيتم إرسال رابط النقاط إليك.")
    del memory_games[user_id]  # إزالة بيانات المستخدم بعد إتمام السحب

def cancel_withdraw(call):
    user_id = call.message.chat.id
    if user_id in memory_games:
        del memory_games[user_id]
    bot.send_message(user_id, "❌ تم إلغاء عملية السحب بنجاح.")
    bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)

bot.callback_query_handler(func=lambda call: call.data == "cancel_withdraw")(cancel_withdraw)

# زر إلغاء العملية
@bot.callback_query_handler(func=lambda call: call.data == "cancel_withdraw")
def cancel_withdraw(call):
    bot.answer_callback_query(call.id, "تم إلغاء العملية ✅")  # يرسل إشعار للمستخدم
    bot.send_message(call.message.chat.id, "تم إلغاء طلب السحب بنجاح! 😎")
    
    # إذا كنت تستخدم بيانات مخزنة للمستخدم، قم بحذفها هنا
    # user_data.pop(call.message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "📅 المهام اليومية")
def show_daily_tasks(message):
    user_id = message.chat.id

    # تحقق مما إذا كان البوت نشطًا
    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return

    # تحقق مما إذا كانت المهام اليومية مفعلة
    if not DAILY_TASKS_ACTIVE:
        bot.send_message(user_id, "🚫 لا توجد مهام يومية متاحة حاليًا.")
        return

    response = "📅 *المهام اليومية المتاحة:*\n\n"
    keyboard = InlineKeyboardMarkup()

    # استعلام لجلب المهام اليومية من قاعدة البيانات
    cursor.execute("SELECT id, task, points FROM daily_tasks")
    tasks = cursor.fetchall()

    for task_id, task_text, points in tasks:
        response += f"- {task_text} ({points} نقطة)\n"
        keyboard.add(InlineKeyboardButton(f"✔️ إتمام المهمة", callback_data=f"complete_task_{task_id}"))

    bot.send_message(user_id, response, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("complete_task_"))
def complete_task(call):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])

    # التحقق مما إذا كانت المهام اليومية مفعلة
    if not DAILY_TASKS_ACTIVE:
        bot.answer_callback_query(call.id, "⚠️ المهام اليومية غير مفعلة حاليًا.")
        return

    # التحقق مما إذا كان المستخدم قد أكمل المهمة من قبل
    cursor.execute("SELECT completed FROM user_tasks WHERE user_id=? AND task_id=?", (user_id, task_id))
    task_status = cursor.fetchone()

    if task_status and task_status[0]:  # المهمة مكتملة مسبقًا
        bot.answer_callback_query(call.id, "✅ لقد أكملت هذه المهمة بالفعل!")
        return

    # الحصول على نقاط المهمة
    cursor.execute("SELECT points FROM daily_tasks WHERE id=?", (task_id,))
    task_points = cursor.fetchone()

    if not task_points:
        bot.answer_callback_query(call.id, "❌ هذه المهمة غير موجودة.")
        return

    points = task_points[0]

    # تحديث قاعدة البيانات وإضافة النقاط للمستخدم
    cursor.execute("INSERT OR REPLACE INTO user_tasks (user_id, task_id, completed) VALUES (?, ?, 1)", (user_id, task_id))
    cursor.execute("UPDATE users SET points = points + ? WHERE id=?", (points, user_id))
    conn.commit()

    bot.answer_callback_query(call.id, f"🎉 لقد أكملت المهمة بنجاح وحصلت على {points} نقطة!")
    bot.send_message(user_id, f"🎉 لقد أكملت المهمة وحصلت على {points} نقطة!")

@bot.message_handler(func=lambda m: m.text == button_names["trivia"])
def play_trivia(message):
    user_id = message.chat.id
    if not bot_running:
        bot.send_message(message.chat.id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < GAME_SETTINGS["trivia"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['trivia']['entry']} نقطة. يرجى شحن رصيدك عبر الوكيل.", reply_markup=get_user_menu())
        return
    question_data = random.choice(trivia_questions)
    msg = bot.send_message(user_id, f"❓ {question_data['q']}\n⏳ لديك {GAME_SETTINGS['trivia']['time']} ثوانٍ للإجابة:")
    def countdown():
        for i in range(GAME_SETTINGS["trivia"]["time"], 0, -1):
            try:
                bot.edit_message_text(chat_id=user_id, message_id=msg.message_id,
                                      text=f"❓ {question_data['q']}\n⏳ {i} ثانية متبقية")
                time.sleep(1)
            except Exception:
                break
        bot.edit_message_text(chat_id=user_id, message_id=msg.message_id,
                              text=f"⏰ انتهى الوقت!")
        remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
    threading.Thread(target=countdown).start()
    def check_answer(msg):
        if msg.text.strip().lower() == question_data["a"].lower():
            add_points(user_id, GAME_SETTINGS["trivia"]["win"])
            bot.send_message(user_id, f"✅ إجابة صحيحة! ربحت {GAME_SETTINGS['trivia']['win']} نقطة.")
        else:
            remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
            bot.send_message(user_id, f"❌ إجابة خاطئة!.تم خصم {GAME_SETTINGS['trivia']['loss']} نقطة.")
    bot.register_next_step_handler(message, check_answer)

# --- لعبة عجلة الحظ ---
@bot.message_handler(func=lambda m: m.text == button_names["wheel"])
def play_wheel_game(message):
    user_id = message.chat.id
    if not bot_running:
        bot.send_message(message.chat.id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return
    # التحقق من رصيد المستخدم
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[0] < GAME_SETTINGS["wheel"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['wheel']['entry']} نقطة. يرجى شحن رصيدك عبر الوكيل.", reply_markup=get_user_menu())
        return

    # خصم تكلفة اللعبة
    remove_points(user_id, GAME_SETTINGS["wheel"]["entry"])

    # تحديد النتيجة عشوائيًا
    outcome = random.randint(1, 100)

    if outcome <= 40:  # 40% فرصة للفوز
        win_points = random.randint(1, 50)
        add_points(user_id, win_points)
        result_msg = f"🎉 مبروك! ربحت {win_points} نقطة."

    elif outcome <= 80:  # 40% فرصة للخسارة
        loss_points = random.randint(1, 50)
        remove_points(user_id, loss_points)
        result_msg = f"💔 للأسف، خسرت {loss_points} نقطة."

    else:  # 20% فرصة لخسارة كل النقاط
        cursor.execute("UPDATE users SET points = 0 WHERE id=?", (user_id,))
        conn.commit()
        result_msg = "😱 حظ سيء! خسرت جميع نقاطك."

    # إرسال نتيجة اللعبة للمستخدم
    bot.send_message(user_id, f"🎡 {result_msg}")

#اختبار_الذاكرة
@bot.message_handler(func=lambda m: m.text == "🧠 اختبار الذاكرة")
def play_memory_game(message):
    user_id = message.chat.id
    if not bot_running:
        bot.send_message(message.chat.id, "⚠️ البوت متوقف حاليًا. يرجى المحاولة لاحقًا.")
        return

    # التحقق من الرصيد
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[0] < GAME_SETTINGS["memory"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['memory']['entry']} نقطة.", reply_markup=get_user_menu())
        return

    # خصم تكلفة الدخول للعبة
    remove_points(user_id, GAME_SETTINGS["memory"]["entry"])

    # إنشاء رقم عشوائي مكون من 5 أرقام
    memory_number = "".join(str(random.randint(0, 9)) for _ in range(5))

    # تخزين حالة اللعبة لمنع المستخدم من إرسال الإجابة قبل انتهاء العد التنازلي
    memory_games[user_id] = {"number": memory_number, "active": True}

    # إرسال الرقم إلى المستخدم مع رسالة العد التنازلي
    time_limit = GAME_SETTINGS["trivia"]["time"]
    msg = bot.send_message(user_id, f"🔢 تذكر هذا الرقم: **{memory_number}**\n⏳ لديك {time_limit} ثوانٍ لحفظه!", parse_mode="Markdown")

    # تشغيل العد التنازلي في `Thread`
    thread = threading.Thread(target=countdown, args=(time_limit, user_id, msg.message_id, message, memory_number))
    thread.start()

def countdown(time_limit, user_id, message_id, message, memory_number):
    """دالة العد التنازلي وحماية المستخدم من الغش"""
    for i in range(time_limit, 0, -2):
        try:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=f"🔢 تذكر هذا الرقم: **{memory_games[user_id]['number']}**\n⏳ لديك {i} ثانية متبقية!",
                parse_mode="Markdown"
            )
            time.sleep(1)
        except:
            break  # إذا حدث خطأ أثناء التعديل، لا تتوقف اللعبة

    # بعد انتهاء العد التنازلي، إزالة الرقم والسماح بالإجابة
    bot.edit_message_text(
        chat_id=user_id,
        message_id=message_id,
        text="❓ الآن، ما هو الرقم الذي تذكرته؟"
    )

    # السماح للمستخدم بالإجابة بعد انتهاء العد التنازلي
    memory_games[user_id]["active"] = False
    bot.register_next_step_handler(message, lambda m: check_memory_game(m, memory_number))

def check_memory_game(message, correct_number):
    user_id = message.chat.id

    # التحقق مما إذا كان المستخدم يحاول الغش بإرسال الإجابة مبكرًا
    if memory_games.get(user_id, {}).get("active", True):
        bot.send_message(user_id, "⚠️ لا يمكنك إرسال الإجابة قبل انتهاء وقت الحفظ!")
        return

    user_answer = message.text.strip()

    if user_answer == correct_number:
        add_points(user_id, GAME_SETTINGS["memory"]["win"])
        bot.send_message(user_id, f"✅ إجابة صحيحة! ربحت {GAME_SETTINGS['memory']['win']} نقطة.")
    else:
        remove_points(user_id, GAME_SETTINGS["memory"]["loss"])
        bot.send_message(user_id, f"❌ إجابة خاطئة!\nالرقم الصحيح كان: **{correct_number}**\nتم خصم {GAME_SETTINGS['memory']['loss']} نقطة.", parse_mode="Markdown")

    # حذف بيانات اللعبة بعد انتهاء الجواب
    memory_games.pop(user_id, None)

# ===================== أوامر الإدارة =====================
@bot.callback_query_handler(func=lambda call: call.data in [
    "broadcast", "admin_add_points", "admin_remove_points", "set_channel",
    "add_points_all", "remove_points_all", "edit_welcome", "toggle_notifications",
    "toggle_bot", "edit_game_settings", "edit_game_prices", "edit_game_points",
    "set_trivia_time", "toggle_invite", "manage_tasks", "set_invite_points", "set_transfer_fee"
])

def handle_admin_buttons(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحيات!")
        return

    if call.data == "admin_add_points":
        bot.send_message(ADMIN_ID, "💰 أدخل معرف المستخدم وعدد النقاط للإضافة (مثال: 123456 50):")
        bot.register_next_step_handler(call.message, admin_add_points_handler)

    elif call.data == "admin_remove_points":
        bot.send_message(ADMIN_ID, "❌ أدخل معرف المستخدم وعدد النقاط للخصم (مثال: 123456 30):")
        bot.register_next_step_handler(call.message, admin_remove_points_handler)

    elif call.data == "manage_tasks":
        bot.send_message(ADMIN_ID, "📌 أرسل المهمة اليومية الجديدة بهذا الشكل:\n\nالمهمة | عدد النقاط")
        bot.register_next_step_handler(call.message, add_daily_task)

    elif call.data == "add_points_all":  # ✅ إضافة نقاط للجميع
        bot.send_message(ADMIN_ID, "💰 أدخل عدد النقاط التي تريد إضافتها لجميع المستخدمين:")
        bot.register_next_step_handler(call.message, admin_add_points_all)

    elif call.data == "remove_points_all":  # ✅ خصم نقاط من الجميع
        bot.send_message(ADMIN_ID, "❌ أدخل عدد النقاط التي تريد خصمها من جميع المستخدمين:")
        bot.register_next_step_handler(call.message, admin_remove_points_all)

    elif call.data == "broadcast":
        bot.send_message(ADMIN_ID, "📢 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        bot.register_next_step_handler(call.message, admin_broadcast)

    elif call.data == "set_channel":
        bot.send_message(ADMIN_ID, "🔗 أدخل معرف القناة للاشتراك الإجباري:")
        bot.register_next_step_handler(call.message, admin_set_channel)

    elif call.data == "edit_welcome":
        bot.send_message(ADMIN_ID, "⚙ أدخل رسالة الترحيب الجديدة:")
        bot.register_next_step_handler(call.message, admin_set_welcome)

    elif call.data == "toggle_notifications":
        global NOTIFICATIONS_ENABLED
        NOTIFICATIONS_ENABLED = not NOTIFICATIONS_ENABLED
        status = "✅ مفعّل" if NOTIFICATIONS_ENABLED else "❌ معطّل"
        bot.answer_callback_query(call.id, f"🔄 إشعارات الدخول الآن: {status}")
        bot.send_message(ADMIN_ID, f"🔄 إشعارات الدخول الآن: {status}")

    elif call.data == "toggle_bot":
        global BOT_ACTIVE
        BOT_ACTIVE = not BOT_ACTIVE
        status = "✅ يعمل الآن" if BOT_ACTIVE else "⏸ متوقف مؤقتًا"
        bot.answer_callback_query(call.id, f"🚫 حالة البوت: {status}")
        bot.send_message(ADMIN_ID, f"🚫 حالة البوت: {status}")

    elif call.data == "admin_edit_game":
        bot.send_message(ADMIN_ID, "🛠 أدخل الإعدادات الجديدة للعبة (الصيغة: game_name entry win loss):")
        bot.register_next_step_handler(call.message, admin_edit_game)

    elif call.data == "edit_game_prices":
        bot.send_message(ADMIN_ID, "🔢 أدخل اسم اللعبة وتكلفتها (مثال: guess 5):")
        bot.register_next_step_handler(call.message, admin_edit_game_prices)  

    elif call.data == "edit_game_points":
        bot.send_message(ADMIN_ID, "🔢 أدخل اسم اللعبة ونقاط الدخول (مثال: guess 5):")
        bot.register_next_step_handler(call.message, admin_edit_game_points)

    elif call.data == "set_trivia_time":
        bot.send_message(ADMIN_ID, "⏰ أدخل وقت الانتظار لأسئلة اللعبة (بالثواني):")
        bot.register_next_step_handler(call.message, admin_set_trivia_time)

    elif call.data == "toggle_invite":  # ✅ زر تشغيل/إيقاف رابط الدعوة
        global INVITE_ENABLED
        INVITE_ENABLED = not INVITE_ENABLED  # ✅ تبديل الحالة بين تشغيل وإيقاف
        status = "✅ مفعل" if INVITE_ENABLED else "❌ موقوف"
        bot.answer_callback_query(call.id, f"🔗 رابط الدعوة الآن: {status}")
        bot.send_message(ADMIN_ID, f"🔗 تم تغيير حالة رابط الدعوة إلى: {status}")
    elif call.data == "set_invite_points":
        bot.send_message(ADMIN_ID, "🔢 أدخل عدد النقاط التي تُعطى عند مشاركة رابط الدعوة:")
        bot.register_next_step_handler(call.message, set_invite_points_handler)

def admin_broadcast(message):
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    
    success_count = 0
    failed_count = 0

    for user in users:
        try:
            bot.send_message(user[0], f"رسالة من المطور🧑‍💻\n{message.text}")
            success_count += 1
        except Exception:
            failed_count += 1
            continue
    
    bot.send_message(ADMIN_ID, f"✅ تمت الإذاعة لـ {success_count} مستخدم.\n⚠️ فشل الإرسال لـ {failed_count} مستخدم.")

def admin_add_points_handler(message):
    try:
        user_id, pts = map(int, message.text.split())
        
        # إضافة النقاط إلى المستخدم
        add_points(user_id, pts)
        
        # إرسال تأكيد إلى الأدمن
        bot.send_message(ADMIN_ID, f"✅ تمت إضافة {pts} نقطة للمستخدم {user_id} بنجاح.")
        
        # إشعار المستخدم بالنقاط المضافة
        bot.send_message(user_id, f"🎉 تم إضافة {pts} نقطة إلى رصيدك بواسطة المطور! شكرًا لاستخدامك البوت. 😊")
    
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: user_id points")

def process_user_info(message):
    user_input = message.text.strip()

    # تحقق مما إذا كان الإدخال هو رقم آيدي أو يوزر
    if user_input.isdigit():
        user_id = int(user_input)
    elif user_input.startswith("@"):
        user_id = user_input[1:]
    else:
        bot.send_message(message.chat.id, "❌ يرجى إدخال آيدي رقمي أو يوزر بصيغة @username")
        return

    try:
        # استخدم get_chat للحصول على معلومات المستخدم في المحادثات الخاصة
        user = bot.get_chat(user_id)

        # استرجاع معلومات إضافية من قاعدة البيانات
        user_info = get_user_info(user_id)  # أو استخدم username إذا كنت تفضل
        if user_info is None:
            bot.send_message(message.chat.id, "❌ المستخدم غير موجود في قاعدة البيانات.")
            return

        # جمع التفاصيل الخاصة بالمستخدم
        info_text = f"👤| اسم المستخدم : {user.first_name} {user.last_name if user.last_name else ''}\n"
        info_text += f"ℹ️| معرف المستخدم : {user.id}\n"
        info_text += f"📍| اليوزر: @{user.username if user.username else 'غير متوفر'}\n"
        info_text += f"🏵| السيرة الذاتية : {user_info['bio'] if user_info['bio'] else 'None'}\n"
        info_text += f"🌀| حالة المستخدم : {'محظور' if user_info['status'] == 'banned' else 'غير محظور'}\n"
        info_text += f"🎗| حالة عمل البوت مع المستخدم : {'نشط' if user_info['status'] == 'active' else 'غير نشط'}\n"
        info_text += f"🚸| عدد نقاط المستخدم : {user_info['points']}\n"

        # إضافة مزيد من المعلومات عن المستخدم
        info_text += f"\n🌀| مزيد من المعلومات عن المستخدم :\n"
        info_text += f"- عدد عمليات التحويل التي قام بها : {user_info['transfers']}\n"
        info_text += f"- عدد الهدايا اليومية التي جمعها : {user_info['gifts']}\n"
        info_text += f"- عدد السلع التي تم شراؤها : {user_info['purchases']}\n"
        info_text += f"- عدد المشاركات لرابط الدعوة : {user_info['shares']}\n"
        info_text += f"- عدد النقاط التي تم استخدامها : {user_info['used_points']}\n"

        bot.send_message(message.chat.id, info_text)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ: {str(e)}")
    
    user_id, username, points, transfers, gifts, purchases, shares, used_points, bio, status = user_data
    
    return (
        f"👤| اسم المستخدم : {username or 'غير متوفر'}\n"
        f"ℹ️| معرف المستخدم : {user_id}\n\n"
        f"📍| اسم المستخدم : @{username if username else 'غير متوفر'}\n"
        f"🏵| السيرة الذاتية للمستخدم : {bio if bio else 'غير متوفر'}\n"
        f"🌀| حالة المستخدم : {'محظور' if status == 'banned' else 'غير محظور'}\n"
        f"🎗| حالة عمل البوت مع المستخدم : {'نشط' if status == 'active' else 'غير نشط'}\n"
        f"🚸| عدد نقاط المستخدم : {points}\n\n"
        f"🌀| مزيد من المعلومات عن المستخدم :\n\n"
        f"- عدد عمليات التحويل التي قام بها : {transfers}\n"
        f"- عدد الهدايا اليومية التي جمعها : {gifts}\n"
        f"- عدد السلع التي تم شراؤها : {purchases}\n\n"
        f"- عدد المشاركات لرابط الدعوة : {shares}\n"
        f"- عدد النقاط التي تم استخدامها : {used_points}\n"
    )

def admin_remove_points_handler(message):
    try:
        user_id, pts = map(int, message.text.split())
        remove_points(user_id, pts)
        bot.send_message(ADMIN_ID, f"✅ تمت خصم {pts} نقطة من المستخدم {user_id}.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: user_id points")

def add_daily_task(message):
    try:
        task_data = message.text.split("|")
        if len(task_data) != 2:
            bot.send_message(ADMIN_ID, "❌ الصيغة غير صحيحة! استخدم: المهمة | عدد النقاط")
            return
        
        task_text = task_data[0].strip()
        task_points = int(task_data[1].strip())

        cursor.execute("INSERT INTO daily_tasks (task, points) VALUES (?, ?)", (task_text, task_points))
        conn.commit()

        bot.send_message(ADMIN_ID, f"✅ تمت إضافة المهمة اليومية: {task_text} ({task_points} نقطة)")
    
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ عدد النقاط يجب أن يكون رقمًا صحيحًا!")

def admin_remove_points_handler(message):
    try:
        user_id, pts = map(int, message.text.split())
        remove_points(user_id, pts)
        bot.send_message(ADMIN_ID, f"✅ تم خصم {pts} نقطة من المستخدم {user_id}.")
        bot.send_message(user_id, f"⚠️ تم خصم {pts} نقطة من رصيدك بواسطة الأدمن.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: user_id points")

def admin_edit_game_prices(message):
    try:
        game_name, new_price = message.text.split()
        new_price = int(new_price)
        if game_name in GAME_SETTINGS:
            GAME_SETTINGS[game_name]["entry"] = new_price
            save_price_changes()  # 🔄 تحديث الأسعار في الملف
            bot.send_message(ADMIN_ID, f"✅ تم تعديل تكلفة الدخول للعبة {game_name} إلى {new_price} نقطة وحفظها في الملف.")
        else:
            bot.send_message(ADMIN_ID, "❌ اسم اللعبة غير صحيح.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: game_name new_entry_cost")

def admin_add_points_all(message):
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.send_message(ADMIN_ID, "❌ يجب أن يكون العدد أكبر من 0!")
            return

        cursor.execute("UPDATE users SET points = points + ?", (amount,))
        conn.commit()
        
        bot.send_message(ADMIN_ID, f"✅ تم إضافة {amount} نقطة لجميع المستخدمين.")
    
    except ValueError:
        bot.send_message(ADMIN_ID, "⚠️ يرجى إدخال رقم صحيح.")

def admin_remove_points_all(message):
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.send_message(ADMIN_ID, "❌ يجب أن يكون العدد أكبر من 0!")
            return

        # التأكد من عدم تقليل الرصيد لأقل من الصفر
        cursor.execute("UPDATE users SET points = CASE WHEN points >= ? THEN points - ? ELSE 0 END", (amount, amount))
        conn.commit()

        bot.send_message(ADMIN_ID, f"✅ تم خصم {amount} نقطة من جميع المستخدمين.")
    
    except ValueError:
        bot.send_message(ADMIN_ID, "⚠️ يرجى إدخال رقم صحيح.")

def admin_edit_game_points(message):
    try:
        game_name, new_entry_points = message.text.split()
        new_entry_points = int(new_entry_points)
        if game_name in GAME_SETTINGS:
            GAME_SETTINGS[game_name]["entry"] = new_entry_points
            bot.send_message(ADMIN_ID, f"✅ تم تعديل نقاط الدخول للعبة {game_name} إلى {new_entry_points} نقطة.")
        else:
            bot.send_message(ADMIN_ID, "❌ اسم اللعبة غير صحيح.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: game_name new_entry_points")

def admin_set_trivia_time(message):
    try:
        new_time = int(message.text)
        GAME_SETTINGS["trivia"]["time"] = new_time
        bot.send_message(ADMIN_ID, f"✅ تم تعديل وقت الانتظار لأسئلة اللعبة إلى {new_time} ثانية.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ يرجى إدخال رقم صحيح.")

def admin_set_welcome(message):
    global WELCOME_MESSAGE
    WELCOME_MESSAGE = message.text
    bot.send_message(ADMIN_ID, "✅ تم تعديل رسالة الترحيب.")

def is_subscribed(user_id, channel):
    try:
        # التحقق من الاشتراك في القناة
        chat_member = bot.get_chat_member(channel, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

def admin_set_channel(message):
    global REQUIRED_CHANNEL
    REQUIRED_CHANNEL = message.text
    bot.send_message(ADMIN_ID, f"✅ تم تعيين قناة الاشتراك الإجباري: {REQUIRED_CHANNEL}")

def set_invite_points_handler(message):
    global INVITE_POINTS
    try:
        points = int(message.text)
        if points < 0:
            raise ValueError("❌ يجب أن تكون النقاط 0 أو أكثر!")

        INVITE_POINTS = points
        bot.send_message(ADMIN_ID, f"✅ تم تعيين نقاط الدعوة إلى {INVITE_POINTS} نقطة.")
    except ValueError:
        bot.send_message(ADMIN_ID, "⚠️ يرجى إدخال رقم صحيح.")

@bot.callback_query_handler(func=lambda call: call.data == "get_user_info")
def request_user_info(call):
    bot.send_message(call.message.chat.id, "🔍 يرجى إرسال معرف المستخدم أو اليوزر:")
    bot.register_next_step_handler(call.message, process_user_info)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_points:"))
def send_points_handler(call):
    admin_id = call.from_user.id
    if admin_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحيات للرد على هذا الطلب.")
        return

    user_id = call.data.split(":")[1]  
    bot.send_message(admin_id, f"📩 أرسل رابط النقاط للمستخدم: [اضغط هنا](tg://user?id={user_id})", parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(admin_id, lambda message: forward_points_link(message, user_id))

def forward_points_link(message, user_id):
    admin_id = message.chat.id
    if admin_id != ADMIN_ID:
        return

    points_link = message.text  
    bot.send_message(user_id, f"🔗 رابط استلام النقاط:\n{points_link}")
    bot.send_message(admin_id, "✅ تم إرسال رابط النقاط بنجاح!")

# ===================== لعبة الطيارة =====================
class PlaneGame:
    def __init__(self):
        self.running = False
        self.multiplier = 1.0
        self.players = {}

    def start_game(self):
        if self.running:
            return "🚨 اللعبة قيد التشغيل!"
        self.running = True
        self.multiplier = 1.0
        self.players = {}
        time.sleep(3)  # تأخير قبل الإقلاع
        while self.running:
            self.multiplier += 0.1
            time.sleep(1)

    def stop_game(self):
        self.running = False
        return self.multiplier

    def join_game(self, user_id, bet):
        if not self.running:
            return "🚫 لا توجد جولة نشطة!"
        if user_id in self.players:
            return "❌ أنت مشترك بالفعل!"
        self.players[user_id] = bet
        return "✅ تم الاشتراك!"

    def cashout(self, user_id):
        if user_id not in self.players:
            return "❌ لم تشارك!"
        bet = self.players.pop(user_id)
        winnings = bet * self.multiplier
        return f"💰 ربحت {winnings} نقطة!"

game = PlaneGame()

@bot.callback_query_handler(func=lambda call: call.data == "backup_menu")
def show_backup_menu(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحيات!")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("⬇️ أخذ نسخة احتياطية", callback_data="download_backup"),
        InlineKeyboardButton("⬆️ رفع نسخة احتياطية", callback_data="upload_backup")
    )
    bot.send_message(call.message.chat.id, "📦 اختر خيار النسخة الاحتياطية:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "download_backup")
def backup_data(call):
    backup = {}

    # جلب بيانات المستخدمين
    cursor.execute("SELECT id, username, points, invites FROM users")
    backup['users'] = cursor.fetchall()

    # جلب بيانات الدعوات
    cursor.execute("SELECT inviter_id, invited_id FROM referrals")
    backup['referrals'] = cursor.fetchall()

    # حفظ النسخة في ملف JSON
    with open("backup.json", "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=4)

    # إرسال الملف للأدمن
    with open("backup.json", "rb") as f:
        bot.send_document(call.message.chat.id, f)

@bot.callback_query_handler(func=lambda call: call.data == "upload_backup")
def request_backup_file(call):
    bot.send_message(call.message.chat.id, "📁 أرسل ملف النسخة الاحتياطية (backup.json):")
    bot.register_next_step_handler(call.message, handle_uploaded_backup)

def handle_uploaded_backup(message):
    if not message.document:
        bot.send_message(message.chat.id, "❌ الملف غير صالح.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("uploaded_backup.json", "wb") as f:
        f.write(downloaded_file)

    with open("uploaded_backup.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # استرجاع بيانات المستخدمين
    for user in data.get("users", []):
        cursor.execute("""
            INSERT OR REPLACE INTO users (id, username, points, invites)
            VALUES (?, ?, ?, ?)
        """, (user[0], user[1], user[2], user[3]))

    # استرجاع بيانات الدعوات
    for ref in data.get("referrals", []):
        cursor.execute("""
            INSERT OR IGNORE INTO referrals (inviter_id, invited_id)
            VALUES (?, ?)
        """, (ref[0], ref[1]))

    conn.commit()
    bot.send_message(message.chat.id, "✅ تم استعادة النسخة الاحتياطية بنجاح.")

# ===================== تشغيل البوت =====================
while True:
    try:
        print("🤖 البوت يعمل...")
        bot.infinity_polling(timeout=30, long_polling_timeout=10)
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بـ Telegram API: {e}")
        time.sleep(5)  # انتظار 5 ثواني قبل إعادة المحاولة
