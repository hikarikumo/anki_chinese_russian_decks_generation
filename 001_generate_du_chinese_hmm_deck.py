import genanki
import random
import requests
import os
import urllib.parse
import re
import json
from datetime import datetime
from openai import OpenAI, OpenAIError
from googletrans import Translator
import asyncio
import replicate
import shutil
from pypinyin import pinyin, Style
import time

# Этот скрипт содержит общие классы, которые могут быть использованы в обоих файлах.
# В более крупном проекте их можно было бы вынести в отдельный файл `common.py`.

# --- НАСТРОЙКИ ---
STORIES_JSON_FILE = "stories/stories_for_review.json"
anki_deck_name = "DuChinese Hanzi Spaces with Actors (Русский)"
output_deck = "duchinese_hanzi_spaces_actors_rus.apkg"

# --- OpenAI и DALL-E Настройки ---
OPENAI_IMAGE_MODEL = "dall-e-2"
IMAGE_SIZE = "512x512"  # Размер изображения для DALL-E



class AnkiDeckGenerator:
    def __init__(self):
        self.model = genanki.Model(
            random.randrange(1 << 30, 1 << 31),
            anki_deck_name,
            fields=[
                {"name": "Иероглиф"}, {"name": "Пиньинь"}, {"name": "ЦветнойПиньинь"},
                {"name": "Значение"}, {"name": "Пространство"}, {"name": "Подсказка"},
                {"name": "Аудио"}, {"name": "История"}, {"name": "ИсторияИзображение"},
                {"name": "StrokeOrder"},
            ],
            templates=[
                {
                    "name": "Узнавание",
                    "qfmt": '<div class="stroke-order">{{StrokeOrder}}</div>',
                    "afmt": """
                        <div class="stroke-order">{{StrokeOrder}}</div><hr>
                        <div class="pinyin">{{Пиньинь}}</div><div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="meaning">{{Значение}}</div><div class="space"><b>Пространство:</b> {{Пространство}}</div>
                        <div class="hint"><b>Подсказка:</b> {{Подсказка}}</div><div class="story"><b>История:</b> {{История}}</div>
                        <div class="story-image">{{ИсторияИзображение}}</div>{{Аудио}}
                    """,
                },
                {
                    "name": "Вспоминание",
                    "qfmt": '<div class="meaning">{{Значение}}</div><div class="space"><b>Пространство:</b> {{Пространство}}</div>',
                    "afmt": """
                        <div class="meaning">{{Значение}}</div><hr><div class="hanzi">{{Иероглиф}}</div>
                        <div class="pinyin">{{Пиньинь}}</div><div class="colored-pinyin">{{ЦветнойПиньинь}}</div>
                        <div class="space"><b>Пространство:</b> {{Пространство}}</div><div class="hint"><b>Подсказка:</b> {{Подсказка}}</div>
                        <div class="story"><b>История:</b> {{История}}</div><div class="story-image">{{ИсторияИзображение}}</div>{{Аудио}}
                    """,
                },
            ],
            css="""
                .card { font-family: Arial, sans-serif; font-size: 16px; text-align: center; color: black; background-color: white; padding: 20px; }
                .hanzi { font-size: 50px; font-weight: bold; margin-bottom: 15px; }
                .stroke-order img, .stroke-order svg { max-width: 200px; height: 100px; margin-top: 15px; margin-right: 10px; }
                .pinyin, .colored-pinyin { font-size: 18px; margin-bottom: 10px; }
                .meaning { font-size: 20px; margin-bottom: 15px; }
                .location, .hint, .story { font-size: 16px; margin-top: 10px; }
                .story { color: #333; font-style: italic; }
                .story-image img { max-width: 350px; height: auto; margin-top: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
                .tone1 { color: blue; } .tone2 { color: green; } .tone3 { color: purple; } .tone4 { color: red; } .tone5 { color: gray; }
            """,
        )
        self.deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), anki_deck_name)
        self.media_files = []

    def color_pinyin(self, pinyin_text):
        result = []
        for syllable in pinyin_text.split():
            tone = next((char for char in syllable if char.isdigit()), None)
            if tone:    
                syllable_without_tone = syllable.replace(tone, "")
                result.append(f'<span class="tone{tone}">{syllable_without_tone}{tone}</span>')
            else: result.append(syllable)
        return " ".join(result)

    def _build_image_prompt(self, primary_meaning, actor, location, story):
        return (
            f"Фотореалистичное изображение, кинематографический свет, высокая детализация. "
            f"Сцена, основанная на истории: '{story}'.\n"
            f"На сцене находятся: {actor} в локации '{location}'. "
            f"Изображение иллюстрирует идею '{primary_meaning}'.\n\n"
            f"КРАЙНЕ ВАЖНО: на изображении должна быть только сцена. Никаких иероглифов, слов, надписей, текста. Абсолютно чистое изображение."
        )

    def generate_story_image(self, hanzi, meaning_ru, actor, location, story):
        image_dir = "story_images"
        os.makedirs(image_dir, exist_ok=True)
        image_file_path = f"{image_dir}/{hanzi}_story.png"
        if os.path.exists(image_file_path):
            print(f"Image for {hanzi} already exists. Using existing.")
            self.media_files.append(image_file_path)
            return image_file_path

        prompt = self._build_image_prompt(meaning_ru, actor, location, story)
        try:
            print(f"Generating image for {hanzi} based on your edited story...")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not client.api_key: raise OpenAIError("Ключ OpenAI API не найден")
            response = client.images.generate(model=OPENAI_IMAGE_MODEL, prompt=prompt, n=1, size=IMAGE_SIZE)
            image_url = response.data[0].url
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                with open(image_file_path, "wb") as f: f.write(image_response.content)
                print(f"Successfully saved image for {hanzi}")
                self.media_files.append(image_file_path)
                print("Waiting 15 seconds to respect the rate limit...")
                time.sleep(15)
                return image_file_path
        except Exception as e:
            print(f"Error generating image for {hanzi} with DALL-E: {e}")
            print("Waiting 15 seconds to respect the rate limit...")
            time.sleep(15)
        return None

    # def generate_story_image(self, hanzi, meaning_ru, actor, location, story, anki_media_dir=None):
    #     """
    #     Generate an image using Replicate's API with Google Imagen 3 for a given hanzi,
    #     incorporating Russian text and Chinese characters in the prompt. Copies the image
    #     to Anki's media folder and ensures compatibility with .apkg files.
        
    #     Args:
    #         hanzi (str): The Chinese character (e.g., '办' or '不').
    #         meaning_ru (str): The Russian meaning of the hanzi (e.g., 'делать' or 'нет').
    #         actor (str): The actor in the story (e.g., 'Леонардо ДиКаприо').
    #         location (str): The location in the story (e.g., 'медитационной комнате своего экодома').
    #         story (str): The full story prompt with Russian text and Chinese characters.
    #         anki_media_dir (str, optional): Path to Anki's media folder (e.g., collection.media/).
        
    #     Returns:
    #         tuple: (image_path, image_tag) where image_path is the path to the saved image
    #             in Anki's media folder (or local if anki_media_dir is None), and
    #             image_tag is the HTML tag for Anki (e.g., '<img src="ban3_story.png">').
    #             Returns (None, None) if generation fails.
    #     """
    #     # image_dir = "story_images"
    #     # os.makedirs(image_dir, exist_ok=True)
    #     # hanzi_pinyin = pinyin(hanzi, style=Style.TONE3)[0][0]  # e.g., "ban3" for 办
    #     # image_file_path = os.path.join(image_dir, f"{hanzi_pinyin}_story.png")
    #     # image_tag = f'<img src="{hanzi_pinyin}_story.png">'
    #     image_dir = "story_images"
    #     os.makedirs(image_dir, exist_ok=True)
    #     image_file_path = f"{image_dir}/{hanzi}_story.png"
    #     if os.path.exists(image_file_path):
    #         print(f"Image for {hanzi} already exists. Using existing.")
    #         return image_file_path        

    #     # Build the prompt
    #     prompt = self._build_image_prompt(meaning_ru, actor, location, story)
    #     # print(f"Prompt for {hanzi}: {prompt}")
        
    #     try:
    #         print(f"Generating image for {hanzi} based on your edited story...")
            
    #         # Initialize Replicate client
    #         client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
            
    #         # Run Google Imagen 3 model
    #         input_params = {
    #             "prompt": prompt,
    #             "num_outputs": 1,
    #             "aspect_ratio": "1:1",
    #             "output_format": "png",
    #             "safety_filter_level": "block_medium_and_above"
    #         }
    #         output = client.run("google/imagen-3", input=input_params)
            
    #         # Handle different output types
    #         if isinstance(output, list) and len(output) > 0:
    #             image_url = output[0]
    #         elif hasattr(output, 'url'):
    #             image_url = output.url
    #         elif isinstance(output, str):
    #             image_url = output
    #         else:
    #             raise ValueError(f"Unexpected output format for {hanzi}: {type(output)}")
            
    #         # Download and save the image
    #         image_response = requests.get(image_url)
    #         print(f"Download status for {hanzi}: {image_response.status_code}, Size: {len(image_response.content)} bytes")
    #         if image_response.status_code == 200:
    #             with open(image_file_path, "wb") as f:
    #                 f.write(image_response.content)
    #             if os.path.getsize(image_file_path) == 0:
    #                 print(f"Error: Image file for {hanzi} ({image_file_path}) is empty")
    #                 return None, None
                    
    #             print(f"Successfully saved image for {hanzi}: {image_file_path}")
                
    #             self.media_files.append(image_file_path)
    #             return image_file_path
    #         else:
    #             print(f"Failed to download image for {hanzi}: {image_response.status_code}")
    #             return None, None
                
    #     except replicate.exceptions.ReplicateError as e:
    #         if "authentication" in str(e).lower():
    #             print(f"Authentication error for {hanzi}: Invalid or missing REPLICATE_API_TOKEN.")
    #         elif "rate limit" in str(e).lower():
    #             print(f"Rate limit exceeded for {hanzi}. Try again later.")
    #         elif "credit" in str(e).lower():
    #             print(f"Insufficient credits for {hanzi}. Check your Replicate billing at https://replicate.com/account.")
    #         else:
    #             print(f"Replicate API error for {hanzi}: {e}")
    #         return None, None
    #     except requests.exceptions.HTTPError as e:
    #         if e.response.status_code == 429:
    #             print(f"Rate limit exceeded for {hanzi}. Try again later.")
    #         elif e.response.status_code == 402:
    #             print(f"Insufficient credits for {hanzi}. Check your Replicate billing at https://replicate.com/account.")
    #         else:
    #             print(f"HTTP error generating image for {hanzi}: {e}")
    #         return None, None
    #     except Exception as e:
    #         print(f"Error generating image for {hanzi} with Replicate: {e}")
    #         return None, None

    def get_audio_from_forvo(self, hanzi):
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
            else:
                print(f"No audio found for {hanzi} on Forvo.")
        except Exception as e:
            print(f"Ошибка при загрузке аудио для {hanzi}: {e}")
        return None
        

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


async def google_translate_ru(en_word):
    if not en_word: return ""
    translator = Translator()
    try:
        return (await translator.translate(en_word, src="ru", dest="en")).text
    except Exception as e:
        print(f"Translation error: {e}")
        return en_word


# --- ГЛАВНАЯ ЛОГИКА СКРИПТА 2 ---
def main():
    if not os.path.exists(STORIES_JSON_FILE):
        print(f"Файл '{STORIES_JSON_FILE}' не найден. Сначала запустите скрипт '1_generate_stories.py'.")
        return

    with open(STORIES_JSON_FILE, 'r', encoding='utf-8') as f:
        stories_data = json.load(f)

    generator = AnkiDeckGenerator()

    for data in stories_data:
        hanzi = data['hanzi']
        print(f"Creating card for: {hanzi}")
        
        # Генерация медиафайлов
        image_file = generator.generate_story_image(hanzi, data['meaning_ru'], data['actor'], data['location'], data['story'])
        audio_file = generator.get_audio_from_forvo(hanzi)
        stroke_image_result = generator.create_stroke_image(hanzi)

        # Форматирование тегов для Anki
        if image_file: 
            image_tag = f'<img src="{os.path.basename(image_file)}">' if image_file else ""
        
        if audio_file:            
            audio_tag = f"[sound:{os.path.basename(audio_file)}]" if audio_file else ""
        stroke_tag = ""
        if stroke_image_result:
            if isinstance(stroke_image_result, tuple):
                stroke_tag = "".join(f'<img src="{os.path.basename(p)}">' for p in stroke_image_result[1])
            else:
                stroke_tag = f'<img src="{os.path.basename(stroke_image_result)}">'

        # Создание карточки
        note = genanki.Note(
            model=generator.model,
            fields=[
                data['hanzi'], data['pinyin'], generator.color_pinyin(data['pinyin']),
                data['meaning_en'], data['location'], data['hint'],
                audio_tag, data['story'], image_tag, stroke_tag,
            ]
        )
        generator.deck.add_note(note)

    # Сохранение колоды
    package = genanki.Package(generator.deck)
    package.media_files = generator.media_files
    package.write_to_file(output_deck)
    print(f"\nКолода '{output_deck}' успешно создана с {len(stories_data)} карточками.")
    
    # Архивируем файл с историями, чтобы не использовать его повторно
    archive_dir = "processed_stories_archive"
    os.makedirs(archive_dir, exist_ok=True)
    archive_filename = f'stories_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.json'
    os.rename(STORIES_JSON_FILE, os.path.join(archive_dir, archive_filename))
    print(f"Файл '{STORIES_JSON_FILE}' перемещен в архив.")


if __name__ == "__main__":
    main()