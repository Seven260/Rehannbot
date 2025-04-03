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
def get_admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="broadcast"),
        InlineKeyboardButton("💰 إضافة نقاط", callback_data="admin_add_points")
    )
    markup.add(
    InlineKeyboardButton("➕ إضافة نقاط للجميع", callback_data="add_points_all"),
    InlineKeyboardButton("➖ خصم نقاط من الجميع", callback_data="remove_points_all")
    )
    markup.add(
        InlineKeyboardButton("❌ خصم نقاط", callback_data="admin_remove_points"),
        InlineKeyboardButton("⏳ تعديل وقت اختبار الذاكرة", callback_data="set_memory_time"),
        InlineKeyboardButton("🔗 تعيين قناة اشتراك", callback_data="set_channel"),
        InlineKeyboardButton("📋 معلومات المستخدم", callback_data="get_user_info")
    )
    markup.add(
        InlineKeyboardButton("⚙ تعديل رسالة الترحيب", callback_data="edit_welcome"),
        InlineKeyboardButton("🔄 إشعار الدخول", callback_data="toggle_notifications")
    )
    markup.add(
        InlineKeyboardButton("⏹ تشغيل/إيقاف البوت", callback_data="toggle_bot"),
        InlineKeyboardButton("🎯 تعديل إعدادات الألعاب", callback_data="edit_game_settings")
    )
    markup.add(
        InlineKeyboardButton("🔢 تعديل أسعار الألعاب", callback_data="edit_game_prices"),
        InlineKeyboardButton("🔢 تعديل نقاط اللعبة", callback_data="edit_game_points")
    )
    markup.add(
        InlineKeyboardButton("📅 إدارة المهام اليومية", callback_data="manage_tasks"),
        InlineKeyboardButton("⏰ تعديل وقت الأسئلة", callback_data="set_trivia_time")
    )
    markup.add(
        InlineKeyboardButton("🔗 تشغيل/إيقاف رابط الدعوة", callback_data="toggle_invite"),
        InlineKeyboardButton("🔢 تعيين نقاط الدعوة", callback_data="set_invite_points")
    )
    return markup

# ===================== أوامر البوت العامة =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username if message.from_user.username else "NoUsername"

    if not BOT_ACTIVE and user_id != ADMIN_ID:  # ✅ محاذاة صحيحة داخل الدالة
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا من قبل الإدارة.")
        return

    # استخراج معرف المُرسل من رابط الدعوة إن وجد
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and INVITE_ENABLED:
        try:
            referrer_id = int(args[1])
        except ValueError:
            referrer_id = None

    # إذا كان الأدمن، عرض لوحة الإدارة فقط
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "👨‍💻 أنت الأدمن! إليك لوحة الإدارة.", reply_markup=get_admin_menu(), parse_mode="Markdown")
        return

    # التحقق مما إذا كان المستخدم مسجلًا بالفعل في قاعدة البيانات
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        # تسجيل المستخدم الجديد في قاعدة البيانات
        cursor.execute("INSERT INTO users (id, username, points) VALUES (?, ?, ?)", (user_id, username, 0))
        conn.commit()

        # التحقق من أن المستخدم دخل عبر رابط الدعوة ولم يحصل على النقاط من قبل
        if referrer_id and referrer_id != user_id:
            referral_exists = cursor.fetchone()

            if not referral_exists:
                add_points(referrer_id, INVITE_POINTS)
                cursor.execute("INSERT INTO referrals (inviter_id, invited_id) VALUES (?, ?)", (referrer_id, user_id))
                conn.commit()

                # إرسال إشعار لصاحب الرابط
                bot.send_message(referrer_id, f"🎉 لقد انضم {message.from_user.first_name} عبر رابط الدعوة الخاص بك! 🚀\n📌 تم إضافة {INVITE_POINTS} نقطة إلى رصيدك.")

        bot.send_message(user_id, "👋 هلا بيك حبيبي نورت البوت\n\nمعاك مطور البوت👈𝑩𝑳𝑨𝑪𝑲\n\nشرح البوت👇\n\n1👈شحن النقاط عن طريق الوكيل للعب الالعاب الالعاب\n\n2👈بعد شحن النقاط يمكنك لعب الالعاب كل لعبة لها سعر \n\n3👈بعد بدء العبة عند الإجابة الصحيحة تكسب نقاط عند الإجابة الخاطئة تخسر نقاط\n\n4👈تجميع النقاط عبر الهداية التي ستنزل فى قناة البوت\n\n5👈تجميع النقاط عند مشاركة رابط الدعوة\n\n6👈يمكنك استبدال نقاط البوت بنقاط بوت تمويل كل 10 نقاط فى البوت =100 نقطة", reply_markup=get_user_menu())
    else:
        bot.send_message(user_id, f"🎉 مرحبا يا👈 {message.from_user.first_name} 👉نورت البوت \n \n رصيدك الحالي👈: {user[2]} نقطة.", reply_markup=get_user_menu())

# زر دعوة الأصدقاء (للمستخدم)
@bot.message_handler(func=lambda m: m.text == "🎟 دعوة الأصدقاء")
def invite_friends(message):
    user_id = message.chat.id  # ✅ تعريف user_id في البداية

    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا، لا يمكنك دعوة الأصدقاء الآن.")
        return

    invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"

    # جلب عدد الدعوات من قاعدة البيانات
    cursor.execute("SELECT invites FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    user_invites = row[0] if row else 0  # إذا لم يكن هناك سجل، افتراضيًا 0
    invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    bot.send_message(user_id, f"انسخ الرابط ثم قم بمشاركته مع اصدقائك 📥 .\n\n • كل شخص يقوم بالدخول ستحصل على {INVITE_POINTS} 💲\n\n  بإمكانك عمل اعلان خاص برابط الدعوة الخاص بك\n\n ~ رابط الدعوة :{invite_link}\n\n• مشاركتك للرابط : {user_invites} 🌀", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 شحن الرصيد")
def charge_points(message):
    user_id = message.chat.id  # ✅ تعريف user_id في بداية الدالة

    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا، لا يمكنك شحن النقاط الآن.")
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
    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا من قبل الإدارة.")
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
    if not BOT_ACTIVE:
        bot.send_message(user_id, "⚠️ البوت متوقف حاليًا من قبل الإدارة.")
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
    
