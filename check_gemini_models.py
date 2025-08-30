import google.generativeai as genai
import os

# Получаем API-ключ из переменной окружения
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)

# Проверяем доступные модели
models = genai.list_models()
for model in models:
    print(model.name)