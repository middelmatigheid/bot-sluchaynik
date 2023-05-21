# bot-sluchaynik

Бот представляет собой миниверсию 'Вавилонской башни', в частности может генерировать тексты до 250 символов из русских прописных букв, пробела и цифр, картинки размером 250 на 250 пикселей, цвет каждого из которых генерируется случайным образом. Все тексты и картинки заносятся в базу данных для дальнейшего использования и просмотра при использовании бота. Для создания изображения используется модуль 'pillow', для случайной генерации - модуль 'random', для взаимодействия с базой данных PostgreSQL - модуль 'psycopg2', для добавления даты используется встроенный модуль 'date'. Более подробное объяснение принципа работы бота изложено в комментариях файла 'main.py'.

Перед запуском бота необходимо:
- Создать папку 'images' в той же директории, что и бот
- Изменить значения в файле 'config.py' в соответствии с Вашей базой данных PostgreSQL
- Создать виртуальное окружение с помощью `python -m venv env`
- Установить необходимые модули с помощью `pip install -r requirements.txt`

middelmatigheid 21-05-2023
