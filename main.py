import os  # لقراءة المتغيرات البيئية مثل التوكن والأدمن ID
import random  # لاختيار عبارة تحفيزية عشوائية
import asyncio  # لتشغيل الـ async
import logging  # لتسجيل الأحداث
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
from aiogram.client.default import DefaultBotProperties  # لإعدادات البوت الافتراضية
from aiogram.enums import ParseMode  # لتحديد ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application  # لإعداد webhook مع aiohttp
from aiohttp import web  # للـ HTTP server

# إعداد اللوغينغ
logging.basicConfig(level=logging.INFO)

# إعداد البوت
TOKEN = os.getenv('BOT_TOKEN')  # قراءة التوكن من المتغيرات البيئية
ADMIN_ID = int(os.getenv('CHAT_ADMIN_ID'))  # ID الدردشة للأدمن

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  # إنشاء كائن البوت مع ParseMode
storage = MemoryStorage()  # تخزين الحالات في الذاكرة (غير دائم، مناسب للتطوير)
dp = Dispatcher(storage=storage)  # Dispatcher لإدارة الرسائل والكولباكات

# عداد تسلسلي للطلبات (يبدأ من 1، يزيد مع كل طلب جديد - في الذاكرة، يعاد تعيينه عند إعادة التشغيل)
request_counter = 1

# تخزين مواعيد الاجتماعات (قاموس في الذاكرة)
meeting_schedules = {
    'الاجتماع العام': 'غير محدد',
    'اجتماع فريق الدعم الاول': 'غير محدد',
    'فريق الدعم الثاني': 'غير محدد',
    'الفريق المركزي': 'غير محدد'
}

# حالات FSM للاعتذار (لجمع البيانات خطوة بخطوة)
class ExcuseStates(StatesGroup):
    waiting_name = State()  # انتظار اسم المتطوع
    waiting_activity_type = State()  # انتظار نوع النشاط (مبادرة، اجتماع، آخر)
    waiting_reason = State()  # انتظار سبب الاعتذار (إذا آخر)
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

# حالات FSM للوحة الأدمن (إدخال مواعيد الاجتماعات)
class AdminStates(StatesGroup):
    waiting_meeting_type = State()  # انتظار نوع الاجتماع
    waiting_meeting_date = State()  # انتظار تاريخ الاجتماع

# لوحة المفاتيح الرئيسية (تظهر للمستخدم عند /start) - مع إضافة الأزرار الجديدة
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اعتذار"), KeyboardButton(text="إجازة")],
        [KeyboardButton(text="تتبع طلباتي"), KeyboardButton(text="مراجع الفريق")],
        [KeyboardButton(text="أهدني عبارة"), KeyboardButton(text="لا تنس ذكر الله")],
        [KeyboardButton(text="استعلامات")]
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

# الذكر الإسلامي
dhikr_phrases = [
    "سبحان الله\nالحمدلله\nلا إله إلا الله\nالله اكبر\nسبحان الله وبحمده\nسبحان الله العظيم"
]

# معالج الرجوع إلى القائمة الرئيسية (للـ ReplyKeyboard)
@dp.message(lambda message: message.text == "رجوع")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()  # مسح أي حالة FSM حالية
    await message.answer(
        "تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕",
        reply_markup=main_keyboard
    )

# معالج الرجوع للـ Inline (callback back_to_main)
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_inline(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  # مسح أي حالة FSM حالية
    await callback.message.edit_text(
        "تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕",
        reply_markup=None
    )
    await callback.message.answer(
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )
    await callback.answer()

# معالج الأمر /start - يرسل رسالة الترحيب ولوحة المفاتيح
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "مرحباً بك في بوت إدارة شؤون الموارد البشرية لفريق أبناء الأرض! 🌟\n"
        "نحن سعيدون بوجودك معنا، وسنكون دائماً بجانبك في رحلتك التطوعية. 💖\n"
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )

# معالج زر الاعتذار - يبدأ عملية جمع بيانات الاعتذار
@dp.message(lambda message: message.text == "اعتذار")
async def excuse_start(message: types.Message, state: FSMContext):
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما اسمك الكامل كمتطوع؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(ExcuseStates.waiting_name)

@dp.message(ExcuseStates.waiting_name)
async def excuse_name(message: types.Message, state: FSMContext):
    # حفظ الاسم في حالة FSM
    await state.update_data(name=message.text)
    # لوحة لاختيار نوع النشاط مع رجوع
    activity_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="مبادرة"), KeyboardButton(text="اجتماع")],
            [KeyboardButton(text="آخر"), KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(f"مرحباً {message.text}، سعيدون بك معنا! 🌹\nعن شو الاعتذار؟", reply_markup=activity_keyboard)
    await state.set_state(ExcuseStates.waiting_activity_type)

@dp.message(ExcuseStates.waiting_activity_type)
async def excuse_activity_type(message: types.Message, state: FSMContext):
    data = await state.get_data()
    activity_type = message.text
    if activity_type == "آخر":
        await state.update_data(activity_type="آخر")
        back_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="رجوع")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        await message.answer("نحن نفهم أن الحياة مليئة بالمفاجآت، يرجى توضيح العمل الذي تريد الاعتذار عنه: 💕", reply_markup=back_keyboard)
        await state.set_state(ExcuseStates.waiting_reason)
    else:
        await state.update_data(activity_type=activity_type)
        # لوحة تأكيد مع رجوع inline
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="تأكيد الطلب", callback_data="confirm_excuse")],
            [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
        ])
        await message.answer(
            f"شكراً لثقتك بنا، {data['name']}! 😊\n"
            f"تأكيد الطلب:\n"
            f"الاسم: {data['name']}\n"
            f"نوع النشاط: {activity_type}\n\n"
            "هل تريد تأكيد الطلب؟",
            reply_markup=confirm_keyboard
        )
        await state.set_state(ExcuseStates.waiting_confirm)

@dp.message(ExcuseStates.waiting_reason)
async def excuse_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['reason'] = message.text  # حفظ السبب
    
    # إنشاء لوحة تأكيد داخلية مع رجوع
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تأكيد الطلب", callback_data="confirm_excuse")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    
    await message.answer(
        f"نحن نقدر صراحتك وشجاعتك في التعبير، {data['name']}! 💖\n"
        f"تأكيد الطلب:\n"
        f"الاسم: {data['name']}\n"
        f"نوع النشاط: آخر\n"
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
    activity_details = f"نوع النشاط: {data.get('activity_type', 'غير محدد')}\nالسبب: {data.get('reason', 'غير محدد')}"
    
    # إخطار المستخدم بنجاح الإرسال
    await callback.message.edit_text(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
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
        f"{activity_details}",
        reply_markup=admin_keyboard
    )
    
    await state.clear()  # مسح الحالة بعد الإكمال

# معالج زر الإجازة - يبدأ عملية جمع بيانات الإجازة
@dp.message(lambda message: message.text == "إجازة")
async def leave_start(message: types.Message, state: FSMContext):
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما اسمك الكامل كمتطوع؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_name)

@dp.message(LeaveStates.waiting_name)
async def leave_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer(f"مرحباً {message.text}، سعيدون بك معنا! 🌹\nما سبب الإجازة؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_reason)

@dp.message(LeaveStates.waiting_reason)
async def leave_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما مدة الإجازة (بالأيام)؟ نتمنى لك وقتاً جميلاً! 💕", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_duration)

@dp.message(LeaveStates.waiting_duration)
async def leave_duration(message: types.Message, state: FSMContext):
    await state.update_data(duration=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما تاريخ بدء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_start_date)

@dp.message(LeaveStates.waiting_start_date)
async def leave_start_date(message: types.Message, state: FSMContext):
    await state.update_data(start_date=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما تاريخ انتهاء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_end_date)

@dp.message(LeaveStates.waiting_end_date)
async def leave_end_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['end_date'] = message.text
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    
    # إنشاء لوحة تأكيد مع رجوع
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تأكيد الطلب", callback_data="confirm_leave")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    
    await message.answer(
        f"شكراً لثقتك بنا، {data['name']}! 😊\n"
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
    await callback.message.edit_text(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
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
    await bot.send_message(user_id, f"تهانينا! 🎉 تم قبول طلبك #{request_id} بكل فرحة. نحن فخورون بك! 💖")
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
    await bot.send_message(user_id, f"نأسف لإخبارك بذلك، 😔 تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل. نحن هنا لدعمك!")
    # تحديث الرسالة للأدمن
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

# معالج زر تتبع الطلبات - مؤقت بدون DB
@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="رجوع")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ميزة التتبع غير متوفرة حالياً. يرجى التواصل مع الإدارة للاستعلام عن طلباتك. نحن نسعد بمساعدتك! 💕", reply_markup=back_keyboard)

# معالج زر المراجع - يعرض خيارات المراجع الخاصة بالفريق
@dp.message(lambda message: message.text == "مراجع الفريق")
async def references_handler(message: types.Message):
    refs_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="مدونة السلوك", callback_data="code_of_conduct")],
        [InlineKeyboardButton(text="بنود وقوانين الفريق", callback_data="rules")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    
    await message.answer(
        "نحن فخورون بقيمنا في فريق أبناء الأرض! 🌟\nاختر المرجع المطلوب:",
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
        "للمزيد، تواصل مع الإدارة. نحن معاً في هذه الرحلة! 💖"
    )
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=back_keyboard)
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
        "للنسخة الكاملة، اطلب من الإدارة. نحن نبني عائلة قوية معاً! 🌹"
    )
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# معالج زر أهدني عبارة - يرسل عبارة تحفيزية عشوائية
@dp.message(lambda message: message.text == "أهدني عبارة")
async def phrase_handler(message: types.Message):
    phrase = random.choice(motivational_phrases)  # اختيار عشوائي
    await message.answer(f"إليك عبارة تحفيزية من القلب: {phrase} 💖", reply_markup=main_keyboard)

# معالج زر لا تنس ذكر الله
@dp.message(lambda message: message.text == "لا تنس ذكر الله")
async def dhikr_handler(message: types.Message):
    dhikr = "\n".join(dhikr_phrases)
    await message.answer(f"اللهم اجعل هذا الذكر نوراً لقلبك: {dhikr} 🌟", reply_markup=main_keyboard)

# معالج زر استعلامات
@dp.message(lambda message: message.text == "استعلامات")
async def inquiries_handler(message: types.Message):
    inquiries_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="استعلام عن اجتماع", callback_data="inquire_meeting")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await message.answer("نحن هنا لنجيب على استفساراتك بكل حب! 💕\nاختر نوع الاستعلام:", reply_markup=inquiries_keyboard)

@dp.callback_query(lambda c: c.data == "inquire_meeting")
async def inquire_meeting(callback: types.CallbackQuery):
    meeting_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الاجتماع العام", callback_data="meeting_general")],
        [InlineKeyboardButton(text="اجتماع فريق الدعم الاول", callback_data="meeting_support1")],
        [InlineKeyboardButton(text="فريق الدعم الثاني", callback_data="meeting_support2")],
        [InlineKeyboardButton(text="الفريق المركزي", callback_data="meeting_central")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("اختر الاجتماع الذي تهتم به: 😊", reply_markup=meeting_keyboard)
    await callback.answer()

# معالجات الاستعلامات عن الاجتماعات (عرض المواعيد من القاموس)
@dp.callback_query(lambda c: c.data == "meeting_general")
async def meeting_general(callback: types.CallbackQuery):
    date = meeting_schedules.get('الاجتماع العام', 'غير محدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد الاجتماع العام: {date}\n\nنحن نتطلع للقائك هناك! 🌹", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_support1")
async def meeting_support1(callback: types.CallbackQuery):
    date = meeting_schedules.get('اجتماع فريق الدعم الاول', 'غير محدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد اجتماع فريق الدعم الاول: {date}\n\nمعاً نبني الدعم الأقوى! 💪", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_support2")
async def meeting_support2(callback: types.CallbackQuery):
    date = meeting_schedules.get('فريق الدعم الثاني', 'غير محدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد فريق الدعم الثاني: {date}\n\nدعمكم يلهمنا دائماً! 😊", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_central")
async def meeting_central(callback: types.CallbackQuery):
    date = meeting_schedules.get('الفريق المركزي', 'غير محدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد الفريق المركزي: {date}\n\nمركزنا هو قلب الفريق! ❤️", reply_markup=back_keyboard)
    await callback.answer()

# معالج لوحة التحكم للأدمن (/admin)
@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("غير مصرح لك!")
        return
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="وضع موعد الاجتماع العام", callback_data="admin_general")],
        [InlineKeyboardButton(text="وضع موعد دعم أول", callback_data="admin_support1")],
        [InlineKeyboardButton(text="وضع موعد دعم ثاني", callback_data="admin_support2")],
        [InlineKeyboardButton(text="وضع موعد مركزي", callback_data="admin_central")]
    ])
    await message.answer("لوحة التحكم للأدمن: نحن فخورون بإدارتك الرائعة! 🌟", reply_markup=admin_keyboard)
    await state.set_state(AdminStates.waiting_meeting_type)  # بدء حالة الأدمن

# معالجات لوحة الأدمن لاختيار نوع الاجتماع (بدون فلتر state في callback)
@dp.callback_query(lambda c: c.data == "admin_general")
async def admin_general(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='الاجتماع العام')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("أدخل موعد الاجتماع العام (YYYY-MM-DD HH:MM): شكراً لجهودك في تنظيمنا! 😊", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_support1")
async def admin_support1(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='اجتماع فريق الدعم الاول')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("أدخل موعد اجتماع فريق الدعم الاول (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_support2")
async def admin_support2(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='فريق الدعم الثاني')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("أدخل موعد فريق الدعم الثاني (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_central")
async def admin_central(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='الفريق المركزي')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("أدخل موعد الفريق المركزي (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)
    await callback.answer()

@dp.message(AdminStates.waiting_meeting_date)
async def admin_set_date(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    data = await state.get_data()
    meeting_type = data['meeting_type']
    meeting_date = message.text
    meeting_schedules[meeting_type] = meeting_date  # حفظ في القاموس
    await message.answer(f"تم حفظ موعد {meeting_type}: {meeting_date}\nشكراً لك، أنت تجعل فريقنا أقوى! 🌹", reply_markup=main_keyboard)
    await state.clear()

# دالة التشغيل الرئيسية عند بدء البوت
async def on_startup(bot: Bot) -> None:
    """إعداد webhook عند بدء التشغيل"""
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/webhook"
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
    await bot.set_webhook(url=webhook_url, secret_token=webhook_secret)
    logging.info(f"Webhook set to {webhook_url}")

# دالة التشغيل الرئيسية لـ Web Service مع webhook
def main() -> None:
    """بدء تشغيل البوت بـ webhook لـ Web Service"""
    # تسجيل دالة الـ startup
    dp.startup.register(on_startup)

    # إعداد webhook secret
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
    webhook_path = "/webhook"

    # إنشاء aiohttp.web.Application instance
    app = web.Application()

    # إنشاء SimpleRequestHandler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret,
    )
    # تسجيل webhook handler
    webhook_requests_handler.register(app, path=webhook_path)

    # ربط startup و shutdown hooks مع aiohttp app
    setup_application(app, dp, bot=bot)

    # تشغيل الـ server على المنفذ المطلوب في Render
    port = int(os.getenv('PORT', 10000))  # Render يحدد PORT
    host = '0.0.0.0'  # للاستماع على جميع الواجهات
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    main()
