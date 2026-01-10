import os
import random
import json
import requests
import phonenumbers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# الإعدادات
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
IPQS_API_KEY = os.environ.get("IPQS_API_KEY", "")
ALLOWED_USER_ID = 8319511583
DATA_FILE = "guessed_numbers.json"
EXCLUDED_FILE = "excluded_numbers.json"
SUSPICIOUS_FILE = "suspicious.json"
SUSPICIOUS_2_FILE = "suspicious_2.json"
SETTINGS_FILE = "settings.json"
TOTAL_POSSIBILITIES = 100000 # 00000 to 99999

def is_number_active(phone_number):
    if not IPQS_API_KEY or not settings.get("ipqs_filter", True):
        return True # Fallback if no API key or disabled
    
    try:
        # IPQS expects numbers in international format or with country code
        formatted_num = phone_number
        if phone_number.startswith('09'):
            formatted_num = "963" + phone_number[1:]
        elif phone_number.startswith('+'):
            formatted_num = phone_number.replace('+', '')
        
        url = f"https://www.ipqualityscore.com/api/json/phone/{IPQS_API_KEY}/{formatted_num}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Check if the number is active
        return data.get('active', True)
    except Exception as e:
        print(f"Error checking number activity: {e}")
        return True # Fallback to true on error to not block numbers

def format_syrian_number(number_str):
    try:
        # إرجاع الرقم كما هو بدون أي فراغات أو تنسيق إضافي
        return number_str.replace(" ", "").replace("-", "")
    except:
        return number_str

def load_set(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except:
            return set()
    return set()

def load_dict(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def save_data(file_path, data):
    with open(file_path, "w") as f:
        if isinstance(data, set):
            json.dump(list(data), f)
        else:
            json.dump(data, f)

# تحميل البيانات عند التشغيل
guessed_numbers = load_set(DATA_FILE)
excluded_numbers = load_set(EXCLUDED_FILE)
suspicious_list = load_set(SUSPICIOUS_FILE)
suspicious_2_list = load_set(SUSPICIOUS_2_FILE)
settings = load_dict(SETTINGS_FILE)

# الإعدادات الافتراضية
if "google_filter" not in settings: settings["google_filter"] = False
if "ipqs_filter" not in settings: settings["ipqs_filter"] = True
if "priority_digit" not in settings: settings["priority_digit"] = None
if "susp_markdown" not in settings: settings["susp_markdown"] = True
if "susp_page_size" not in settings: settings["susp_page_size"] = 15

def generate_number_only(priority=None):
    attempts = 0
    max_attempts = 5000
    while attempts < max_attempts:
        if priority is not None:
            suffix = "".join([str(random.randint(0, 9)) for _ in range(4)])
            middle = f"{priority}{suffix}"
        else:
            middle = "".join([str(random.randint(0, 9)) for _ in range(5)])
        if middle not in guessed_numbers:
            return middle
        attempts += 1
    return None

def mark_as_guessed(middle):
    global guessed_numbers
    if middle not in guessed_numbers:
        guessed_numbers.add(middle)
        save_data(DATA_FILE, guessed_numbers)

def mark_as_excluded(middle):
    global excluded_numbers
    if middle not in excluded_numbers:
        excluded_numbers.add(middle)
        save_data(EXCLUDED_FILE, excluded_numbers)

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID: return
    remaining = TOTAL_POSSIBILITIES - len(guessed_numbers) - len(excluded_numbers)
    keyboard = [
        [InlineKeyboardButton("تخمين عادي (09XXX)", callback_data="guess_normal")],
        [InlineKeyboardButton("تخمين دولي (9639XXX)", callback_data="guess_intl")],
        [InlineKeyboardButton("ارقام مشتبهة", callback_data="view_susp_1_0"), InlineKeyboardButton("مشتبه به 2", callback_data="view_susp_2_0")],
        [InlineKeyboardButton("أرقام مستبعدة", callback_data="view_excluded_0")],
        [InlineKeyboardButton("إعدادات التخمين المفلتر", callback_data="filter_settings")],
        [InlineKeyboardButton("إعدادات المشتبه", callback_data="susp_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(f"أهلاً بك\nالاحتمالات المتبقية: {remaining}", reply_markup=reply_markup)

def get_filter_settings_markup():
    g_status = "مفعلة" if settings.get("google_filter", False) else "غير مفعلة"
    i_status = "مفعل" if settings.get("ipqs_filter", True) else "معطل"
    priority = settings.get("priority_digit") if settings.get("priority_digit") is not None else "تلقائي"
    
    text = (f"إعدادات التخمين المفلتر:\n\n"
            f"حالة مكتبة غوغل: {g_status}\n"
            f"حالة فحص IPQS: {i_status}\n"
            f"الأولوية الحالية: {priority}\n\n"
            f"سيتم تطبيق هذه الإعدادات تلقائياً عند الضغط على أزرار التخمين في القائمة الرئيسية.")
            
    toggle_g = "تعطيل فلترة google" if settings.get("google_filter", False) else "تفعيل فلترة google"
    toggle_i = "تعطيل فحص IPQS" if settings.get("ipqs_filter", True) else "تفعيل فحص IPQS"
    
    keyboard = [
        [InlineKeyboardButton(toggle_g, callback_data="toggle_google")],
        [InlineKeyboardButton(toggle_i, callback_data="toggle_ipqs")],
        [InlineKeyboardButton("تحديد الأولوية (09X...)", callback_data="set_priority_menu")],
        [InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_susp_settings_markup():
    mk_status = "مفعل" if settings.get("susp_markdown", True) else "غير مفعل"
    page_size = settings.get("susp_page_size", 15)
    text = f"إعدادات المشتبه:\n\nماركداون: {mk_status}\nعدد الأرقام في كل رسالة: {page_size}"
    keyboard = [
        [InlineKeyboardButton("تفعيل/تعطيل ماركداون", callback_data="toggle_susp_markdown")],
        [InlineKeyboardButton("تغيير عدد الأرقام", callback_data="change_page_size_menu")],
        [InlineKeyboardButton("إضافة رقم يدوي", callback_data="manual_add_prompt")],
        [InlineKeyboardButton("حذف رقم يدوي", callback_data="manual_del_prompt")],
        [InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != ALLOWED_USER_ID: return
    data = query.data
    
    if data == "back_to_main":
        remaining = TOTAL_POSSIBILITIES - len(guessed_numbers) - len(excluded_numbers)
        keyboard = [
            [InlineKeyboardButton("تخمين عادي (09XXX)", callback_data="guess_normal")],
            [InlineKeyboardButton("تخمين دولي (9639XXX)", callback_data="guess_intl")],
            [InlineKeyboardButton("ارقام مشتبهة", callback_data="view_susp_1_0"), InlineKeyboardButton("مشتبه به 2", callback_data="view_susp_2_0")],
            [InlineKeyboardButton("أرقام مستبعدة", callback_data="view_excluded_0")],
            [InlineKeyboardButton("إعدادات التخمين المفلتر", callback_data="filter_settings")],
            [InlineKeyboardButton("إعدادات المشتبه", callback_data="susp_settings")]
        ]
        query.edit_message_text(f"أهلاً بك\nالاحتمالات المتبقية: {remaining}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "susp_settings":
        text, markup = get_susp_settings_markup()
        query.edit_message_text(text, reply_markup=markup)
        return

    if data == "toggle_susp_markdown":
        settings["susp_markdown"] = not settings.get("susp_markdown", True)
        save_data(SETTINGS_FILE, settings)
        text, markup = get_susp_settings_markup()
        query.edit_message_text(text, reply_markup=markup); query.answer("تم التغيير")
        return

    if data == "change_page_size_menu":
        text = "اختر عدد الأرقام لكل صفحة:"
        row = [InlineKeyboardButton(str(x), callback_data=f"set_psize_{x}") for x in [3, 5, 10, 25, 35]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([row, [InlineKeyboardButton("إلغاء", callback_data="susp_settings")]]))
        return

    if data.startswith("set_psize_"):
        settings["susp_page_size"] = int(data.split("_")[2])
        save_data(SETTINGS_FILE, settings)
        text, markup = get_susp_settings_markup()
        query.edit_message_text(text, reply_markup=markup); query.answer("تم التحديث")
        return

    if data == "manual_add_prompt":
        query.message.reply_text("أرسل الرقم الذي تريد إضافته:\nمثال: `09XXXXXXXX`", parse_mode='Markdown')
        context.user_data["awaiting_manual"] = "add"
        query.answer()
        return

    if data == "manual_del_prompt":
        query.message.reply_text("أرسل الرقم الذي تريد حذفه من كافة القوائم:")
        context.user_data["awaiting_manual"] = "del"
        query.answer()
        return

    if data == "filter_settings":
        text, markup = get_filter_settings_markup()
        query.edit_message_text(text, reply_markup=markup); return

    if data == "toggle_google":
        settings["google_filter"] = not settings.get("google_filter", False)
        save_data(SETTINGS_FILE, settings); text, markup = get_filter_settings_markup()
        query.edit_message_text(text, reply_markup=markup); query.answer("تم التغيير"); return

    if data == "toggle_ipqs":
        settings["ipqs_filter"] = not settings.get("ipqs_filter", True)
        save_data(SETTINGS_FILE, settings); text, markup = get_filter_settings_markup()
        query.edit_message_text(text, reply_markup=markup); query.answer("تم التغيير"); return

    if data == "set_priority_menu":
        text, markup = get_priority_menu_markup()
        query.edit_message_text(text, reply_markup=markup); return

    if data.startswith("set_prio_"):
        val = data.split("_")[2]
        settings["priority_digit"] = int(val) if val != "none" else None
        save_data(SETTINGS_FILE, settings); text, markup = get_filter_settings_markup()
        query.edit_message_text(text, reply_markup=markup); query.answer("تم تحديد الأولوية"); return

    if data.startswith("view_susp_"):
        parts = data.split("_")
        text, markup = get_suspicious_markup(int(parts[2]), int(parts[3]))
        query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown' if settings.get("susp_markdown", True) else None)
        return

    if data.startswith("clear_susp_"):
        list_type = int(data.split("_")[2])
        if list_type == 1: suspicious_list.clear(); save_data(SUSPICIOUS_FILE, suspicious_list)
        else: suspicious_2_list.clear(); save_data(SUSPICIOUS_2_FILE, suspicious_2_list)
        query.answer("تم حذف القائمة")
        text, markup = get_suspicious_markup(list_type, 0)
        query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown' if settings.get("susp_markdown", True) else None)
        return

    if data.startswith("view_excluded_"):
        page = int(data.split("_")[2])
        text, markup = get_excluded_markup(page)
        query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown' if settings.get("susp_markdown", True) else None)
        return

    if data == "clear_excluded":
        excluded_numbers.clear()
        save_data(EXCLUDED_FILE, excluded_numbers)
        query.answer("تم حذف قائمة المستبعدات")
        text, markup = get_excluded_markup(0)
        query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown' if settings.get("susp_markdown", True) else None)
        return

    if data.startswith("save_"):
        parts = data.split("_")
        stype, full_number, middle = parts[1], parts[2], parts[3]
        if stype == "1": suspicious_list.add(full_number); save_data(SUSPICIOUS_FILE, suspicious_list)
        else: suspicious_2_list.add(full_number); save_data(SUSPICIOUS_2_FILE, suspicious_2_list)
        query.answer("تم الحفظ"); mark_as_guessed(middle); return

    if data.startswith("next_guess_"):
        parts = data.split("_")
        itype, is_filtered, old_middle = parts[2], parts[3] == "True", parts[4]
        mark_as_guessed(old_middle)
        send_guess(query, itype == "intl", is_filtered=is_filtered, edit=True)
        query.answer(); return

    if data in ["guess_normal", "guess_intl"]:
        # Always use filtered settings if defined
        send_guess(query, data == "guess_intl", is_filtered=True)
        query.answer()

def message_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID: return
    action = context.user_data.get("awaiting_manual")
    if not action: return
    number = update.message.text.strip()
    if action == "add":
        kb = [[InlineKeyboardButton("قائمة 1", callback_data=f"manual_save_1_{number}"),
               InlineKeyboardButton("قائمة 2", callback_data=f"manual_save_2_{number}")]]
        update.message.reply_text(f"أين تريد إضافة الرقم `{number}`؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif action == "del":
        suspicious_list.discard(number); save_data(SUSPICIOUS_FILE, suspicious_list)
        suspicious_2_list.discard(number); save_data(SUSPICIOUS_2_FILE, suspicious_2_list)
        update.message.reply_text(f"تم حذف الرقم `{number}` من كافة القوائم إن وجد.", parse_mode='Markdown')
    context.user_data["awaiting_manual"] = None

def manual_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query.data.startswith("manual_save_"): return
    parts = query.data.split("_")
    list_type, number = int(parts[2]), parts[3]
    if list_type == 1: suspicious_list.add(number); save_data(SUSPICIOUS_FILE, suspicious_list)
    else: suspicious_2_list.add(number); save_data(SUSPICIOUS_2_FILE, suspicious_2_list)
    query.edit_message_text(f"تمت إضافة `{number}` إلى القائمة {list_type}", parse_mode='Markdown')

def get_excluded_markup(page):
    data = list(excluded_numbers)
    total = len(data)
    page_size = settings.get("susp_page_size", 15)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    current_items = data[start_idx:end_idx]
    text = f"قائمة الأرقام المستبعدة:\n\n"
    if not current_items: text += "لا يوجد أرقام حالياً."
    else:
        for i, num in enumerate(current_items):
            display_num = f"09{num}630"
            text += f"{start_idx + i + 1}. `{display_num}`\n"
    keyboard = []
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("السابق", callback_data=f"view_excluded_{page-1}"))
    if end_idx < total: nav_row.append(InlineKeyboardButton("التالي", callback_data=f"view_excluded_{page+1}"))
    if nav_row: keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("حذف القائمة الحالية", callback_data="clear_excluded")])
    keyboard.append([InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="back_to_main")])
    return text, InlineKeyboardMarkup(keyboard)

def get_suspicious_markup(list_type, page):
    data = list(suspicious_list if list_type == 1 else suspicious_2_list)
    total = len(data)
    page_size = settings.get("susp_page_size", 15)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    current_items = data[start_idx:end_idx]
    text = f"قائمة الأرقام المشتبه بها ({'1' if list_type == 1 else '2'}):\n\n"
    if not current_items: text += "لا يوجد أرقام حالياً."
    else:
        for i, num in enumerate(current_items):
            text += f"{start_idx + i + 1}. `{num}`\n"
    keyboard = []
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("السابق", callback_data=f"view_susp_{list_type}_{page-1}"))
    if end_idx < total: nav_row.append(InlineKeyboardButton("التالي", callback_data=f"view_susp_{list_type}_{page+1}"))
    if nav_row: keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("حذف القائمة الحالية", callback_data=f"clear_susp_{list_type}")])
    keyboard.append([InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="back_to_main")])
    return text, InlineKeyboardMarkup(keyboard)

def send_guess(query, is_intl, is_filtered=False, edit=False):
    priority = settings.get("priority_digit") if is_filtered else None
    
    # Try to find an active number
    middle = None
    attempts = 0
    max_search_attempts = 5 # Limit API calls to save credits
    
    while attempts < max_search_attempts:
        candidate_middle = generate_number_only(priority=priority)
        if not candidate_middle:
            break
            
        if candidate_middle in excluded_numbers:
            attempts += 1
            continue

        raw_number = f"9639{candidate_middle}630" if is_intl else f"09{candidate_middle}630"
        
        # Check if number is active
        if is_number_active(raw_number):
            middle = candidate_middle
            break
        else:
            # Mark as excluded instead of guessed if IPQS says inactive
            mark_as_excluded(candidate_middle)
        attempts += 1

    if not middle:
        text = "انتهت الاحتمالات أو لم يتم العثور على رقم نشط حالياً!"
        if edit: query.edit_message_text(text)
        else: query.message.reply_text(text)
        return
    
    number = format_syrian_number(f"9639{middle}630" if is_intl else f"09{middle}630")
    type_str = "intl" if is_intl else "normal"
    kb = [[InlineKeyboardButton("مشتبه به", callback_data=f"save_1_{number}_{middle}"),
           InlineKeyboardButton("مشتبه به 2", callback_data=f"save_2_{number}_{middle}")],
          [InlineKeyboardButton("التالي", callback_data=f"next_guess_{type_str}_{is_filtered}_{middle}")]]
    text = f"الرقم المخمن:\n\n`{number}`"
    if edit: query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    else: query.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

def get_priority_menu_markup():
    text = "اختر رقم الأولوية (09X...):"
    keyboard = []
    row = []
    for i in range(10):
        row.append(InlineKeyboardButton(str(i), callback_data=f"set_prio_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("تلقائي (بدون أولوية)", callback_data="set_prio_none")])
    keyboard.append([InlineKeyboardButton("إلغاء", callback_data="filter_settings")])
    return text, InlineKeyboardMarkup(keyboard)

if __name__ == "__main__":
    if not BOT_TOKEN: print("Error: TELEGRAM_BOT_TOKEN not set.")
    else:
        updater = Updater(BOT_TOKEN)
        updater.dispatcher.add_handler(CommandHandler("start", start))
        from telegram.ext import MessageHandler, Filters
        updater.dispatcher.add_handler(CallbackQueryHandler(manual_callback_handler, pattern="^manual_save_"))
        updater.dispatcher.add_handler(CallbackQueryHandler(button_handler))
        updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
        updater.start_polling(); updater.idle()
