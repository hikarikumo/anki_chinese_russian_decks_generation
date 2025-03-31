import genanki
import random
import requests
import os, time
from pypinyin import pinyin, Style
import urllib.parse
import requests
from googletrans import Translator
import asyncio
from datetime import datetime


class ChineseAnkiGenerator:
    def __init__(self):
        # Create Anki model
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            "Vova chinese HSK1",
            fields=[
                {"name": "Chinese"},
                {"name": "Pinyin"},
                {"name": "ColoredPinyin"},
                {"name": "Meaning"},
                {"name": "Example"},
                {"name": "ExamplePinyin"},
                {"name": "ExampleMeaning"},
                {"name": "Audio"},
            ],
            templates=[
                {
                    "name": "Recognition",
                    "qfmt": '<div class="chinese">{{Chinese}}</div>',
                    "afmt": """
                        <div class="chinese">{{Chinese}}</div>
                        <hr>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="meaning">{{Meaning}}</div>
                        <div class="example"> {{Example}}</div>
                        <div class="example-pinyin">{{ExamplePinyin}}</div>
                        <div class="example-meaning">{{ExampleMeaning}}</div>
                        {{Audio}}
                    """,
                },
                {
                    "name": "Production",
                    "qfmt": '<div class="meaning">{{Meaning}}</div>',
                    "afmt": """
                        <div class="meaning">{{Meaning}}</div>
                        <hr>
                        <div class="chinese">{{Chinese}}</div>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="example"> {{Example}}</div>
                        <div class="example-pinyin">{{ExamplePinyin}}</div>
                        <div class="example-meaning">{{ExampleMeaning}}</div>
                        {{Audio}}
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
                .pinyin {
                    font-size: 18px;
                    margin-bottom: 10px;
                }
                .meaning {
                    font-size: 20px;
                    margin-bottom: 15px;
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
                    font-size: 14px;
                    font-style: italic;
                    margin-bottom: 15px;
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
            random.randrange(1 << 30, 1 << 31), "Vova chinese HSK1"
        )

        # Media files
        self.media_files = []

    def color_pinyin(self, pinyin_text):
        """Format pinyin with tone colors using HTML spans"""
        result = ""
        syllables = pinyin_text.split()

        for syllable in syllables:
            # Extract tone number
            tone = None
            for char in syllable:
                if char.isdigit():
                    tone = char
                    break

            if tone:
                syllable_without_tone = syllable.replace(tone, "")
                result += (
                    f'<span class="tone{tone}">{syllable_without_tone}{tone}</span> '
                )
            else:
                result += f"{syllable} "

        return result.strip()

    def get_dictionary_data(self, word):
        """Get dictionary data using Google Translate API with fallbacks"""
        try:
            # Инициализируем Google Translate
            result = asyncio.run(google_translate(word))
            if result:
                return result

            # Если Google Translate не сработал, пробуем альтернативный API (HanziDB)
            backup_url = f"http://api.hanzidb.org/dictionary/search?q={word}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(backup_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data and "results" in data and data["results"]:
                    definitions = []
                    for result in data["results"][:3]:
                        if "definition" in result:
                            definitions.append(result["definition"])
                    return "; ".join(definitions)

            # Локальный словарь как запасной вариант
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

            # Если ничего не сработало, возвращаем пиньинь
            pinyin_result = pinyin(word, tone_numbers=True)
            return f"[{pinyin_result}] Definition not available - please check a dictionary"

        except Exception as e:
            print(f"Error fetching dictionary data: {e}")
            # Последний запасной вариант - только пиньинь
            try:
                pinyin_result = pinyin(word, tone_numbers=True)
                return f"[{pinyin_result}] Unable to fetch definition"
            except:
                return "Unable to fetch definition"

    def get_example_from_tatoeba(self, word):
        lang = "cmn"
        translation_lang = "eng"
        url = f"https://tatoeba.org/eng/api_v0/search?from={lang}&to={translation_lang}&query={word}&sort=relevance&word_count_max=&word_count_min=1"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Проверка HTTP ошибок
            data = response.json()

            if not data or "results" not in data:
                return None

            for item in data["results"]:
                # Проверяем наличие всех необходимых полей
                if not all(key in item for key in ["text", "translations"]):
                    continue

                # Безопасное извлечение перевода
                if item["translations"]:  # Есть ли переводы вообще
                    # Берем первый перевод (проверяя его структуру)
                    first_translation = (
                        item["translations"][0] if item["translations"] else None
                    )

                    if isinstance(first_translation, dict):
                        translation_text = first_translation.get("text", "")
                    elif isinstance(first_translation, list) and first_translation:
                        translation_text = (
                            first_translation[0].get("text", "")
                            if isinstance(first_translation[0], dict)
                            else str(first_translation[0])
                        )
                    else:
                        translation_text = ""

                    if translation_text.strip():
                        return {"chinese": item["text"], "meaning": translation_text}

            # Если ничего не нашли
            return None

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
        except ValueError as e:
            print(f"JSON decode error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    def get_audio_from_forvo(self, word):
        """Get audio pronunciation from Forvo API"""
        audio_dir = "forvo_audio"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
        audio_file_path = f"{audio_dir}/{word}_audio.mp3"
        if os.path.exists(audio_file_path):
            return audio_file_path
        try:
            # Encode the word for URL
            encoded_word = urllib.parse.quote(word)

            # Use your API key
            forvo_api_key = os.getenv("FORVO_API_KEY")

            # Construct the API URL
            api_url = f"https://apifree.forvo.com/key/{forvo_api_key}/format/json/action/word-pronunciations/word/{encoded_word}/language/zh"

            response = requests.get(api_url)

            if response.status_code == 200:
                data = response.json()

                # Check if there are any items
                if "items" in data and len(data["items"]) > 0:
                    # Sort by votes to get the most popular pronunciation
                    sorted_items = sorted(
                        data["items"],
                        key=lambda x: int(x.get("num_positive_votes", 0)),
                        reverse=True,
                    )

                    # Get the audio URL of the top voted pronunciation
                    audio_url = sorted_items[0]["pathmp3"]

                    # Create a suitable filename

                    audio_filename = audio_file_path

                    # Download the audio file
                    audio_response = requests.get(audio_url)

                    if audio_response.status_code == 200:
                        with open(audio_filename, "wb") as f:
                            f.write(audio_response.content)

                        print(f"Downloaded audio for {word}")
                        return audio_filename
                    else:
                        print(
                            f"Failed to download audio file: {audio_response.status_code}"
                        )
                else:
                    print(f"No pronunciations found for {word}")
            else:
                print(f"API request failed: {response.status_code}")

            return None
        except Exception as e:
            print(f"Error fetching audio: {e}")
            return None

    def process_word(self, word):
        """Process a single Chinese word"""
        print(f"Processing: {word}")

        # Get pinyin using pypinyin
        raw_pinyin = pinyin(word, style=Style.TONE3)
        pinyin_text = " ".join(["".join(p) for p in raw_pinyin])

        # Get colored HTML pinyin
        colored_pinyin = self.color_pinyin(pinyin_text)

        # Get dictionary definition
        meaning = self.get_dictionary_data(word)

        # Get example sentence
        try:
            example = self.get_example_from_tatoeba(word)
            example_chinese = example["chinese"]
            example_meaning = example["meaning"]

            # Get example pinyin
            example_raw_pinyin = pinyin(example_chinese, style=Style.TONE3)
            example_pinyin_text = " ".join(["".join(p) for p in example_raw_pinyin])
            example_colored_pinyin = self.color_pinyin(example_pinyin_text)
        except Exception as e:
            print(f"Error fetching example: {e}")
            example_chinese = ""
            example_colored_pinyin = ""
            example_meaning = ""
        audio_file = self.get_audio_from_forvo(word)
        if audio_file and os.path.exists(audio_file):
            # Use only the basename for the [sound:…] tag
            audio_filename = os.path.basename(audio_file)  # e.g., "你好_audio.mp3"
            audio_tag = f"[sound:{audio_filename}]"
            self.media_files.append(audio_file)  # Full path for media_files

        # Create Anki note
        note = genanki.Note(
            model=self.model,
            fields=[
                word,  # Chinese
                pinyin_text,  # Pinyin
                colored_pinyin,  # ColoredPinyin
                meaning,  # Meaning
                example_chinese,  # Example
                example_colored_pinyin,  # ExamplePinyin
                example_meaning,  # ExampleMeaning
                audio_tag,  # Audio
            ],
        )

        self.deck.add_note(note)

        # Be nice to APIs - don't hammer them
        time.sleep(1)

        return {
            "word": word,
            "pinyin": pinyin_text,
            "meaning": meaning[:50] + "..." if len(meaning) > 50 else meaning,
        }

    def create_deck_from_file(self, input_words, output_file="vova_chinese_hsk1.apkg"):
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
        output_file_archive_path = "input_words_archive"
        output_filename = (
            f'chinese_words_{datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.txt'
        )
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

    # Translate text to English (default destination language)
    translation = await translator.translate(word, src="zh-cn", dest="en")

    if translation and translation.text:
        meaning = translation.text
        return meaning.capitalize()


def check_input_duplicates(input_file):
    """Check if input_words contains duplicates"""
    # read all files in input_words_archive
    new_input_words = []
    files = os.listdir("input_words_archive")
    words = []
    for file in files:
        with open(f"input_words_archive/{file}", "r", encoding="utf-8") as f:
            words += [line.strip().replace("\u200b", "") for line in f if line.strip()]
    # read input_words
    with open(input_file, "r", encoding="utf-8") as f:
        input_words = [line.strip().replace("\u200b", "") for line in f if line.strip()]
    for word in input_words:
        is_chinese_char(word)
        if not is_chinese_char(word):
            raise ValueError(f"Invalid Chinese character: {word}")
        if word in words:
            print(f"Duplicate word: {word}")
        else:
            new_input_words.append(word)

    print(f"Removed {len(input_words) - len(new_input_words)} duplicates")
    print(f"Found {len(new_input_words)} words to process")
    with open(input_file, "w", encoding="utf-8") as f:
        for word in new_input_words:
            f.write(f"{word}\n")
    return new_input_words


def is_chinese_char(text):
    """
    Check if all characters in the input text are Chinese characters (汉字).
    Returns True if all characters are Chinese, False if any character is not.

    Uses Unicode ranges:
    - CJK Unified Ideographs: U+4E00 - U+9FFF (basic Chinese characters)
    - CJK Unified Ideographs Extension A: U+3400 - U+4DBF (less common)
    """
    if not text or len(text) == 0:  # Handle empty input
        return False

    for char in text:
        code_point = ord(char)
        # Check if character is outside both Unicode ranges
        if not ((0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF)):
            return False
    return True


if __name__ == "__main__":
    generator = ChineseAnkiGenerator()

    # Example usage with a file
    input_file = "chinese_words.txt"

    # Create example file if it doesn't exist
    if not os.path.exists(input_file):
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("你好\n")
        print(f"Created example file: {input_file}")

    # check if input_words contains duplicates
    checked_input_words = check_input_duplicates(input_file)
    # Process the file
    results = generator.create_deck_from_file(checked_input_words)

    # Display results
    print("\nProcessed words:")
    for result in results:
        print(f"{result['word']} ({result['pinyin']}): {result['meaning']}")
