import os  # لقراءة المتغيرات البيئية مثل التوكن والأدمن ID
import sqlite3  # لإدارة قاعدة البيانات SQLite
import random  # لاختيار عبارة تحفيزية عشوائية
import asyncio  # لتشغيل الـ async
from datetime import datetime  # للتعامل مع التواريخ في قاعدة البيانات
from aiogram import Bot, Dispatcher, types  # مكتبة aiogram الأساسية للبوت
from aiogram.filters import Command  # لتصفية الأوامر مثل /start
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,  # لوحة المفاتيح العادية
    InlineKeyboardMarkup, InlineKeyboardButton  # لوحة المفاتيح الداخلية
)
from aiogram.fsm.context import FSMContext  # لإدارة حالات FSM
from aiogram.fsm.state import State, StatesGroup  # لتعريف الحالات
from aiogram.fsm.storage.memory import MemoryStorage  # تخزين الحالات في الذاكرة (يمكن تغييرها لـ Redis للإنتاج)
from aiohttp import web  # إضافة للـ HTTP server في Web Service

# إعداد البوت
TOKEN = os.getenv('BOT_TOKEN')  # قراءة التوكن من المتغيرات البيئية
ADMIN_ID = int(os.getenv('CHAT_ADMIN_ID'))  # ID الدردشة للأدمن

bot = Bot(token=TOKEN)  # إنشاء كائن البوت
storage = MemoryStorage()  # تخزين الحالات في الذاكرة (غير دائم، مناسب للتطوير)
dp = Dispatcher(storage=storage)  # Dispatcher لإدارة الرسائل والكولباكات

# قاعدة بيانات SQLite
DB_PATH = '/app/bot_database.db'  # مسار ملف قاعدة البيانات للتخزين المستمر في Render

def init_db():
    """إنشاء قاعدة البيانات وجدول الطلبات إذا لم يكن موجوداً"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول الطلبات العام لتخزين طلبات الاعتذار والإجازة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- رقم الطلب التلقائي
            user_id INTEGER,  -- ID المستخدم في تلغرام
            user_name TEXT,  -- اسم المتطوع
            request_type TEXT,  -- 'excuse' أو 'leave'
            reason TEXT,  -- سبب الطلب
            details TEXT,  -- تفاصيل إضافية (للإجازة: المدة والتواريخ)
            status TEXT DEFAULT 'pending',  -- الحالة: pending, approved, rejected
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- تاريخ الإنشاء
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()  # استدعاء الدالة لتهيئة قاعدة البيانات عند بدء التشغيل

# حالات FSM للاعتذار (لجمع البيانات خطوة بخطوة)
class ExcuseStates(StatesGroup):
    waiting_name = State()  # انتظار اسم المتطوع
    waiting_reason = State()  # انتظار سبب الاعتذار
    waiting_confirm = State()  # انتظار التأكيد

# حالات FSM للإجازة (أكثر خطوات بسبب التفاصيل)
class LeaveStates(StatesGroup):
    waiting_name = State()  # انتظار اسم المتطوع
    waiting_reason = State()  # انتظار سبب الإجازة
    waiting_duration = State()  # انتظار مدة الإجازة
    waiting_start_date = State()  # انتظار تاريخ البدء
    waiting_end_date = State()  # انتظار تاريخ الانتهاء
    waiting_confirm = State()  # انتظار التأكيد

# حالات FSM لتتبع الطلبات
class TrackStates(StatesGroup):
    waiting_request_id = State()  # انتظار رقم الطلب أو 'جميع'

# لوحة المفاتيح الرئيسية (تظهر للمستخدم عند /start)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اعتذار"), KeyboardButton(text="إجازة")],  # أزرار الطلبات الرئيسية
        [KeyboardButton(text="تتبع طلباتي"), KeyboardButton(text="مراجع الفريق"), KeyboardButton(text="أهدني عبارة")]  # أزرار إضافية
    ],
    resize_keyboard=True  # تكييف حجم اللوحة مع الشاشة
)

# قائمة العبارات التحفيزية (يمكن إضافة المزيد هنا)
motivational_phrases = [
    "العمل الخيري هو بذرة الأمل في قلوب الناس، ازرعها وستحصد الابتسامات!",
    "في كل يد تمتد للمساعدة، ينبت أمل جديد. استمر في إشراقك مع فريق أبناء الأرض!",
    "الأمل يبدأ بخطوة صغيرة، وأنت جزء من هذه الخطوات العظيمة. شكراً لتطوعك!",
    "كل جهد يبذل في سبيل الخير يعود بالبركة. كن مصدر إلهام دائماً!",
    "مع فريق أبناء الأرض، نبني جسور الأمل. أنت بطل هذه القصة!"
]

# معالج الأمر /start - يرسل رسالة الترحيب ولوحة المفاتيح
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "مرحباً بك في بوت إدارة شؤون الموارد البشرية لفريق أبناء الأرض!\n"
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )

# معالج زر الاعتذار - يبدأ عملية جمع بيانات الاعتذار
@dp.message(lambda message: message.text == "اعتذار")
async def excuse_start(message: types.Message, state: FSMContext):
    await message.answer("ما اسمك الكامل كمتطوع؟")
    await state.set_state(ExcuseStates.waiting_name)

@dp.message(ExcuseStates.waiting_name)
async def excuse_name(message: types.Message, state: FSMContext):
    # حفظ الاسم في حالة FSM
    await state.update_data(name=message.text)
    await message.answer("ما سبب الاعتذار عن المبادرة/الاجتماع/النشاط؟")
    await state.set_state(ExcuseStates.waiting_reason)

@dp.message(ExcuseStates.waiting_reason)
async def excuse_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['reason'] = message.text  # حفظ السبب
    
    # إنشاء لوحة تأكيد داخلية
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تأكيد الطلب", callback_data="confirm_excuse")]
    ])
    
    await message.answer(
        f"تأكيد الطلب:\n"
        f"الاسم: {data['name']}\n"
        f"السبب: {data['reason']}\n\n"
        "هل تريد تأكيد الطلب؟",
        reply_markup=confirm_keyboard
    )
    await state.update_data(reason=data['reason'])
    await state.set_state(ExcuseStates.waiting_confirm)

# معالج الكولباك لتأكيد الاعتذار
@dp.callback_query(lambda c: c.data == "confirm_excuse", ExcuseStates.waiting_confirm)
async def confirm_excuse(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # حفظ الطلب في قاعدة البيانات
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO requests (user_id, user_name, request_type, reason) VALUES (?, ?, ?, ?)",
        (callback.from_user.id, data['name'], 'excuse', data['reason'])
    )
    request_id = cursor.lastrowid  # الحصول على رقم الطلب الجديد
    conn.commit()
    conn.close()
    
    # إخطار المستخدم بنجاح الإرسال
    await callback.message.edit_text("تم إرسال طلبك بنجاح! سيتم معالجته قريباً (قبول أو رفض).")
    await callback.answer()
    
    # إنشاء لوحة للأدمن للقبول/الرفض
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}")
        ]
    ])
    
    # إرسال الطلب إلى الأدمن
    await bot.send_message(
        ADMIN_ID,
        f"طلب اعتذار جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"سبب الاعتذار: {data['reason']}",
        reply_markup=admin_keyboard
    )
    
    await state.clear()  # مسح الحالة بعد الإكمال

# معالج زر الإجازة - يبدأ عملية جمع بيانات الإجازة
@dp.message(lambda message: message.text == "إجازة")
async def leave_start(message: types.Message, state: FSMContext):
    await message.answer("ما اسمك الكامل كمتطوع؟")
    await state.set_state(LeaveStates.waiting_name)

@dp.message(LeaveStates.waiting_name)
async def leave_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("ما سبب الإجازة؟")
    await state.set_state(LeaveStates.waiting_reason)

@dp.message(LeaveStates.waiting_reason)
async def leave_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("ما مدة الإجازة (بالأيام)؟")
    await state.set_state(LeaveStates.waiting_duration)

@dp.message(LeaveStates.waiting_duration)
async def leave_duration(message: types.Message, state: FSMContext):
    await state.update_data(duration=message.text)
    await message.answer("ما تاريخ بدء الإجازة (YYYY-MM-DD)؟")
    await state.set_state(LeaveStates.waiting_start_date)

@dp.message(LeaveStates.waiting_start_date)
async def leave_start_date(message: types.Message, state: FSMContext):
    await state.update_data(start_date=message.text)
    await message.answer("ما تاريخ انتهاء الإجازة (YYYY-MM-DD)؟")
    await state.set_state(LeaveStates.waiting_end_date)

@dp.message(LeaveStates.waiting_end_date)
async def leave_end_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['end_date'] = message.text
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    
    # إنشاء لوحة تأكيد
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تأكيد الطلب", callback_data="confirm_leave")]
    ])
    
    await message.answer(
        f"تأكيد الطلب:\n"
        f"الاسم: {data['name']}\n"
        f"السبب: {data['reason']}\n"
        f"التفاصيل: {details}\n\n"
        "هل تريد تأكيد الطلب؟",
        reply_markup=confirm_keyboard
    )
    await state.update_data(end_date=data['end_date'])
    await state.set_state(LeaveStates.waiting_confirm)

# معالج الكولباك لتأكيد الإجازة
@dp.callback_query(lambda c: c.data == "confirm_leave", LeaveStates.waiting_confirm)
async def confirm_leave(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    
    # حفظ الطلب في قاعدة البيانات مع التفاصيل
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO requests (user_id, user_name, request_type, reason, details) VALUES (?, ?, ?, ?, ?)",
        (callback.from_user.id, data['name'], 'leave', data['reason'], details)
    )
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إخطار المستخدم
    await callback.message.edit_text("تم إرسال طلبك بنجاح! سيتم معالجته قريباً (قبول أو رفض).")
    await callback.answer()
    
    # لوحة الأدمن
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}")
        ]
    ])
    
    # إرسال إلى الأدمن
    await bot.send_message(
        ADMIN_ID,
        f"طلب إجازة جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"سبب الإجازة: {data['reason']}\n"
        f"التفاصيل: {details}",
        reply_markup=admin_keyboard
    )
    
    await state.clear()

# معالج قرارات الأدمن - للقبول
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    # التحقق من أن المستخدم هو الأدمن فقط
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    
    parts = callback.data.split("_")  # تحليل البيانات: approve_[type]_[id]
    request_type = parts[1]
    request_id = int(parts[2])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'approved' WHERE id = ?", (request_id,))
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    user_id = cursor.fetchone()[0]  # الحصول على ID المستخدم
    conn.commit()
    conn.close()
    
    # إخطار المستخدم بالقبول
    await bot.send_message(user_id, f"تم قبول طلبك #{request_id}!")
    # تحديث الرسالة للأدمن
    await callback.message.edit_text(callback.message.text + "\n\nتم القبول.")
    await callback.answer()

# معالج قرارات الأدمن - للرفض
@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = int(parts[2])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'rejected' WHERE id = ?", (request_id,))
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    user_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    # إخطار المستخدم بالرفض
    await bot.send_message(user_id, f"تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل.")
    # تحديث الرسالة للأدمن
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

# معالج زر تتبع الطلبات - يبدأ عملية التتبع
@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    await message.answer("أدخل رقم الطلب لتتبعه (أو اكتب 'جميع' لعرض كل طلباتك):")
    await state.set_state(TrackStates.waiting_request_id)

@dp.message(TrackStates.waiting_request_id)
async def track_request(message: types.Message, state: FSMContext):
    user_id = message.from_user.id  # ID المستخدم الحالي
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    input_text = message.text.strip().lower()  # تنظيف الإدخال
    
    if input_text == 'جميع':
        # استعلام لجلب جميع طلبات المستخدم
        cursor.execute(
            "SELECT id, request_type, reason, details, status, created_at FROM requests WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        requests = cursor.fetchall()
        
        if not requests:
            await message.answer("لا توجد طلبات سابقة لديك.")
        else:
            response_text = "طلباتك السابقة:\n\n"
            for req in requests:
                req_id, req_type, reason, details, status, created_at = req
                type_ar = "اعتذار" if req_type == 'excuse' else "إجازة"  # ترجمة النوع
                status_ar = "قيد الانتظار" if status == 'pending' else "مقبول" if status == 'approved' else "مرفوض"  # ترجمة الحالة
                response_text += f"رقم الطلب: {req_id}\nنوع: {type_ar}\nالحالة: {status_ar}\nالتاريخ: {created_at}\nالسبب: {reason}\n"
                if details:
                    response_text += f"التفاصيل: {details}\n"
                response_text += "---\n"
            
            await message.answer(response_text)
    else:
        try:
            request_id = int(input_text)  # تحويل إلى رقم
            # استعلام للطلب المحدد، مع التحقق من الملكية
            cursor.execute(
                "SELECT request_type, reason, details, status, created_at FROM requests WHERE id = ? AND user_id = ?",
                (request_id, user_id)
            )
            req = cursor.fetchone()
            
            if not req:
                await message.answer("لا يوجد طلب بهذا الرقم أو غير متاح لك.")
            else:
                req_type, reason, details, status, created_at = req
                type_ar = "اعتذار" if req_type == 'excuse' else "إجازة"
                status_ar = "قيد الانتظار" if status == 'pending' else "مقبول" if status == 'approved' else "مرفوض"
                response_text = f"تفاصيل الطلب #{request_id}:\n\nنوع: {type_ar}\nالحالة: {status_ar}\nالتاريخ: {created_at}\nالسبب: {reason}\n"
                if details:
                    response_text += f"التفاصيل: {details}\n"
                await message.answer(response_text)
        except ValueError:
            await message.answer("يرجى إدخال رقم صحيح أو 'جميع'.")
    
    conn.close()
    await state.clear()  # مسح الحالة

# معالج زر المراجع - يعرض خيارات المراجع الخاصة بالفريق
@dp.message(lambda message: message.text == "مراجع الفريق")
async def references_handler(message: types.Message):
    refs_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="مدونة السلوك", callback_data="code_of_conduct")],
        [InlineKeyboardButton(text="بنود وقوانين الفريق", callback_data="rules")]
    ])
    
    await message.answer(
        "اختر المرجع المطلوب:",
        reply_markup=refs_keyboard
    )

# معالج كولباك مدونة السلوك
@dp.callback_query(lambda c: c.data == "code_of_conduct")
async def code_of_conduct(callback: types.CallbackQuery):
    text = (
        "مدونة السلوك لفريق أبناء الأرض:\n\n"
        "1. الاحترام المتبادل: احترم زملاءك وكل الأطراف.\n"
        "2. الالتزام بالمواعيد: كن دقيقاً في الاجتماعات والأنشطة.\n"
        "3. السرية: احفظ معلومات الفريق سراً.\n"
        "4. الإيجابية: شجع الآخرين وكن مصدر إلهام.\n\n"
        "للمزيد، تواصل مع الإدارة."
    )
    await callback.message.edit_text(text)
    await callback.answer()

# معالج كولباك بنود وقوانين الفريق
@dp.callback_query(lambda c: c.data == "rules")
async def rules(callback: types.CallbackQuery):
    text = (
        "بنود وقوانين فريق أبناء الأرض:\n\n"
        "1. الالتزام بالأهداف الخيرية.\n"
        "2. عدم مشاركة المعلومات الخاصة.\n"
        "3. المشاركة الفعالة في الأنشطة.\n"
        "4. الإبلاغ عن أي مشكلات فوراً.\n"
        "5. عقوبات: تحذير، إيقاف، إنهاء العضوية حسب الخطأ.\n\n"
        "للنسخة الكاملة، اطلب من الإدارة."
    )
    await callback.message.edit_text(text)
    await callback.answer()

# معالج زر أهدني عبارة - يرسل عبارة تحفيزية عشوائية
@dp.message(lambda message: message.text == "أهدني عبارة")
async def phrase_handler(message: types.Message):
    phrase = random.choice(motivational_phrases)  # اختيار عشوائي
    await message.answer(phrase)

# دالة التشغيل الرئيسية لـ Web Service مع webhook
async def main():
    """بدء تشغيل البوت بـ webhook لـ Web Service"""
    # إعداد webhook
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/webhook"
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')

    await bot.set_webhook(url=webhook_url, secret_token=webhook_secret)

    # إعداد الـ app لـ aiohttp
    app = web.Application()
    app.router.add_post('/webhook', dp.feed_webhook_updates)  # يتلقى التحديثات من تلغرام

    # تشغيل الـ server على المنفذ المطلوب في Render
    port = int(os.getenv('PORT', 10000))  # Render يحدد PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    print(f"Webhook server started on port {port} at {webhook_url}")
    await asyncio.Event().wait()  # يبقي الـ server يعمل مستمراً

if __name__ == "__main__":
    asyncio.run(main())
