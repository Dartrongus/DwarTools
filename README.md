# ⚔ DwarTools
[Скачать](https://github.com/Dartrongus/DwarTools/releases/download/DwarTools/DwarTools.exe)
Инструмент для работы с Dwarium через Chrome DevTools Protocol.

## Возможности

* автоматическое подключение DwarTools к Dwarium;
* автоматический запуск DwarTools на странице персонажа;
* быстрый просмотр Тени персонажа;
* быстрый просмотр Эффектов персонажа;
* отображение информации об экипировке;
* создание специального ярлыка Dwarium с параметрами DevTools;
* ручное подключение через параметры запуска.

## Автоматическое подключение

Для работы DwarTools Dwarium необходимо запускать с параметрами:

```text
--remote-debugging-port=9222 --remote-allow-origins=*
```

Самый простой способ — использовать встроенную функцию создания ярлыка.

1. Запустите DwarTools.
2. В разделе **«Подключение Dwarium»** нажмите **«Выбрать Dwarium.exe»**.
3. Выберите исполняемый файл Dwarium.
4. Нажмите **«Создать ярлык»**.
5. На рабочем столе появится ярлык:

```text
Dwarium - DwarTools.lnk
```

6. Полностью закройте Dwarium.
7. Запускайте Dwarium через созданный ярлык.

После запуска DwarTools сможет подключиться к Dwarium через DevTools.

## Быстрый просмотр персонажа

В окне DwarTools можно ввести ник персонажа.

Доступны две кнопки:

* 👻 **Тень**
* ✨ **Эффекты**

Страницы открываются в новой вкладке непосредственно в запущенном Dwarium.

## Ручное подключение

Если создание ярлыка не используется:

1. Найдите ярлык Dwarium.
2. Нажмите правой кнопкой мыши.
3. Выберите **«Свойства»**.
4. Откройте вкладку **«Ярлык»**.
5. В поле **«Объект»** после пути к `Dwarium.exe` добавьте:

```text
--remote-debugging-port=9222 --remote-allow-origins=*
```

Пример:

```text
"C:\Dwarium\Dwarium.exe" --remote-debugging-port=9222 --remote-allow-origins=*
```

Нажмите **«Применить» → «ОК»**.

После этого полностью перезапустите Dwarium.

## Запуск готового EXE

Если используется готовая версия из GitHub Releases, Python устанавливать не требуется.

Запустите:

```text
DwarTools_v0.6.exe
```

## Запуск из исходного кода

Требуется Python 3.

Установите зависимости:

```bat
python -m pip install -r requirements.txt
```

Запустите:

```bat
python DwarTools_v0.6.py
```

## Сборка EXE

Для самостоятельной сборки:

1. Установите Python 3.
2. Скачайте репозиторий.
3. Поместите все файлы в одну папку.
4. Запустите:

```text
build.bat
```

Скрипт автоматически установит зависимости и создаст EXE.

Готовый файл появится здесь:

```text
dist\DwarTools_v0.6.exe
```

## Структура проекта

```text
DwarTools/
│
├── DwarTools_v0.6.py
├── build.bat
├── requirements.txt
├── README.md
└── .gitignore
```

Папки `build` и `dist` не являются частью исходного проекта и исключены из Git.

## DevTools

DwarTools использует Chrome DevTools Protocol через локальный порт:

```text
9222
```

Если Dwarium запущен без параметров DevTools, подключение DwarTools невозможно.

В таком случае полностью закройте Dwarium и запустите его через специальный ярлык.

## Ссылки

GitHub:

https://github.com/Dartrongus/DwarTools

Полезные ссылки:

https://dartrongus.github.io/dwar/menu

## Версия

**DwarTools v0.6**
