#_______ системные модули
import sqlite3 as sqlite
import telebot
import threading # для отложенных сообщений
from multiprocessing import Process
from time import sleep
import re
from datetime import datetime, date, time, timedelta
import json
from telebot import types
from peewee import *
from playhouse.sqlite_ext import *
from playhouse.shortcuts import model_to_dict, dict_to_model # для сериализации peewee-объектов во время логирования ошибок
# ______ модули приложения
import config as cfg 
import strings as s # все строки хранятся здесь
import check # различные проверки: правильно ли юзер ввёл рост/вес/etc
from functions import send_mail 
from channels import Group

# импорт моделей
from bot_models import User
from bot_models import Routing
from bot_models import Trainer
from bot_models import Error
from bot_models import Photo
from bot_models import Message
from bot_models import Schedule


# README
#
# Shortcuts:
#	sid 	= sender chat id
#	m 		= message
#	cog 	= create_or_get
#	c 		= call

class TeleBot(telebot.TeleBot):
	def send_message(self, chat_id, text, disable_web_page_preview=None, reply_to_message_id=None, reply_markup=None, parse_mode=None, disable_notification=None):
		Message.create(sender = bot_id, sender_type = "bot", receiver = chat_id, text = text)
		response = super().send_message(chat_id, text, disable_web_page_preview, reply_to_message_id, reply_markup, parse_mode, disable_notification)
		# print('RESPONSE:')
		# print(response)


bot = TeleBot(cfg.token)
bot_id = cfg.token.split(":")[0]
# db = SqliteDatabase('../db.sqlite3')
# db = SqliteDatabase('bot.db')

sid = lambda m: m.chat.id # лямбды для определения адреса ответа
uid = lambda m: m.from_user.id
cid = lambda c: c.message.chat.id

# _____________ FUNCTIONS

def delay(func): # отсылка сообщений с задержкой
    def delayed(*args, **kwargs):
        chat_id, m = args
        u = User.get(user_id = chat_id)
        u.state = s.stop
        u.save()
        timer = threading.Timer(kwargs['delay'], func, args=args, kwargs=kwargs)
        timer.start()
    return delayed


@delay
def send_message_delay(chat_id, m, state=None, delay = 0, reply_markup=None, disable_notification=None, parse_mode = 'Markdown'):
	u = User.get(user_id = chat_id)
	if state != None:
		u.state = state
	u.save()
	bot.send_message(chat_id, m, reply_markup=reply_markup, parse_mode=parse_mode, disable_notification=disable_notification)


@delay
def send_photo_delay(chat_id, p, state=None, delay = 0, disable_notification=None):
	u = User.get(user_id = chat_id)
	if state != None:
		u.state = state
	u.save()
	bot.send_photo(chat_id, p, disable_notification=disable_notification)

def schedule(dt, action, **kwargs):
	dt = dt.replace(second = 0, microsecond = 0)
	try:
		Schedule.create(timestamp = dt, action = action, arguments = json.dumps(kwargs))
	except Exception as e:
		print(e)


# _____________ END FUNCTIONS

# _____________ ACTIONS


def cancel(u, c):
	u.state = s.stop
	u.save()
	bot.send_message(chat_id, s.canceled_course)


def confirm_name(u, c):
	u.state = s.lets_confirm_name
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	agree_btn = types.InlineKeyboardButton(text = s.my_name_is_btn.format(u.first_name), callback_data = s.agree)
	keyboard.add(agree_btn)
	bot.send_message(cid(c), s.confirm_name.format(u.first_name), reply_markup = keyboard)





def confirm_last_name(u, m = None, c = None): # получает имя (текстом) или подтверждение того, что мы правильно записали его имя
	if m != None:
		chat_id = uid(m)
		u.first_name = m.text
		keyboard = types.InlineKeyboardMarkup()
		bot.edit_message_reply_markup(uid(m), message_id = int(m.message_id) - 1, reply_markup = keyboard)
	else:
		chat_id = cid(c)
	u.state = s.lets_confirm_last_name
	u.save()	
	keyboard = types.InlineKeyboardMarkup()
	if u.last_name != None:
		agree_btn = types.InlineKeyboardButton(text = s.my_last_name_is_btn.format(u.last_name), callback_data = s.agree)
		keyboard.add(agree_btn)
		bot.send_message(chat_id, s.confirm_last_name.format(u.last_name), reply_markup = keyboard)
		return
	bot.send_message(chat_id, s.type_last_name.format(u.last_name), reply_markup = keyboard)


def select_sex(u, m = None, c = None):
	if m != None:
		chat_id = uid(m)
		u.last_name = m.text
		keyboard = types.InlineKeyboardMarkup()
		try:
			bot.edit_message_reply_markup(uid(m), message_id = int(m.message_id) - 1, reply_markup = keyboard)
		except Exception as e:
			print(e)
	else:
		chat_id = cid(c)
	u.state = s.sex
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	male_btn = types.InlineKeyboardButton(text = s.male_btn, callback_data = s.male)
	female_btn = types.InlineKeyboardButton(text = s.female_btn, callback_data = s.female)
	keyboard.add(male_btn, female_btn)
	bot.send_message(chat_id, s.male_or_female, reply_markup = keyboard)


def type_age(u, c = None):
	u.sex = c.data
	u.state = s.age
	u.save()
	bot.send_message(cid(c), s.type_age)


def incorrect_age(u, m):
	bot.send_message(uid(m), s.incorrect_age)


def type_email(u, m):
	if not check.age(m.text):
		incorrect_age(u, m)
		return False
	u.age = check.age(m.text)
	u.state = s.email
	u.save()
	bot.send_message(uid(m), s.type_email)

def incorrect_email(m):
	bot.send_message(uid(m), s.incorrect_email)


def video_intro(u, m):
	if not check.email(m.text):
		incorrect_email(m)
		return False
	u.email = check.email(m.text)
	u.save()
	bot.send_message(uid(m), s.who_we_are.format(s.intro_link)) # отправим видео
																 # и через 5 минут -- продолжаем
	keyboard = types.InlineKeyboardMarkup()
	agree_btn = types.InlineKeyboardButton(text = s.agree_btn, callback_data = s.agree)			
	keyboard.add(agree_btn)						
	send_message_delay(uid(m), s.are_we_continuing, delay = 5, state = s.video_intro, reply_markup = keyboard)


def present_trainer(u, c):
	tes = Trainer.select().order_by(fn.Random()).limit(1)
	for t in tes:
		pass
		# print(t.first_name)

	u.trainer_id = t.id
	# u.state = s.trainer
	u.save()
	photo = open("images/trainers/{}".format(t.photo), 'rb')
	bot.send_photo(cid(c), photo, s.your_trainer.format(t.first_name, t.last_name))
	send_message_delay(cid(c), s.what_to_do.format(s.next_3_days_link), delay = 3, state = s.trainer, parse_mode = 'HTML') # присвоен тренер

	keyboard = types.InlineKeyboardMarkup()
	agree_btn = types.InlineKeyboardButton(text = s.agree_btn, callback_data = s.agree)			
	disagree_btn = types.InlineKeyboardButton(text = s.disagree_btn, callback_data = s.disagree)			
	keyboard.add(agree_btn, disagree_btn)	
	send_message_delay(cid(c), s.are_you_ready, delay = 6, state = s.ready, reply_markup = keyboard, disable_notification = True) # "Вы готовы?"


def remind_1(u, c):
	u.state = s.stop
	u.save()
	# bot.send_message(chat_id, s.waiting_from_you, parse_mode = 'Markdown')
	img = open("images/system/img4.jpeg", "rb")
	bot.send_photo(cid(c), img)

	files = ['files/Анализы.pdf', 'files/Анкета.docx', 'files/Анкета физактивность.docx']
	send_mail(u.email, s.your_documents, s.your_documents, files = files)

	img = open("images/system/img2.jpeg", "rb")
	send_photo_delay(cid(c), img, delay=3, state = s.stop)
	img = open("images/system/img1.jpeg", "rb")
	send_photo_delay(cid(c), img, delay=6, state = s.stop)
	# send_message_delay(chat_id, s.fact_finding_remind, delay=3, state = s.stop)

	keyboard = types.InlineKeyboardMarkup()
	continue_btn = types.InlineKeyboardButton(text = s.continue_btn, callback_data = s.agree)
	keyboard.add(continue_btn)
	send_message_delay(cid(c), s.we_sent_mail, delay=9, state = s.remind_1, reply_markup = keyboard)


def city(u, c):
	u.state = s.city
	u.save()
	bot.send_message(cid(c), s.type_city)


def job(u, m):
	u.city = m.text
	u.state = s.job
	u.save()
	bot.send_message(uid(m), s.type_job)


def height(u, m):
	u.job = m.text
	u.state = s.height
	u.save()
	bot.send_message(uid(m), s.type_height)


def incorrect_height(chat_id):
	bot.send_message(chat_id, s.incorrect_height)


def weight(u, m):
	if not check.height(m.text):
		incorrect_height(uid(m))
		return False
	u.height = check.height(m.text)
	u.state = s.weight
	u.save()
	bot.send_message(uid(m), s.type_weight)


def incorrect_weight(chat_id):
	bot.send_message(chat_id, s.incorrect_weight)


def target_weight(u, m):
	if not check.weight(m.text):
		incorrect_weight(uid(m))
		return False
	u.state = s.target_weight
	u.weight = m.text
	u.save()
	bot.send_message(uid(m), s.type_target_weight)


def methodologies(u, m):
	# u.state = s.methodologies
	u.target_weight = m.text
	u.save()
	bot.send_message(uid(m), s.thanks_for_answers)
	send_message_delay(uid(m), s.type_methodologies, delay=5, state = s.methodologies)


def most_difficult(u, m):
	u.methodologies = m.text
	u.state = s.most_difficult
	u.save()
	bot.send_message(uid(m), s.type_most_difficult)


def was_result(u, m):
	u.most_difficult = m.text
	u.state = s.was_result
	u.save()
	bot.send_message(uid(m), s.type_was_result)


def why_fat_again(u, m):
	u.was_result = m.text
	u.state = s.why_fat_again
	u.save()
	bot.send_message(uid(m), s.type_why_fat_again)	


def waiting_from_you(u, m):
	u.why_fat_again = m.text
	u.state = s.waiting_from_you
	u.save()

	img = open("images/system/img4.jpeg", "rb") # "напоминаем что ждём от вас"
	bot.send_photo(uid(m), img)

	# устанавливаем отправку сообщения на 21.00
	dt = datetime.now()
	dt = dt.replace(hour = 21, minute = 0)
	schedule(dt, "thanks_for_efforts", user_id = uid(m))
	dt = dt.replace(minute = 30)
	schedule(dt, "waiting_sticker", user_id = uid(m))
	# send_message_delay(uid(m), s.thanks_for_efforts, delay = 15)

	send_message_delay(uid(m), s.food_romance, delay = 15)
	send_message_delay(uid(m), s.measurements_link, delay = 25)
	send_mail(u.email, "Замеры тела", s.measurements_link)

	dt = datetime.now()
	dt = dt.replace(hour = 10, minute = 0)
	delta = timedelta(days = 1)
	schedule(dt + delta, "day_2", user_id = uid(m))
	

def thanks_for_efforts(user_id):
	bot.send_message(user_id, s.thanks_for_efforts)

def waiting_sticker(user_id):
	img = open("images/system/img4.jpeg", "rb") # "напоминаем что ждём от вас"
	bot.send_photo(user_id, img)


# _________ Day 2

def day_2(user_id):
	# u = User.get(user_id = user_id)
	# u.state = s.day_2
	# u.save()
	bot.send_message(user_id, s.greeting_2)	
	img = open("images/system/img4.jpeg", "rb") # "напоминаем что ждём от вас"
	bot.send_photo(user_id, img)
	send_message_delay(user_id, s.day_2_start, state = s.day_2, delay = 10)
	send_message_delay(user_id, "Продолжайте присылать фото всего, что Вы едите и пьёте", delay = 20)

def tolerancy(u, m):
	u.state = s.tolerancy
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	looked_btn = types.InlineKeyboardButton(text = s.looked_btn, callback_data = s.agree)
	keyboard.add(looked_btn)
	bot.send_message(uid(m), s.tolerancy_movie, reply_markup = keyboard)

def when_start_fat(u, m = None, c = None):
	if m:
		chat_id = uid(m)
	else:
		chat_id = cid(c)
	u.state = s.start_fat
	u.save()
	bot.send_message(chat_id, s.when_start_fat)

def why_fat_now(u, m):
	u.state = s.why_fat
	u.start_fat = m.text
	u.save()
	bot.send_message(uid(m), s.why_fat_now)

def hormonals(u, m):
	u.state = s.hormonals
	u.why_fat_now = m.text
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	disagree_btn = types.InlineKeyboardButton(text = s.disagree_btn, callback_data = s.disagree)
	keyboard.add(disagree_btn)
	bot.send_message(uid(m), s.hormonal_acception, reply_markup = keyboard)

def last_analyzes(u, m = None, c = None):
	if m != None:
		chat_id = uid(m)
		u.hormonals = m.text
		keyboard = types.InlineKeyboardMarkup()
		try:
			bot.edit_message_reply_markup(uid(m), message_id = int(m.message_id) - 1, reply_markup = keyboard)
		except Exception as e:
			print(e)
	else:
		chat_id = cid(c)
	u.state = s.last_analyzes
	u.save()
	bot.send_message(chat_id, s.last_analyzes_and_what)

def not_eat(u, m):
	u.analyzes = m.text
	u.state = s.not_eat
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	meat_btn = types.InlineKeyboardButton(text = s.meat_btn, callback_data = s.meat)
	fish_btn = types.InlineKeyboardButton(text = s.fish_btn, callback_data = s.fish)
	seafood_btn = types.InlineKeyboardButton(text = s.seafood_btn, callback_data = s.seafood)
	milk_btn = types.InlineKeyboardButton(text = s.milk_btn, callback_data = s.milk)
	fowl_btn = types.InlineKeyboardButton(text = s.fowl_btn, callback_data = s.fowl)
	eat_all_btn = types.InlineKeyboardButton(text = s.eat_all_btn, callback_data = s.eat_all)
	keyboard.add(meat_btn)
	keyboard.add(fish_btn)
	keyboard.add(seafood_btn)
	keyboard.add(milk_btn)
	keyboard.add(fowl_btn)
	keyboard.add(eat_all_btn)
	bot.send_message(uid(m), s.not_eat_products, reply_markup=keyboard)

def allergy(u, m = None, c = None):
	if m != None:
		u.not_eat = m.text
		keyboard = types.InlineKeyboardMarkup()
		try:
			bot.edit_message_reply_markup(uid(m), message_id = int(m.message_id) - 1, reply_markup = keyboard)
		except Exception as e:
			print(e)
	else:
		u.not_eat = c.data
	u.state = s.allergy
	u.save()
	bot.send_message(u.user_id, s.any_allergies)


def day_2_end(u, m):
	u.allergy = m.text
	u.state = s.pause 
	u.save()

	dt = datetime.now()
	dt = dt.replace(hour = 10, minute = 0)
	delta = timedelta(days = 1)
	schedule(dt + delta, "day_3", user_id = uid(m))
	img = open("images/system/img4.jpeg", "rb") # "напоминаем что ждём от вас"
	send_photo_delay(uid(m), img, state = s.pause, delay = 2)


# day 3
def day_3(user_id):
	bot.send_message(user_id, s.greeting_3)
	send

	img = open("images/system/img4.jpeg", "rb") # "напоминаем что ждём от вас"
	send_photo_delay(uid(m), img, delay = 15)




	





# _________ Day 3






















	


# _____________ END ACTIONS

@bot.message_handler(commands = ['ping'])
def ping(m):
	bot.send_message(uid(m), "I'm alive")


@bot.message_handler(commands = ['init'])
def init(m):
	User.create_table(fail_silently = True)
	# Trainer.create_table(fail_silently = True)
	# Routing.create_table(fail_silently = True)
	# Error.create_table(fail_silently = True)
	# Photo.create_table(fail_silently = True)
	# Schedule.create_table(fail_silently = True)



@bot.message_handler(commands = ['start'])
def start(m):
	# print(u, m)
	u = User.cog(user_id = uid(m), username = m.from_user.username, first_name = m.from_user.first_name, last_name = m.from_user.last_name)
	u.state = s.default
	u.save()
	keyboard = types.InlineKeyboardMarkup()
	agree_btn = types.InlineKeyboardButton(text = s.agree_btn, callback_data = s.agree)
	disagree_btn = types.InlineKeyboardButton(text = s.disagree_btn, callback_data = s.disagree)
	more_btn = types.InlineKeyboardButton(text = s.more_btn, url = "http://1fitchat.ru")
	keyboard.add(agree_btn)
	keyboard.add(disagree_btn)
	keyboard.add(more_btn)
	bot.send_message(uid(m), s.greeting, reply_markup = keyboard, parse_mode = "Markdown")


@bot.callback_query_handler(func=lambda call: True)
def clbck(c):
	chat_id = cid(c)
	u = User.cog(user_id = cid(c))
	Message.create(sender = cid(c), sender_type = "user", receiver = bot_id, text = c.data, msg_type = 'text')
	try:
		r = Routing.get(state = u.state, decision = c.data)
		keyboard = types.InlineKeyboardMarkup()
		bot.edit_message_reply_markup(chat_id = cid(c), message_id = c.message.message_id, reply_markup = keyboard)
		bot.answer_callback_query(callback_query_id = c.id, show_alert = True)

		try: # на случай если action не определён в таблице роутинга
			if u.state != s.stop:
				eval(r.action)(u = u, c = c)
		except Exception as e:
			Error.create(message = c.data, state = u.state, exception = e)
			print(e)
			print(s.action_not_defined)
	except Exception as e:
		Error.create(message = c.data, state = u.state, exception = e)
		print(e)
	



@bot.message_handler(content_types = ['text'])
def action(m):
	chat_id = sid(m)
	u = User.cog(user_id = uid(m))
	Message.create(sender = uid(m), sender_type = "user", receiver = bot_id, text = m.text)
	if u.state == s.canceled:
		return False
	try:
		r = Routing.get(state = u.state, decision = 'text')
		try: # на случай если action не определён в таблице роутинга
			if u.state != s.stop:
				eval(r.action)(u = u, m = m)
		except Exception as e:
			Error.create(message = m.text, state = u.state, exception = e)
			print(e)
			print(m)
	except Exception as e:
		Error.create(message = m.text, state = u.state, exception = e)
		print(e)
	

def save_photo(message): # системная функция, не вызывает отправку сообщения в ТГ
	user_id = message.from_user.id
	fileID = message.photo[-1].file_id
	file_info = bot.get_file(fileID)
	downloaded_file = bot.download_file(file_info.file_path)
	photo_name = "{}_{}.jpg".format(user_id, message.message_id)
	with open("./images/photo/{}".format(photo_name), 'wb') as new_file:
		new_file.write(downloaded_file)
		new_file.close()
	return photo_name


@bot.message_handler(content_types = ['photo'])
def photo(m):
	photo_name = save_photo(m)
	Message.create(sender = uid(m), sender_type = "user", receiver = bot_id, text = photo_name, msg_type = 'photo')
	photo = Photo.create(user_id = uid(m), message_id = m.message_id)



class Watcher:
	def __call__(self):
		while True:
			now = datetime.now()
			now = now.replace(microsecond = 0)
			for row in Schedule.select():
				if row.timestamp == now:
					eval(row.action)(**json.loads(row.arguments))
			sleep(1)


# t = time(5, 8)
# schedule(t, "kek", name = "Alex", surname = "Kott")

def kek(name = False, surname = False):
	print("KEK {} {}".format(name, surname))

if __name__ == '__main__':
	watcher = Watcher()
	w = Process(target = watcher)
	w.start()

	bot.polling(none_stop=True)