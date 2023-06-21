import telebot as tb
import random
import datetime
from math import ceil
from PIL import Image, ImageDraw
import psycopg2
# Importing values from config.py, which are used to create bot and connect to database
from config import bot_api, host, user, password, db_name


# Connecting to the bot with telegram bot api
bot = tb.TeleBot(bot_api)


# Connecting with PostgreSQL database
connection = psycopg2.connect(host=host, user=user, password=password, database=db_name)
connection.autocommit = True


# Deleting all tables from database
def delete_tables():
    with connection.cursor() as cursor:
        cursor.execute("""DROP TABLE IF EXISTS users, images, texts""")


# delete_tables()


# Creating tables if they don't exist
def create_tables():
    with connection.cursor() as cursor:
        # Table users stores users' nicknames
        # user_id stores user's telegram id
        # nickname stores user's nickname, which is used when generating images and texts to identify the author
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users(
                user_id int PRIMARY KEY,
                nickname varchar(50) NOT NULL);"""
        )
        # Table images stores generated images
        # image_id stores serial number of image, which is also image's saved name in catalog
        # user_id stores image author's telegram id, which is used when claiming user's own generated images
        # user_image_id stores serial number of user's image, which is used when claiming user's own generated images
        # to get only 5 images according to number of image page
        # nickname stores author's nickname, under which image was generated to identify author
        # nickname_image_id stores serial number of nickname's image, which is used when claiming generated images by
        # author's nickname to get only 5 images according to number of image page
        # date stores date when image was generated in format DD-MM-YYYY
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS images(
                image_id serial PRIMARY KEY,
                user_id int NOT NULL,
                user_image_id int NOT NULL,
                nickname varchar(50) NOT NULL,
                nickname_image_id int NOT NULL,
                date varchar(10) NOT NULL);"""
        )
        # Table texts stores generated texts
        # text_id stores serial number of text
        # user_id stores image author's telegram id, which is used when claiming user's own generated texts
        # user_text_id stores serial number of user's text, which is used when claiming user's own generated texts
        # to get only 5 texts according to number of text page
        # nickname stores author's nickname, under which text was generated to identify author
        # nickname_text_id stores serial number of nickname's text, which is used when claiming generated texts by
        # author's nickname to get only 5 texts according to number of text page
        # date stores date when text was generated in format DD-MM-YYYY
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS texts(
                text_id serial PRIMARY KEY,
                user_id int NOT NULL,
                user_text_id int NOT NULL,
                nickname varchar(50) NOT NULL,
                nickname_text_id int NOT NULL,
                date varchar(10) NOT NULL,
                text varchar(250) NOT NULL);"""
        )


create_tables()


# Function creates ReplyKeyboardMarkup with buttons, with text from buttons list
# Takes one argument *buttons list, which stores buttons' texts
def add_markup(*buttons):
    markup = tb.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for button in buttons:
        markup.row(button)
    return markup


# Function creates date in format DD-MM-YYYY (Moscow timezone)
def add_date():
    date = str(datetime.datetime.utcnow() + datetime.timedelta(hours=3))[:10]
    date = date[8:] + date[4:8] + date[:4]
    return date


# Function checks if the number of page is correct, returns True if so
# Returns False, sending message to the user that the number of page is incorrect with correct reply_markup, setting
# correct page number otherwise
# Takes two arguments chat_id, which stores message.chat.id, and num, which stores the number of page
def check_page(chat_id, num):
    global step, page
    if num < 6 and page != 1:
        bot.send_message(chat_id, 'Некорректный номер страницы, попробуй снова',
                         reply_markup=add_markup('Посмотреть мои работы',
                                                 'Поиск по автору', 'Главное меню'))
        return False
    elif page > ceil(num / 5):
        page -= 1
        bot.send_message(chat_id, 'Некорректный номер страницы, попробуй снова',
                         reply_markup=add_markup('Предыдущая страница', 'Ввести номер страницы',
                                                 'Посмотреть мои работы', 'Поиск по автору', 'Главное меню'))
        return False
    elif page == 0:
        page = 1
        bot.send_message(chat_id, 'Некорректный номер страницы, попробуй снова',
                         reply_markup=add_markup('Следующая страница',  'Ввести номер страницы',
                                                 'Посмотреть мои работы', 'Поиск по автору', 'Главное меню'))
        return False
    else:
        return True


# Function creates and returns correct ReplyKeyboardMarkup according to the number of page
# Takes one argument num, which stores the number of page
def add_page_markup(num):
    if page < ceil(num / 5) and page != 1:
        markup = add_markup('Следующая страница', 'Предыдущая страница', 'Ввести номер страницы',
                            'Посмотреть мои работы', 'Поиск по автору', 'Главное меню')
    elif page != 1:
        markup = add_markup('Предыдущая страница', 'Ввести номер страницы', 'Посмотреть мои работы',
                            'Поиск по автору', 'Главное меню')
    elif page < ceil(num / 5):
        markup = add_markup('Следующая страница', 'Ввести номер страницы', 'Посмотреть мои работы',
                            'Поиск по автору', 'Главное меню')
    else:
        markup = add_markup('Посмотреть мои работы', 'Поиск по автору', 'Главное меню')
    return markup


# Function creates and sends message of previously generated texts, returns True if everything is fine, returns False
# otherwise, takes one required argument chat_id, which stores message.chat.id, and two optional arguments user_id,
# which stores user's telegram id, and nickname, which stores author's nickname, both are used in different text pages
# generations according to the step
def text_page(chat_id, user_id=None, nickname=None):
    global step, page
    message_text = ''

    if step == 'viewing own generated texts':
        # Receiving 5 texts from database by user's telegram id according to number of text page and saving them to
        # texts list and receiving texts amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT text_id, nickname, date, text FROM texts WHERE 
                                (user_id = {user_id} AND {(page - 1) * 5} < user_text_id 
                                AND user_text_id < {page * 5 + 1})""")
            texts = cursor.fetchall()
            cursor.execute(f"""SELECT MAX(nickname_text_id) FROM texts WHERE (user_id = {user_id})""")
            texts_amount = cursor.fetchone()[0]
        # Checking if the texts list is empty
        if not texts:
            bot.send_message(chat_id, 'У тебя еще нет сгенерированных работ, попробуй позже')
            return False
        # Checking if the page number is correct
        if not check_page(chat_id, texts_amount):
            return False
        # Generating message text of user's generated texts
        for elem in texts:
            if elem[0] != 1:
                message_text += '\n'
            message_text += f'Текст №{elem[0]} сгенерирован {elem[2]} под именем "{elem[1]}":\n{elem[3]}\n'
        message_text += f'\nСтраница {page} из {ceil(texts_amount / 5)}'

    elif step == 'viewing nickname generated texts':
        # Receiving 5 texts from database by author's nickname according to number of text page and saving them to
        # texts list and receiving texts amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT text_id, nickname, date, text FROM texts WHERE 
                            (nickname = '{nickname}' AND {(page - 1) * 5} < nickname_text_id 
                            AND nickname_text_id < {page * 5 + 1})""")
            texts = cursor.fetchall()
            cursor.execute(f"""SELECT MAX(nickname_text_id) FROM texts WHERE (nickname = '{nickname}')""")
            texts_amount = cursor.fetchone()[0]
        # Checking if the texts list is empty
        if not texts:
            bot.send_message(chat_id, 'У данного автора еще нет работ, попробуй другого')
            return False
        # Checking if the page number is correct
        if not check_page(chat_id, texts_amount):
            return False
        # Generating message text of nickname's generated texts
        for elem in texts:
            if elem[0] != 1:
                message_text += '\n'
            message_text += f'Текст №{elem[0]} сгенерирован {elem[2]} пользователем "{elem[1]}":\n{elem[3]}\n'
        message_text += f'\nСтраница {page} из {ceil(texts_amount / 5)}'

    else:
        # Receiving 5 texts from database according to number of text page and saving them to texts list and
        # receiving texts amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT text_id, nickname, date, text FROM texts WHERE 
                            ({(page - 1) * 5} < text_id AND text_id < {page * 5 + 1})""")
            texts = cursor.fetchall()
            cursor.execute("""SELECT MAX(text_id) FROM texts""")
            texts_amount = cursor.fetchone()[0]
        # Checking if the page number is correct
        if not check_page(chat_id, texts_amount):
            return False
        # Generating message text of generated texts
        for elem in texts:
            if elem[0] != 1:
                message_text += '\n'
            message_text += f'Текст №{elem[0]} сгенерирован {elem[2]} пользователем "{elem[1]}":\n{elem[3]}\n'
        message_text += f'\nСтраница {page} из {ceil(texts_amount / 5)}'
    bot.send_message(chat_id, message_text, reply_markup=add_page_markup(texts_amount))
    return True


# Function creates and sends message of previously generated images, returns True if everything is fine, returns False
# otherwise, takes one required argument chat_id, which stores message.chat.id, and two optional arguments user_id,
# which stores user's telegram id, and nickname, which stores author's nickname, both are used in different image pages
# generations according to the step
def image_page(chat_id, user_id=None, nickname=None):
    global step, page

    if step == 'viewing own generated images':
        # Receiving 5 images' names from database by user's telegram id according to number of image page and
        # saving them to images list and receiving images amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT image_id, nickname, date FROM images WHERE 
                            (user_id = {user_id} AND {(page - 1) * 5} < user_image_id
                             AND user_image_id < {page * 5 + 1})""")
            images = cursor.fetchall()
            cursor.execute(f"""SELECT MAX(user_image_id) FROM images WHERE (user_id = {user_id})""")
            images_amount = cursor.fetchone()[0]
        # Checking if the images list is empty
        if not images:
            bot.send_message(chat_id, 'У тебя еще нет сгенерированных работ, попробуй позже')
            return False
        # Checking if the page number is correct
        if not check_page(chat_id, images_amount):
            return False
        # Sending messages of generated images
        for elem in images[:- 1]:
            with open(f'images/{elem[0]}.jpeg', 'rb') as image:
                bot.send_photo(chat_id, photo=image,
                               caption=f'Картинка №{elem[0]} сгенерирована {elem[2]} под именем "{elem[1]}"')
        with open(f'images/{images[-1][0]}.jpeg', 'rb') as image:
            bot.send_photo(chat_id, photo=image, caption=f'Картинка №{images[-1][0]} сгенерирована {images[-1][2]} '
                                                         f'под именем "{images[-1][1]}"\n\nСтраница {page} '
                                                         f'из {ceil(images_amount / 5)}',
                           reply_markup=add_page_markup(images_amount))

    elif step == 'viewing nickname generated images':
        # Receiving 5 images' names from database by author's nickname according to number of image page and
        # saving them to images list and receiving images amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT image_id, nickname, date FROM images WHERE (nickname = '{nickname}' 
                            AND {(page - 1) * 5} < nickname_image_id 
                            AND nickname_image_id < {page * 5 + 1})""")
            images = cursor.fetchall()
            cursor.execute(f"""SELECT MAX(nickname_image_id) FROM images WHERE (nickname = '{nickname}')""")
            images_amount = cursor.fetchone()[0]
        # Checking if the images list is empty
        if not images:
            bot.send_message(chat_id, 'У данного автора еще нет работ, попробуй другого')
            return False
        # Checking if the page number is correct
        if not check_page(chat_id, images_amount):
            return False
        # Sending messages of generated images
        for elem in images[:- 1]:
            with open(f'images/{elem[0]}.jpeg', 'rb') as image:
                bot.send_photo(chat_id, photo=image, caption=f'Картинка №{elem[0]} сгенерирована {elem[2]}'
                                                             f' пользователем "{elem[1]}"')
        with open(f'images/{images[-1][0]}.jpeg', 'rb') as image:
            bot.send_photo(chat_id, photo=image, caption=f'Картинка №{images[-1][0]} сгенерирована {images[-1][2]} '
                                                         f'пользователем "{images[-1][1]}"\n\nСтраница '
                                                         f'{page} из {ceil(images_amount / 5)}',
                           reply_markup=add_page_markup(images_amount))

    else:
        # Receiving 5 images' names from database according to number of image page and
        # saving them to images list and receiving images amount
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT image_id, nickname, date FROM images WHERE ({(page - 1) * 5} < image_id 
                            AND image_id < {page * 5 + 1})""")
            images = cursor.fetchall()
            cursor.execute("""SELECT MAX(image_id) FROM images""")
            images_amount = cursor.fetchone()[0]
        # Checking if the page number is correct
        if not check_page(chat_id, images_amount):
            return False
        # Sending messages of generated images
        for elem in images[:- 1]:
            with open(f'images/{elem[0]}.jpeg', 'rb') as image:
                bot.send_photo(chat_id, photo=image, caption=f'Картинка №{elem[0]} сгенерирована {elem[2]} '
                                                             f'пользователем "{elem[1]}"')
        with open(f'images/{images[-1][0]}.jpeg', 'rb') as image:
            bot.send_photo(chat_id, photo=image, caption=f'Картинка №{images[-1][0]} сгенерирована {images[-1][2]} '
                                                         f'пользователем "{images[-1][1]}"\n\nСтраница '
                                                         f'{page} из {ceil(images_amount / 5)}',
                           reply_markup=add_page_markup(images_amount))
    return True


@bot.message_handler(commands=['start'])
def command_start(message):
    message_text = 'Выбери одно из действий, чтобы начать'
    bot.send_message(message.chat.id, message_text, reply_markup=add_markup('Сгенерировать новое',
                                                                            'Посмотреть существующее', 'О проекте'))


@bot.message_handler(commands=['help'])
def command_help(message):
    bot.send_message(message.chat.id, 'Хотел бы я тебе помочь, но я сам уже ничего не понимаю в этом мире...',
                     reply_markup=add_markup('Сгенерировать новое', 'Посмотреть существующее', 'О проекте'))


# step is used to track step of user's usage
# page stores number of viewing page
# last_page stores last seen page
# last_nickname stores last used nickname to view generated works by nickname after using button 'next page' or
# 'previous page'
step = None
page = 1
last_page = None
last_nickname = None


@bot.message_handler(content_types=['text'])
def text(message):
    global step, page, last_page, last_nickname

    # 'Main menu' button
    # Choosing action
    if message.text == 'Главное меню':
        bot.send_message(message.chat.id, 'Выбери одно из действий',
                         reply_markup=add_markup('Сгенерировать новое', 'Посмотреть существующее', 'О проекте'))
        step = None
        page = 1
        last_page = None
        last_nickname = None

    # 'Generate new' button
    # Choosing what to generate
    elif message.text == 'Сгенерировать новое':
        with connection.cursor() as cursor:
            # Checking is the user already registered in the database
            cursor.execute(f"""SELECT * FROM users WHERE (user_id=  {message.from_user.id})""")
            # Going to 'adding nickname' step if the user is new
            if cursor.fetchone() is None:
                bot.send_message(message.chat.id, 'Введи имя, которое будет видно другим пользователям')
                step = 'adding nickname'
            # Choosing what to generate otherwise
            else:
                bot.send_message(message.chat.id, 'Выбери, что сгенерировать',
                                 reply_markup=add_markup('Текст', 'Картинку', 'Изменить имя', 'Главное меню'))
                step = 'generating new'
        page = 1
        last_page = None
        last_nickname = None

    # Adding user's nickname to the database
    elif step == 'adding nickname':
        # Checking if the nickname is valid
        if len(message.text) > 50 and not message.text.isalnum():
            bot.send_message(message.chat.id, 'Длина имени не должна превышать 50 символов, в имени присутствуют '
                                              'некорректные символы, попробуй снова')
        elif len(message.text) > 50:
            bot.send_message(message.chat.id, 'Длина имени не должна превышать 50 символов, попробуй снова')
        elif not message.text.isalnum():
            bot.send_message(message.chat.id, 'В имени присутствуют некорректные символы, попробуй снова')
        else:
            # Adding it to the database if it's correct
            with connection.cursor() as cursor:
                cursor.execute(f"""INSERT INTO users (user_id, nickname) VALUES ({message.from_user.id}, 
                                '{message.text}')""")
            # Choosing what to generate
            bot.send_message(message.chat.id, 'Выбери, что сгенерировать',
                             reply_markup=add_markup('Текст', 'Картинку', 'Изменить имя', 'Главное меню'))
            step = 'generating new'

    # 'Edit name' button
    # Updating nickname in database
    elif message.text == 'Изменить имя':
        bot.send_message(message.chat.id, 'Введи новое имя, которое будет видно другим пользователям')
        step = 'editing nickname'

    elif step == 'editing nickname':
        # Checking if the nickname is valid
        if len(message.text) > 50 and not message.text.isalnum():
            bot.send_message(message.chat.id, 'Длина имени не должна превышать 50 символов, в имени присутствуют '
                                              'некорректные символы, попробуй снова')
        elif len(message.text) > 50:
            bot.send_message(message.chat.id, 'Длина имени не должна превышать 50 символов, попробуй снова')
        elif not message.text.isalnum():
            bot.send_message(message.chat.id, 'В имени присутствуют некорректные символы, попробуй снова')
        else:
            # Updating in the database if it's correct
            with connection.cursor() as cursor:
                cursor.execute(f"""UPDATE users SET nickname = '{message.text}' 
                                WHERE (user_id = {message.from_user.id})""")
            # Choosing what to generate
            bot.send_message(message.chat.id, 'Имя успешно изменено, выбери, что сгенерировать',
                             reply_markup=add_markup('Текст', 'Картинку', 'Изменить имя', 'Главное меню'))
            step = 'generating new'

    # Generate new 'text' button
    # Generating and sending new text
    elif (step == 'generating new' and message.text == 'Текст') \
            or (step == 'generating new text' and message.text == 'Сгенерировать еще'):
        # Generating new string using random
        generated_text = ''.join(random.choices('йфяцычувскамепинртгоьшлбщдюзжхэъ 0123456789',
                                                k=random.randint(1, 250)))
        # Receiving user's nickname, user_text_id, nickname_text_id and adding generated text to the database
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT nickname FROM users WHERE (user_id = {message.from_user.id})""")
            nickname = cursor.fetchone()[0]
            cursor.execute(f"""SELECT MAX(user_text_id) FROM texts WHERE (user_id = {message.from_user.id})""")
            user_text_id = cursor.fetchone()[0]
            if user_text_id is None:
                user_text_id = 0
            cursor.execute(f"""SELECT MAX(nickname_text_id) FROM texts WHERE (nickname = '{nickname}')""")
            nickname_text_id = cursor.fetchone()[0]
            if nickname_text_id is None:
                nickname_text_id = 0
            date = add_date()
            cursor.execute(f"""INSERT INTO texts (user_id, user_text_id, nickname, nickname_text_id, date, text) 
                            VALUES ({message.from_user.id}, {user_text_id + 1}, '{nickname}', {nickname_text_id + 1}, 
                            '{date}', '{generated_text}')""")
            cursor.execute(f"""SELECT MAX(text_id) FROM texts""")
            text_id = cursor.fetchone()[0]
        # Sending generated text to the user
        bot.send_message(message.chat.id, f'Твой текст №{text_id} сгенерирован {date} под именем "{nickname}":'
                                          f'\n{generated_text}', reply_markup=add_markup('Сгенерировать еще',
                                                                                         'Главное меню'))
        step = 'generating new text'

    # Generate new 'image' button
    # Generating and sending new image
    elif (step == 'generating new' and message.text == 'Картинку') \
            or (step == 'generating new image' and message.text == 'Сгенерировать еще'):
        # Generating new image 250*250 pixels
        image = Image.new(mode='RGB', size=(250, 250))
        draw = ImageDraw.Draw(image)
        width = image.size[0]
        height = image.size[1]
        # Generating new color for each pixel in rgb with random
        for i in range(width):
            for j in range(height):
                r, g, b = [random.randint(0, 255) for i in range(3)]
                draw.point((i, j), (r, g, b))
        # Receiving user's nickname, user_image_id, nickname_image_id and adding image's id to the database
        with connection.cursor() as cursor:
            cursor.execute(f"""SELECT nickname FROM users WHERE (user_id = {message.from_user.id})""")
            nickname = cursor.fetchone()[0]
            cursor.execute(f"""SELECT MAX(user_image_id) FROM images WHERE (user_id = {message.from_user.id})""")
            user_image_id = cursor.fetchone()[0]
            if user_image_id is None:
                user_image_id = 0
            cursor.execute(f"""SELECT MAX(nickname_image_id) FROM images WHERE (nickname = '{nickname}')""")
            nickname_image_id = cursor.fetchone()[0]
            if nickname_image_id is None:
                nickname_image_id = 0
            date = add_date()
            cursor.execute(f"""INSERT INTO images (user_id, user_image_id, nickname, nickname_image_id, date) 
                            VALUES ({message.from_user.id}, {user_image_id + 1}, '{nickname}', {nickname_image_id + 1},
                            '{date}')""")
            cursor.execute("""SELECT MAX(image_id) FROM images""")
            image_id = cursor.fetchone()[0]
        # Saving and opening generated image using its id to send it to the user
        image.save(f'images/{image_id}.jpeg')
        with open(f'images/{image_id}.jpeg', 'rb') as image:
            bot.send_photo(message.chat.id, photo=image,
                           caption=f'Твоя картинка №{image_id} сгенерирована {date} под именем "{nickname}"',
                           reply_markup=add_markup('Сгенерировать еще', 'Главное меню'))
        step = 'generating new image'
        del draw

    # 'View existing' button
    # Choosing what to view
    elif message.text == 'Посмотреть существующее':
        bot.send_message(message.chat.id, 'Выбери, что посмотреть',
                         reply_markup=add_markup('Тексты', 'Картинки', 'Главное меню'))
        step = None

    # View existing 'texts' button
    # Viewing previously generated texts
    elif message.text == 'Тексты':
        page = 1
        step = 'viewing generated texts'
        text_page(message.chat.id)

    # 'Next text page' button
    # Next page of previously generated texts
    elif step is not None and step.split()[-1] == 'texts' and message.text == 'Следующая страница':
        page += 1
        if step == 'viewing own generated texts':
            text_page(message.chat.id, user_id=message.from_user.id)
        elif step == 'viewing nickname generated texts':
            text_page(message.chat.id, nickname=last_nickname)
        else:
            text_page(message.chat.id)

    # 'Previous text page' button
    # Previous page of previously generated texts
    elif step is not None and step.split()[-1] == 'texts' and message.text == 'Предыдущая страница':
        page -= 1
        if step == 'viewing own generated texts':
            text_page(message.chat.id, user_id=message.from_user.id)
        elif step == 'viewing nickname generated texts':
            text_page(message.chat.id, nickname=last_nickname)
        else:
            text_page(message.chat.id)

    # 'View my texts' button
    # Viewing user's generated texts
    elif step is not None and step.split()[-1] == 'texts' and message.text == 'Посмотреть мои работы':
        page = 1
        step = 'viewing own generated texts'
        text_page(message.chat.id, user_id=message.from_user.id)

    # 'View texts by author' button
    # Viewing generated texts by author's nickname
    elif step is not None and step.split()[-1] == 'texts' and message.text == 'Поиск по автору':
        page = 1
        step = 'viewing nickname generated texts'
        bot.send_message(message.chat.id, 'Напиши имя автора, чьи работы ты хочешь найти')

    # 'Enter the number of text page' button
    # Viewing page according to the num of page
    elif step is not None and step.split()[-1] == 'texts' and message.text == 'Ввести номер страницы':
        if step == 'viewing own generated texts':
            step = 'viewing page own generated texts'
        elif step == 'viewing nickname generated texts':
            step = 'viewing page nickname generated texts'
        else:
            step = 'viewing page generated texts'
        bot.send_message(message.chat.id, 'Введи номер страницы')

    elif step is not None and step.split()[-1] == 'texts' and step.split()[1] == 'page':
        # Checking if the message.texts is int
        if not message.text.isdigit():
            bot.send_message(message.chat.id, 'Некорректный номер страницы')
        else:
            last_page = page
            page = int(message.text)
            # Checking if the page number is correct, if it's not, setting previous page value
            if step == 'viewing page own generated texts':
                step = 'viewing own generated texts'
                if not text_page(message.chat.id, user_id=message.from_user.id):
                    page = last_page
                step = 'viewing page own generated texts'
            elif step == 'viewing page nickname generated texts':
                step = 'viewing nickname generated texts'
                if not text_page(message.chat.id, nickname=last_nickname):
                    page = last_page
                step = 'viewing page nickname generated texts'
            else:
                step = 'viewing generated texts'
                if not text_page(message.chat.id):
                    page = last_page
                step = 'viewing page generated texts'

    elif step == 'viewing nickname generated texts':
        if text_page(message.chat.id, nickname=message.text):
            last_nickname = message.text

    # View existing 'images' button
    # Viewing previously generated images
    elif message.text == 'Картинки':
        page = 1
        step = 'viewing generated images'
        image_page(message.chat.id)

    # 'Next image page' button
    # Next page of previously generated images
    elif step is not None and step.split()[-1] == 'images' and message.text == 'Следующая страница':
        page += 1
        if step == 'viewing own generated images':
            image_page(message.chat.id, user_id=message.from_user.id)
        elif step == 'viewing nickname generated images':
            image_page(message.chat.id, nickname=last_nickname)
        else:
            image_page(message.chat.id)

    # 'Previous image page' button
    # Previous page of previously generated images
    elif step is not None and step.split()[-1] == 'images' and message.text == 'Предыдущая страница':
        page -= 1
        if step == 'viewing own generated images':
            image_page(message.chat.id, user_id=message.from_user.id)
        elif step == 'viewing nickname generated images':
            image_page(message.chat.id, nickname=last_nickname)
        else:
            image_page(message.chat.id)

    # 'View my images' button
    # Viewing user's generated images
    elif step is not None and step.split()[-1] == 'images' and message.text == 'Посмотреть мои работы':
        page = 1
        step = 'viewing own generated images'
        image_page(message.chat.id, user_id=message.from_user.id)

    # 'View images by author' button
    # Viewing generated texts by author's nickname
    elif step is not None and step.split()[-1] == 'images' and message.text == 'Поиск по автору':
        page = 1
        step = 'viewing nickname generated images'
        bot.send_message(message.chat.id, 'Напиши имя автора, чьи работы ты хочешь найти')

    # 'Enter the number of image page' button
    # Viewing page according to the num of page
    elif step is not None and step.split()[-1] == 'images' and message.text == 'Ввести номер страницы':
        if step == 'viewing own generated images':
            step = 'viewing page own generated images'
        elif step == 'viewing nickname generated images':
            step = 'viewing page nickname generated images'
        else:
            step = 'viewing page generated images'
        bot.send_message(message.chat.id, 'Введи номер страницы')

    elif step is not None and step.split()[-1] == 'images' and step.split()[1] == 'page':
        # Checking if the message.texts is int
        if not message.text.isdigit():
            bot.send_message(message.chat.id, 'Некорректный номер страницы')
        else:
            last_page = page
            page = int(message.text)
            # Checking if the page number is correct, if it's not, setting previous page value
            if step == 'viewing page own generated images':
                step = 'viewing own generated images'
                if not image_page(message.chat.id, user_id=message.from_user.id):
                    page = last_page
                step = 'viewing page own generated images'
            elif step == 'viewing page nickname generated images':
                step = 'viewing nickname generated images'
                if not image_page(message.chat.id, nickname=last_nickname):
                    page = last_page
                step = 'viewing page nickname generated images'
            else:
                step = 'viewing generated images'
                if not image_page(message.chat.id):
                    page = last_page
                step = 'viewing page generated images'

    elif step == 'viewing nickname generated images':
        if image_page(message.chat.id, nickname=message.text):
            last_nickname = message.text

    # 'About project' button
    # Sending message about the project
    elif message.text == 'О проекте':
        message_text = 'Идея этого бота была нагло украдена с простор интернета из-за обделенностью автора ' \
                       'творческого начала и какой-либо фантазии во благо саморазвития без каких-либо корыстных ' \
                       'побуждений. Воодушевление застало меня врасплох после теоремы о бесконечных обезьянах и ' \
                       'рассказом "Вавилонская башня", с которыми я настоятельно рекомендую ознакомиться ' \
                       'любознательному уму. Данный бот представляет собой их корявую миниверсию. Здесь ты сможешь ' \
                       'поиграться с генерацией текстов и картинок, вдруг среди случайного набора русских прописных ' \
                       'букв и арабских цифр тебе удастся выцедить одну из поэм великого Шекспира или увидеть ' \
                       'свое изображение в данный момент, сложившееся из случайного набора пикселей (на самом деле ' \
                       'тебе никогда это не удастся, поскольку ты не обладаешь бесконечным количеством времени, но ' \
                       'попытаться пробудить твои дальние струнки души я был обязан), также ты сможешь посмотреть ' \
                       'сгенерированные работы других людей.\n\nБот сделан 21-05-2023. Код бота ' \
                       'https://github.com/middelmatigheid/tgbot-sluchaynik.'
        bot.send_message(message.chat.id, message_text,
                         reply_markup=add_markup('Сгенерировать новое', 'Посмотреть существующее', 'О проекте'))

    else:
        bot.send_message(message.chat.id, 'Произошли технические шоколадки, неизвестная команда, попробуй снова')


# Adding 1 text and 1 image to the database from developer to prevent empty database, which can cause errors
def from_developer():
    # Generating new image 250*250 pixels
    image = Image.new(mode='RGB', size=(250, 250))
    draw = ImageDraw.Draw(image)
    width = image.size[0]
    height = image.size[1]
    # Generating new color for each pixel in rgb with random
    for i in range(width):
        for j in range(height):
            r, g, b = [random.randint(0, 255) for i in range(3)]
            draw.point((i, j), (r, g, b))
    # Saving image
    image.save('images/1.jpeg')
    del draw
    # Adding to the databse
    with connection.cursor() as cursor:
        cursor.execute("""INSERT INTO texts (user_id, user_text_id, nickname, nickname_text_id, date, text) 
                        VALUES (1, 1, 'разработчик', 1, '10-05-2003', 'привет')""")
        cursor.execute("""INSERT INTO images (user_id, user_image_id, nickname, nickname_image_id, date) 
                        VALUES (1, 1, 'разработчик', 1, '20-05-2003')""")


from_developer()


if __name__ == '__main__':
    bot.infinity_polling()
    
