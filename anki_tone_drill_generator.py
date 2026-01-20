import csv
import random
import os
import re
import json
import subprocess
import genanki
from gtts import gTTS
import time

INPUT_CSV = "hsk tonepairs sorted.csv"
BASE_DECK_NAME = "Chinese decks::ToneDrills::Tone Drill"
AUDIO_DIR = "tone_audio_mac"
STATE_FILE = "tone_drill_state.json"
MAX_CARDS_PER_DECK = 20
MIN_SYLLABLES = 2
# === Настройки TTS (macOS) ===
# Скорость речи для голоса Tingting: чем меньше значение — тем медленнее.
# Рекомендуемые значения:
#   HSK 1–2: 120–140  (очень чётко, с акцентом на каждый слог)
#   HSK 3–4: 150–170  (естественно, но чуть замедленно)
#   HSK 5–6: 180–200  (почти как носитель, но всё ещё разборчиво)
#
# Для тренировки тонов лучше начинать с HSK1-скорости.
SPEECH_RATE = 130  # ← по умолчанию для HSK1

os.makedirs(AUDIO_DIR, exist_ok=True)

def get_next_deck_number():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            n = json.load(f)["last_deck_number"] + 1
    else:
        n = 1
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_deck_number": n}, f)
    return n

def extract_syllables(pinyin_str):
    clean = pinyin_str.replace(' ', '')
    raw = re.findall(r'[a-zA-ZüÜ]+[1-5]?', clean)
    return [s + ('5' if not s[-1].isdigit() else '') for s in raw]

def load_words(csv_path, min_syllables=2):
    words = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 3:
                hanzi, pinyin_raw = row[1].strip(), row[2].strip()
                if len(extract_syllables(pinyin_raw)) >= min_syllables:
                    words.append((hanzi, ' '.join(extract_syllables(pinyin_raw))))
    return words


def get_audio_from_tts(text, output_path):
    """
    Generate audio pronunciation using Google TTS 
    and save it to the specific output_path provided.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        tts = gTTS(text=text, lang='zh-cn')
        tts.save(output_path)
        print(f"Generated TTS audio for {text}")
        return output_path
    except Exception as e:
        print(f"Error generating TTS audio: {e}")
        return None

def main():
    all_words = load_words(INPUT_CSV, MIN_SYLLABLES)
    if not all_words:
        print("❌ Нет подходящих слов.")
        return

    deck_num = get_next_deck_number()
    deck_name = f"{BASE_DECK_NAME} {deck_num:03d}"
    output_apkg = f"Tone_Drill_{deck_num:03d}.apkg"

    selected = random.sample(all_words, min(MAX_CARDS_PER_DECK, len(all_words)))

    model = genanki.Model(
        random.randrange(1 << 30, 1 << 31),
        'Tone Drill macOS',
        fields=[{'name': 'Pinyin'}, {'name': 'Hanzi'}, {'name': 'Audio'}],
        templates=[{
            'name': 'Card',
            'qfmt': '{{Audio}}',
            'afmt': '''
                <div style="font-size: 28px; line-height: 1.6;">{{Pinyin}}</div>
                <div style="font-size: 24px; color: #555;">{{Hanzi}}</div>
            '''
        }],
        css='.card { font-family: Arial; text-align: center; padding: 20px; }'
    )

    deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), deck_name)
    media_files = []

    for hanzi, pinyin_display in selected:
        # Create a safe filename (no timestamps needed here, uniqueness handled by deck_num)
        safe_name = "".join(c if c.isalnum() else "_" for c in hanzi)
        filename = f"{safe_name}_{deck_num:03d}.mp3"
        mp3_path = os.path.join(AUDIO_DIR, filename)

        # Updated call: passing the text and the EXACT path we want to save to
        if get_audio_from_tts(hanzi, mp3_path):
            media_files.append(mp3_path)
            # Anki expects just the filename in the tag, not the full path
            audio_tag = f'[sound:{filename}]'
        else:
            audio_tag = "[Аудио не создано]"

        deck.add_note(genanki.Note(model=model, fields=[pinyin_display, hanzi, audio_tag]))

    genanki.Package(deck, media_files=media_files).write_to_file(output_apkg)
    print(f"✅ Готово: {deck_name} ({len(selected)} карточек)")

if __name__ == "__main__":
    main()