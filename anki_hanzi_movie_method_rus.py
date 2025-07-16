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

# input_file = "chinese_words_hanzi_movie_method.txt"
input_file = "du_chinese_words_hanzi_movie_method.txt"
output_file_archive_path = "input_words_du_chinese_hmm_archive"

anki_deck_name = "DuChinese Hanzi Spaces with Actors (Русский)"
output_deck = "duchinese_hanzi_spaces_actors_rus.apkg"

# --- Constants for OpenAI ---
OPENAI_MODEL = "gpt-4o-mini"
# OPENAI_MODEL = "o3-mini-2025-01-31"
OPENAI_MAX_TOKENS = 300
OPENAI_TEMPERATURE = 0.8
# --- FIXED: Added missing constants for DALL-E ---
OPENAI_IMAGE_MODEL = "dall-e-3"
# OPENAI_IMAGE_MODEL = "dall-e-2"
IMAGE_SIZE = "1024x1024"

class HanziComponentsDB:
    def __init__(self, db_file='hanzi_db.txt'):
        self.db = self._load_db(db_file)
        self.component_meanings = {
            '⿰': 'слева направо', '⿱': 'сверху вниз', '⿲': 'три части горизонтально',
            '⿳': 'три части вертикально', '⿴': 'внешнее-внутреннее', '⿵': 'верхняя рамка',
            '⿶': 'нижняя рамка', '⿷': 'левая рамка', '⿸': 'верхне-левая рамка',
            '⿹': 'верхне-правая рамка', '⿺': 'нижне-левая рамка', '⿻': 'пересекающиеся компоненты'
        }

    def _load_db(self, db_file):
        db = {}
        try:
            with open(db_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        db[data['character']] = data
        except FileNotFoundError:
            print(f"Файл {db_file} не найден! Будет использован пустой словарь.")
        return db

    def parse_separated_values(self, input_string):
        standardized = str(input_string).replace(';', ',')
        values = [item.strip() for item in standardized.split(',')]
        return [item for item in values if item]

    def get_hanzi_components(self, hanzi):
        if hanzi not in self.db:
            return None
        data = self.db[hanzi]
        decomposition = data.get('decomposition', '')
        structure, components = self._parse_decomposition(decomposition)
        new_components = []
        for component in components:
            if component:
                meanings_list = ""
                component_data = self.db.get(component, {})
                meaning_data = component_data.get('definition', '')
                if meaning_data:
                    meanings_list = self.parse_separated_values(meaning_data)
                    meanings_list = meanings_list[0] if meanings_list else ""
                new_components.append(f'{component} ({meanings_list})')
        components_with_meaning = ", ".join(new_components)
        return {
            'character': hanzi, 'structure': structure, 'components': components,
            'components_with_meaning': components_with_meaning, 'radical': data.get('radical', ''),
            'etymology': data.get('etymology', {}).get('hint', ''), 'definition': data.get('definition', '')
        }

    def _parse_decomposition(self, decomposition):
        if not decomposition:
            return '', []
        structure_symbol = decomposition[0]
        structure = self.component_meanings.get(structure_symbol, 'неизвестная структура')
        components = [char for char in decomposition[1:] if char not in self.component_meanings]
        return structure, components

class HanziSpacesGenerator:
    def __init__(self):
        self.components_db = HanziComponentsDB('hanzi_db.txt')
        # --- FIXED: Corrected Anki model definition ---
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name,
            fields=[
                {"name": "Иероглиф"},
                {"name": "Пиньинь"},
                {"name": "ЦветнойПиньинь"},
                {"name": "Значение"},
                {"name": "Пространство"},
                {"name": "Подсказка"},
                {"name": "Аудио"},
                {"name": "История"},
                {"name": "ИсторияИзображение"},  # New field for the story image
                {"name": "StrokeOrder"},
            ],
            templates=[
                {
                    "name": "Узнавание",
                    "qfmt": '<div class="stroke-order">{{StrokeOrder}}</div>',
                    "afmt": """
                        <div class="stroke-order">{{StrokeOrder}}</div><hr>
                        <div class="pinyin">{{Пиньинь}}</div>
                        <div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="meaning">{{Значение}}</div>
                        <div class="space"><b>Пространство:</b> {{Пространство}}</div>
                        <div class="hint"><b>Подсказка:</b> {{Подсказка}}</div>
                        <div class="story"><b>История:</b> {{История}}</div>
                        <div class="story-image">{{ИсторияИзображение}}</div>
                        {{Аудио}}
                    """,
                },
                {
                    "name": "Вспоминание",
                    "qfmt": '<div class="meaning">{{Значение}}</div><div class="space"><b>Пространство:</b> {{Пространство}}</div>',
                    "afmt": """
                        <div class="meaning">{{Значение}}</div><hr>
                        <div class="hanzi">{{Иероглиф}}</div>
                        <div class="pinyin">{{Пиньинь}}</div>
                        <div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="space"><b>Пространство:</b> {{Пространство}}</div>
                        <div class="hint"><b>Подсказка:</b> {{Подсказка}}</div>
                        <div class="story"><b>История:</b> {{История}}</div>
                        <div class="story-image">{{ИсторияИзображение}}</div>
                        {{Аудио}}
                    """,
                },
            ],
            css="""
                .card { font-family: Arial, sans-serif; font-size: 16px; text-align: center; color: black; background-color: white; padding: 20px; }
                .hanzi { font-size: 50px; font-weight: bold; margin-bottom: 15px; }
                .stroke-order img, .stroke-order svg { max-width: 200px; height: 100px; margin-top: 15px; margin-right: 10px; }
                .pinyin, .colored-pinyin { font-size: 18px; margin-bottom: 10px; }
                .meaning { font-size: 20px; margin-bottom: 15px; }
                .space, .hint, .story { font-size: 16px; margin-top: 10px; }
                .story { color: #333; font-style: italic; }
                .story-image img { max-width: 350px; height: auto; margin-top: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
                .tone1 { color: blue; } .tone2 { color: green; } .tone3 { color: purple; } .tone4 { color: red; } .tone5 { color: gray; }
            """,
        )
        self.deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), anki_deck_name)
        self.media_files = []
        # (Dictionaries for spaces and actors remain unchanged)
        self.spaces = {
            "a": {"name": "Арт-галерея", "tones": {"1": "Вестибюль", "2": "Главный выставочный зал", "3": "Мастерская художников", "4": "Кабинет куратора"}},
            "o": {"name": "Отель", "tones": {"1": "Ресепшн", "2": "Главный коридор", "3": "Общая гостиная", "4": "Номер отдыха"}},
            "e": {"name": "Эко-дом", "tones": {"1": "Солнечная веранда", "2": "Центральная гостиная", "3": "Зимний сад", "4": "Медитационная комната"}},
            "ai": {"name": "Айсберг-хижина", "tones": {"1": "Ледяной вход", "2": "Центральный зал", "3": "Теплый очаг", "4": "Спальный отсек"}},
            "ei": {"name": "Эйфелева башня (жилые помещения)", "tones": {"1": "Лифтовой холл", "2": "Панорамный салон", "3": "Инженерная комната", "4": "Смотровая площадка"}},
            "ao": {"name": "Вау-хаус", "tones": {"1": "Футуристический вход", "2": "Главный атриум с панорамной крышей", "3": "Комната аудиовизуальных эффектов", "4": "Спальня-трансформер"}},
            "ou": {"name": "Оукхаус (дубовый дом)", "tones": {"1": "Прихожая с деревянной отделкой", "2": "Каминный зал", "3": "Библиотека", "4": "Мансарда"}},
            "an": {"name": "Ангар-лофт", "tones": {"1": "Грузовой вход", "2": "Центральное пространство", "3": "Технический отсек", "4": "Жилая зона"}},
            "ang": {"name": "Английский коттедж", "tones": {"1": "Садовая калитка", "2": "Гостиная с камином", "3": "Чайная комната", "4": "Спальня с балдахином"}},
            "en": {"name": "Энциклопедическая библиотека-дом", "tones": {"1": "Архивный вход", "2": "Главный читальный зал", "3": "Кабинет каталогизации", "4": "Кабинет редких изданий"}},
            "eng": {"name": "Инглиш Мэнор (английское поместье)", "tones": {"1": "Парадный вход", "2": "Бальный зал", "3": "Охотничья комната", "4": "Господская спальня"}},
            "ong": {"name": "Замок Конга", "tones": {"1": "Крепостные ворота", "2": "Тронный зал", "3": "Сокровищница", "4": "Королевские покои"}},
            "null": {"name": "Нулевой дом (минималистичный дом)", "tones": {"1": "Стеклянный вход", "2": "Открытое пространство", "3": "Медитативная зона", "4": "Спальная капсула"}},
        }
        self.male_actors = {
            "b": "Брэд (Питт) 'Бойцовский клуб' — Брэд в роли Тайлера Дардена, дерзкого и бунтарского.",
            "p": "Пушкин — поэт во фраке, с бакенбардами, пером и романтическим взглядом.",
            "m": "Михаил (Боярский)  'Мушкетер' — Михаил в шляпе с пером и шпагой из 'Трех мушкетеров'",
            "f": "Фродо — хоббит с кольцом, в плаще, с мечом Жалом и отважным взглядом.",
            "t": "Тесла — изобретатель в пиджаке, с молниями из катушки и загадочным взглядом.",
            "d": "Дарт Вейдер — злодей в чёрной броне, с красным световым мечом и тяжёлым дыханием.",
            "n": "Наполеон — полководец в треуголке и мундире, с рукой за пазухой и властным взглядом.",
            "l": "Леонардо (ДиКаприо) 'Ледяной выживший' — Лео в шкурах из 'Выжившего', борющийся с медведем.",
            "g": "Гоша (Куценко) 'Гангстер' — Гоша в кожаной куртке из 'Антикиллера'",
            "k": "Кинг Конг — гигантская горилла, рычащая, бьющая себя в грудь, с дикой мощью.",
            "h": "Хью (Джекман) 'Харизматичный Росомаха' — Хью с когтями из 'Людей Икс'",
            "zh": "Джокер — коварный злодей с зелёными волосами, в фиолетовом костюме, с картами и безумной ухмылкой.",
            "ch": "Черчилль Винстон — харизматичный премьер с сигарой, в котелке и строгом костюме, держащий речь.",
            "sh": "Шон (Коннери) 'Шпион 007' — Шон в смокинге с пистолетом из 'Джеймса Бонда'",
            "r": "Железный человек _Красный с золотом костюм, реактор светится, руки в репульсорах — мощный, технологичный, готов к бою.",
            "z": "Зорро — мститель в чёрной маске, с шпагой, плащом и знаком 'Z'.",
            "c": "Цой Виктор — рок-музыкант в кожаной куртке, с гитарой и бунтарским взглядом.",
            "s": "Сильвестр (Сталлоне) 'Солдат Рэмбо' — Сильвестр с пулеметом и повязкой на голове.",
            "null": "(без инициали) Джеки (Чан) 'Мастер трюков' — Джеки, прыгающий с крыши с улыбкой из 'Полицейской истории'."
        }
        self.female_actors = {
            "y": "Исида — египетская богиня в сияющем платье, с рогами, солнечным диском и магическим жезлом.",
            "bi": "Биби Дун — холодная императрица в тёмно-фиолетовых одеждах в высокой короне с  посохом",
            "pi": "Пенелопа (Крус) 'Пылкая испанка' — Пенелопа в красном платье",
            "mi": "Мила (Йовович) Мила с оружием из 'Обители зла' (Milla Jovovich).",
            "di": "маленькая серая кошка из аниме _Sailor Moon_ с магическими способностями , спутница Чиби Усы и Артемиды. Грациозная серая кошка с красным ошейником и колокольчиком, иногда в человеческой форме как юная девушка с фиолетовыми волосами и лунным символом на лбу",
            "ti": "Тильда (Суинтон) 'Таинственная волшебница' — Тильда в белом из 'Хроник Нарнии' (Tilda Swinton)",
            "ni": "Ника — богиня победы в белой тунике, с крыльями, лавровым венком и жезлом",
            "li": "Лили (Коллинз) 'Легкая романтика' — Лили в Париже из 'Эмили в Париже' (Lily Collins)",
            "ji": "Джулия (Робертс) 'Жизнерадостная красотка' — Джулия с улыбкой из 'Красотки' (Julia Roberts)",
            "qi": "Кира (Найтли) 'Королева пиратов' — Кира в шляпе из 'Пиратов Карибского моря' (Keira Knightley)",
            "xi": "Си Ванму — Царица-Мать Запада из китайской мифологии, в золотых одеждах, с короной из перьев феникса, магическим персиком и фениксами. Верхом на журавле"
        }
        self.fictional_actors = {
            "w": "Винни-Пух - медведь с горшочком мёда, красная футболка, любитель немножко подкрепиться",
            "bu": "Буратино - деревянный мальчик с длинным носом, золотой ключик, яркая шапочка с кисточкой",
            "pu": "Пушок (из 'Трёх котов') - белый котёнок в голубом комбинезоне, любознательный и мечтательный",
            "mu": "Муми-тролль - белый круглый тролль с большим носом из финских сказок",
            "fu": "Фунтик - поросёнок в шляпе, сбежавший от госпожи Беладонны",
            "du": "Дюймовочка - крошечная девочка, родившаяся из цветка, путешествующая с ласточкой",
            "tu": "Тутанхамон - юный фараон с золотой маской, древнеегипетскими одеждами",
            "nu": "Нуф-Нуф - поросёнок из сказки 'Три поросёнка', строитель дома из дерева",
            "lu": "Лунтик - фиолетовое существо, 'родившееся на Луне', с большими ушами",
            "gu": "Гулливер - путешественник среди лилипутов, высокий рост по сравнению с окружающими, связанный верёвками",
            "ku": "Кузя (домовёнок) - лохматый домовой в красной рубахе с мешком за спиной",
            "hu": "Хуч (пёс из мультфильма 'Пёс и кот') - рыжий пёс с чёрными ушами, любитель поесть",
            "zhu": "Джуд Лоу - харизматичный сыщик в стильном костюме, с тростью и лукавой улыбкой.",
            "chu": "Чубакка — огромный вуки из Звёздных войн с рыжей шерстью, арбалетом и громким рёвом",
            "shu": "Шушу (крыс из 'Рататуя') – гурман в поварском колпаке",
            "ru": "Жужу — Зоро Ророноа из _One Piece_ с тремя катанами, зелёными волосами и саркастичным характером.",
            "zu": "Змей Горыныч – трёхглавый дракон, изрыгающий огонь",
            "cu": "Цунами — гигантская бурлящая волна, с пеной и разрушительной силой.",
            "su": "Сунь Укун — Король обезьян в красном плаще, с золотым посохом и озорным взглядом.",
        }
        self.gods_actors = {
            "yu": "Юрий Гагарин (первый человек в космосе) - космический скафандр, шлем, знаменитая улыбка",
            "nü": "Нюй-ва (китайская богиня-создательница) - тело наполовину женщины, наполовину змеи, создательница человечества",
            "lü": "Люцифер (падший ангел) - красивое лицо с дьявольскими чертами, сломанные крылья, демонические рога",
            "ju": "Юлий Цезарь (римский император) - лавровый венок, тога, знаменитый профиль на монетах",
            "qu": "Чьюя — Курапика из _Hunter x Hunter_ с длинными светлыми волосами, красными глазами и магическими цепями.",
            "xu": "Сюань-у — Чёрная Черепаха-Змея, небесный страж Севера, в чёрных доспехах, с древним свитком или мечом, окружённый водой и туманом."
        }

    def create_stroke_image(self, word):
        svg_paths = []
        for char in word:
            code_point = ord(char)
            svg_path = f"svgs/{code_point}.svg"
            if not os.path.exists(svg_path):
                svg_path = f"svgs-still/{code_point}-still.svg"
                if not os.path.exists(svg_path):
                    print(f"Warning: No SVG file found for '{char}' (code point {code_point})")
                    continue
            svg_paths.append(svg_path)
        if not svg_paths:
            return None
        for svg_path in svg_paths:
            self.media_files.append(svg_path)
        if len(svg_paths) > 1:
            return svg_paths[0], svg_paths
        return svg_paths[0]

    def get_pinyin(self, hanzi):
        raw_pinyin = pinyin(hanzi, style=Style.TONE3)
        return " ".join(["".join(p) for p in raw_pinyin])

    def color_pinyin(self, pinyin_text):
        result = []
        for syllable in pinyin_text.split():
            tone = next((char for char in syllable if char.isdigit()), None)
            if tone:
                syllable_without_tone = syllable.replace(tone, "")
                result.append(f'<span class="tone{tone}">{syllable_without_tone}{tone}</span>')
            else:
                result.append(syllable)
        return " ".join(result)

    def get_meaning(self, hanzi):
        data = self.components_db.get_hanzi_components(hanzi)
        return data.get('definition', '') if data else ""

    def decompose_hanzi(self, hanzi):
        data = self.components_db.get_hanzi_components(hanzi)
        if data and data['components_with_meaning']:
            return f"{data['components_with_meaning']}"
        return "Не удалось разобрать"

    def generate_space(self, pinyin_text):
        pinyin_syllable = pinyin_text.split()[0]
        tone = next((char for char in pinyin_syllable if char.isdigit()), None)
        pinyin_without_tone = re.sub(r'\d', '', pinyin_syllable)
        final_key = None
        for f in self.spaces.keys():
            # Construct a regex to match the final at the end of the syllable
            # This handles cases like 'e' vs 'en' vs 'eng' correctly
            if re.search(f"{f}$", pinyin_without_tone):
                final_key = f
                break
        if final_key is None:
            final_key = "null"

        all_actors = {**self.male_actors, **self.female_actors, **self.fictional_actors, **self.gods_actors}
        initial = next((init for init in sorted(all_actors.keys(), key=len, reverse=True) if pinyin_without_tone.startswith(init)), "null")
        actor = all_actors.get(initial)
        
        if final_key and actor:
            space_name = self.spaces[final_key]["name"]
            tone_space = self.spaces[final_key]["tones"].get(tone, "Неизвестное место")
            return f"({actor}) {space_name} - {tone_space}"
        return "Неизвестное пространство"

    def get_audio_from_forvo(self, hanzi):
        # (This function remains unchanged)
        audio_dir = "forvo_audio"
        os.makedirs(audio_dir, exist_ok=True)
        audio_file_path = f"{audio_dir}/{hanzi}_audio.mp3"
        if os.path.exists(audio_file_path):
            return audio_file_path
        try:
            encoded_hanzi = urllib.parse.quote(hanzi)
            forvo_api_key = os.getenv("FORVO_API_KEY")
            api_url = f"https://apifree.forvo.com/key/{forvo_api_key}/format/json/action/word-pronunciations/word/{encoded_hanzi}/language/zh"
            response = requests.get(api_url)
            if response.status_code == 200 and "items" in response.json() and response.json()["items"]:
                items = sorted(response.json()["items"], key=lambda x: int(x.get("num_positive_votes", 0)), reverse=True)
                audio_url = items[0]["pathmp3"]
                audio_response = requests.get(audio_url)
                if audio_response.status_code == 200:
                    with open(audio_file_path, "wb") as f:
                        f.write(audio_response.content)
                    return audio_file_path
        except Exception as e:
            print(f"Ошибка при загрузке аудио для {hanzi}: {e}")
        return None

    def _build_hanzi_story_prompt(self, hanzi, primary_meaning, actor, location, components_str):
        return f"""
        Создай яркую, абсурдную и запоминающуюся историю по методу Hanzi Movie Method для изучения китайского иероглифа.
        Данные:
        - Иероглиф: {hanzi}, Значение: {primary_meaning}
        - Место действия: {location}, Главный герой: {actor}
        - Компоненты иероглифа: {components_str}
        Требования:
        - История должна быть короткой (1-2 предложения), легко запоминаемой и связывать все элементы.
        - Важно! История должна быть напрямую связана со значением компонентов иероглифа.
        - Пиши на русском языке.
        """

    # --- FIXED: Corrected function signature and logic ---
    def generate_hanzi_movie_story(self, hanzi, meaning, actor, location, hint):
        primary_meaning = self.components_db.parse_separated_values(meaning)[0] if meaning else "нечто"
        prompt = self._build_hanzi_story_prompt(hanzi, primary_meaning, actor, location, hint)
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not client.api_key: raise OpenAIError("Ключ OpenAI API не найден")
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты креативный помощник для создания мнемонических историй."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=OPENAI_MAX_TOKENS, temperature=OPENAI_TEMPERATURE
            )
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print(f"Ошибка при вызове OpenAI API для {hanzi}: {e}")
            return f"{actor} в {location} видит иероглиф {hanzi} и вспоминает '{primary_meaning}'."

    def _build_image_prompt(self, hanzi, primary_meaning, actor, location, story):
        """
        Builds a prompt focused on visual style and positive framing 
        to minimize the chance of text generation.
        """
        # Переменная `hanzi` намеренно НЕ используется в промпте,
        # так как это главный триггер для генерации псевдо-иероглифов.
        
        return (
            # 1. Задаем стиль, который редко содержит текст
            f"Фотореалистичное изображение, кинематографический свет, высокая детализация. "
            
            # 2. Описываем сцену без упоминания иероглифа
            f"Сцена, основанная на истории: '{story}'.\n"
            f"На сцене находятся: {actor} в локации '{location}'. "
            f"Изображение иллюстрирует идею '{primary_meaning}'.\n\n"
            # 3. Один, но очень сильный и простой запрет в самом конце
            f"КРАЙНЕ ВАЖНО: на изображении должна быть только сцена. Никаких букв, слов, надписей, текста, символов или логотипов. Абсолютно чистое изображение."
        )

    def generate_story_image(self, hanzi, meaning_ru, actor, location, story):
        image_dir = "story_images"
        os.makedirs(image_dir, exist_ok=True)
        image_file_path = f"{image_dir}/{hanzi}_story.png"
        if os.path.exists(image_file_path):
            print(f"Image for {hanzi} already exists. Skipping generation.")
            return image_file_path

        primary_meaning_ru = self.components_db.parse_separated_values(meaning_ru)[0] if meaning_ru else ""
        prompt = self._build_image_prompt(hanzi, primary_meaning_ru, actor, location, story)
        try:
            print(f"Generating image for {hanzi}...")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not client.api_key: raise OpenAIError("Ключ OpenAI API не найден")
            response = client.images.generate(model=OPENAI_IMAGE_MODEL, prompt=prompt, n=1, size=IMAGE_SIZE)
            image_url = response.data[0].url
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                with open(image_file_path, "wb") as f:
                    f.write(image_response.content)
                print(f"Successfully saved image for {hanzi} to {image_file_path}")
                return image_file_path
        except Exception as e:
            print(f"Error generating image for {hanzi} with DALL-E: {e}")
        return None

    def process_hanzi(self, hanzi):
        hanzi = HanziConv.toSimplified(hanzi)
        print(f"Обрабатываем: {hanzi}")

        pinyin_text = self.get_pinyin(hanzi)
        colored_pinyin = self.color_pinyin(pinyin_text)
        meaning_en = self.get_meaning(hanzi)
        meaning_ru = asyncio.run(google_translate_en(self.components_db.parse_separated_values(meaning_en)[0] if meaning_en else hanzi))
        space = self.generate_space(pinyin_text)
        hint = self.decompose_hanzi(hanzi)

        audio_tag = ""
        audio_file = self.get_audio_from_forvo(hanzi)
        if audio_file:
            audio_tag = f"[sound:{os.path.basename(audio_file)}]"
            self.media_files.append(audio_file)

        actor_match = re.match(r'\((.*?)\)\s*(.*)', space)
        actor = actor_match.group(1) if actor_match else "Неизвестный актер"
        location = actor_match.group(2) if actor_match else "Неизвестное место"
        
        story = self.generate_hanzi_movie_story(hanzi, meaning_ru, actor, location, hint)
        
        image_tag = ""
        image_file = self.generate_story_image(hanzi, meaning_ru, actor, location, story)
        if image_file:
            image_tag = f'<img src="{os.path.basename(image_file)}">'
            self.media_files.append(image_file)

        stroke_tag = ""
        stroke_image_result = self.create_stroke_image(hanzi)
        if stroke_image_result:
            if isinstance(stroke_image_result, tuple):
                _, all_svg_paths = stroke_image_result
                stroke_tag = "".join(f'<img src="{os.path.basename(p)}">' for p in all_svg_paths)
            else:
                stroke_tag = f'<img src="{os.path.basename(stroke_image_result)}">'

        # --- FIXED: Aligned Note creation with model fields ---
        note = genanki.Note(
            model=self.model,
            fields=[
                hanzi, pinyin_text, colored_pinyin, meaning_en,
                space, hint, audio_tag, story,
                image_tag, stroke_tag,
            ],
        )
        self.deck.add_note(note)

        time.sleep(20)
        return {"иероглиф": hanzi, "пиньинь": pinyin_text, "значение": meaning_en}

    def create_deck_from_file(self, input_hanzi, output_file=output_deck):
        results = [self.process_hanzi(hanzi) for hanzi in input_hanzi]
        package = genanki.Package(self.deck)
        package.media_files = self.media_files
        package.write_to_file(output_file)
        print(f"Created Anki deck: {output_file}")
        
        if os.path.exists(input_file):
            os.makedirs(output_file_archive_path, exist_ok=True)
            output_filename = f'chinese_words_{datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.txt'
            try:
                os.rename(input_file, os.path.join(output_file_archive_path, output_filename))
                print(f"Archived input file to: {output_filename}")
                with open(input_file, "w", encoding="utf-8") as f:
                    f.write("")
            except OSError as e:
                print(f"Error archiving file: {e}")

        return results

async def google_translate_en(en_word):
    if not en_word: return ""
    translator = Translator()
    try:
        translation = await translator.translate(en_word, src="en", dest="ru")
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return en_word

def check_input_duplicates(input_file, archive_path):
    if not os.path.exists(input_file): return []
    archived_words = set()
    if os.path.exists(archive_path):
        for file in os.listdir(archive_path):
            try:
                with open(os.path.join(archive_path, file), "r", encoding="utf-8") as f:
                    archived_words.update(line.strip().replace("\u200b", "") for line in f if line.strip())
            except Exception as e:
                print(f"Could not read archive file {file}: {e}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        input_words = {line.strip().replace("\u200b", "") for line in f if line.strip() and is_chinese_char(line.strip())}
    
    new_words = list(input_words - archived_words)
    print(f"Found {len(archived_words)} words in archive.")
    print(f"Removed {len(input_words) - len(new_words)} duplicates.")
    print(f"Found {len(new_words)} new words to process.")
    return new_words

def is_chinese_char(text):
    return bool(text) and all(0x4E00 <= ord(char) <= 0x9FFF or 0x3400 <= ord(char) <= 0x4DBF for char in text)

if __name__ == "__main__":
    generator = HanziSpacesGenerator()
    if not os.path.exists(input_file):
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("爱\n")
        print(f"Создан пример файла: {input_file}")

    checked_hanzi = check_input_duplicates(input_file, output_file_archive_path)
    if checked_hanzi:
        results = generator.create_deck_from_file(checked_hanzi)
        print("\nОбработанные иероглифы:")
        for result in results:
            print(f"{result['иероглиф']} ({result['пиньинь']}): {result['значение']}")
    else:
        print("No new words to process.")