import telebot
import sqlite3
import random
import time
import threading
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# إعدادات البوت
TOKEN = "7984622218:AAEhjLtLp2WFWLdYxcVxmxW-AQAf4nKShiI"  # ضع توكن البوت الصحيح هنا
ADMIN_ID = 7347225275      # ضع معرف الأدمن الصحيح هنا
SUPPORT_LINK = "https://t.me/Vuvuvuuu_bot"  # رابط الدعم لشحن الرصيد

# إعدادات الدعوات
INVITE_ENABLED = True  # تفعيل أو تعطيل نظام الدعوات
INVITE_POINTS = 10  # عدد النقاط المكتسبة عند دعوة صديق

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
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton(button_names["balance"]), KeyboardButton("🎮 الألعاب"))
    markup.row(KeyboardButton(button_names["referral"]))
    markup.add(KeyboardButton(button_names["sh_charge"]))
    return markup

def get_games_menu():
    markup = ReplyKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎲 تخمين الرقم", callback_data="play_guess"),
        InlineKeyboardButton("❓ أسئلة عامة", callback_data="play_trivia")
    )
    markup.add(
        InlineKeyboardButton("🎡 عجلة الحظ", callback_data="play_wheel"),
        InlineKeyboardButton("🏆 تخمين مكان الكرة", callback_data="play_ball_guess")
    )
    markup.add(
        InlineKeyboardButton("🧠 اختبار الذاكرة", callback_data="play_memory"),
        InlineKeyboardButton("⬅ العودة", callback_data="back_to_main")
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
        InlineKeyboardButton("❌ خصم نقاط", callback_data="admin_remove_points"),
        InlineKeyboardButton("⏳ تعديل وقت اختبار الذاكرة", callback_data="set_memory_time"),
        InlineKeyboardButton("🔗 تعيين قناة اشتراك", callback_data="set_channel")
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
@bot.message_handler(func=lambda m: m.text == button_names["referral"])
def invite_friends(message):
    user_id = message.chat.id
    
    # ✅ التحقق إذا كان رابط الدعوة موقوفًا
    if not INVITE_ENABLED:
        bot.send_message(user_id, "⚠️ عذرًا، ميزة مشاركة رابط الدعوة متوقفة حاليًا.")
        return
    
    invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    bot.send_message(user_id, f"🎟 شارك رابط الدعوة الخاص بك:\n\n{invite_link}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == button_names["sh_charge"])
def recharge_balance(message):
    user_id = message.chat.id
    bot.send_message(user_id, f"⚠️ للتواصل مع الدعم لشحن رصيدك:\n{SUPPORT_LINK}")

# ===================== قسم الألعاب =====================
@bot.message_handler(func=lambda m: m.text == "🎮 الألعاب")
def show_games(message):
    bot.send_message(message.chat.id, "🎮 اختر لعبة:", reply_markup=get_games_menu())

@bot.message_handler(func=lambda m: m.text == "🏆 تخمين مكان الكرة")
def play_guess_ball(message):
    user_id = message.chat.id

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
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < GAME_SETTINGS["guess"]["entry"]:
        bot.send_message(user_id, f"⚠️ لا تملك نقاط كافية للعب. تكلفة اللعبة: {GAME_SETTINGS['guess']['entry']} نقطة. يرجى شحن رصيدك عبر الوكيل.", reply_markup=get_user_menu())
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

# قائمة المعرفات الخاصة بالمشرفين (يمكنك تعديلها وإضافة أكثر من ID)
ADMIN_IDS = [7347225275]  # استبدل 123456789 بـ ID الأدمن الفعلي

@bot.message_handler(func=lambda message: message.text == button_names["balance"])
def show_balance(message):
    user_id = message.from_user.id

    # استعلام لجلب رصيد المستخدم
    cursor.execute("SELECT points FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # تجهيز رسالة الرصيد
    user_balance_text = f"💰 رصيدك الحالي: {user[0]} نقطة." if user else "💸 ليس لديك نقاط حالياً."

    # التحقق مما إذا كان المستخدم أدمن أم لا
    if user_id not in ADMIN_IDS:
        # استعلام لجلب رصيد الأدمن
        cursor.execute("SELECT SUM(points) FROM users WHERE id IN ({})".format(
            ",".join("?" * len(ADMIN_IDS))
        ), ADMIN_IDS)
        admin_balance = cursor.fetchone()[0] or 0  # في حالة عدم وجود نقاط
        admin_text = f"\n👑 رصيد الأدمن: {admin_balance} نقطة."
    else:
        admin_text = ""  # لا نضيف رصيد الأدمن لنفسه

    # إرسال الرسالة مرة واحدة فقط
    bot.send_message(message.chat.id, user_balance_text + admin_text)
        
@bot.message_handler(func=lambda m: m.text == button_names["trivia"])
def play_trivia(message):
    user_id = message.chat.id
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
                              text=f"⏰ انتهى الوقت! الجواب الصحيح: {question_data['a']}")
        remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
    threading.Thread(target=countdown).start()
    def check_answer(msg):
        if msg.text.strip().lower() == question_data["a"].lower():
            add_points(user_id, GAME_SETTINGS["trivia"]["win"])
            bot.send_message(user_id, f"✅ إجابة صحيحة! ربحت {GAME_SETTINGS['trivia']['win']} نقطة.")
        else:
            remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
            bot.send_message(user_id, f"❌ إجابة خاطئة! تم خصم {GAME_SETTINGS['trivia']['loss']} نقطة.")
    bot.register_next_step_handler(message, check_answer)

@bot.message_handler(func=lambda m: m.text == button_names["trivia"])
def play_trivia(message):
    user_id = message.chat.id
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
                              text=f"⏰ انتهى الوقت! الجواب الصحيح: {question_data['a']}")
        remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
    threading.Thread(target=countdown).start()
    def check_answer(msg):
        if msg.text.strip().lower() == question_data["a"].lower():
            add_points(user_id, GAME_SETTINGS["trivia"]["win"])
            bot.send_message(user_id, f"✅ إجابة صحيحة! ربحت {GAME_SETTINGS['trivia']['win']} نقطة.")
        else:
            remove_points(user_id, GAME_SETTINGS["trivia"]["loss"])
            bot.send_message(user_id, f"❌ إجابة خاطئة! الجواب الصحيح: {question_data['a']}. تم خصم {GAME_SETTINGS['trivia']['loss']} نقطة.")
    bot.register_next_step_handler(message, check_answer)

# --- لعبة عجلة الحظ ---
@bot.message_handler(func=lambda m: m.text == button_names["wheel"])
def play_wheel_game(message):
    user_id = message.chat.id

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

    # إرسال الرقم إلى المستخدم مع عداد تنازلي
    time_limit = GAME_SETTINGS["memory"]["time"]
    msg = bot.send_message(user_id, f"🔢 تذكر هذا الرقم: **{memory_number}**\n⏳ لديك {time_limit} ثوانٍ لحفظه!", parse_mode="Markdown")

    # دالة للعد التنازلي وحذف الرقم
    def countdown():
        for i in range(time_limit, 0, -1):
            try:
                bot.edit_message_text(chat_id=user_id, message_id=msg.message_id, 
                                      text=f"🔢 تذكر هذا الرقم \n{memory_number}\n⏳ {i} ثانية متبقية!", 
                                      parse_mode="Markdown")
                time.sleep(1)
            except:
                break
        
        # حذف الرقم بعد انتهاء الوقت
        try:
            bot.edit_message_text(chat_id=user_id, message_id=msg.message_id, text="❓ الآن، ما هو الرقم الذي تذكرته؟")
        except:
            pass

    threading.Thread(target=countdown).start()

    # انتظار المستخدم لإدخال الرقم
    bot.register_next_step_handler(message, lambda m: check_memory_game(m, memory_number))

def check_memory_game(message, correct_number):
    user_id = message.chat.id
    user_answer = message.text.strip()

    if user_answer == correct_number:
        add_points(user_id, GAME_SETTINGS["memory"]["win"])
        bot.send_message(user_id, f"✅ إجابة صحيحة! ربحت {GAME_SETTINGS['memory']['win']} نقطة.")
    else:
        remove_points(user_id, GAME_SETTINGS["memory"]["loss"])
        bot.send_message(user_id, f"❌ إجابة خاطئة! الرقم الصحيح كان: **{correct_number}**\nتم خصم {GAME_SETTINGS['memory']['loss']} نقطة.", parse_mode="Markdown")

# ===================== أوامر الإدارة =====================
@bot.message_handler(commands=['admin'])
def admin_panel_handler(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "⚙ *لوحة الإدارة:*", reply_markup=get_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ ليس لديك صلاحيات لاستخدام هذه الأوامر.")

@bot.callback_query_handler(func=lambda call: call.data in [
    "broadcast", "admin_add_points", "admin_remove_points", "set_channel",
    "edit_welcome", "toggle_notifications", "toggle_bot", "edit_game_settings",
    "edit_game_prices", "edit_game_points", "set_trivia_time", "toggle_invite"
])
def handle_admin_buttons(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحيات!")
        return

    if call.data == "broadcast":
        bot.send_message(ADMIN_ID, "✉️ أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        bot.register_next_step_handler(call.message, admin_broadcast)

    elif call.data == "admin_add_points":
        bot.send_message(ADMIN_ID, "💰 أدخل معرف المستخدم وعدد النقاط للإضافة (مثال: 123456 50):")
        bot.register_next_step_handler(call.message, admin_add_points_handler)

    elif call.data == "admin_remove_points":
        bot.send_message(ADMIN_ID, "❌ أدخل معرف المستخدم وعدد النقاط للخصم (مثال: 123456 30):")
        bot.register_next_step_handler(call.message, admin_remove_points_handler)

    elif call.data == "set_channel":
        bot.send_message(ADMIN_ID, "🔗 أدخل معرف القناة للاشتراك الإجباري:")
        bot.register_next_step_handler(call.message, admin_set_channel)

    elif call.data == "edit_welcome":
        bot.send_message(ADMIN_ID, "⚙ أدخل رسالة الترحيب الجديدة:")
        bot.register_next_step_handler(call.message, admin_set_welcome)

    elif call.data == "toggle_notifications":
        global NOTIFICATIONS_ENABLED
        NOTIFICATIONS_ENABLED = not NOTIFICATIONS_ENABLED
        bot.answer_callback_query(call.id, f"🔄 إشعارات الدخول {'مفعل' if NOTIFICATIONS_ENABLED else 'موقوف'}.")

    elif call.data == "toggle_bot":
        global BOT_ACTIVE
        BOT_ACTIVE = not BOT_ACTIVE
        status = "✅ يعمل الآن" if BOT_ACTIVE else "⏸ متوقف مؤقتًا"
        bot.answer_callback_query(call.id, f"🚫 حالة البوت: {status}")
        if not BOT_ACTIVE:
            bot.send_message(ADMIN_ID, "⚠️ البوت متوقف مؤقتًا.")

    elif call.data == "edit_game_settings":
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
    for user in users:
        try:
            bot.send_message(user[0], f"📢 رسالة إدارية:\n{message.text}")
        except Exception:
            continue
    bot.send_message(ADMIN_ID, "✅ تمت الإذاعة لجميع المستخدمين.")

def admin_add_points_handler(message):
    try:
        user_id, pts = map(int, message.text.split())
        add_points(user_id, pts)
        bot.send_message(ADMIN_ID, f"✅ تمت إضافة {pts} نقطة للمستخدم {user_id}.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: user_id points")

def admin_remove_points_handler(message):
    try:
        user_id, pts = map(int, message.text.split())
        remove_points(user_id, pts)
        bot.send_message(ADMIN_ID, f"✅ تمت خصم {pts} نقطة من المستخدم {user_id}.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: user_id points")

def admin_edit_game(message):
    try:
        _, game_name, entry, win, loss = message.text.split()
        if game_name in GAME_SETTINGS:
            GAME_SETTINGS[game_name]["entry"] = int(entry)
            GAME_SETTINGS[game_name]["win"] = int(win)
            GAME_SETTINGS[game_name]["loss"] = int(loss)
            bot.send_message(ADMIN_ID, f"✅ تم تعديل إعدادات {game_name}:\nدخول: {entry}, ربح: {win}, خسارة: {loss}")
        else:
            bot.send_message(ADMIN_ID, "❌ اسم اللعبة غير موجود.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ صيغة غير صحيحة. استخدم: /edit_game game_name entry win loss")

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

def admin_set_channel(message):
    global REQUIRED_CHANNEL
    REQUIRED_CHANNEL = message.text
    bot.send_message(ADMIN_ID, f"✅ تم تعيين قناة الاشتراك الإجباري: {REQUIRED_CHANNEL}")

def set_invite_points_handler(message):
    global INVITE_POINTS
    try:
        pts = int(message.text)
        INVITE_POINTS = pts
        bot.send_message(ADMIN_ID, f"✅ تم تعيين نقاط الدعوة إلى {INVITE_POINTS} نقطة.")
    except ValueError:
        bot.send_message(ADMIN_ID, "⚠️ يرجى إدخال رقم صحيح.")

# ===================== تشغيل البوت =====================
while True:
    try:
        print("🤖 البوت يعمل...")
        bot.infinity_polling(timeout=30, long_polling_timeout=10)
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بـ Telegram API: {e}")
        time.sleep(5)  # انتظار 5 ثواني قبل إعادة المحاولة
