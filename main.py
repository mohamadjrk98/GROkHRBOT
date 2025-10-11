import os
import random
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables and constants
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(os.getenv('CHAT_ADMIN_ID')), 5780307552]  # Added second admin
EXCUSE_GROUP_ID = -4737111167  # Chat ID for the excuses group
LEAVE_GROUP_ID = -4868672688  # Chat ID for the leave group
ATTENDANCE_GROUP_ID = -4966592161  # Chat ID for the attendance group

# Bot and Dispatcher setup
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global variables
request_counter = 1
users = set()
meeting_schedules = {
    'الاجتماع العام': 'غير محدد',
    'اجتماع فريق الدعم الاول': 'غير محدد',
    'فريق الدعم الثاني': 'غير محدد',
    'الفريق المركزي': 'غير محدد'
}
team_photos = []  # List to store photo file_ids, e.g., [{'file_id': 'id1'}, {'file_id': 'id2'}]

# Lists and data
motivational_phrases = [
    "العمل الخيري هو بذرة الأمل في قلوب الناس، ازرعها وستحصد الابتسامات!",
    "في كل يد تمتد للمساعدة، ينبت أمل جديد. استمر في إشراقك مع فريق أبناء الأرض!",
    "الأمل يبدأ بخطوة صغيرة، وأنت جزء من هذه الخطوات العظيمة. شكراً لتطوعك!",
    "كل جهد يبذل في سبيل الخير يعود بالبركة. كن مصدر إلهام دائماً!",
    "مع فريق أبناء الأرض، نبني جسور الأمل. أنت بطل هذه القصة!",
    "إنّ التطوع ليس مجرد فعل، بل هو ثقافة عطاء تُثري الروح والمجتمع.",
    "يُضيء العمل الخيري حياة من حولنا، لكنّه يُنير قلوبنا نحن أولًا.",
    "كل يد ممدودة بالخير هي بستان يُزهر أملًا في حياة الآخرين.",
    "نجاح فريق أبناء الأرض يكمن في إيمان أعضائه بأنّ سعادة الآخرين تبدأ بخطواتهم.",
    "التطوع هو أن تمنح بلا مقابل، وتجد المقابل الأعظم في ابتسامة محتاج.",
    "يؤمن فريق أبناء الأرض بأنّ قوة المجتمع تقاس بمدى تكاتف أفراده في البذل والعطاء.",
    "أجمل ما يُخلفه المرء وراءه هو أثر طيب من جهد تطوعي خالص.",
    "عندما نتطوع، فإننا لا نُغيّر حياة الآخرين فحسب، بل نُعيد اكتشاف أجمل ما في أنفسنا.",
    "لتكن خطواتك في العمل الخيري أوسع من كلماتك؛ فالأفعال هي التي تصنع الفرق الحقيقي.",
    "رسالة فريق أبناء الأرض هي دليل على أنّ العمل الجماعي المخلص هو مفتاح التغيير الإيجابي في العالم.",
    "التطوع هو الجسر الذي نعبُر به من الأنا إلى نحن."
]

dhikr_phrases = [
    "سبحان الله\nالحمدلله\nلا إله إلا الله\nالله اكبر\nسبحان الله وبحمده\nسبحان الله العظيم"
]

# Keyboards
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اعتذار"), KeyboardButton(text="إجازة")],
        [KeyboardButton(text="تتبع طلباتي"), KeyboardButton(text="مراجع الفريق")],
        [KeyboardButton(text="أهدني عبارة"), KeyboardButton(text="لا تنس ذكر الله")],
        [KeyboardButton(text="استعلامات"), KeyboardButton(text="اقتراحات")],
        [KeyboardButton(text="تحميل صور الفريق الاخيرة")]
    ],
    resize_keyboard=True
)

back_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="رجوع")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

feedback_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اقتراح تطوير البوت")],
        [KeyboardButton(text="اقتراح مبادرة")],
        [KeyboardButton(text="آخر")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="تأكيد الطلب")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

inquiries_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="استعلام عن اجتماع")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

meeting_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="الاجتماع العام")],
        [KeyboardButton(text="اجتماع فريق الدعم الاول")],
        [KeyboardButton(text="اجتماع فريق الدعم الثاني")],
        [KeyboardButton(text="اجتماع الفريق المركزي")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

refs_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="مدونة السلوك")],
        [KeyboardButton(text="بنود وقوانين الفريق")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="وضع موعد الاجتماع العام")],
        [KeyboardButton(text="وضع موعد دعم أول")],
        [KeyboardButton(text="وضع موعد دعم ثاني")],
        [KeyboardButton(text="وضع موعد مركزي")],
        [KeyboardButton(text="إرسال بث للجميع")],
        [KeyboardButton(text="رفع صور الفريق")],
        [KeyboardButton(text="حذف صور الفريق")],
        [KeyboardButton(text="إرسال رسالة لمستخدم")],
        [KeyboardButton(text="تفقد")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

attendance_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="تفقد اجتماع")],
        [KeyboardButton(text="تفقد مبادرة")],
        [KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

activity_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="مبادرة"), KeyboardButton(text="اجتماع")],
        [KeyboardButton(text="آخر"), KeyboardButton(text="رجوع")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# FSM States
class ExcuseStates(StatesGroup):
    waiting_name = State()
    waiting_activity_type = State()
    waiting_reason = State()
    waiting_confirm = State()

class LeaveStates(StatesGroup):
    waiting_name = State()
    waiting_reason = State()
    waiting_duration = State()
    waiting_start_date = State()
    waiting_end_date = State()
    waiting_confirm = State()

class TrackStates(StatesGroup):
    waiting_request_id = State()

class AdminStates(StatesGroup):
    waiting_meeting_type = State()
    waiting_meeting_date = State()
    waiting_broadcast_message = State()
    waiting_upload_photo = State()
    waiting_user_id = State()
    waiting_user_message = State()
    waiting_attendance_type = State()
    waiting_attendance_names = State()

class FeedbackStates(StatesGroup):
    waiting_type = State()
    waiting_bot_suggestion = State()
    waiting_other_suggestion = State()
    waiting_initiative_name = State()
    waiting_initiative_intro = State()
    waiting_initiative_goals = State()
    waiting_initiative_target = State()
    waiting_initiative_plan = State()
    waiting_initiative_resources = State()
    waiting_initiative_partners = State()
    waiting_initiative_timeline = State()
    waiting_initiative_success = State()

# Utility functions
async def send_to_admins(text: str):
    """Send message to all admins."""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Failed to send to admin {admin_id}: {e}")

# Debug command for webhook info (admin only)
@dp.message(Command("webhook"))
async def check_webhook(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    try:
        info = await bot.get_webhook_info()
        await message.answer(f"Webhook Info: {info}")
        logger.info(f"Webhook info requested by {message.from_user.id}: {info}")
    except Exception as e:
        await message.answer(f"Error getting webhook info: {e}")
        logger.error(f"Error in check_webhook: {e}")

# Back navigation handlers
@dp.message(lambda message: message.text == "رجوع")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕", reply_markup=main_keyboard)

# Start handler
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    users.add(message.from_user.id)
    await message.answer(
        "مرحباً بك في بوت شؤون الموارد البشرية لفريق أبناء الأرض! 🌟\n"
        "نحن مبسوطين بوجودك معنا، و رح نكون دائماً جنبك  برحلتك التطوعية. 💖\n"
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )

# Feedback handlers
@dp.message(lambda message: message.text == "اقتراحات")
async def feedback_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await message.answer("شكراً لاهتمامك بتقديم اقتراح! اختر نوع الاقتراح: 💕", reply_markup=feedback_keyboard)
    await state.set_state(FeedbackStates.waiting_type)
    logger.info(f"Feedback state set for user {message.from_user.id}")

@dp.message(F.and_(lambda message: message.text == "اقتراح تطوير البوت", StateFilter(FeedbackStates.waiting_type)))
async def feedback_bot_start(message: types.Message, state: FSMContext):
    logger.info(f"Feedback bot from {message.from_user.id}")
    users.add(message.from_user.id)
    await message.answer("شكراً لاقتراحك لتطوير البوت! يرجى كتابة الاقتراح كاملاً: 💕", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_bot_suggestion)

@dp.message(FeedbackStates.waiting_bot_suggestion)
async def feedback_bot_message(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    user_name = message.from_user.first_name or "غير محدد"
    suggestion_text = message.text
    await send_to_admins(
        f"اقتراح تطوير البوت:\n"
        f"المرسل: {user_name} (ID: {message.from_user.id})\n"
        f"الاقتراح: {suggestion_text}\n\n"
        f"تاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await message.answer("شكراً جزيلاً لاقتراحك! سنراجعه بعناية لتحسين تجربتك معنا. 🌟", reply_markup=main_keyboard)
    await state.clear()

@dp.message(F.and_(lambda message: message.text == "آخر", StateFilter(FeedbackStates.waiting_type)))
async def feedback_other_start(message: types.Message, state: FSMContext):
    logger.info(f"Feedback other from {message.from_user.id}")
    users.add(message.from_user.id)
    await message.answer("شكراً لاقتراحك! يرجى كتابة الاقتراح كاملاً: 💕", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_other_suggestion)

@dp.message(FeedbackStates.waiting_other_suggestion)
async def feedback_other_message(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    user_name = message.from_user.first_name or "غير محدد"
    suggestion_text = message.text
    await send_to_admins(
        f"اقتراح آخر:\n"
        f"المرسل: {user_name} (ID: {message.from_user.id})\n"
        f"الاقتراح: {suggestion_text}\n\n"
        f"تاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await message.answer("شكراً جزيلاً لاقتراحك! سنراجعه بعناية لتحسين تجربتك معنا. 🌟", reply_markup=main_keyboard)
    await state.clear()

@dp.message(F.and_(lambda message: message.text == "اقتراح مبادرة", StateFilter(FeedbackStates.waiting_type)))
async def feedback_initiative_start(message: types.Message, state: FSMContext):
    logger.info(f"Feedback initiative from {message.from_user.id}")
    users.add(message.from_user.id)
    await message.answer("شكراً لاقتراح مبادرة! يرجى ملء الفورم التالي:\n\n# إسم المبادرة الرئيسي:", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_name)

@dp.message(FeedbackStates.waiting_initiative_name)
async def feedback_initiative_name(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_name=message.text)
    await message.answer("#مقدمة المبادرة:", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_intro)

@dp.message(FeedbackStates.waiting_initiative_intro)
async def feedback_initiative_intro(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_intro=message.text)
    await message.answer("# أهداف المبادرة:", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_goals)

@dp.message(FeedbackStates.waiting_initiative_goals)
async def feedback_initiative_goals(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_goals=message.text)
    await message.answer("#الفئة المستهدفة:", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_target)

@dp.message(FeedbackStates.waiting_initiative_target)
async def feedback_initiative_target(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_target=message.text)
    await message.answer("# خطة العمل:", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_plan)

@dp.message(FeedbackStates.waiting_initiative_plan)
async def feedback_initiative_plan(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_plan=message.text)
    await message.answer("# الموارد المطلوبة :", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_resources)

@dp.message(FeedbackStates.waiting_initiative_resources)
async def feedback_initiative_resources(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_resources=message.text)
    await message.answer("#الشركاء والداعمين :", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_partners)

@dp.message(FeedbackStates.waiting_initiative_partners)
async def feedback_initiative_partners(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_partners=message.text)
    await message.answer("# الجدول الزمني :", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_timeline)

@dp.message(FeedbackStates.waiting_initiative_timeline)
async def feedback_initiative_timeline(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(initiative_timeline=message.text)
    await message.answer("# قياس النجاح :", reply_markup=back_keyboard)
    await state.set_state(FeedbackStates.waiting_initiative_success)

@dp.message(FeedbackStates.waiting_initiative_success)
async def feedback_initiative_success(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    data = await state.get_data()
    await state.update_data(initiative_success=message.text)
    user_name = message.from_user.first_name or "غير محدد"
    initiative_report = (
        f"اقتراح مبادرة جديد:\n"
        f"المرسل: {user_name} (ID: {message.from_user.id})\n\n"
        f"إسم المبادرة الرئيسي: {data['initiative_name']}\n"
        f"مقدمة المبادرة: {data['initiative_intro']}\n"
        f"أهداف المبادرة: {data['initiative_goals']}\n"
        f"الفئة المستهدفة: {data['initiative_target']}\n"
        f"خطة العمل: {data['initiative_plan']}\n"
        f"الموارد المطلوبة: {data['initiative_resources']}\n"
        f"الشركاء والداعمين: {data['initiative_partners']}\n"
        f"الجدول الزمني: {data['initiative_timeline']}\n"
        f"قياس النجاح: {message.text}\n\n"
        f"تاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await send_to_admins(initiative_report)
    await message.answer("شكراً جزيلاً لاقتراحك! سنراجعه بعناية. 🌟", reply_markup=main_keyboard)
    await state.clear()

# Excuse handlers
@dp.message(lambda message: message.text == "اعتذار")
async def excuse_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await message.answer("ما اسمك الكامل؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(ExcuseStates.waiting_name)

@dp.message(ExcuseStates.waiting_name)
async def excuse_name(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(name=message.text)
    await message.answer(f"مرحباً {message.text}، سعيدون بك معنا! 🌹\nعن شو الاعتذار؟", reply_markup=activity_keyboard)
    await state.set_state(ExcuseStates.waiting_activity_type)

@dp.message(ExcuseStates.waiting_activity_type)
async def excuse_activity_type(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    data = await state.get_data()
    activity_type = message.text
    if activity_type == "رجوع":
        await state.clear()
        await message.answer("تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕", reply_markup=main_keyboard)
        return
    await state.update_data(activity_type=activity_type)
    await message.answer(f"شكراً لك، {data['name']}! 😊\nما هو السبب في الاعتذار عن {activity_type}؟", reply_markup=back_keyboard)
    await state.set_state(ExcuseStates.waiting_reason)

@dp.message(ExcuseStates.waiting_reason)
async def excuse_reason(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    data = await state.get_data()
    await state.update_data(reason=message.text)
    await message.answer(
        f"نحن نقدر صراحتك وشجاعتك في التعبير، {data['name']}! 💖\n"
        f"تأكيد الطلب:\n"
        f"الاسم: {data['name']}\n"
        f"نوع النشاط: {data['activity_type']}\n"
        f"السبب: {message.text}\n\n"
        "هل تريد تأكيد الطلب؟",
        reply_markup=confirm_keyboard
    )
    await state.set_state(ExcuseStates.waiting_confirm)

@dp.message(F.and_(lambda message: message.text == "تأكيد الطلب", StateFilter(ExcuseStates.waiting_confirm)))
async def confirm_excuse(message: types.Message, state: FSMContext):
    logger.info(f"Confirm excuse from {message.from_user.id}")
    global request_counter
    users.add(message.from_user.id)
    data = await state.get_data()
    user_id = message.from_user.id
    request_id = request_counter
    request_counter += 1
    activity_details = f"نوع النشاط: {data.get('activity_type', 'غير محدد')}\nالسبب: {data.get('reason', 'غير محدد')}"
    await message.answer(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}_{user_id}")
        ]
    ])
    await bot.send_message(
        EXCUSE_GROUP_ID,
        f"طلب اعتذار جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"{activity_details}",
        reply_markup=admin_keyboard
    )
    await state.clear()

# Leave handlers
@dp.message(lambda message: message.text == "إجازة")
async def leave_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await message.answer("ما اسمك الكامل كمتطوع؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_name)

@dp.message(LeaveStates.waiting_name)
async def leave_name(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(name=message.text)
    await message.answer(f"اهلييين {message.text}، سعيدون بك معنا! 🌹\nما سبب الإجازة؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_reason)

@dp.message(LeaveStates.waiting_reason)
async def leave_reason(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(reason=message.text)
    await message.answer("ما مدة الإجازة (بالأيام)؟ نتمنى لك وقتاً جميلاً! 💕", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_duration)

@dp.message(LeaveStates.waiting_duration)
async def leave_duration(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(duration=message.text)
    await message.answer("ما تاريخ بدء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_start_date)

@dp.message(LeaveStates.waiting_start_date)
async def leave_start_date(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(start_date=message.text)
    await message.answer("ما تاريخ انتهاء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_end_date)

@dp.message(LeaveStates.waiting_end_date)
async def leave_end_date(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    data = await state.get_data()
    await state.update_data(end_date=message.text)
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {message.text}"
    await message.answer(
        f"شكراً لثقتك بنا، {data['name']}! 😊\n"
        f"تأكيد الطلب:\n"
        f"الاسم: {data['name']}\n"
        f"السبب: {data['reason']}\n"
        f"التفاصيل: {details}\n\n"
        "هل تريد تأكيد الطلب؟",
        reply_markup=confirm_keyboard
    )
    await state.set_state(LeaveStates.waiting_confirm)

@dp.message(F.and_(lambda message: message.text == "تأكيد الطلب", StateFilter(LeaveStates.waiting_confirm)))
async def confirm_leave(message: types.Message, state: FSMContext):
    logger.info(f"Confirm leave from {message.from_user.id}")
    global request_counter
    users.add(message.from_user.id)
    data = await state.get_data()
    user_id = message.from_user.id
    request_id = request_counter
    request_counter += 1
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    await message.answer(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}_{user_id}")
        ]
    ])
    await bot.send_message(
        LEAVE_GROUP_ID,
        f"طلب إجازة جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"سبب الإجازة: {data['reason']}\n"
        f"التفاصيل: {details}",
        reply_markup=admin_keyboard
    )
    await state.clear()

# Request approval/rejection handlers (keep inline for admin group)
@dp.callback_query(F.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    logger.info(f"Approve callback: {callback.data} from {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("غير مصرح لك!")
        return
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])
    await bot.send_message(user_id, f" ابشر! 🎉 تم قبول طلبك #{request_id} بكل فرحة. نحن فخورون بك! 💖")
    await callback.message.edit_text(callback.message.text + "\n\nتم القبول.")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    logger.info(f"Reject callback: {callback.data} from {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("مين قلك أنك آدمن ؟!")
        return
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])
    await bot.send_message(user_id, f"نأسف لإخبارك بذلك، 😔 تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل. نحن هنا لدعمك!")
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

# Track requests handler
@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    await message.answer(" ميزة التتبع لسا ما جهزت . حكي محمد الجرك مطور البوت و المسؤول اللطيف. 💕", reply_markup=back_keyboard)

# References handlers
@dp.message(lambda message: message.text == "مراجع الفريق")
async def references_handler(message: types.Message):
    await message.answer("نحن فخورون بقيمنا في فريق أبناء الأرض! 🌟\nاختر المرجع:", reply_markup=refs_keyboard)

@dp.message(lambda message: message.text == "مدونة السلوك")
async def code_of_conduct(message: types.Message):
    logger.info(f"Code of conduct from {message.from_user.id}")
    text = (
        "مدونة السلوك لفريق أبناء الأرض:\n\n"
        "1. الاحترام المتبادل: احترم زملاءك وكل الأطراف.\n"
        "2. الالتزام بالمواعيد: كن دقيقاً في الاجتماعات والأنشطة.\n"
        "3. السرية: احفظ معلومات الفريق سراً.\n"
        "4. الإيجابية: شجع الآخرين وكن مصدر إلهام.\n\n"
        "للمزيد، تواصل مع الإدارة. نحن معاً في هذه الرحلة! 💖"
    )
    await message.answer(text, reply_markup=back_keyboard)

@dp.message(lambda message: message.text == "بنود وقوانين الفريق")
async def rules(message: types.Message):
    logger.info(f"Rules from {message.from_user.id}")
    text = (
        "بنود وقوانين فريق أبناء الأرض:\n\n"
        "1. الالتزام بالأهداف الخيرية.\n"
        "2. عدم مشاركة المعلومات الخاصة.\n"
        "3. المشاركة الفعالة في الأنشطة.\n"
        "4. الإبلاغ عن أي مشكلات فوراً.\n"
        "5. عقوبات: تحذير، إيقاف، إنهاء العضوية حسب الخطأ.\n\n"
        "للنسخة الكاملة، اطلب من الإدارة. نحن نبني عائلة قوية معاً! 🌹"
    )
    await message.answer(text, reply_markup=back_keyboard)

# Motivational and Dhikr handlers
@dp.message(lambda message: message.text == "أهدني عبارة")
async def phrase_handler(message: types.Message):
    phrase = random.choice(motivational_phrases)
    await message.answer(f"{phrase} 💖", reply_markup=main_keyboard)

@dp.message(lambda message: message.text == "لا تنس ذكر الله")
async def dhikr_handler(message: types.Message):
    dhikr = "\n".join(dhikr_phrases)
    await message.answer(f"{dhikr} 🌟", reply_markup=main_keyboard)

# Inquiries handlers
@dp.message(lambda message: message.text == "استعلامات")
async def inquiries_handler(message: types.Message):
    await message.answer("نحن هنا لنجيب على استفساراتك بكل حب! 💕\nاختر نوع الاستعلام:", reply_markup=inquiries_keyboard)

@dp.message(lambda message: message.text == "استعلام عن اجتماع")
async def inquire_meeting(message: types.Message):
    logger.info(f"Inquire meeting from {message.from_user.id}")
    await message.answer("اختر الاجتماع الذي تهتم به: 😊", reply_markup=meeting_keyboard)

@dp.message(lambda message: message.text == "الاجتماع العام")
async def meeting_general(message: types.Message):
    logger.info(f"Meeting general from {message.from_user.id}")
    date = meeting_schedules.get('الاجتماع العام', 'لسا ما تحدد')
    await message.answer(f"موعد الاجتماع العام: {date}\n\nنحن نتطلع للقائك هناك! 🌹", reply_markup=back_keyboard)

@dp.message(lambda message: message.text == "اجتماع فريق الدعم الاول")
async def meeting_support1(message: types.Message):
    logger.info(f"Meeting support1 from {message.from_user.id}")
    date = meeting_schedules.get('اجتماع فريق الدعم الاول', 'لسا ما تحدد')
    await message.answer(f"موعد اجتماع فريق الدعم الاول: {date}\n\nمعاً نبني الدعم الأقوى! 💪", reply_markup=back_keyboard)

@dp.message(lambda message: message.text == "اجتماع فريق الدعم الثاني")
async def meeting_support2(message: types.Message):
    logger.info(f"Meeting support2 from {message.from_user.id}")
    date = meeting_schedules.get('فريق الدعم الثاني', 'لسا ما تحدد')
    await message.answer(f"موعد فريق الدعم الثاني: {date}\n\nدعمكم يلهمنا دائماً! 😊", reply_markup=back_keyboard)

@dp.message(lambda message: message.text == "اجتماع الفريق المركزي")
async def meeting_central(message: types.Message):
    logger.info(f"Meeting central from {message.from_user.id}")
    date = meeting_schedules.get('الفريق المركزي', 'لسا ما تحدد')
    await message.answer(f"موعد الفريق المركزي: {date}\n\nمركزنا هو قلب الفريق! ❤️", reply_markup=back_keyboard)

# Team photos handler
@dp.message(lambda message: message.text == "تحميل صور الفريق الاخيرة")
async def download_team_photos(message: types.Message):
    if not team_photos:
        await message.answer("لا توجد صور متاحة حالياً. شكراً لاهتمامك! 💕", reply_markup=main_keyboard)
        return
    # Send the last 5 photos or all if less
    num_photos = min(5, len(team_photos))
    for i in range(num_photos):
        photo_info = team_photos[-1 - i]  # Reverse to get latest first
        await bot.send_photo(
            message.chat.id,
            photo_info['file_id'],
            caption=f"صورة الفريق الأخيرة ({i+1}/{num_photos}) 🌟"
        )
    await message.answer("تم تحميل أحدث الصور! استمتع بذكرياتنا معاً. 💖", reply_markup=main_keyboard)

# Admin panel handlers
@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("مين قلك أنك آدمن ؟!")
        return
    await message.answer("لوحة التحكم للأدمن: نحن فخورون بإدارتك الرائعة! 🌟", reply_markup=admin_keyboard)

# Admin meeting schedule handlers
@dp.message(lambda message: message.text == "وضع موعد الاجتماع العام")
async def admin_general(message: types.Message, state: FSMContext):
    logger.info(f"Admin general from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("رو من هان مانك آدمن ")
        return
    await state.update_data(meeting_type='الاجتماع العام')
    await message.answer("أدخل موعد الاجتماع العام (YYYY-MM-DD HH:MM): شكراً لجهودك في تنظيمنا! 😊", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)

@dp.message(lambda message: message.text == "وضع موعد دعم أول")
async def admin_support1(message: types.Message, state: FSMContext):
    logger.info(f"Admin support1 from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("كاشفك ، مانك آدمن 😝")
        return
    await state.update_data(meeting_type='اجتماع فريق الدعم الاول')
    await message.answer("أدخل موعد اجتماع فريق الدعم الاول (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)

@dp.message(lambda message: message.text == "وضع موعد دعم ثاني")
async def admin_support2(message: types.Message, state: FSMContext):
    logger.info(f"Admin support2 from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='فريق الدعم الثاني')
    await message.answer("أدخل موعد فريق الدعم الثاني (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)

@dp.message(lambda message: message.text == "وضع موعد مركزي")
async def admin_central(message: types.Message, state: FSMContext):
    logger.info(f"Admin central from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await state.update_data(meeting_type='الفريق المركزي')
    await message.answer("أدخل موعد الفريق المركزي (YYYY-MM-DD HH:MM):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_meeting_date)

@dp.message(AdminStates.waiting_meeting_date)
async def admin_set_date(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    data = await state.get_data()
    meeting_type = data['meeting_type']
    meeting_date = message.text
    meeting_schedules[meeting_type] = meeting_date
    await message.answer(f"تم حفظ موعد {meeting_type}: {meeting_date}\nشكراً لك، أنت تجعل فريقنا أقوى! 🌹", reply_markup=admin_keyboard)
    await state.clear()

# Admin broadcast handlers
@dp.message(lambda message: message.text == "إرسال بث للجميع")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    logger.info(f"Admin broadcast from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await message.answer("أدخل الرسالة التي تريد إرسالها لجميع المستخدمين:", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_broadcast_message)

@dp.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("قعود عاقل و حاج تبعت")
        await state.clear()
        return
    broadcast_msg = message.text
    sent_count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, broadcast_msg)
            sent_count += 1
            await asyncio.sleep(0.05)  # Delay to avoid rate limit
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
    await message.answer(f"تم إرسال الرسالة إلى {sent_count} مستخدم. شكراً لك! 💖", reply_markup=admin_keyboard)
    await state.clear()

# Admin send user message handlers
@dp.message(lambda message: message.text == "إرسال رسالة لمستخدم")
async def admin_send_user_msg_start(message: types.Message, state: FSMContext):
    logger.info(f"Admin send user msg from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await message.answer("أدخل ID التلغرام للمستخدم (رقم فقط):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def admin_waiting_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer("الآن أدخل الرسالة التي تريد إرسالها:", reply_markup=back_keyboard)
        await state.set_state(AdminStates.waiting_user_message)
    except ValueError:
        await message.answer("يرجى إدخال رقم صحيح لـ ID المستخدم.")

@dp.message(AdminStates.waiting_user_message)
async def admin_send_user_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    data = await state.get_data()
    user_id = data['user_id']
    user_msg = message.text
    try:
        await bot.send_message(user_id, user_msg)
        await message.answer("تم إرسال الرسالة بنجاح! 💖", reply_markup=admin_keyboard)
    except Exception as e:
        await message.answer(f"حدث خطأ في إرسال الرسالة: {e}")
    await state.clear()

# Admin attendance handlers
@dp.message(lambda message: message.text == "تفقد")
async def admin_attendance_start(message: types.Message, state: FSMContext):
    logger.info(f"Admin attendance from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await message.answer("اختر نوع التفقد:", reply_markup=attendance_keyboard)

@dp.message(lambda message: message.text == "تفقد اجتماع")
async def attendance_meeting(message: types.Message, state: FSMContext):
    logger.info(f"Attendance meeting from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await state.update_data(attendance_type="تفقد اجتماع")
    await message.answer("أدخل أسماء المتطوعين الحاضرين مفصولة بفاصلة (مثال: أحمد محمد, فاطمة علي):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_attendance_names)

@dp.message(lambda message: message.text == "تفقد مبادرة")
async def attendance_initiative(message: types.Message, state: FSMContext):
    logger.info(f"Attendance initiative from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await state.update_data(attendance_type="تفقد مبادرة")
    await message.answer("أدخل أسماء المتطوعين الحاضرين مفصولة بفاصلة (مثال: أحمد محمد, فاطمة علي):", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_attendance_names)

@dp.message(AdminStates.waiting_attendance_names)
async def admin_attendance_names(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    data = await state.get_data()
    attendance_type = data['attendance_type']
    names = message.text
    names_list = [name.strip() for name in names.split(',')]
    report = f"تقرير {attendance_type} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n\nالحاضرون:\n" + "\n".join(f"- {name}" for name in names_list)
    await bot.send_message(
        ATTENDANCE_GROUP_ID,
        report
    )
    await message.answer(f"تم إرسال تقرير {attendance_type} بنجاح! 🌟", reply_markup=admin_keyboard)
    await state.clear()

# Admin photo upload handlers
@dp.message(lambda message: message.text == "رفع صور الفريق")
async def admin_upload_photos_start(message: types.Message, state: FSMContext):
    logger.info(f"Admin upload photos from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    await message.answer("أرسل الصور الجديدة للفريق (يمكنك إرسال عدة صور): 💕", reply_markup=back_keyboard)
    await state.set_state(AdminStates.waiting_upload_photo)

@dp.message(AdminStates.waiting_upload_photo)
async def admin_upload_photo(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        await state.clear()
        return
    if message.photo:
        file_id = message.photo[-1].file_id
        team_photos.append({'file_id': file_id})
        await message.answer("تم رفع الصورة بنجاح! أرسل المزيد إذا أردت، أو /admin للعودة. 🌟", reply_markup=admin_keyboard)
    else:
        await message.answer("يرجى إرسال صورة فقط. 💕", reply_markup=admin_keyboard)
    # Stay in state to allow multiple uploads

# Admin photo delete handlers (keep inline for photos)
@dp.message(lambda message: message.text == "حذف صور الفريق")
async def admin_delete_photos_start(message: types.Message):
    logger.info(f"Admin delete photos from {message.from_user.id}")
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("غير مصرح لك!")
        return
    if not team_photos:
        await message.answer("لا توجد صور للحذف حالياً. 💕", reply_markup=admin_keyboard)
        return
    # Send all photos with delete buttons
    for idx, photo_info in enumerate(team_photos):
        delete_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="حذف هذه الصورة", callback_data=f"delete_photo_{idx}")],
            [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
        ])
        await bot.send_photo(
            message.chat.id,
            photo_info['file_id'],
            caption=f"صورة الفريق #{idx + 1}",
            reply_markup=delete_keyboard
        )
    await message.answer("اختر الصورة التي تريد حذفها من الرسائل أعلاه. شكراً لإدارتك! 🌹", reply_markup=admin_keyboard)

@dp.callback_query(F.data.startswith("delete_photo_"))
async def delete_photo(callback: types.CallbackQuery):
    logger.info(f"Delete photo callback: {callback.data} from {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("غير مصرح لك!")
        return
    try:
        idx = int(callback.data.split("_")[2])
        if 0 <= idx < len(team_photos):
            del team_photos[idx]
            await callback.message.edit_caption(
                caption=callback.message.caption + "\n\nتم الحذف بنجاح! 💖",
                reply_markup=None
            )
        else:
            await callback.answer("الصورة غير موجودة.")
    except Exception as e:
        logger.error(f"Error deleting photo: {e}")
        await callback.answer("حدث خطأ في الحذف.")
    await callback.answer()

# Startup function
async def on_startup(bot: Bot) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/webhook"
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
    await bot.set_webhook(url=webhook_url, secret_token=webhook_secret, allowed_updates=dp.resolve_used_update_types())
    info = await bot.get_webhook_info()
    logger.info(f"Webhook set to {webhook_url}, info: {info}")

# Main function
def main() -> None:
    dp.startup.register(on_startup)
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
    webhook_path = "/webhook"
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret,
    )
    webhook_requests_handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)
    port = int(os.getenv('PORT', 10000))
    host = '0.0.0.0'
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    main()
