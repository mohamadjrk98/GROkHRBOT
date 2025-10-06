import os
import sqlite3
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# إعداد البوت
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('CHAT_ADMIN_ID'))

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# قاعدة بيانات SQLite
DB_PATH = 'bot_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول الطلبات العام
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            request_type TEXT,  -- 'excuse' or 'leave'
            reason TEXT,
            details TEXT,  -- for leave: duration, start_date, end_date
            status TEXT DEFAULT 'pending',  -- pending, approved, rejected
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# حالات FSM للاعتذار
class ExcuseStates(StatesGroup):
    waiting_name = State()
    waiting_reason = State()
    waiting_confirm = State()

# حالات FSM للإجازة
class LeaveStates(StatesGroup):
    waiting_name = State()
    waiting_reason = State()
    waiting_duration = State()
    waiting_start_date = State()
    waiting_end_date = State()
    waiting_confirm = State()

# حالات FSM لتتبع الطلبات
class TrackStates(StatesGroup):
    waiting_request_id = State()

# لوحة المفاتيح الرئيسية
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اعتذار"), KeyboardButton(text="إجازة")],
        [KeyboardButton(text="تتبع طلباتي"), KeyboardButton(text="مراجع الفريق"), KeyboardButton(text="أهدني عبارة")]
    ],
    resize_keyboard=True
)

# عبارات تحفيزية
motivational_phrases = [
    "العمل الخيري هو بذرة الأمل في قلوب الناس، ازرعها وستحصد الابتسامات!",
    "في كل يد تمتد للمساعدة، ينبت أمل جديد. استمر في إشراقك مع فريق أبناء الأرض!",
    "الأمل يبدأ بخطوة صغيرة، وأنت جزء من هذه الخطوات العظيمة. شكراً لتطوعك!",
    "كل جهد يبذل في سبيل الخير يعود بالبركة. كن مصدر إلهام دائماً!",
    "مع فريق أبناء الأرض، نبني جسور الأمل. أنت بطل هذه القصة!"
]

# معالج الأمر /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "مرحباً بك في بوت إدارة شؤون الموارد البشرية لفريق أبناء الأرض!\n"
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )

# معالج زر الاعتذار
@dp.message(lambda message: message.text == "اعتذار")
async def excuse_start(message: types.Message, state: FSMContext):
    await message.answer("ما اسمك الكامل كمتطوع؟")
    await state.set_state(ExcuseStates.waiting_name)

@dp.message(ExcuseStates.waiting_name)
async def excuse_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("ما سبب الاعتذار عن المبادرة/الاجتماع/النشاط؟")
    await state.set_state(ExcuseStates.waiting_reason)

@dp.message(ExcuseStates.waiting_reason)
async def excuse_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['reason'] = message.text
    
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

@dp.callback_query(lambda c: c.data == "confirm_excuse", ExcuseStates.waiting_confirm)
async def confirm_excuse(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # حفظ في قاعدة البيانات
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO requests (user_id, user_name, request_type, reason) VALUES (?, ?, ?, ?)",
        (callback.from_user.id, data['name'], 'excuse', data['reason'])
    )
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إخطار المستخدم
    await callback.message.edit_text("تم إرسال طلبك بنجاح! سيتم معالجته قريباً (قبول أو رفض).")
    await callback.answer()
    
    # إخطار الأدمن
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}")
        ]
    ])
    
    await bot.send_message(
        ADMIN_ID,
        f"طلب اعتذار جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"سبب الاعتذار: {data['reason']}",
        reply_markup=admin_keyboard
    )
    
    await state.clear()

# معالج زر الإجازة
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

@dp.callback_query(lambda c: c.data == "confirm_leave", LeaveStates.waiting_confirm)
async def confirm_leave(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    
    # حفظ في قاعدة البيانات
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
    
    # إخطار الأدمن
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}")
        ]
    ])
    
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

# معالج قرارات الأدمن
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = int(parts[2])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'approved' WHERE id = ?", (request_id,))
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    user_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    await bot.send_message(user_id, f"تم قبول طلبك #{request_id}!")
    await callback.message.edit_text(callback.message.text + "\n\nتم القبول.")
    await callback.answer()

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
    
    await bot.send_message(user_id, f"تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل.")
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

# معالج زر تتبع الطلبات
@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    await message.answer("أدخل رقم الطلب لتتبعه (أو اكتب 'جميع' لعرض كل طلباتك):")
    await state.set_state(TrackStates.waiting_request_id)

@dp.message(TrackStates.waiting_request_id)
async def track_request(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    input_text = message.text.strip().lower()
    
    if input_text == 'جميع':
        # عرض جميع الطلبات
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
                type_ar = "اعتذار" if req_type == 'excuse' else "إجازة"
                status_ar = "قيد الانتظار" if status == 'pending' else "مقبول" if status == 'approved' else "مرفوض"
                response_text += f"رقم الطلب: {req_id}\nنوع: {type_ar}\nالحالة: {status_ar}\nالتاريخ: {created_at}\nالسبب: {reason}\n"
                if details:
                    response_text += f"التفاصيل: {details}\n"
                response_text += "---\n"
            
            await message.answer(response_text)
    else:
        try:
            request_id = int(input_text)
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
    await state.clear()

# معالج زر المراجع
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

# معالج زر أهدني عبارة
@dp.message(lambda message: message.text == "أهدني عبارة")
async def phrase_handler(message: types.Message):
    phrase = random.choice(motivational_phrases)
    await message.answer(phrase)

# تشغيل البوت
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
