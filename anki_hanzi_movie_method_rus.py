import genanki
import random
import requests
import os
import time
from pypinyin import pinyin, Style
import urllib.parse
from hanziconv import HanziConv
from googletrans import Translator
import re
import asyncio
import json
from datetime import datetime
from openai import OpenAI
from openai import OpenAIError

input_file = "chinese_words_hanzi_movie_method.txt"
output_file_archive_path = "input_words_hmm_archive"

anki_deck_name = "Vova Hanzi Spaces with Actors (Русский)"
# anki_deck_name = "214 radicals Hanzi Movie Method (Русский)"
output_deck = "vova_hanzi_spaces_actors_rus.apkg"
# output_deck = "214_radicals_hanzi_spaces_actors_rus.apkg"

# OPENAI_MODEL = "gpt-3.5-turbo"  # Можно заменить на "gpt-4o"
OPENAI_MODEL = "gpt-4o-mini"  # Можно заменить на "gpt-4o"
OPENAI_MAX_TOKENS = 300
OPENAI_TEMPERATURE = 0.8

class HanziComponentsDB:
    def __init__(self, db_file='hanzi_db.txt'):
        self.db = self._load_db(db_file)
        self.component_meanings = {
            '⿰': 'слева направо',
            '⿱': 'сверху вниз',
            '⿲': 'три части горизонтально',
            '⿳': 'три части вертикально',
            '⿴': 'внешнее-внутреннее',
            '⿵': 'верхняя рамка',
            '⿶': 'нижняя рамка',
            '⿷': 'левая рамка',
            '⿸': 'верхне-левая рамка',
            '⿹': 'верхне-правая рамка',
            '⿺': 'нижне-левая рамка',
            '⿻': 'пересекающиеся компоненты'
        }
    
    def _load_db(self, db_file):
        """Загружает данные из файла в словарь"""
        db = {}
        try:
            with open(db_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        db[data['character']] = data
        except FileNotFoundError:
            print(f"Файл {db_file} не найден! Будет использован пустой словарь.")
            return {}
        return db
    
    def parse_separated_values(self, input_string):
        """
        Parse a string containing values separated by commas or semicolons into an ordered list.
        
        Args:
            input_string (str): String containing values separated by , or ;
            
        Returns:
            list: Ordered list of values with whitespace stripped
        """
        # Replace semicolons with commas to standardize the separator
        standardized = input_string.replace(';', ',')
        
        # Split by commas and strip whitespace from each item
        values = [item.strip() for item in standardized.split(',')]
        
        # Remove any empty strings that might result from splitting
        values = [item for item in values if item]
        
        return values

    def get_hanzi_components(self, hanzi):
        """Получает информацию о компонентах иероглифа"""
        if hanzi not in self.db:
            return None
            
        data = self.db[hanzi]
        decomposition = data.get('decomposition', '')
        radical = data.get('radical', '')
        etymology = data.get('etymology', {})
        definition = data.get('definition', '')
                

        # # Разбираем декомпозицию
        structure, components = self._parse_decomposition(decomposition)
        
        new_components = list()
        for component in components:
            if component:
                meanings_list = ""
                component_data = self.db.get(component, {})
                meaning_data = component_data.get('definition', '')
                if meaning_data:
                    meanings_list = self.parse_separated_values(meaning_data)                
                    meanings_list = [meaning.strip() for meaning in meanings_list][0]
                new_components.append(f'{component} ({meanings_list})')
        components_with_meaning = ", ".join(new_components)
        return {
            'character': hanzi,
            'structure': structure,
            'components': components,
            'components_with_meaning': components_with_meaning,
            'radical': radical,
            'etymology': etymology.get('hint', ''),
            'definition': definition
        }
    
    def _parse_decomposition(self, decomposition):
        """Разбирает строку декомпозиции на структуру и компоненты"""
        if not decomposition:
            return '', []
        
        # Определяем тип структуры
        structure_symbol = decomposition[0]
        structure = self.component_meanings.get(structure_symbol, 'неизвестная структура')
        
        # Извлекаем компоненты (удаляем первый символ структуры)
        components = []
        for char in decomposition[1:]:
            if char not in self.component_meanings:  # Пропускаем символы структур
                components.append(char)
        
        return structure, components


class HanziSpacesGenerator:
    def __init__(self):
        # Создаем модель Anki для метода "Пространства" с актерами на русском
        self.components_db = HanziComponentsDB('hanzi_db.txt')
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name,
            fields=[
                {"name": "Иероглиф"},      # Китайский иероглиф
                {"name": "Пиньинь"},       # Простой пиньинь
                {"name": "ЦветнойПиньинь"}, # Пиньинь с цветными тонами
                {"name": "Значение"},      # Значение на русском
                {"name": "Пространство"},  # Мнемоническое пространство с актерами
                {"name": "Подсказка"},     # Подсказка (разбор иероглифа)
                {"name": "Аудио"},         # Аудио произношения
                {"name": "История"},        # Новое поле для историй
                {"name": "StrokeOrder"},  # Порядок черт
            ],
            templates=[
                {
                    "name": "Узнавание",
                    "qfmt": '<div class="stroke-order">{{StrokeOrder}}</div>',
                    "afmt": """
                        <div class="stroke-order">{{StrokeOrder}}</div>
                        <hr>
                        <div class="pinyin">{{Пиньинь}}</div>
                        <div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="meaning">{{Значение}}</div>
                        <div class="space"><b>Пространство:</b> {{Пространство}}</div>
                        <div class="hint"><b>Подсказка:</b> {{Подсказка}}</div>
                        <div class="story"><b>История:</b> {{История}}</div>
                        {{Аудио}}
                    """,
                },
                {
                    "name": "Вспоминание",
                    "qfmt": '<div class="meaning">{{Значение}}</div><div class="space"><b>Пространство:</b> {{Пространство}}</div>',
                    "afmt": """
                        <div class="meaning">{{Значение}}</div>
                        <hr>
                        <div class="hanzi">{{Иероглиф}}</div>
                        <div class="pinyin">{{Пиньинь}}</div>
                        <div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="space"><b>Пространство:</b> {{Пространство}}</div>
                        <div class="hint"><b>Подсказка:</b> {{Подсказка}}</div>
                        <div class="story"><b>История:</b> {{История}}</div>
                        {{Аудио}}
                    """,
                },
            ],
            css="""
                .card {
                    font-family: Arial, sans-serif;
                    font-size: 16px;
                    text-align: center;
                    color: black;
                    background-color: white;
                    padding: 20px;
                }
                .hanzi {
                    font-size: 50px;
                    font-weight: bold;
                    margin-bottom: 15px;
                }
                .stroke-order img {
                    max-width: 200px;
                    height: 100px;
                    margin-top: 15px;
                    margin-right: 10px;
                }
                .stroke-order svg {
                    max-width: 200px;
                    margin-top: 15px;
                }                
                .pinyin {
                    font-size: 18px;
                    margin-bottom: 10px;
                }
                .colored-pinyin {
                    font-size: 18px;
                    margin-bottom: 10px;
                }
                .meaning {
                    font-size: 20px;
                    margin-bottom: 15px;
                }
                .space {
                    font-size: 16px;
                    color: #444;
                    margin-top: 10px;
                }
                .hint {
                    font-size: 16px;
                    margin-bottom: 10px;
                }
                .story {
                    font-size: 16px;
                    color: #333;
                    margin-top: 10px;
                    font-style: italic;
                }                          
                .tone1 { color: blue; }
                .tone2 { color: green; }
                .tone3 { color: purple; }
                .tone4 { color: red; }
                .tone5 { color: gray; }
            """,
        )

        # Создаем колоду
        self.deck = genanki.Deck(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name
        )

        # Медиафайлы (аудио)
        self.media_files = []

        # Словарь "Пространств" на основе финалей и тонов
        self.spaces = {
            "a": {
                "name": "Арт-галерея",
                "tones": {
                    "1": "Вестибюль",
                    "2": "Главный выставочный зал",
                    "3": "Мастерская художников",
                    "4": "Кабинет куратора",
                },
            },
            "o": {
                "name": "Мотель",
                "tones": {
                    "1": "Ресепшн",
                    "2": "Главный коридор",
                    "3": "Общая гостиная",
                    "4": "Номер отдыха",
                },
            },
            "e": {
                "name": "Эко-дом",
                "tones": {
                    "1": "Солнечная веранда",
                    "2": "Центральная гостиная",
                    "3": "Зимний сад",
                    "4": "Медитационная комната",
                },
            },
            "ai": {
                "name": "Айсберг-хижина",
                "tones": {
                    "1": "Ледяной вход",
                    "2": "Центральный зал",
                    "3": "Теплый очаг",
                    "4": "Спальный отсек",
                },
            },
            "ei": {
                "name": "Эйфелева башня (жилые помещения)",
                "tones": {
                    "1": "Лифтовой холл",
                    "2": "Панорамный салон",
                    "3": "Инженерная комната",
                    "4": "Смотровая площадка",
                },
            },
            "ao": {
                "name": "Вау-хаус",
                "tones": {
                    "1": "Футуристический вход",
                    "2": "Главный атриум с панорамной крышей",
                    "3": "Комната аудиовизуальных эффектов",
                    "4": "Спальня-трансформер",
                },
            },
            "ou": {
                "name": "Оукхаус (дубовый дом)",
                "tones": {
                    "1": "Прихожая с деревянной отделкой",
                    "2": "Каминный зал",
                    "3": "Библиотека",
                    "4": "Мансарда",
                },
            },
            "an": {
                "name": "Ангар-лофт",
                "tones": {
                    "1": "Грузовой вход",
                    "2": "Центральное пространство",
                    "3": "Технический отсек",
                    "4": "Жилая зона",
                },
            },
            "ang": {
                "name": "Английский коттедж",
                "tones": {
                    "1": "Садовая калитка",
                    "2": "Гостиная с камином",
                    "3": "Чайная комната",
                    "4": "Спальня с балдахином",
                },
            },
            "en": {
                "name": "Энциклопедическая библиотека-дом",
                "tones": {
                    "1": "Архивный вход",
                    "2": "Главный читальный зал",
                    "3": "Кабинет каталогизации",
                    "4": "Кабинет редких изданий",
                },
            },
            "eng": {
                "name": "Инглиш Мэнор (английское поместье)",
                "tones": {
                    "1": "Парадный вход",
                    "2": "Бальный зал",
                    "3": "Охотничья комната",
                    "4": "Господская спальня",
                },
            },
            "ong": {
                "name": "Замок Конга",
                "tones": {
                    "1": "Крепостные ворота",
                    "2": "Тронный зал",
                    "3": "Сокровищница",
                    "4": "Королевские покои",
                },
            },
            "null": {
                "name": "Нулевой дом (минималистичный дом)",
                "tones": {
                    "1": "Стеклянный вход",
                    "2": "Открытое пространство",
                    "3": "Медитативная зона",
                    "4": "Спальная капсула",
                },
            },
        }

        # Словарь мужских актеров на основе инициалов (согласные)
        self.male_actors = {
            "b": "Брэд Питт - Бойцовский клуб: дерзкий Тайлер Дарден",
            "p": "Павел Дуров - Программист в изгнании: с ноутбуком на пляже",
            "m": "Михаил Боярский - Мушкетер: в шляпе с пером и шпагой",
            "f": "Федор Бондарчук - Фантастический режиссер: на съемочной площадке",
            "d": "Дмитрий Нагиев - Дока с экрана: в черных очках",
            "t": "Том Харди - Тихий воин: безмолвный Макс",
            "n": "Николай Басков - Нотный принц: в белом костюме",
            "l": "Леонардо ДиКаприо - Ледяной выживший: в шкурах",
            "g": "Гоша Куценко - Гангстер: в кожаной куртке",
            "k": "Константин Хабенский - Космический герой: в скафандре",
            "h": "Хью Джекман - Харизматичный Росомаха: с когтями",
            "zh": "Жан-Клод Ван Дамм - Жесткий каратист: в шпагате",
            "ch": "Ченнинг Татум - Чаровник-танцор: в движении",
            "sh": "Шон Коннери - Шпион 007: в смокинге с пистолетом",
            "r": "Роберт Дауни-мл. - Робот в броне: Железный человек",
            "z": "Захар Прилепин - Задумчивый писатель: с книгой и бородой",
            "c": "Сергей Безруков - Суровый Есенин: с трагичным взглядом",
            "s": "Сильвестр Сталлоне - Солдат Рэмбо: с пулеметом и повязкой",
            "": "Джеки Чан - Мастер трюков: прыгающий с крыши с улыбкой",
        }

        # Словарь женских актеров на основе инициалов (гласные)
        self.female_actors = {
            "y": "Юлия Пересильд - Космическая героиня: в скафандре",
            "bi": "Блейк Лайвли - Блондинка в сплетнях: в платье",
            "pi": "Пенелопа Крус - Пылкая испанка: в красном",
            "mi": "Мила Йовович - Миссия невыполнима: с оружием",
            "di": "Дженнифер Лоуренс - Девушка-стрелок: с луком",
            "ti": "Тильда Суинтон - Таинственная волшебница: в белом",
            "ni": "Натали Портман - Нежная балерина: в пачке",
            "li": "Лили Коллинз - Легкая романтика: в Париже",
            "ji": "Джулия Робертс - Жизнерадостная красотка: с улыбкой",
            "qi": "Кира Найтли - Королева пиратов: в шляпе",
            "xi": "Сиенна Миллер - Хиппи-звезда: в богемном стиле",
        }
        
        self.fictional_actors = {
            "w": "Винни-Пух - медведь с горшочком мёда, красная футболка, любитель немножко подкрепиться",
            "bu": "Буратино - деревянный мальчик с длинным носом, золотой ключик, яркая шапочка с кисточкой",
            "pu": "Пушок (из 'Трёх котов') - белый котёнок в голубом комбинезоне, любознательный и мечтательный",
            "mu": "Муми-тролль - белый круглый тролль с большим носом из финских сказок",
            "fu": "Фунтик - поросёнок в шляпе, сбежавший от госпожи Беладонны",
            "du": "Дюймовочка - крошечная девочка, родившаяся из цветка, путешествующая с ласточкой",
            "tu": "Тутанхамон - юный фараон с золотой маской, древнеегипетскими одеждами",
            "nu": "Нуф-Нуф - поросёнок из сказки Три поросёнка, строитель дома из дерева",
            "lu": "Лунтик - фиолетовое существо родившееся на Луне, с большими ушами",
            "gu": "Гулливер - путешественник среди лилипутов, высокий рост по сравнению с окружающими, связанный верёвками",
            "ku": "Кузя (домовёнок) - лохматый домовой в красной рубахе с мешком за спиной",
            "hu": "Хуч (пёс из мультфильма Пёс и кот) - рыжий пёс с чёрными ушами, любитель поесть",
            "zhu": "Жулики (Братья Гавс) - банда преступников в полосатой тюремной одежде и с номерами",
            "chu": "Чуковский Корней - знаменитый писатель с густой бородой, в очках, автор Мойдодыра и Айболита",
            "shu": "Шушара (из Незнайки) - человечек-учёный в фиолетовом костюме с большим носом",
            "ru": "Жуков Георгий (маршал) - военная форма с множеством наград, характерная фуражка, суровое выражение лица",
            "zu": "Змей Горыныч – трёхглавый дракон, изрыгающий огонь",
            "cu": "Цыпа (цыплёнок из «Курочки Рябы») – жёлтый пушистый малыш",
            "su": "Супермен – герой в синем костюме и красном плаще"
        }

        self.gods_actors = {
            "yu": "Юрий Гагарин (первый человек в космосе) - космический скафандр, шлем, знаменитая улыбка",
            "nü": "Нюй-ва (китайская богиня-создательница) - тело наполовину женщины, наполовину змеи, создательница человечества",
            "lü": "Люцифер (падший ангел) - красивое лицо с дьявольскими чертами, сломанные крылья, демонические рога",
            "ju": "Юпитер (римский бог) - лавровый венок, скипетр, гром и молнии",
            "qu": "Кутузов (русский полководец) - военный мундир, повязка на глазу, седые усы",
            "xu": "Хуэй-цзун (китайский император) - жёлтые императорские одежды, свиток с каллиграфией, корона",
        }

    def load_graphics_data(self, file_path):
        """Load stroke data from makemeahanzi graphics.txt"""
        characters = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    characters[data['character']] = {
                        'strokes': data['strokes'],
                        'medians': data['medians']
                    }
            print(f"Loaded stroke data for {len(characters)} characters")
        except FileNotFoundError:
            print(f"Error: {file_path} not found. Stroke order will not be included.")
        return characters
                
    def create_stroke_image(self, word, output_path):
        """Use existing SVG files for each character without combining them"""
        svg_paths = []
        
        # For each character in the word, find its corresponding SVG file
        for char in word:
            # Convert character to Unicode code point
            code_point = ord(char)
            
            # Check for SVG file in svgs directory
            svg_path = f"svgs/{code_point}.svg"
            if not os.path.exists(svg_path):
                # Try with "-still" suffix
                svg_path = f"svgs-still/{code_point}-still.svg"
                if not os.path.exists(svg_path):
                    print(f"Warning: No SVG file found for '{char}' (code point {code_point})")
                    continue
            
            svg_paths.append(svg_path)
            print(f"Found existing SVG for '{char}' at {svg_path}")
        
        if not svg_paths:
            return None
        
        # Add all SVGs to media files
        for svg_path in svg_paths:
            self.media_files.append(svg_path)
        
        # Return the first SVG path to be used as the primary reference
        primary_svg_path = svg_paths[0]
        
        # For multi-character words, we'll need to update how we display the SVGs
        if len(svg_paths) > 1:
            # Instead of creating a combined SVG, we'll just return the first one
            # But we'll update the process_word method to include all SVGs in the note
            return primary_svg_path, svg_paths
        else:
            # For single character, just return the SVG path
            return primary_svg_path    

    def get_pinyin(self, hanzi):
        """Генерируем простой пиньинь для иероглифа"""
        raw_pinyin = pinyin(hanzi, style=Style.TONE3)
        return " ".join(["".join(p) for p in raw_pinyin])

    def color_pinyin(self, pinyin_text):
        """Форматируем пиньинь с цветными тонами в HTML"""
        result = ""
        syllables = pinyin_text.split()

        for syllable in syllables:
            tone = None
            for char in syllable:
                if char.isdigit():
                    tone = char
                    break

            if tone:
                syllable_without_tone = syllable.replace(tone, "")
                result += f'<span class="tone{tone}">{syllable_without_tone}{tone}</span> '
            else:
                result += f"{syllable} "

        return result.strip()

    def get_meaning(self, hanzi):
        """Разбирает иероглиф на компоненты используя локальную базу"""
        data = self.components_db.get_hanzi_components(hanzi)
        meaning = ""
        if data:
            meaning = data.get('definition', '')
            return meaning
            
    # def get_meaning(self, hanzi):
    #     try:
    #         result = asyncio.run(google_translate(hanzi))
    #         if result:
    #             return result
    #     except Exception as e:
    #         print(f"Ошибка при обращении к Google Translate для {hanzi}: {e}")
    #         return None

        """Простое значение на русском (временный словарь)"""
        common_words = {
            "你": "ты",
            "好": "хороший",
            "我": "я",
            "爱": "любовь",
            "家": "дом; семья",
            "人": "человек",
            "中": "середина",
            "国": "страна",
        }
        return common_words.get(hanzi, "Значение не найдено")

    
    def decompose_hanzi(self, hanzi):
        """Разбирает иероглиф на компоненты используя локальную базу"""
        data = self.components_db.get_hanzi_components(hanzi)
        
        if data:
            components_info = []
            for comp in data['components']:
                # Можно добавить поиск значений для каждого компонента
                components_info.append(comp)
            
            # return (
            #     f"Структура: {data['structure']}\n"
            #     f"Компоненты: {' + '.join(components_info)}\n"
            #     f"Компоненты с значением: {data['components_with_meaning']}\n"
            #     f"Радикал: {data['radical']}\n"
            #     f"Этимология: {data['etymology']}\n"
            #     f"Значение: {data['definition']}"
            # )
            return (
                # f"Структура: {data['structure']}\n"
                # f"Компоненты: {' + '.join(components_info)}\n"
                f"{data['components_with_meaning']}\n"
                # f"Радикал: {data['radical']}\n"
                # f"Этимология: {data['etymology']}\n"
                # f"Значение: {data['definition']}"
            )         
        
        # Локальный запасной вариант
        decomposition = self.component_data.get(hanzi, {})
        if decomposition:
            components = decomposition.get("components", [])
            meanings = decomposition.get("meanings", [])
            result = []
            for comp, meaning in zip(components, meanings):
                comp_info = f"{comp}"
                if meaning:
                    comp_info += f" ({meaning})"
                result.append(comp_info)
            return " + ".join(result) if result else "Не удалось разобрать"
        
        return self.visual_decomposition(hanzi)

    def parse_separated_values(self, input_string):
        """
        Parse a string containing values separated by commas or semicolons into an ordered list.
        
        Args:
            input_string (str): String containing values separated by , or ;
            
        Returns:
            list: Ordered list of values with whitespace stripped
        """
        # Replace semicolons with commas to standardize the separator
        standardized = input_string.replace(';', ',')
        
        # Split by commas and strip whitespace from each item
        values = [item.strip() for item in standardized.split(',')]
        
        # Remove any empty strings that might result from splitting
        values = [item for item in values if item]
        
        return values

    def generate_space(self, pinyin_text):
            """Генерируем пространство с актером на основе финали и инициала"""
            pinyin_syllable = pinyin_text.split()[0]  # Берем первый слог
            tone = None
            for char in pinyin_syllable:
                if char.isdigit():
                    tone = char
                    break

            # Извлекаем финаль
            final = None
            for f in self.spaces.keys():
                if pinyin_syllable.endswith(f + (tone or "")) or (f == "null" and not any(pinyin_syllable.endswith(x + (tone or "")) for x in self.spaces.keys() if x != "null")):
                    final = f
                    break

            # Удаляем тон для поиска инициала
            pinyin_without_tone = re.sub(r'\d', '', pinyin_syllable)
            
            # Создаем объединенный словарь всех актеров
            all_actors = {}
            all_actors.update(self.male_actors)
            all_actors.update(self.female_actors)
            all_actors.update(self.fictional_actors)
            all_actors.update(self.gods_actors)
            
            # Ищем наиболее длинное совпадение инициала
            actor = None
            initial = ""
            
            # Сортируем ключи по убыванию длины для поиска наиболее длинного совпадения
            for init in sorted(all_actors.keys(), key=len, reverse=True):
                if pinyin_without_tone.startswith(init):
                    initial = init
                    actor = all_actors[init]
                    break
            
            # Если инициал не найден, используем Джеки Чана по умолчанию (для "")
            if not actor:
                actor = self.male_actors.get("", "Неизвестный актер")

            # Генерируем пространство и актера
            if final:
                space_name = self.spaces[final]["name"]
                tone_space = self.spaces[final]["tones"].get(tone, "Неизвестное место")
                return f"({actor}) {space_name} - {tone_space}"
            return "Неизвестное пространство"

    def get_audio_from_forvo(self, hanzi):
        """Получаем аудио произношения с Forvo API"""
        audio_dir = "forvo_audio"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
        audio_file_path = f"{audio_dir}/{hanzi}_audio.mp3"
        if os.path.exists(audio_file_path):
            return audio_file_path
        try:
            encoded_hanzi = urllib.parse.quote(hanzi)
            forvo_api_key = os.getenv("FORVO_API_KEY")  # Укажи ключ в переменных окружения
            api_url = f"https://apifree.forvo.com/key/{forvo_api_key}/format/json/action/word-pronunciations/word/{encoded_hanzi}/language/zh"
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if "items" in data and data["items"]:
                    audio_url = sorted(data["items"], key=lambda x: int(x.get("num_positive_votes", 0)), reverse=True)[0]["pathmp3"]
                    audio_response = requests.get(audio_url)
                    if audio_response.status_code == 200:
                        with open(audio_file_path, "wb") as f:
                            f.write(audio_response.content)
                        return audio_file_path
            return None
        except Exception as e:
            print(f"Ошибка при загрузке аудио для {hanzi}: {e}")
            return None

    def _build_hanzi_story_prompt(self, hanzi, primary_meaning, actor, location, components):
        """Формирует промпт для OpenAI API"""
        components_str = ', '.join([f'{comp} ({comp_meaning})' for comp, comp_meaning in components]) if components else 'нет компонентов'
        return f"""
        Создай яркую, абсурдную и запоминающуюся историю по методу Hanzi Movie Method для изучения китайского иероглифа.
        Данные:
        - Иероглиф: {hanzi}
        - Значение: {primary_meaning}
        - Место действия: {location}
        - Главный герой: {actor}
        - Компоненты иероглифа: {components_str}

        Требования к истории:
        - Она должна быть визуальной, эмоциональной и слегка абсурдной, чтобы легко запоминалась.
        - Связывай актера, место, компоненты (если есть) и значение иероглифа в короткий сюжет (2-4 предложения).
        - Компоненты должны появляться как объекты, действия или символы в истории.
        - История должна быть короткой чтобы быстро читаться и без лишних (не связанных с Иероглиф: {hanzi}, Значение: {primary_meaning}, Компоненты иероглифа: {components_str} ) деталей.
        - История должна помогать запомнить иероглиф {hanzi} и его значение '{primary_meaning}'.
        - В истории должен быть показан сам иероглиф {hanzi} в контексте.
        - Пиши на русском языке.
        - Размер истории: 2-4 предложения.
        """

    def generate_hanzi_movie_story(self, hanzi, meaning, space, hint):
        """
        Генерирует запоминающуюся историю по Hanzi Movie Method с использованием OpenAI API.
        """
        # Извлечение актера и локации
        actor_match = re.match(r'\((.*?)\)\s*(.*)', space)
        actor = actor_match.group(1) if actor_match else "Неизвестный актер"
        location = actor_match.group(2) if actor_match else "Неизвестное место"

        # Разбор значения
        meanings = self.parse_separated_values(meaning)
        primary_meaning = meanings[0] if meanings else "нечто"

        # Разбор компонентов
        components = []
        if hint.strip():
            component_matches = re.findall(r'(\S+)\s*\((.*?)\)', hint)
            components = [(comp, comp_meaning) for comp, comp_meaning in component_matches]

        # Формирование промпта
        prompt = self._build_hanzi_story_prompt(hanzi, primary_meaning, actor, location, components)

        try:
            # Инициализация клиента OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not client.api_key:
                raise OpenAIError("Ключ OpenAI API не найден")

            # Запрос к API
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты креативный помощник для создания мнемонических историй."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=OPENAI_MAX_TOKENS,
                temperature=OPENAI_TEMPERATURE
            )

            # Извлечение истории
            story = response.choices[0].message.content.strip()
            return story

        except OpenAIError as e:
            print(f"Ошибка при вызове OpenAI API для {hanzi}: {e}")
            return f"{actor} в {location} видит иероглиф {hanzi} и вспоминает '{primary_meaning}'."

    def process_hanzi(self, hanzi):
        """Обрабатываем один иероглиф для колоды"""
        hanzi = HanziConv.toSimplified(hanzi)
        print(f"Обрабатываем: {hanzi}")

        # Получаем данные
        pinyin_text = self.get_pinyin(hanzi)
        colored_pinyin = self.color_pinyin(pinyin_text)
        meanings = self.get_meaning(hanzi)
        meanings_list = self.parse_separated_values(meanings)
        meaning_ru = asyncio.run(google_translate_en(meanings_list[0]))
        meaning = ", ".join(meanings_list)
        space = self.generate_space(pinyin_text)
        hint = str()
        audio_file = self.get_audio_from_forvo(hanzi)

        # Обрабатываем аудио
        audio_tag = ""
        if audio_file and os.path.exists(audio_file):
            audio_filename = os.path.basename(audio_file)
            audio_tag = f"[sound:{audio_filename}]"
            self.media_files.append(audio_file)
        
        # Получаем компоненты иероглифа
        
        decomposition = self.decompose_hanzi(hanzi)

        if decomposition:
            hint += f" {decomposition}"
            
        else:
            hint += " (не удалось разобрать)"
        # Получаем иероглиф в упрощенном виде

        story = self.generate_hanzi_movie_story(hanzi, meaning_ru, space, hint)

        # Generate stroke order image references
        stroke_image_result = self.create_stroke_image(hanzi, f"strokes/{hanzi}_strokes.png")

        if stroke_image_result:
            if isinstance(stroke_image_result, tuple):
                # We have multiple SVGs for a multi-character word
                primary_svg_path, all_svg_paths = stroke_image_result
                
                # Create HTML to display all SVGs side by side
                stroke_tag = ""
                for svg_path in all_svg_paths:
                    base_filename = os.path.basename(svg_path)
                    stroke_tag += f'<img src="{base_filename}" style="height:100px; margin-right:10px;">'
            else:
                # Single SVG
                base_filename = os.path.basename(stroke_image_result)
                stroke_tag = f'<img src="{base_filename}">'
        else:
            stroke_tag = ""

        # Создаем заметку Anki
        note = genanki.Note(
            model=self.model,
            fields=[
                hanzi,          # Иероглиф
                pinyin_text,    # Пиньинь
                colored_pinyin, # ЦветнойПиньинь
                meaning,        # Значение
                space,          # Пространство с актером
                hint,           # Подсказка
                audio_tag,      # Аудио
                story,          # История
                stroke_tag,        # StrokeOrder
            ],
        )
        self.deck.add_note(note)

        time.sleep(1)  # Ограничение скорости для API
        return {"иероглиф": hanzi, "пиньинь": pinyin_text, "значение": meaning, "пространство": space, "подсказка": hint}

    def create_deck_from_file(self, input_hanzi, output_file=output_deck):
        """Создаем колоду Anki из списка иероглифов"""
        results = []
        for hanzi in input_hanzi:
            result = self.process_hanzi(hanzi)
            results.append(result)

        # Создаем пакет с медиафайлами
        package = genanki.Package(self.deck)
        if self.media_files:
            package.media_files = self.media_files

        # Записываем в файл
        package.write_to_file(output_file)
        print(f"Создана колода Anki: {output_file}")

        # Write to file
        package.write_to_file(output_file)
        print(f"Created Anki deck: {output_file}")

        # Archive input file (your existing logic)
        if not os.path.exists(output_file_archive_path):
            os.makedirs(output_file_archive_path)
        output_filename = f'chinese_words_{datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.txt'
        with open(input_file, "r", encoding="utf-8") as f:
            with open(f"{output_file_archive_path}/{output_filename}", "w", encoding="utf-8") as f2:
                f2.write(f.read())
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("")
        print(f"Archived input file: {output_file_archive_path}/{output_filename}")

        return results


async def google_translate(word):
    translator = Translator()

    # Translate text to English (default destination language)
    translation = await translator.translate(word, src="zh-cn", dest="ru")

    if translation and translation.text:
        meaning = translation.text
        return meaning.capitalize()

async def google_translate_en(en_word):
    translator = Translator()

    # Translate text to English (default destination language)
    translation = await translator.translate(en_word, src="en", dest="ru")

    if translation and translation.text:
        meaning = translation.text
        return meaning


def check_input_duplicates(input_file, output_file_archive_path):
    new_input_words = []
    files = os.listdir(output_file_archive_path) if os.path.exists(output_file_archive_path) else []
    words = []
    for file in files:
        with open(f"input_words_hmm_archive/{file}", "r", encoding="utf-8") as f:
            words += [line.strip().replace("\u200b", "") for line in f if line.strip()]
    with open(input_file, "r", encoding="utf-8") as f:
        input_words = [line.strip().replace("\u200b", "") for line in f if line.strip()]

    # output_file = f"input_words_hmm_archive/chinese_words_{datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}.txt"
    # with open(output_file, "w", encoding="utf-8") as f:
    #     for word in words:
    #         f.write(f"{word}\n")
    # print(f"Found {len(words)} words in archive")

    input_words = list(set(input_words))
    for word in input_words:
        if not is_chinese_char(word):
            raise ValueError(f"Invalid Chinese character: {word}")
        if word in words:
            print(f"Duplicate word: {word}")
        else:
            new_input_words.append(word)
    print(f"Found {len(words)} words in archive")
    print(f"Removed {len(input_words) - len(new_input_words)} duplicates")
    print(f"Found {len(new_input_words)} words to process")
    with open(input_file, "w", encoding="utf-8") as f:
        for word in new_input_words:
            f.write(f"{word}\n")
    return new_input_words

def is_chinese_char(text):
    if not text or len(text) == 0:
        return False
    for char in text:
        code_point = ord(char)
        if not ((0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF)):
            return False
    return True


def get_hanzi_component_meaning(hanzi):
    """
    Получаем компоненты иероглифа с использованием локальной базы данных.
    Возвращает структуру, компоненты, радикал и этимологию.
    """
    components_db = HanziComponentsDB('hanzi_db.txt')
    data = components_db.get_components(hanzi)
    
    if data:
        meaning_values = parse_separated_values(data.get('definition'))
        meanings = ", ".join(meaning_values)
        return meanings
    
    return None


def parse_separated_values(input_string):
    """
    Parse a string containing values separated by commas or semicolons into an ordered list.
    
    Args:
        input_string (str): String containing values separated by , or ;
        
    Returns:
        list: Ordered list of values with whitespace stripped
    """
    # Replace semicolons with commas to standardize the separator
    standardized = input_string.replace(';', ',')
    
    # Split by commas and strip whitespace from each item
    values = [item.strip() for item in standardized.split(',')]
    
    # Remove any empty strings that might result from splitting
    values = [item for item in values if item]
    
    return values


if __name__ == "__main__":
    generator = HanziSpacesGenerator()

    # Пример использования с файлом

    # Создаем пример файла, если его нет
    if not os.path.exists(input_file):
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("你\n好\n我\n爱\n家\n")
        print(f"Создан пример файла: {input_file}")

    # Обрабатываем файл
    checked_hanzi = check_input_duplicates(input_file, output_file_archive_path)
    results = generator.create_deck_from_file(checked_hanzi)

    # Выводим результаты
    print("\nОбработанные иероглифы:")
    for result in results:
        print(f"{result['иероглиф']} ({result['пиньинь']}): {result['значение']}, {result['пространство']}")