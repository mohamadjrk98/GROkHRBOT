import os  # لقراءة المتغيرات البيئية مثل التوكن والأدمن ID
import random  # لاختيار عبارة تحفيزية عشوائية
import asyncio  # لتشغيل الـ async
from datetime import datetime  # للتعامل مع التواريخ
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

# عداد تسلسلي للطلبات (يبدأ من 1، يزيد مع كل طلب جديد - في الذاكرة، يعاد تعيينه عند إعادة التشغيل)
request_counter = 1

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

# حالات FSM لتتبع الطلبات (مؤقتة، بدون DB)
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

# معالج الكولباك لتأكيد الاعتذار (مع عداد تسلسلي)
@dp.callback_query(lambda c: c.data == "confirm_excuse", ExcuseStates.waiting_confirm)
async def confirm_excuse(callback: types.CallbackQuery, state: FSMContext):
    global request_counter  # استخدام العداد العام
    data = await state.get_data()
    user_id = callback.from_user.id
    request_id = request_counter  # الحصول على الرقم التسلسلي
    request_counter += 1  # زيادة العداد للطلب التالي
    
    # إخطار المستخدم بنجاح الإرسال
    await callback.message.edit_text(f"تم إرسال طلبك #{request_id} بنجاح! سيتم معالجته قريباً (قبول أو رفض).")
    await callback.answer()
    
    # إنشاء لوحة للأدمن للقبول/الرفض مع user_id في callback_data
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}_{user_id}")
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

# معالج الكولباك لتأكيد الإجازة (مع عداد تسلسلي)
@dp.callback_query(lambda c: c.data == "confirm_leave", LeaveStates.waiting_confirm)
async def confirm_leave(callback: types.CallbackQuery, state: FSMContext):
    global request_counter  # استخدام العداد العام
    data = await state.get_data()
    user_id = callback.from_user.id
    request_id = request_counter  # الحصول على الرقم التسلسلي
    request_counter += 1  # زيادة العداد للطلب التالي
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    
    # إخطار المستخدم
    await callback.message.edit_text(f"تم إرسال طلبك #{request_id} بنجاح! سيتم معالجته قريباً (قبول أو رفض).")
    await callback.answer()
    
    # لوحة الأدمن مع user_id في callback_data
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}_{user_id}")
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

# معالج قرارات الأدمن - للقبول (بدون DB، إرسال مباشر للمستخدم)
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    # التحقق من أن المستخدم هو الأدمن فقط
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    
    parts = callback.data.split("_")  # تحليل البيانات: approve_[type]_[id]_[user_id]
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])  # استخراج user_id من callback_data
    
    # إخطار المستخدم بالقبول
    await bot.send_message(user_id, f"تم قبول طلبك #{request_id}!")
    # تحديث الرسالة للأدمن
    await callback.message.edit_text(callback.message.text + "\n\nتم القبول.")
    await callback.answer()

# معالج قرارات الأدمن - للرفض (بدون DB، إرسال مباشر للمستخدم)
@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    
    parts = callback.data.split("_")  # تحليل البيانات: reject_[type]_[id]_[user_id]
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])  # استخراج user_id من callback_data
    
    # إخطار المستخدم بالرفض
    await bot.send_message(user_id, f"تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل.")
    # تحديث الرسالة للأدمن
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

# معالج زر تتبع الطلبات - مؤقت بدون DB
@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    await message.answer("ميزة التتبع غير متوفرة حالياً. يرجى التواصل مع الإدارة للاستعلام عن طلباتك.")

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
