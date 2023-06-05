from aiogram import Bot, Dispatcher, types
from aiogram.types.message import ContentType
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from prices import MARAPHON, VPN
from models import User

import paramiko
import requests
import config
from celery import Celery
from celery.schedules import crontab
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

client = Celery('profoto', broker=config.CELERY_BROKER_URL)
client.conf.result_backend = config.CELERY_RESULT_BACKEND
client.conf.timezone = 'Europe/Moscow'


client.conf.beat_schedule = {
    'check_subscription': {
        'task': 'handlers.check_subscription',
        'schedule': crontab(hour=config.CHECK_HOUR, minute=config.CHECK_MINUTE)
    }
}

bot = Bot(token=config.TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

@client.task()
def check_subscription():
    users = User.select()
    for user in users:
        expire = user.expire_in.strftime('%Y-%m-%d') 
        check = date.today() + timedelta(3)
        
        msg = 'До окончания вашей подписки осталось 3 дня. Оплатить можно командой\n/buy_vpn'
        
        if str(expire) == str(check):
            send_msg(user.user_id, msg)

def send_msg(chat_id, text):
    response = requests.post('https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}'.format(
        token = config.TELEGRAM_TOKEN,
        chat_id = chat_id,
        text = text
    ))
    
def send_document(chat_id, doc):
    '''
    response = requests.post('https://api.telegram.org/bot{token}/sendDocument?chat_id={chat_id}&document={doc}'.format(
        token = config.TELEGRAM_TOKEN,
        chat_id = chat_id,
        doc = '{name}.ovpn'.format(name=chat_id)
    ))
    '''
    url = 'https://api.telegram.org/bot{token}/sendDocument'.format(token=config.TELEGRAM_TOKEN)
    resp = requests.post(url, data={'chat_id': chat_id}, files={'document': doc})

    print(resp.json())

@client.task()
def create_vpn(data):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(config.HOSTNAME, config.PORT, config.USERNAME, config.PASSWORD)
    
    user_id = data['user_id']
    command = './add_user.sh {name}'.format(name=user_id)

    entry, is_new = User.get_or_create(
            user_id = user_id
        )
    if not is_new:
            data = {'expire_in': entry.expire_in + timedelta(30),
                'is_active': True,
                'is_freemium': False
                }
            query = User.update(data).where(User.user_id==user_id)
            query.execute()
            send_msg(user_id, 'Ваша подписка продлена!')
            return 100
    if is_new:
        msg_instruction = 'Инструкция по использованию:\n\n1. Скачай приложение\n\nДля Айфона:\nhttps://apps.apple.com/ru/app/openvpn-connect-openvpn-app/id590379981\n\nДля Андроида:\nhttps://play.google.com/store/apps/details?id=net.openvpn.openvpn\n'
        send_msg(user_id, msg_instruction)
        data = {'expire_in': date.today() + timedelta(30),
                'is_active': True,
                'is_freemium': False
                }
        query = User.update(data).where(User.user_id==user_id)
        query.execute()
        stdin, stdout, stderr = ssh_client.exec_command(command)
        with ssh_client.open_sftp() as sftp:
            name = user_id
            sftp.get('{name}.ovpn'.format(name=name), '{name}.ovpn'.format(name=name))
        doc = open('{name}.ovpn'.format(name=name), 'rb')
        send_document(user_id, doc)
        msg = '2.Открой файл {name}.ovpn в приложении OpenVPN Connect и нажми ADD.\n\nx3. Включи VPN и радуйся жизни!'.format(
            name=user_id
        )
        send_msg(user_id, msg)
        return 200
        

@dp.message_handler(commands=['start'])
async def start(message: types.message):
    await message.answer('Привет {name}!\nЗдесь ты можешь приобрести подписку на VPN\n/buy_vpn\n\nИли записаться на сдледующий марафон “Больше чем селфи 2.0”\n/buy_maraphone'.format(
        name=message.from_user.first_name
    ))

@dp.message_handler(commands=['check'])
async def start(message: types.message):
    users = User.select()
    for user in users:
        
        expire = user.expire_in.strftime('%Y-%m-%d')
        print(expire)
        check = date.today() + timedelta(3)
        print(check)
        if str(expire) == str(check):
            print('asd')
        #print(date.today())

@dp.message_handler(commands=['buy_maraphone'])
async def buy(message: types.Message):
    await bot.send_invoice(
        message.chat.id,
        title = 'Марафон "Больше чем селфи 2.0"',
        description = 'Двухнедельный марафон по фото и видео съемке себя',
        provider_token = config.PAYMENTS_TOKEN,
        currency = 'rub',
        #photo_url="https://milalink.ru/uploads/posts/2018-02/1518206226_selfi-zhizn-napokaz.jpg",
        #photo_width=416,
        #photo_height=234,
        #photo_size=416,
        is_flexible=False,
        prices=[MARAPHON],
        start_parameter="marafon-subscription",
        payload="maraphone-invoice-payload")

@dp.message_handler(commands=['buy_vpn'])
async def buy(message: types.Message):
    await bot.send_invoice(
        message.chat.id,
        title = 'Подписка на VPN',
        description = 'на 1 месяц',
        provider_token = config.PAYMENTS_TOKEN,
        currency = 'rub',
        #photo_url="https://milalink.ru/uploads/posts/2018-02/1518206226_selfi-zhizn-napokaz.jpg",
        #photo_width=416,
        #photo_height=234,
        #photo_size=416,
        is_flexible=False,
        prices=[VPN],
        start_parameter="vpn-subscription",
        payload="vpn-invoice-payload")

# pre checkout  (must be answered in 10 seconds)
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# successful payment
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    print("SUCCESSFUL PAYMENT:")
    payment_info = message.successful_payment.to_python()
    for k, v in payment_info.items():
        print(f"{k} = {v}")

    if payment_info['invoice_payload'] == 'vpn-invoice-payload':
        data = {}
        data['user_id'] = message.chat.id
        create_vpn.apply_async(args=[data])
        return await message.answer('Платеж прошел успешно! Обработаю информацию, это не займет много времени.')
        

    if payment_info['invoice_payload'] == 'maraphone-invoice-payload':
        await bot.send_message(message.chat.id,
                           f"Платеж на сумму {message.successful_payment.total_amount // 100} {message.successful_payment.currency} прошел успешно!!!\nСсылка на группу https://t.me/+1vSqZKna4RVjNWMy")
