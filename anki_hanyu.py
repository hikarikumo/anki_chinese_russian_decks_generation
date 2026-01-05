import genanki
import random
import requests
import os, time
from pypinyin import pinyin, Style
import urllib.parse
import asyncio
from googletrans import Translator
from datetime import datetime
from hanziconv import HanziConv
import json
import random
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from gtts import gTTS

# import openai
# from openai import OpenAI
# from openai import OpenAIError
# import base64
# import http.client
# import re



input_file = "chinese_words.txt"

# anki_deck_name = "Chinese decks::MandarinBean::Chinese MandarinBean hsk2"
# output_deck = "Chinese-MandarinBean-hsk2.apkg"
# input_words_archive = "input_words_archive_mandarinbean_hsk2"

anki_deck_name = "Chinese decks::MandarinBean::MandarinBean hsk1"
output_deck = "MandarinBean_hsk1.apkg"
input_words_archive = "input_words_archive/input_words_archive_mandarinbean_hsk1"

# Path to makemeahanzi graphics.txt (update this to your local path)
GRAPHICS_PATH = "graphics.txt"
OPENAI_MODEL = "gpt-4o-mini"
# OPENAI_MODEL = "o3-mini-2025-01-31"
OPENAI_MAX_TOKENS = 300
OPENAI_TEMPERATURE = 0.8
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
            print(f"Файл базы данных компонентов '{db_file}' не найден. Разбор компонентов будет недоступен.")
        except json.JSONDecodeError:
            print(f"Ошибка декодирования JSON в файле '{db_file}'. Проверьте формат.")
        return db

    def parse_separated_values(self, input_string):
        standardized = str(input_string).replace(';', ',')
        values = [item.strip() for item in standardized.split(',')]
        return [item for item in values if item]

    def get_hanzi_components(self, hanzi):
        if len(hanzi) != 1 or hanzi not in self.db:
            return None
        
        data = self.db[hanzi]
        decomposition = data.get('decomposition', '')
        definition = data.get('definition', '')
        structure, components = self._parse_decomposition(decomposition)
        
        new_components = []
        for component in components:
            if component:
                component_data = self.db.get(component, {})
                meaning_data = component_data.get('definition', '')
                meanings_list = self.parse_separated_values(meaning_data)
                meaning = meanings_list[0] if meanings_list else "без значения"
                
                new_components.append(f'{component} ({meaning})')
        
        components_with_meaning = ", ".join(new_components)
        
        return {
            'character': hanzi, 
            'structure': self.component_meanings.get(structure[0], definition) if structure else '',
            'components_with_meaning': components_with_meaning,
        }

    def _parse_decomposition(self, decomposition):
        if not decomposition:
            return '', []
        structure_symbol = decomposition[0]
        structure = self.component_meanings.get(structure_symbol, 'неизвестная структура')
        components = [char for char in decomposition[1:] if char not in self.component_meanings]
        return structure, components


class ChineseAnkiGenerator:
    def __init__(self):
        # Load stroke data from makemeahanzi
        self.graphics_data = self.load_graphics_data(GRAPHICS_PATH)
        self.components_db = HanziComponentsDB(db_file='hanzi_db.txt') 

        # Create Anki model with StrokeOrder field
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name,
            fields=[
                {"name": "Chinese"},
                {"name": "Pinyin"},
                {"name": "ColoredPinyin"},
                {"name": "Meaning"},
                {"name": "WordMnemonic"}, # <--- НОВОЕ ПОЛЕ: Мнемоника для слова
                {"name": "Example"},
                {"name": "ExamplePinyin"},
                {"name": "ExampleMeaning"},
                {"name": "Hint"}, 
                {"name": "Audio"},
                {"name": "ExampleAudio"},
                {"name": "StrokeOrder"},
            ],
            templates=[
                {
                    "name": "Recognition (Chinese -> Russian)",
                    "qfmt": '<div class="chinese">{{Chinese}}</div><div class="stroke-order">{{StrokeOrder}}</div>',
                    "afmt": """
                        {{Audio}} <div class="stroke-order">{{StrokeOrder}}</div>
                        <hr>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="meaning">{{Meaning}}</div>
                        <div class="word-mnemonic">{{WordMnemonic}}</div> <div class="example">{{Example}}</div>
                        <div class="example-pinyin">{{ExamplePinyin}}</div>
                        <div class="example-meaning">{{ExampleMeaning}}</div>
                        <div class="example-audio">{{ExampleAudio}}</div>
                        <div class="hint-section">{{Hint}}</div> 
                    """,
                },
                {
                    "name": "Recall (Russian -> Chinese)",
                    "qfmt": """
                            <div class="meaning">{{Meaning}}</div>
                            """,
                    "afmt": """
                        {{Audio}} <div class="meaning">{{Meaning}}</div>
                        <hr>
                        <div class="chinese">{{Chinese}}</div>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="word-mnemonic">{{WordMnemonic}}</div> <div class="example">{{Example}}</div>
                        <div class="example-pinyin">{{ExamplePinyin}}</div>
                        <div class="example-meaning">{{ExampleMeaning}}</div>
                        <div class="example-audio">{{ExampleAudio}}</div>
                        <div class="stroke-order">{{StrokeOrder}}</div>
                        <div class="hint-section">{{Hint}}</div> 
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
                .chinese {
                    font-size: 40px;
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
                .meaning {
                    font-size: 20px;
                    margin-bottom: 15px;
                }
                /* СТИЛЬ ДЛЯ МНЕМОНИКИ СЛОВА */
                .word-mnemonic {
                    font-size: 16px;
                    color: #2c3e50;
                    background-color: #e8f4f8;
                    padding: 8px;
                    border-radius: 5px;
                    margin: 10px 0;
                    font-style: italic;
                    border-left: 4px solid #3498db;
                }
                .example {
                    font-size: 18px;
                    margin-top: 15px;
                    font-weight: normal;
                }
                .example-pinyin {
                    font-size: 14px;
                }
                .example-meaning { 
                    font-size: 16px; 
                    font-style: italic; 
                    margin-bottom: 5px;
                    color: #555;
                }
                .example-audio {
                    margin-bottom: 15px;
                }
                .hint-section {
                    margin-top: 20px;
                    padding: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                    text-align: left;
                    font-size: 14px;
                }
                /* 💡 ИЗМЕНЕНИЕ: Убран жирный шрифт из заголовка подсказки */
                .hint-section h4 {
                    margin-top: 0;
                    margin-bottom: 5px;
                    color: #333;
                }               
                .tone1 { color: blue; }
                .tone2 { color: green; }
                .tone3 { color: purple; }
                .tone4 { color: red; }
                .tone5 { color: gray; }
            """,
        )

        # Create deck
        self.deck = genanki.Deck(
            random.randrange(1 << 30, 1 << 31), anki_deck_name
        )

        # Media files
        self.media_files = []

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
                    # print(f"Warning: No SVG file found for '{char}' (code point {code_point})") 
                    continue
            
            svg_paths.append(svg_path)
            # print(f"Found existing SVG for '{char}' at {svg_path}") # ВОССТАНОВЛЕНО
        
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
    
    
    def color_pinyin(self, pinyin_text):
        """Format pinyin with tone colors using HTML spans"""
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

    def get_dictionary_data(self, word):
        """Get dictionary data using Google Translate API with fallbacks"""
        try:
            result = asyncio.run(google_translate(word))
            if result:
                return result

            backup_url = f"http://api.hanzidb.org/dictionary/search?q={word}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(backup_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data and "results" in data and data["results"]:
                    definitions = [result["definition"] for result in data["results"][:3] if "definition" in result]
                    return "; ".join(definitions)

            common_words = {
                "你好": "hello; hi",
                "谢谢": "thank you; thanks",
                "再见": "goodbye; see you again",
                "学习": "to learn; to study",
                "中国": "China",
                "朋友": "friend",
                "工作": "work; job",
                "家": "home; family",
                "爱": "love; to love",
                "人": "person; people",
            }
            if word in common_words:
                return common_words[word]

            pinyin_result = pinyin(word, style=Style.TONE3)
            return f"[{pinyin_result}] Definition not available - please check a dictionary"
        except Exception as e:
            print(f"Error fetching dictionary data: {e}")
            try:
                pinyin_result = pinyin(word, style=Style.TONE3)
                return f"[{pinyin_result}] Unable to fetch definition"
            except:
                return "Unable to fetch definition"

    def get_example_from_gemini(self, word):
        """
        Generate an example sentence using the word with translation via Gemini.
        Ensures sentence is in Simplified Chinese with Russian translation.
        """
        # print(f'{word=}') # ВОССТАНОВЛЕНО

        # Configure the Gemini API client with the API key from environment variables.
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY environment variable not set.")
            return None
        genai.configure(api_key=api_key)

        try:
            model = genai.GenerativeModel('gemini-2.5-pro') 
            
            prompt = (
                f"Provide one example sentence in Simplified Chinese that uses the word '{word}', "
                "along with its Russian translation from Chinese. Return the response in JSON format like this:\n"
                "{\n  \"chinese\": \"<Simplified Chinese sentence>\",\n  \"meaning\": \"<Russian translation>\"\n}"
            )            

            generation_config = {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "chinese": {"type": "STRING"},
                        "meaning": {"type": "STRING"}
                    }
                }
            }

            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )

            if response.text:
                example = json.loads(response.text)
                if "chinese" in example and "meaning" in example:
                    return example
                else:
                    print("Unexpected format in Gemini response.")
                    return None
            else:
                print("Gemini response was empty.")
                return None

        except google_exceptions.GoogleAPIError as e:
            print(f"Error generating example with Gemini API: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from Gemini response: {e}")
            print(f"Response content: {response.text}") # ВОССТАНОВЛЕНО
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None


    def get_mnemonic_from_gemini(self, hanzi):
        """
        Генерирует короткую мнемонику для запоминания иероглифа с использованием Gemini (Синхронно).
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "Ошибка: GOOGLE_API_KEY не установлен."
        genai.configure(api_key=api_key)

        try:
            model = genai.GenerativeModel('gemini-2.5-pro') 
            
            prompt = (
                f"Напиши очень короткую, запоминающуюся и креативную мнемонику на русском языке "
                f"для запоминания китайского иероглифа '{hanzi}'. "
                f"Мнемоника должна быть только одним предложением и помогать запомнить значение, "
                f"основываясь на его структуре или значении. "
                "Верни мнемонику как чистый текст, без кавычек, префиксов или объяснений. "
                "Например, для '好' (hǎo, хороший): 'Женщина (女) и ребенок (子) — это хорошо (好).'"
            )            

            # 💡 Синхронный вызов
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.9}
            )

            if response.text:
                # Очистка от потенциальных кавычек или лишних символов
                mnemonic = response.text.strip().replace('"', '').replace("'", "")
                return mnemonic
            else:
                return "Не удалось сгенерировать мнемонику."

        except google_exceptions.GoogleAPIError as e:
            print(f"Error generating mnemonic with Gemini API for '{hanzi}': {e}")
            return f"Ошибка API Gemini: {e}"
        except Exception as e:
            print(f"An unexpected error occurred while generating mnemonic for '{hanzi}': {e}")
            return "Непредвиденная ошибка при генерации мнемоники."

    def get_word_mnemonic_from_gemini(self, word, meaning):
        """
        Генерирует мнемонику для ЦЕЛОГО слова, если оно состоит из 2+ иероглифов.
        Обыгрывает значение каждого иероглифа для объяснения смысла всего слова.
        """
        # Если слово состоит из 1 иероглифа или меньше, мнемоника для слова не нужна 
        # (она будет в Hint как разбор иероглифа)
        if len(word) < 2:
            return ""

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return ""
        genai.configure(api_key=api_key)

        try:
            model = genai.GenerativeModel('gemini-2.5-pro') 
            
            prompt = (
                f"Придумай короткую, логичную мнемонику на русском языке для китайского слова '{word}', "
                f"которое означает '{meaning}'. "
                f"Слово состоит из нескольких иероглифов. Разбей слово на иероглифы, укажи значение каждого "
                f"и объедини их в одну фразу-историю, объясняющую смысл целого слова. "
                f"Формат ответа: только текст мнемоники, без кавычек. "
                f"Пример для '电脑' (компьютер): 'Электрический (电) мозг (脑) — это компьютер'."
            )            

            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.8}
            )

            if response.text:
                return response.text.strip().replace('"', '').replace("'", "")
            else:
                return ""

        except Exception as e:
            print(f"Error generating word mnemonic for '{word}': {e}")
            return ""

    def get_audio_from_tts(self, word):
        """Generate audio pronunciation using Google TTS (Replacing Forvo)"""
        audio_dir = "chinese_audio_files"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
            
        # Добавляем timestamp, чтобы имена файлов не конфликтовали
        safe_word = "".join([c for c in word if c.isalnum()])
        if len(safe_word) > 50: # Ограничиваем длину имени файла
             safe_word = safe_word[:50]
             
        timestamp = int(time.time())
        filename = f"{safe_word}_{timestamp}.mp3"
        audio_file_path = os.path.join(audio_dir, filename)
        
        try:
            # zh-cn для упрощенного китайского
            tts = gTTS(text=word, lang='zh-cn')
            tts.save(audio_file_path)
            print(f"Generated TTS audio for {word}")
            return audio_file_path
        except Exception as e:
            print(f"Error generating TTS audio: {e}")
            return None


    def get_hanzi_hint(self, word):
        """
        Разбирает каждый иероглиф в слове на компоненты со значениями и добавляет мнемонику.
        """
        hints = []
        for char in word:
            if is_chinese_char(char):
                data = self.components_db.get_hanzi_components(char)
                mnemonic = self.get_mnemonic_from_gemini(char) 

                hint_parts = []
                if data and data['structure']:
                    structure = f"Значение: {data['structure']}"
                    hint_parts.append(structure)
                if data and data['components_with_meaning']:
                    components = f"Компоненты: {data['components_with_meaning'].replace('<b>', '').replace('</b>', '')}"
                    hint_parts.append(components)

                if mnemonic and mnemonic != "Непредвиденная ошибка при генерации мнемоники.":
                    hint_parts.append(f"Мнемоника: **{mnemonic}**")

                if hint_parts:
                    hints.append(f"• {char}: {', '.join(hint_parts)}")
        
        if hints:
            # Объединяем элементы списка через <br> для переноса строки
            return "<br>".join(hints)
        else:
            return ""


    def process_word(self, word):
        """Process a single Chinese word"""
        print(f"Processing: {word}")

        # Get pinyin
        raw_pinyin = pinyin(word, style=Style.TONE3)
        pinyin_text = " ".join(["".join(p) for p in raw_pinyin])
        colored_pinyin = self.color_pinyin(pinyin_text)

        # Get dictionary definition
        meaning = self.get_dictionary_data(word)

        # --- НОВОЕ: Генерируем мнемонику для составного слова ---
        word_mnemonic = self.get_word_mnemonic_from_gemini(word, meaning)
        # -------------------------------------------------------

        # Get example sentence
        try:
            example = self.get_example_from_gemini(word)
            example_chinese = example["chinese"] if example else ""
            example_meaning = example["meaning"] if example else ""
            example_raw_pinyin = pinyin(example_chinese, style=Style.TONE3)
            example_pinyin_text = " ".join(["".join(p) for p in example_raw_pinyin])
            example_colored_pinyin = self.color_pinyin(example_pinyin_text)
        except Exception as e:
            print(f"Error fetching example: {e}")
            example_chinese = ""
            example_colored_pinyin = ""
            example_meaning = ""

        component_hint = self.get_hanzi_hint(word)
        
        final_example_meaning = f"{example_meaning}" if example_meaning else ""
        
        # Get audio (UPDATED: USING TTS INSTEAD OF FORVO)
        audio_file = self.get_audio_from_tts(word)
        audio_tag = f"[sound:{os.path.basename(audio_file)}]" if audio_file and os.path.exists(audio_file) else ""
        if audio_file:
            self.media_files.append(audio_file)

        # --- Озвучка примера предложения ---
        example_audio_tag = ""
        if example_chinese:
             # Генерируем аудио для всего предложения примера
             example_audio_file = self.get_audio_from_tts(example_chinese)
             if example_audio_file and os.path.exists(example_audio_file):
                  self.media_files.append(example_audio_file)
                  example_audio_tag = f"[sound:{os.path.basename(example_audio_file)}]"
        # -------------------------------------------------

        # Generate stroke order image references
        stroke_image_result = self.create_stroke_image(word, f"strokes/{word}_strokes.png")

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

        # Create Anki note
        note = genanki.Note(
            model=self.model,
            fields=[
                word,              # Chinese
                pinyin_text,       # Pinyin
                colored_pinyin,    # ColoredPinyin
                meaning,           # Meaning
                word_mnemonic,     # WordMnemonic
                example_chinese,   # Example
                example_colored_pinyin,  # ExamplePinyin
                final_example_meaning,   # ExampleMeaning (Только перевод примера)
                component_hint,    # Hint (Подсказка с компонентами)
                audio_tag,         # Audio
                example_audio_tag, # ExampleAudio (Аудио примера)
                stroke_tag,        # StrokeOrder
            ],
        )

        self.deck.add_note(note)
        time.sleep(1)

        return {
            "word": word,
            "pinyin": pinyin_text,
            "meaning": meaning[:50] + "..." if len(meaning) > 50 else meaning,
        }


    def get_or_create_archive_path(self):
        """
        Returns the path to the archive directory for input words.
        Creates the directory if it does not exist.
        """
        archive_path = input_words_archive
        if not os.path.exists(archive_path):
            os.makedirs(archive_path, exist_ok=True)
        return archive_path


    def create_deck_from_file(self, input_words, output_file=output_deck):
        """Create Anki deck from Chinese words"""
        results = []
        for word in input_words:
            result = self.process_word(word)
            results.append(result)

        # Create package with media files
        package = genanki.Package(self.deck)
        if self.media_files:
            package.media_files = self.media_files

        # Write to file
        package.write_to_file(output_file)
        print(f"Created Anki deck: {output_file}")

        # copy inputs to archive
        output_file_archive_path = self.get_or_create_archive_path()

        output_filename = (
            f'chinese_words_{datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.txt'
        )
        if not os.path.exists(output_file_archive_path):
            os.makedirs(output_file_archive_path)

        with open(input_file, "r", encoding="utf-8") as f:
            with open(
                f"{output_file_archive_path}/{output_filename}", "w", encoding="utf-8"
            ) as f2:
                f2.write(f.read())
        
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("")
        print(f"Archived input file: {output_file_archive_path}/{output_filename}")

        return results

async def google_translate(word):
    translator = Translator()
    translation = await translator.translate(word, src="zh-cn", dest="ru") 
    if translation and translation.text:
        return translation.text.capitalize()

def check_input_duplicates(input_file):
    new_input_words = []
    files = os.listdir(input_words_archive) if os.path.exists(input_words_archive) else []
    words = []
    for file in files:
        with open(f"{input_words_archive}/{file}", "r", encoding="utf-8") as f:
            words += [line.strip().replace("\u200b", "") for line in f if line.strip()]
    with open(input_file, "r", encoding="utf-8") as f:
        input_words = [line.strip().replace("\u200b", "") for line in f if line.strip()]

    input_words = list(set(input_words))
    for word in input_words:
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
    for char in text:
        code_point = ord(char)
        if not ((0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF)):
            return False
    return True


if __name__ == "__main__":

    generator = ChineseAnkiGenerator()

    if not os.path.exists(input_file):
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("你好\n")
        print(f"Created example file: {input_file}")

    checked_input_words = check_input_duplicates(input_file)
    results = generator.create_deck_from_file(checked_input_words)

    print("\nProcessed words:")
    for result in results:
        print(f"{result['word']} ({result['pinyin']}): {result['meaning']}")