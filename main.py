import os
import random
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
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

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('CHAT_ADMIN_ID'))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

request_counter = 1
users = set()

meeting_schedules = {
    'الاجتماع العام': 'غير محدد',
    'اجتماع فريق الدعم الاول': 'غير محدد',
    'فريق الدعم الثاني': 'غير محدد',
    'الفريق المركزي': 'غير محدد'
}

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

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="اعتذار"), KeyboardButton(text="إجازة")],
        [KeyboardButton(text="تتبع طلباتي"), KeyboardButton(text="مراجع الفريق")],
        [KeyboardButton(text="أهدني عبارة"), KeyboardButton(text="لا تنس ذكر الله")],
        [KeyboardButton(text="استعلامات")]
    ],
    resize_keyboard=True
)

motivational_phrases = [
    "العمل الخيري هو بذرة الأمل في قلوب الناس، ازرعها وستحصد الابتسامات!",
    "في كل يد تمتد للمساعدة، ينبت أمل جديد. استمر في إشراقك مع فريق أبناء الأرض!",
    "الأمل يبدأ بخطوة صغيرة، وأنت جزء من هذه الخطوات العظيمة. شكراً لتطوعك!",
    "كل جهد يبذل في سبيل الخير يعود بالبركة. كن مصدر إلهام دائماً!",
    "مع فريق أبناء الأرض، نبني جسور الأمل. أنت بطل هذه القصة!"
]

dhikr_phrases = [
    "سبحان الله\nالحمدلله\nلا إله إلا الله\nالله اكبر\nسبحان الله وبحمده\nسبحان الله العظيم"
]

@dp.message(lambda message: message.text == "رجوع")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕", reply_markup=main_keyboard)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_inline(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("تم العودة إلى القائمة الرئيسية. نحن هنا لمساعدتك دائماً! 💕", reply_markup=None)
    await callback.message.answer("اختر الخيار الذي تريده:", reply_markup=main_keyboard)
    await callback.answer()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    users.add(message.from_user.id)
    await message.answer(
        "مرحباً بك في بوت شؤون الموارد البشرية لفريق أبناء الأرض! 🌟\n"
        "نحن مبسوطين بوجودك معنا، و رح نكون دائماً جنبك  برحلتك التطوعية. 💖\n"
        "اختر الخيار الذي تريده:",
        reply_markup=main_keyboard
    )

@dp.message(lambda message: message.text == "اعتذار")
async def excuse_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما اسمك الكامل؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(ExcuseStates.waiting_name)

@dp.message(ExcuseStates.waiting_name)
async def excuse_name(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(name=message.text)
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
    users.add(message.from_user.id)
    data = await state.get_data()
    activity_type = message.text
    if activity_type == "آخر":
        await state.update_data(activity_type="آخر")
        back_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="رجوع")]],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        await message.answer("نحن نفهم أن الحياة مليئة بالمفاجآت، يرجى توضيح العمل الذي تريد الاعتذار عنه: 💕", reply_markup=back_keyboard)
        await state.set_state(ExcuseStates.waiting_reason)
    else:
        await state.update_data(activity_type=activity_type)
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
    users.add(message.from_user.id)
    data = await state.get_data()
    data['reason'] = message.text
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

@dp.callback_query(lambda c: c.data == "confirm_excuse", ExcuseStates.waiting_confirm)
async def confirm_excuse(callback: types.CallbackQuery, state: FSMContext):
    global request_counter
    users.add(callback.from_user.id)
    data = await state.get_data()
    user_id = callback.from_user.id
    request_id = request_counter
    request_counter += 1
    activity_details = f"نوع النشاط: {data.get('activity_type', 'غير محدد')}\nالسبب: {data.get('reason', 'غير محدد')}"
    await callback.message.edit_text(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
    await callback.answer()
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_excuse_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_excuse_{request_id}_{user_id}")
        ]
    ])
    await bot.send_message(
        ADMIN_ID,
        f"طلب اعتذار جديد #{request_id}\n"
        f"مقدم الطلب: {data['name']}\n"
        f"رقم الطلب: {request_id}\n"
        f"{activity_details}",
        reply_markup=admin_keyboard
    )
    await state.clear()

@dp.message(lambda message: message.text == "إجازة")
async def leave_start(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما اسمك الكامل كمتطوع؟ نحن نقدر جهودك دائماً! 😊", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_name)

@dp.message(LeaveStates.waiting_name)
async def leave_name(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(name=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer(f"اهلييين {message.text}، سعيدون بك معنا! 🌹\nما سبب الإجازة؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_reason)

@dp.message(LeaveStates.waiting_reason)
async def leave_reason(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(reason=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما مدة الإجازة (بالأيام)؟ نتمنى لك وقتاً جميلاً! 💕", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_duration)

@dp.message(LeaveStates.waiting_duration)
async def leave_duration(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(duration=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما تاريخ بدء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_start_date)

@dp.message(LeaveStates.waiting_start_date)
async def leave_start_date(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    await state.update_data(start_date=message.text)
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("ما تاريخ انتهاء الإجازة (YYYY-MM-DD)؟", reply_markup=back_keyboard)
    await state.set_state(LeaveStates.waiting_end_date)

@dp.message(LeaveStates.waiting_end_date)
async def leave_end_date(message: types.Message, state: FSMContext):
    users.add(message.from_user.id)
    data = await state.get_data()
    data['end_date'] = message.text
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
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

@dp.callback_query(lambda c: c.data == "confirm_leave", LeaveStates.waiting_confirm)
async def confirm_leave(callback: types.CallbackQuery, state: FSMContext):
    global request_counter
    users.add(callback.from_user.id)
    data = await state.get_data()
    user_id = callback.from_user.id
    request_id = request_counter
    request_counter += 1
    details = f"مدة: {data['duration']} أيام\nتاريخ البدء: {data['start_date']}\nتاريخ الانتهاء: {data['end_date']}"
    await callback.message.edit_text(f"شكراً لك يا {data['name']}، طلبك #{request_id} وصلنا بسلام! سنعالجه بكل حب قريباً. 💕")
    await callback.answer()
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول", callback_data=f"approve_leave_{request_id}_{user_id}"),
            InlineKeyboardButton(text="رفض", callback_data=f"reject_leave_{request_id}_{user_id}")
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

@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])
    await bot.send_message(user_id, f" ابشر! 🎉 تم قبول طلبك #{request_id} بكل فرحة. نحن فخورون بك! 💖")
    await callback.message.edit_text(callback.message.text + "\n\nتم القبول.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("مين قلك أنك آدمن ؟!")
        return
    parts = callback.data.split("_")
    request_type = parts[1]
    request_id = parts[2]
    user_id = int(parts[3])
    await bot.send_message(user_id, f"نأسف لإخبارك بذلك، 😔 تم رفض طلبك #{request_id}. يرجى التواصل مع الإدارة للمزيد من التفاصيل. نحن هنا لدعمك!")
    await callback.message.edit_text(callback.message.text + "\n\nتم الرفض.")
    await callback.answer()

@dp.message(lambda message: message.text == "تتبع طلباتي")
async def track_start(message: types.Message, state: FSMContext):
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="رجوع")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer(" ميزة التتبع لسا ما جهزت . حكي محمد الجرك مطور البوت و المسؤول اللطيف. 💕", reply_markup=back_keyboard)

@dp.message(lambda message: message.text == "مراجع الفريق")
async def references_handler(message: types.Message):
    refs_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="مدونة السلوك", callback_data="code_of_conduct")],
        [InlineKeyboardButton(text="بنود وقوانين الفريق", callback_data="rules")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await message.answer("نحن فخورون بقيمنا في فريق أبناء الأرض! 🌟\nاختر المرجع:", reply_markup=refs_keyboard)

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

@dp.message(lambda message: message.text == "أهدني عبارة")
async def phrase_handler(message: types.Message):
    phrase = random.choice(motivational_phrases)
    await message.answer(f"إليك عبارة تحفيزية من القلب: {phrase} 💖", reply_markup=main_keyboard)

@dp.message(lambda message: message.text == "🤍لا تنسَ ذكر الله")
async def dhikr_handler(message: types.Message):
    dhikr = "\n".join(dhikr_phrases)
    await message.answer(f"اللهم اجعل هذا الذكر نوراً لقلبك: {dhikr} 🌟", reply_markup=main_keyboard)

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
        [InlineKeyboardButton(text="اجتماع فريق الدعم الثاني", callback_data="meeting_support2")],
        [InlineKeyboardButton(text="اجتماع الفريق المركزي", callback_data="meeting_central")],
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("اختر الاجتماع الذي تهتم به: 😊", reply_markup=meeting_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_general")
async def meeting_general(callback: types.CallbackQuery):
    date = meeting_schedules.get('الاجتماع العام', 'لسا ما تحدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد الاجتماع العام: {date}\n\nنحن نتطلع للقائك هناك! 🌹", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_support1")
async def meeting_support1(callback: types.CallbackQuery):
    date = meeting_schedules.get('اجتماع فريق الدعم الاول', 'لسا ما تحدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد اجتماع فريق الدعم الاول: {date}\n\nمعاً نبني الدعم الأقوى! 💪", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_support2")
async def meeting_support2(callback: types.CallbackQuery):
    date = meeting_schedules.get('فريق الدعم الثاني', 'لسا ما تحدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد فريق الدعم الثاني: {date}\n\nدعمكم يلهمنا دائماً! 😊", reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "meeting_central")
async def meeting_central(callback: types.CallbackQuery):
    date = meeting_schedules.get('الفريق المركزي', 'لسا ما تحدد')
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رجوع", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(f"موعد الفريق المركزي: {date}\n\nمركزنا هو قلب الفريق! ❤️", reply_markup=back_keyboard)
    await callback.answer()

@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("مين قلك أنك آدمن ؟!")
        return
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="وضع موعد الاجتماع العام", callback_data="admin_general")],
        [InlineKeyboardButton(text="وضع موعد دعم أول", callback_data="admin_support1")],
        [InlineKeyboardButton(text="وضع موعد دعم ثاني", callback_data="admin_support2")],
        [InlineKeyboardButton(text="وضع موعد مركزي", callback_data="admin_central")],
        [InlineKeyboardButton(text="إرسال بث للجميع", callback_data="admin_broadcast")]
    ])
    await message.answer("لوحة التحكم للأدمن: نحن فخورون بإدارتك الرائعة! 🌟", reply_markup=admin_keyboard)
    await state.set_state(AdminStates.waiting_meeting_type)

@dp.callback_query(lambda c: c.data == "admin_general")
async def admin_general(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("رو من هان مانك آدمن ")
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
        await callback.answer("كاشفك ، مانك آدمن 😝")
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
    meeting_schedules[meeting_type] = meeting_date
    await message.answer(f"تم حفظ موعد {meeting_type}: {meeting_date}\nشكراً لك، أنت تجعل فريقنا أقوى! 🌹", reply_markup=main_keyboard)
    await state.clear()

# معالج زر البث في لوحة الأدمن
@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("غير مصرح لك!")
        return
    await callback.message.edit_text("أدخل الرسالة التي تريد إرسالها لجميع المستخدمين:")
    await state.set_state(AdminStates.waiting_broadcast_message)
    await callback.answer()

@dp.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_message(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("قعود عاقل و حاج تبعت")
        await state.clear()
        return
    broadcast_msg = message.text
    sent_count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, broadcast_msg)
            sent_count += 1
            await asyncio.sleep(0.05)  # تأخير قصير لتجنب rate limit
        except Exception as e:
            logging.error(f"Failed to send to {user_id}: {e}")
    await message.answer(f"تم إرسال الرسالة إلى {sent_count} مستخدم. شكراً لك! 💖", reply_markup=main_keyboard)
    await state.clear()

# دالة التشغيل الرئيسية عند بدء البوت
async def on_startup(bot: Bot) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/webhook"
    webhook_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
    await bot.set_webhook(url=webhook_url, secret_token=webhook_secret)
    logging.info(f"Webhook set to {webhook_url}")

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
