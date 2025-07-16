import os
import time
import re
import asyncio
import json
from datetime import datetime
from openai import OpenAI, OpenAIError
from pypinyin import pinyin, Style
from hanziconv import HanziConv
from googletrans import Translator

# Этот скрипт содержит общие классы, которые могут быть использованы в обоих файлах.
# В более крупном проекте их можно было бы вынести в отдельный файл `common.py`.

# --- НАСТРОЙКИ ---
input_file = "input_du_chinese_words_hanzi_movie_method.txt"
output_file_archive_path = "input_words_du_chinese_hmm_archive"
STORIES_JSON_FILE = "stories/stories_for_review.json"  # Промежуточный файл для редактирования

# --- OpenAI Настройки ---
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS = 300
OPENAI_TEMPERATURE = 0.8

# --- КЛАССЫ (HanziComponentsDB и части HanziSpacesGenerator) ---

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
            print(f"Файл {db_file} не найден!")
        return db

    def parse_separated_values(self, input_string):
        standardized = str(input_string).replace(';', ',')
        values = [item.strip() for item in standardized.split(',')]
        return [item for item in values if item]

    def get_hanzi_components(self, hanzi):
        if hanzi not in self.db: return None
        data = self.db[hanzi]
        decomposition = data.get('decomposition', '')
        structure, components = self._parse_decomposition(decomposition)
        new_components = []
        for component in components:
            if component:
                meaning_data = self.db.get(component, {}).get('definition', '')
                meanings_list = self.parse_separated_values(meaning_data)
                new_components.append(f'{component} ({meanings_list[0] if meanings_list else ""})')
        return {
            'components_with_meaning': ", ".join(new_components),
            'definition': data.get('definition', '')
        }
    
    def _parse_decomposition(self, decomposition):
        if not decomposition: return '', []
        structure_symbol = decomposition[0]
        structure = self.component_meanings.get(structure_symbol, '')
        components = [char for char in decomposition[1:] if char not in self.component_meanings]
        return structure, components


class HanziStoryGenerator:
    def __init__(self):
        self.components_db = HanziComponentsDB('hanzi_db.txt')
        # Словарь "Пространств" и "Актеров" (можно скопировать из старого скрипта)
        self.spaces = { "a": {"name": "Арт-галерея", "tones": {"1": "Вестибюль", "2": "Главный выставочный зал", "3": "Мастерская художников", "4": "Кабинет куратора"}},"o": {"name": "Отель", "tones": {"1": "Ресепшн", "2": "Главный коридор", "3": "Общая гостиная", "4": "Номер отдыха"}},"e": {"name": "Эко-дом", "tones": {"1": "Солнечная веранда", "2": "Центральная гостиная", "3": "Зимний сад", "4": "Медитационная комната"}},"ai": {"name": "Айсберг-хижина", "tones": {"1": "Ледяной вход", "2": "Центральный зал", "3": "Теплый очаг", "4": "Спальный отсек"}},"ei": {"name": "Эйфелева башня (жилые помещения)", "tones": {"1": "Лифтовой холл", "2": "Панорамный салон", "3": "Инженерная комната", "4": "Смотровая площадка"}},"ao": {"name": "Вау-хаус", "tones": {"1": "Футуристический вход", "2": "Главный атриум с панорамной крышей", "3": "Комната аудиовизуальных эффектов", "4": "Спальня-трансформер"}},"ou": {"name": "Оукхаус (дубовый дом)", "tones": {"1": "Прихожая с деревянной отделкой", "2": "Каминный зал", "3": "Библиотека", "4": "Мансарда"}},"an": {"name": "Ангар-лофт", "tones": {"1": "Грузовой вход", "2": "Центральное пространство", "3": "Технический отсек", "4": "Жилая зона"}},"ang": {"name": "Английский коттедж", "tones": {"1": "Садовая калитка", "2": "Гостиная с камином", "3": "Чайная комната", "4": "Спальня с балдахином"}},"en": {"name": "Энциклопедическая библиотека-дом", "tones": {"1": "Архивный вход", "2": "Главный читальный зал", "3": "Кабинет каталогизации", "4": "Кабинет редких изданий"}},"eng": {"name": "Инглиш Мэнор (английское поместье)", "tones": {"1": "Парадный вход", "2": "Бальный зал", "3": "Охотничья комната", "4": "Господская спальня"}},"ong": {"name": "Замок Конга", "tones": {"1": "Крепостные ворота", "2": "Тронный зал", "3": "Сокровищница", "4": "Королевские покои"}},"null": {"name": "Нулевой дом (минималистичный дом)", "tones": {"1": "Стеклянный вход", "2": "Открытое пространство", "3": "Медитативная зона", "4": "Спальная капсула"}},}
        self.male_actors = {"b": "Брэд Питт в роли Тайлера Дардена.","p": "Пушкин — поэт во фраке, с бакенбардами, пером и романтическим взглядом.","m": "Михаил (Боярский)  'Мушкетер' — Михаил в шляпе с пером и шпагой из 'Трех мушкетеров'","f": "Фродо — хоббит с кольцом, в плаще, с мечом Жалом и отважным взглядом.","t": "Тесла — изобретатель в пиджаке, с молниями из катушки и загадочным взглядом.","d": "Дарт — в чёрной броне, с красным световым мечом.","n": "Наполеон — полководец в треуголке и мундире, с рукой за пазухой и властным взглядом.","l": "Леонардо (ДиКаприо) 'Ледяной выживший' — Лео в шкурах из 'Выжившего', борющийся с медведем.","g": "Гоша (Куценко) в кожаной куртке из 'Антикиллера'","k": "Кинг Конг — горилла с добротой.","h": "Хью (Джекман) 'Харизматичный Росомаха' — Хью с когтями из 'Людей Икс'","zh": "Джокер — коварный злодей с зелёными волосами, в фиолетовом костюме, с картами и безумной ухмылкой.","ch": "Черчилль Винстон — харизматичный премьер с сигарой, в котелке и строгом костюме, держащий речь.","sh": "Шон (Коннери) 'Шпион 007' — Шон в смокинге с пистолетом из 'Джеймса Бонда'","r": "Железный человек _Красный с золотом костюм, реактор светится, руки в репульсорах — мощный, технологичный","z": "Зорро — в чёрной маске, с шпагой, плащом и знаком 'Z'.","c": "Цой Виктор — рок-музыкант в кожаной куртке, с гитарой и бунтарским взглядом.","s": "Сильвестр (Сталлоне) Рэмбо — Сильвестр с пулеметом и повязкой на голове.","null": "(без инициали) Джеки (Чан) 'Мастер трюков' — Джеки, прыгающий с крыши с улыбкой из 'Полицейской истории'."}
        self.female_actors = {"y": "Исида — египетская богиня в сияющем платье, солнечным диском и магическим жезлом.","bi": "Биби Дун — холодная императрица в тёмно-фиолетовых одеждах в высокой короне с  посохом","pi": "Пенелопа (Крус) 'Пылкая испанка' — Пенелопа в красном платье","mi": "Мила (Йовович) Мила с оружием из 'Обители зла' (Milla Jovovich).","di": "маленькая серая кошка из аниме _Sailor Moon_ с магическими способностями , спутница Чиби Усы и Артемиды. Грациозная серая кошка с красным ошейником и колокольчиком, иногда в человеческой форме как юная девушка с фиолетовыми волосами и лунным символом на лбу","ti": "Тильда (Суинтон) 'Таинственная волшебница' — Тильда в белом из 'Хроник Нарнии' (Tilda Swinton)","ni": "Ника — богиня победы в белой тунике, с крыльями, лавровым венком и жезлом","li": "Лили (Коллинз) 'Легкая романтика' — Лили в Париже из 'Эмили в Париже' (Lily Collins)","ji": "Джулия (Робертс) 'Жизнерадостная красотка' — Джулия с улыбкой из 'Красотки' (Julia Roberts)","qi": "Кира (Найтли) 'Королева пиратов' — Кира в шляпе из 'Пиратов Карибского моря' (Keira Knightley)","xi": "Си Ванму — Царица-Мать Запада из китайской мифологии, в золотых одеждах, с короной из перьев феникса, магическим персиком и фениксами. Верхом на журавле"}
        self.fictional_actors = {"w": "Винни-Пух - медведь с горшочком мёда, красная футболка, любитель немножко подкрепиться","bu": "Буратино - деревянный мальчик с длинным носом, золотой ключик, яркая шапочка с кисточкой","pu": "Пушок (из 'Трёх котов') - белый котёнок в голубом комбинезоне, любознательный и мечтательный","mu": "Муми-тролль - белый круглый тролль с большим носом из финских сказок","fu": "Фунтик - поросёнок в шляпе, сбежавший от госпожи Беладонны","du": "Дюймовочка - крошечная девочка, родившаяся из цветка, путешествующая с ласточкой","tu": "Тутанхамон - юный фараон с золотой маской, древнеегипетскими одеждами","nu": "Нуф-Нуф - поросёнок из сказки 'Три поросёнка', строитель дома из дерева","lu": "Лунтик - фиолетовое существо, 'родившееся на Луне', с большими ушами","gu": "Гулливер - путешественник среди лилипутов, высокий рост по сравнению с окружающими, связанный верёвками","ku": "Кузя (домовёнок) - лохматый домовой в красной рубахе с мешком за спиной","hu": "Хуч (пёс из мультфильма 'Пёс и кот') - рыжий пёс с чёрными ушами, любитель поесть","zhu": "Джуд Лоу - харизматичный сыщик в стильном костюме, с тростью и лукавой улыбкой.","chu": "Чубакка — огромный вуки из Звёздных войн с рыжей шерстью, арбалетом и громким рёвом","shu": "Шушу (крыс из 'Рататуя') – гурман в поварском колпаке","ru": "Жужу — Зоро Ророноа из _One Piece_ с тремя катанами, зелёными волосами и саркастичным характером.","zu": "Змей Горыныч – трёхглавый дракон, изрыгающий огонь","cu": "Цунами — гигантская бурлящая волна, с пеной и разрушительной силой.","su": "Сунь Укун — Король обезьян в красном плаще, с золотым посохом и озорным взглядом.",}
        self.gods_actors = {"yu": "Юрий Гагарин (первый человек в космосе) - космический скафандр, шлем, знаменитая улыбка","nü": "Нюй-ва (китайская богиня-создательница) - тело наполовину женщины, наполовину змеи, создательница человечества","lü": "Люцифер (падший ангел) - красивое лицо с дьявольскими чертами, сломанные крылья, демонические рога","ju": "Юлий Цезарь (римский император) - лавровый венок, тога, знаменитый профиль на монетах","qu": "Чьюя — Курапика из _Hunter x Hunter_ с длинными светлыми волосами, красными глазами и магическими цепями.","xu": "Сюань-у — Чёрная Черепаха-Змея, небесный страж Севера, в чёрных доспехах, с древним свитком или мечом, окружённый водой и туманом."}

    def get_pinyin(self, hanzi):
        return " ".join(["".join(p) for p in pinyin(hanzi, style=Style.TONE3)])

    def generate_space(self, pinyin_text):
        pinyin_syllable = pinyin_text.split()[0]
        tone = next((char for char in pinyin_syllable if char.isdigit()), None)
        pinyin_without_tone = re.sub(r'\d', '', pinyin_syllable)
        final_key = next((f for f in self.spaces if re.search(f"{f}$", pinyin_without_tone)), "null")
        all_actors = {**self.male_actors, **self.female_actors, **self.fictional_actors, **self.gods_actors}
        initial = next((init for init in sorted(all_actors.keys(), key=len, reverse=True) if pinyin_without_tone.startswith(init)), "null")
        actor = all_actors.get(initial)
        if final_key and actor:
            space_name = self.spaces[final_key]["name"]
            tone_space = self.spaces[final_key]["tones"].get(tone, "Неизвестное место")
            return f"({actor}) {space_name} - {tone_space}"
        return "Неизвестное пространство"

    def _build_story_prompt(self, hanzi, primary_meaning, actor, location, components_str):
        return f"""
        Создай простую и запоминающуюся историю по методу Hanzi Movie Method для изучения китайского иероглифа.
        Данные:
        - Иероглиф: {hanzi}, Значение: {primary_meaning}
        - Место действия: {location}, Главный герой: {actor}
        - Компоненты иероглифа: {components_str}
        Требования:
        - История должна быть короткой (1-2 предложения), легко запоминаемой и связывать все элементы.
        - Важно! История должна быть напрямую связана со значением компонентов иероглифа {components_str}.
        - Пиши на русском языке.
        - Описание не должно быть слишком сложным или длинным. 
        - В описании не должно быть нарушений, насилия или оскорблений - что может повлиять на content policy violation
        - В конце истории добавь иероглиф {hanzi} чтобы выделить, что это ключевой элемент.
        """

    def generate_story(self, hanzi, meaning, actor, location, hint):
        primary_meaning = self.components_db.parse_separated_values(meaning)[0] if meaning else "нечто"
        prompt = self._build_story_prompt(hanzi, primary_meaning, actor, location, hint)
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
            return f"[АВТО-ИСТОРИЯ] {actor} в {location} видит иероглиф {hanzi} и вспоминает '{primary_meaning}'."

async def google_translate_en(en_word):
    if not en_word: return ""
    translator = Translator()
    try:
        return (await translator.translate(en_word, src="en", dest="ru")).text
    except Exception as e:
        print(f"Translation error: {e}")
        return en_word

def check_input_duplicates(input_file, archive_path):
    # (Функция без изменений)
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

# --- ГЛАВНАЯ ЛОГИКА СКРИПТА 1 ---
def main():
    generator = HanziStoryGenerator()
    hanzi_to_process = check_input_duplicates(input_file, output_file_archive_path)

    if not hanzi_to_process:
        print("Новых иероглифов для обработки не найдено.")
        return

    all_stories_data = []
    if os.path.exists(STORIES_JSON_FILE):
        with open(STORIES_JSON_FILE, 'r', encoding='utf-8') as f:
            all_stories_data = json.load(f)

    for hanzi in hanzi_to_process:
        print(f"Обрабатываем: {hanzi}...")
        hanzi = HanziConv.toSimplified(hanzi)
        
        components_data = generator.components_db.get_hanzi_components(hanzi)
        meaning_en = components_data.get('definition', '') if components_data else ''
        hint = components_data.get('components_with_meaning', '') if components_data else 'Нет данных'
        
        pinyin_text = generator.get_pinyin(hanzi)
        meaning_ru = asyncio.run(google_translate_en(generator.components_db.parse_separated_values(meaning_en)[0] if meaning_en else hanzi))
        space = generator.generate_space(pinyin_text)

        actor_match = re.match(r'\((.*?)\)\s*(.*)', space)
        actor = actor_match.group(1) if actor_match else "Неизвестный актер"
        location = actor_match.group(2) if actor_match else "Неизвестное место"

        story = generator.generate_story(hanzi, meaning_ru, actor, location, hint)
        
        character_data = {
            "hanzi": hanzi,
            "pinyin": pinyin_text,
            "meaning_en": meaning_en,
            "meaning_ru": meaning_ru,
            "actor": actor,
            "location": location,
            "hint": hint,
            "story": story,
        }
        all_stories_data.append(character_data)
        time.sleep(1) # Задержка между запросами к API

    with open(STORIES_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_stories_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nВсего {len(hanzi_to_process)} историй сгенерировано и сохранено в файл '{STORIES_JSON_FILE}'.")
    print("Пожалуйста, отредактируйте истории в этом файле перед запуском скрипта 2 001_generate_du_chinese_hmm_deck.py.")

    # Архивируем исходный файл
    if os.path.exists(input_file):
        os.makedirs(output_file_archive_path, exist_ok=True)
        archive_filename = f'processed_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.txt'
        
        # Записываем только обработанные слова в архив, а не весь файл
        with open(os.path.join(output_file_archive_path, archive_filename), 'w', encoding='utf-8') as f:
            for word in hanzi_to_process:
                f.write(word + '\n')
        
        # Очищаем исходный файл
        open(input_file, 'w').close()
        print(f"Обработанные слова заархивированы, файл '{input_file}' очищен.")

if __name__ == "__main__":
    main()