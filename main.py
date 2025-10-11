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
# NOTE: Ensure BOT_TOKEN, CHAT_ADMIN_ID, RENDER_EXTERNAL_HOSTNAME, WEBHOOK_SECRET are set in your environment
TOKEN = os.getenv('BOT_TOKEN')
# Use a default ID if the environment variable is not set to prevent runtime errors
try:
    ADMIN_IDS = [int(os.getenv('CHAT_ADMIN_ID')), 5780307552]
except (TypeError, ValueError):
    ADMIN_IDS = [5780307552] # Fallback if primary admin ID is missing or invalid
    logger.warning("CHAT_ADMIN_ID not set or invalid. Using fallback admin ID only.")
    
# NOTE: Replace these with your actual chat IDs
EXCUSE_GROUP_ID = -4737111167  # Chat ID for the excuses group
LEAVE_GROUP_ID = -4868672688  # Chat ID for the leave group
ATTENDANCE_GROUP_ID = -4966592161  # Chat ID for the attendance group

# Bot and Dispatcher setup
if not TOKEN:
    logger.error("BOT_TOKEN is not set. Bot cannot run.")
    
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global variables
request_counter = 1
users = set() # Stores user IDs who have interacted with the bot
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
    "سبحان الله",
    "الحمدلله",
    "لا إله إلا الله",
    "الله اكبر",
    "سبحان الله وبحمده",
    "سبحان الله العظيم"
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
        [KeyboardButton(text="تقييم سري")], # تم التعديل هنا
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
    waiting_other_suggestion = State() # تُستخدم الآن للاقتراحات/التقييمات السرية
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
            await bot.send_message(admin_id, text, parse_mode=ParseMode.MARKDOWN)
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
@dp.message(F.text == "رجوع")
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
@dp.message(F.text == "اقتراحات")
async def feedback_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await message.answer("شكراً لاهتمامك بتقديم اقتراح! اختر نوع الاقتراح: 💕", reply_markup=feedback_keyboard)
    await state.set_state(FeedbackStates.waiting_type)
    logger.info(f"Feedback state set for user {message.from_user.id}")

@dp.message(F.text == "اقتراح تطوير البوت", StateFilter(FeedbackStates.waiting_type))
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
        f"**اقتراح تطوير البوت:**\n"
        f"**المرسل:** {user_name} (ID: {message.from_user.id})\n"
        f"**الاقتراح:** {suggestion_text}\n\n"
        f"**تاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await message.answer("شكراً جزيلاً لاقتراحك! سنراجعه بعناية لتحسين تجربتك معنا. 🌟", reply_markup=main_keyboard)
    await state.clear()

# --- التعديل هنا: استخدام "تقييم سري" ---
@dp.message(F.text == "تقييم سري", StateFilter(FeedbackStates.waiting_type))
async def feedback_secret_start(message: types.Message, state: FSMContext):
    logger.info(f"Secret feedback initiated by {message.from_user.id}")
    users.add(message.from_user.id)
    
    await message.answer(
        "📝 **التقييم السري**\n\n"
        "أهلاً بك! نحن نقدّر صراحتك. يرجى كتابة تقييمك/اقتراحك كاملاً. **لن يتم إرسال هويتك** (لا اسم ولا معرّف) إلى الإدارة. كن صريحاً! 💕", 
        reply_markup=back_keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    # نستخدم نفس حالة الاقتراح الآخر
    await state.set_state(FeedbackStates.waiting_other_suggestion)


@dp.message(FeedbackStates.waiting_other_suggestion)
async def feedback_secret_message(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    suggestion_text = message.text
    
    # إرسال الرسالة إلى الأدمنز بدون أي بيانات تعريفية
    await send_to_admins(
        f"**📣 تقييم سري جديد 📣**\n"
        f"**المرسل:** (مجهول الهوية - حفاظاً على الخصوصية)\n"
        f"**الرسالة:**\n{suggestion_text}\n\n"
        f"**تاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # إرسال رسالة شكر للمستخدم
    await message.answer(
        "شكراً جزيلاً لتقييمك الصادق! تم إرسال رسالتك بصفة **سرية تامة** للإدارة. نحن نقدر صراحتك! 🌟", 
        reply_markup=main_keyboard
    )
    await state.clear()
# --- نهاية التعديل ---

@dp.message(F.text == "اقتراح مبادرة", StateFilter(FeedbackStates.waiting_type))
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
        f"**اقتراح مبادرة جديد:**\n"
        f"**المرسل:** {user_name} (ID: {message.from_user.id})\n\n"
        f"**إسم المبادرة الرئيسي:** {data['initiative_name']}\n"
        f"**مقدمة المبادرة:** {data['initiative_intro']}\n"
        f"**أهداف المبادرة:** {data['initiative_goals']}\n"
        f"**الفئة المستهدفة:** {data['initiative_target']}\n"
        f"**خطة العمل:** {data['initiative_plan']}\n"
        f"**الموارد المطلوبة:** {data['initiative_resources']}\n"
        f"**الشركاء والداعمين:** {data['initiative_partners']}\n"
        f"**الجدول الزمني:** {data['initiative_timeline']}\n"
        f"**قياس النجاح:** {message.text}\n\n"
        f"**تاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await send_to_admins(initiative_report)
    await message.answer("شكراً جزيلاً لاقتراحك! سنراجعه بعناية. 🌟", reply_markup=main_keyboard)
    await state.clear()

# Excuse handlers
@dp.message(F.text == "اعتذار")
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

@dp.message(F.text == "تأكيد الطلب", StateFilter(ExcuseStates.waiting_confirm))
async def confirm_excuse(message: types.Message, state: FSMContext):
    logger.info(f"Confirm excuse from {message.from_user.id}")
    global request_counter
    users.add(message.from_user.id)
    data = await state.get_data()
    user_id = message.from_user.id
    request_id = request_counter
    request_counter += 1
    activity_details = f"نوع النشاط: {data.get('activity_type', 'غير محدد')}\nالسبب: {data.get('reason', 'غير محدد')}"
    await message.answer(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕", reply_markup=main_keyboard)
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}_{user_id}")
        ]
    ])
    await bot.send_message(
        EXCUSE_GROUP_ID,
        f"**طلب اعتذار جديد #{request_id}**\n"
        f"**مقدم الطلب:** {data['name']}\n"
        f"**رقم الطلب:** {request_id}\n"
        f"{activity_details}",
        reply_markup=admin_keyboard
    )
    await state.clear()

# Leave handlers
@dp.message(F.text == "إجازة")
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

@dp.message(F.text == "تأكيد الطلب", StateFilter(LeaveStates.waiting_confirm))
async def confirm_leave(message: types.Message, state: FSMContext):
    logger.info(f"Confirm leave from {message.from_user.id}")
    global request_counter
    users.add(message.from_user.id)
    data = await state.get_data()
    user_id = message.from_user.id
    request_id = request_counter
    request_counter += 1
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    await message.answer(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕", reply_markup=main_keyboard)
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}_{user_id}")
        ]
    ])
    await bot.send_message(
        LEAVE_GROUP_ID,
        f"**طلب إجازة جديد #{request_id}**\n"
        f"**مقدم الطلب:** {data['name']}\n"
        f"**رقم الطلب:** {request_id}\n"
        f"**سبب الإجازة:** {data['reason']}\n"
        f"**التفاصيل:** {details}",
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
    await callback.message.edit_text(callback.message.text + "\n\n**تم القبول.**")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    logger.info(f"Reject callback: {callback.data} from {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("مين قلك أنك آدمن ؟!")
