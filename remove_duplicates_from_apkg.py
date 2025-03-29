import sqlite3
import tempfile
import shutil
import os
from collections import defaultdict

def remove_duplicates_from_apkg(input_path, output_path):
    """
    Удаляет дубликаты карточек из .apkg файла.
    Дубликатами считаются карточки с одинаковым содержимым в полях.
    """
    # Создаем временную директорию
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 1. Распаковываем .apkg (это zip-архив)
        shutil.unpack_archive(input_path, temp_dir, 'zip')
        
        # 2. Подключаемся к SQLite базе Anki
        db_path = os.path.join(temp_dir, 'collection.anki2')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 3. Находим дубликаты
        cursor.execute("""
            SELECT n.id, n.mid, n.flds 
            FROM notes n
            ORDER BY n.flds
        """)
        
        notes = cursor.fetchall()
        duplicates = defaultdict(list)
        
        for note_id, model_id, fields in notes:
            duplicates[(model_id, fields)].append(note_id)
        
        # 4. Удаляем дубликаты (оставляем первую карточку)
        deleted_count = 0
        for (model_id, fields), note_ids in duplicates.items():
            if len(note_ids) > 1:
                # Удаляем все кроме первой карточки
                for note_id in note_ids[1:]:
                    cursor.execute("DELETE FROM cards WHERE nid = ?", (note_id,))
                    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                    deleted_count += 1
        
        print(f"Удалено дубликатов: {deleted_count}")
        
        # 5. Сохраняем изменения
        conn.commit()
        conn.close()
        
        # 6. Создаем новый .apkg
        shutil.make_archive(output_path.replace('.apkg', ''), 'zip', temp_dir)
        os.rename(output_path.replace('.apkg', '') + '.zip', output_path)
        
    finally:
        # Очищаем временные файлы
        shutil.rmtree(temp_dir)


if __name__ == '__main__':

    remove_duplicates_from_apkg('vova_chinese_hsk1.apkg', 'vova_chinese_hsk1_no_duplicates.apkg')

# Использование
# remove_duplicates_from_apkg('input.apkg', 'output_no_duplicates.apkg')