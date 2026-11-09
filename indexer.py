import os
import glob

def index_answers(base_dir="task-dir"):
    print(f"🔍 Сканируем и индексируем файлы `answer.txt` в директории: {base_dir}...\n")
    
    # Ищем все файлы answer.txt рекурсивно по маске
    search_pattern = os.path.join(base_dir, "**", "answer.txt")
    answer_files = glob.glob(search_pattern, recursive=True)
    
    if not answer_files:
        print("❌ Файлы `answer.txt` пока не найдены!")
        return
        
    print(f"✅ Найдено ответов: {len(answer_files)}\n" + "="*60)
    
    for file_path in answer_files:
        # Извлекаем task_id из пути (например, task-dir/coding_0007/answer.txt -> coding_0007)
        path_parts = os.path.normpath(file_path).split(os.sep)
        task_id = path_parts[-2] if len(path_parts) >= 2 else "unknown_task"
        
        # Читаем содержимое ответа
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception as e:
            content = f"[Ошибка чтения файла: {e}]"
            
        print(f"📌 Задача ID : {task_id}")
        print(f"📂 Путь к файлу: {file_path}")
        print(f"📄 Содержимое ответа:\n{content}")
        print("-" * 60)

if __name__ == "__main__":
    index_answers()