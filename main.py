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

# قائمة المستخدمين (set لتجنب التكرار، في الذاكرة)
users = set()

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
    waiting_broadcast_message = State()  # انتظار رسالة البث

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
    "الأمل يبدأ بخطوة صغيرة، وأنت جزء من هذه الخطوات العظيمة
