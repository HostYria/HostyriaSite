import logging
import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Admin ID - Replace with actual Admin Telegram ID or set via Env
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ACCOUNTS_FILE = "accounts.json"

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump([], f)
        return []
    try:
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = load_accounts()
    
    has_account = any(acc.get('owner_id') == user_id for acc in accounts)

    welcome_message = (
        "أهلاً بك في خدمة إستضافة\n"
        "Hostyria Host\n\n"
        f"معرفك الخاص بك:\n`{user_id}`"
    )
    
    account_button_text = "معلومات حسابي" if has_account else "إنشاء حساب"
    
    keyboard = [
        [
            InlineKeyboardButton("Hostyria Host", web_app={"url": "https://hostyriasite.onrender.com"})
        ],
        [
            InlineKeyboardButton(account_button_text, callback_data='create_account')
        ],
        [
            InlineKeyboardButton("تواصل مع الدعم", url="http://t.me/HostyriaSupport_Bot")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    accounts = load_accounts()
    
    if len(context.args) == 3:
        try:
            target_user_id = int(context.args[0])
            username = context.args[1]
            password = context.args[2]
            
            new_acc = {
                "username": username,
                "password": password,
                "used": True,
                "owner_id": target_user_id
            }
            accounts.append(new_acc)
            save_accounts(accounts)
            await update.message.reply_text(f"تم تخصيص الحساب للمستخدم {target_user_id} بنجاح.")
            
            # Send notification to user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="تم إنشاء حسابك من قبل الأدمن ✅"
                )
            except Exception as e:
                logging.error(f"Could not send notification to user {target_user_id}: {e}")
            return
        except ValueError:
            pass

    if len(context.args) < 2:
        await update.message.reply_text("الاستخدام:\nلإضافة حساب عام: /add_account username password\nلتخصيص حساب لمستخدم: /add_account user_id username password")
        return

    username = context.args[0]
    password = context.args[1]

    accounts = load_accounts()
    if any(acc.get('username') == username for acc in accounts):
        await update.message.reply_text(f"خطأ: الحساب {username} موجود بالفعل في المستودع.")
        return

    new_acc = {
        "username": username,
        "password": password,
        "used": False,
        "owner_id": None
    }
    accounts.append(new_acc)
    save_accounts(accounts)

    await update.message.reply_text(f"تم إضافة الحساب بنجاح: {username}")

async def delete_user_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("الاستخدام: /del_user_acc [user_id]")
        return
    try:
        target_id = int(context.args[0])
        accounts = load_accounts()
        new_accounts = [acc for acc in accounts if acc.get('owner_id') != target_id]
        save_accounts(new_accounts)
        await update.message.reply_text(f"تم حذف حساب المستخدم {target_id} بنجاح.")
        
        # Send notification to user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="تم تعطيل حسابك ⚠️"
            )
        except Exception as e:
            logging.error(f"Could not send notification to user {target_id}: {e}")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {str(e)}")

async def delete_account_from_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("الاستخدام: /del_repo_acc [username]")
        return
    username = context.args[0]
    accounts = load_accounts()
    new_accounts = [acc for acc in accounts if not (acc.get('username') == username and acc.get('owner_id') is None)]
    save_accounts(new_accounts)
    await update.message.reply_text(f"تم حذف الحساب {username} من المستودع.")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    accounts = load_accounts()
    
    if not accounts:
        await update.message.reply_text("لا توجد حسابات حالياً.")
        return

    msg = "📂 **قائمة الحسابات المنظمة:**\n\n"
    for acc in accounts:
        username = acc.get('username')
        password = acc.get('password')
        used = acc.get('used', False)
        owner_id = acc.get('owner_id')
        
        status_icon = "👤" if used else "🔓"
        status_text = "مستخدم" if used else "متاح"
        owner_info = f"\n   └─ المالك: `{owner_id}`" if owner_id else ""
        
        msg += (
            f"{status_icon} **الحساب:** `{username}`\n"
            f"   ├─ الكلمة: `{password}`\n"
            f"   ├─ الحالة: {status_text}{owner_info}\n"
            "   " + "─" * 15 + "\n"
        )
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    help_text = (
        "📜 **قائمة الأوامر الإدارية المتاحة:**\n\n"
        "1️⃣ **إضافة حسابات:**\n"
        "• `/add_account user pass` -> إضافة حساب عام للمستودع.\n"
        "• `/add_account id user pass` -> تخصيص حساب لمستخدم معين.\n\n"
        "2️⃣ **حذف الحسابات:**\n"
        "• `/del_user_acc id` -> حذف الحساب المرتبط بمستخدم معين.\n"
        "• `/del_repo_acc user` -> حذف حساب متاح من المستودع.\n\n"
        "3️⃣ **عرض البيانات:**\n"
        "• `/list_accounts` -> عرض جميع الحسابات وحالاتها.\n\n"
        "4️⃣ **المساعدة:**\n"
        "• `/ss10` -> عرض هذه القائمة."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == 'create_account':
        accounts = load_accounts()
        
        # Check if user already has an account
        existing_account = next((acc for acc in accounts if acc.get('owner_id') == user_id), None)
        
        if existing_account:
            username = existing_account.get('username')
            password = existing_account.get('password')
            message = (
                "معلومات حسابك:\n\n"
                f"أسم المستخدم: `{username}`\n"
                f"كلمة المرور: `{password}`"
            )
        else:
            # Find an available account
            account_idx = next((i for i, acc in enumerate(accounts) if not acc.get('used') and acc.get('owner_id') is None), None)

            if account_idx is not None:
                accounts[account_idx]['used'] = True
                accounts[account_idx]['owner_id'] = user_id
                username = accounts[account_idx].get('username')
                password = accounts[account_idx].get('password')
                save_accounts(accounts)
                
                user = update.effective_user
                user_info = f"الاسم: {user.full_name}\nID: `{user.id}`"
                if user.username:
                    user_info += f"\nاليوزر: @{user.username}"

                # Message for the user (only account details)
                message = (
                    "تم إنشاء الحساب بنجاح! ✅\n\n"
                    "**تفاصيل الحساب المستلم:**\n"
                    f"أسم المستخدم: `{username}`\n"
                    f"كلمة المرور: `{password}`"
                )

                # Notification for the admin (user + account details)
                admin_notification = (
                    "🔔 **إشعار إنشاء حساب جديد:**\n\n"
                    "**تفاصيل المستخدم:**\n"
                    f"{user_info}\n\n"
                    "**تفاصيل الحساب المستلم:**\n"
                    f"أسم المستخدم: `{username}`\n"
                    f"كلمة المرور: `{password}`"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=admin_notification,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logging.error(f"Could not send notification to admin: {e}")
                
                keyboard = [
                    [InlineKeyboardButton("Hostyria Host", web_app={"url": "https://hostyriasite.onrender.com"})],
                    [InlineKeyboardButton("معلومات حسابي", callback_data='create_account')],
                    [InlineKeyboardButton("تواصل مع الدعم", url="http://t.me/HostyriaSupport_Bot")]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                message = "إنشاء الحسابات الجديدة متوقفة حالياً...تواصل مع الدعم للمزيد من المعلومات."

        await query.edit_message_text(text=message, parse_mode='Markdown')

if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("Error: TELEGRAM_TOKEN environment variable is not set.")
    else:
        application = ApplicationBuilder().token(token).build()
        
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('add_account', add_account))
        application.add_handler(CommandHandler('del_user_acc', delete_user_account))
        application.add_handler(CommandHandler('del_repo_acc', delete_account_from_repo))
        application.add_handler(CommandHandler('list_accounts', list_accounts))
        application.add_handler(CommandHandler('ss10', admin_help))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        print("Bot is starting...")
        application.run_polling()
