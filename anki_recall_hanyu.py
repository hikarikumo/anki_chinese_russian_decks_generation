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
import openai
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions


# anki_deck_name = "Vova chinese HSK1"
# anki_deck_name = "DuChinese chinese HSK1"
# anki_deck_name = "DuChinese pet store" 
# anki_deck_name = "DuChinese Butterfly lovers"
anki_deck_name = "recall_DuChinese hsk1 dialogues"
# anki_deck_name = "MandarinBean hsk2"
# anki_deck_name = "HSK3 trade bargain"
# anki_deck_name = "HSK3 Standard course"
# anki_deck_name = "Parks"
# anki_deck_name = "昆明周二星期四"
# anki_deck_name = "chinese daily podcast - Why You Still Can’t Speak Chinese?"
# anki_deck_name = "Roman words"
# anki_deck_name = "Chinese Pod Newbie"
# anki_deck_name = "美玲 说话"

# anki_deck_name = "Ян Боровски - частотные слова"
# output_deck = "vova_chinese_hsk1.apkg"
# output_deck = "Duchinese_hsk1.apkg"
# output_deck = "Duchinese_pet_store.apkg"
# output_deck = "Duchinese_butterfly_lovers.apkg"
output_deck = "recall_DuChinese_hsk1_dialogues.apkg"
# output_deck = "MandarinBean_hsk2.apkg"
# output_deck = "HSK3_Standard_course.apkg"
# output_deck = "HSK3_trade_bargain.apkg"
# output_deck = "2025.08.21.apkg"
# output_deck = "chinese_daily_podcast_cannot_speak_chinese.apkg"
# output_deck = "roman_words.apkg"
# output_deck = "chinese_pod_newbie.apkg"
# output_deck = "meiling_conversation.apkg"
# output_deck = "parks.apkg"
input_file = "chinese_words.txt"    
# input_words_archive = "input_words_archive_2025.08.21"
# input_words_archive = "input_words_archive_chinese_daily_podcast"
# input_words_archive = "input_words_archive_chinese_roman"
# input_words_archive = "input_words_archive_chinese_pod"
# input_words_archive = "input_words_archive_meiling"
# input_words_archive = "input_words_archive_duchinese_pet_store"
# input_words_archive = "input_words_archive_duchinese_butterfly_lovers"
input_words_archive = "input_recall_words_archive_duchinese_hsk1_dialogues"
# input_words_archive = "input_words_archive_mandarinbean_hsk2"

# Path to makemeahanzi graphics.txt (update this to your local path)
GRAPHICS_PATH = "graphics.txt"


class ChineseAnkiGenerator:
    def __init__(self):
        # Load stroke data from makemeahanzi
        self.graphics_data = self.load_graphics_data(GRAPHICS_PATH)

        # Create Anki model with StrokeOrder field
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name,
            fields=[
                {"name": "Chinese"},
                {"name": "Pinyin"},
                {"name": "ColoredPinyin"},
                {"name": "Meaning"},
                {"name": "Example"},
                {"name": "ExamplePinyin"},
                {"name": "ExampleMeaning"},
                {"name": "Audio"},
                {"name": "StrokeOrder"},  # New field for stroke order image
            ],
            templates=[
                {
                    # 1. Recognition (Chinese -> Russian) - Default style
                    "name": "Recognition (Chinese -> Russian)",
                    "qfmt": '<div class="meaning">{{Meaning}}</div>',
                    "afmt": """
                        <div class="meaning">{{Meaning}}</div>
                        <hr>
                        <div class="stroke-order">{{StrokeOrder}}</div>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="example">{{Example}}</div>
                        <div class="example-pinyin">{{ExamplePinyin}}</div>
                        <div class="example-meaning">{{ExampleMeaning}}</div>
                        {{Audio}}
                    """,
                },
                {
                    # 2. Recall (Russian -> Chinese) - As explicitly requested
                    # Front (Qfmt): Russian Meaning ONLY
                    "name": "Recall (Russian -> Chinese)",
                    "qfmt": """
                            <div class="stroke-order">{{StrokeOrder}}</div>
                            """,
                    # Back (Afmt): Chinese word/characters FIRST, then details, including Audio
                    "afmt": """
                        <div class="meaning">{{Meaning}}</div>
                        <hr>
                        <div class="pinyin">{{ColoredPinyin}}</div>
                        <div class="example">{{Example}}</div>
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
                    font-weight: bold;
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
        # (UNCHANGED as requested)
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
        print(f'{word=}')

        # Configure the Gemini API client with the API key from environment variables.
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY environment variable not set.")
            return None
        genai.configure(api_key=api_key)

        try:
            # Using a stable, generally available model 
            model = genai.GenerativeModel('gemini-2.5-pro') 
            
            # Define the prompt. The instructions for JSON format are still key.
            prompt = (
                f"Provide one example sentence in Simplified Chinese that uses the word '{word}', "
                "along with its Russian translation from Chinese. Return the response in JSON format like this:\n"
                "{\n  \"chinese\": \"<Simplified Chinese sentence>\",\n  \"meaning\": \"<Russian translation>\"\n}"
            )            

            # Use GenerationConfig to specify a structured JSON output.
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

            # Make the API call to generate content.
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )

            # Access the structured content from the response and parse it.
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
            print(f"Response content: {response.text}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

    def get_audio_from_forvo(self, word):
        """Get audio pronunciation from Forvo API"""
        # (Your existing implementation remains unchanged)
        audio_dir = "forvo_audio"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
        audio_file_path = f"{audio_dir}/{word}_audio.mp3"
        if os.path.exists(audio_file_path):
            return audio_file_path
        try:
            encoded_word = urllib.parse.quote(word)
            forvo_api_key = os.getenv("FORVO_API_KEY")
            api_url = f"https://apifree.forvo.com/key/{forvo_api_key}/format/json/action/word-pronunciations/word/{encoded_word}/language/zh"
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if "items" in data and len(data["items"]) > 0:
                    sorted_items = sorted(data["items"], key=lambda x: int(x.get("num_positive_votes", 0)), reverse=True)
                    audio_url = sorted_items[0]["pathmp3"]
                    audio_response = requests.get(audio_url)
                    if audio_response.status_code == 200:
                        with open(audio_file_path, "wb") as f:
                            f.write(audio_response.content)
                        print(f"Downloaded audio for {word}")
                        return audio_file_path
            return None
        except Exception as e:
            print(f"Error fetching audio: {e}")
            return None

    def process_word(self, word):
        """Process a single Chinese word"""
        print(f"Processing: {word}")

        # Get pinyin
        raw_pinyin = pinyin(word, style=Style.TONE3)
        pinyin_text = " ".join(["".join(p) for p in raw_pinyin])
        colored_pinyin = self.color_pinyin(pinyin_text)

        # Get dictionary definition
        meaning = self.get_dictionary_data(word)

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

        # Get audio
        audio_file = self.get_audio_from_forvo(word)
        audio_tag = f"[sound:{os.path.basename(audio_file)}]" if audio_file and os.path.exists(audio_file) else ""
        if audio_file:
            self.media_files.append(audio_file)

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
                example_chinese,   # Example
                example_colored_pinyin,  # ExamplePinyin
                example_meaning,   # ExampleMeaning
                audio_tag,         # Audio
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
        output_file_archive_path = input_words_archive
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

# 💡 UNCHANGED: This function remains as requested.
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

    # output_file = f"input_words_archive/chinese_words_{datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}.txt"
    # with open(output_file, "w", encoding="utf-8") as f:
    #     for word in words:
    #         f.write(f"{word}\n")
    # print(f"Found {len(words)} words in archive")

    input_words = list(set(input_words))
    for word in input_words:
        # if not is_chinese_char(word):
        #     raise ValueError(f"Invalid Chinese character: {word}")
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