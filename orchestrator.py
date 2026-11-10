import os
import json
import asyncio
import re
import csv
from dotenv import load_dotenv, find_dotenv
from openai import AsyncOpenAI
from openjiuwen.core.runner import Runner

load_dotenv(find_dotenv())

api_key = (
    os.getenv("OPENAI_API_KEY") or 
    os.getenv("API_KEY") or 
    os.getenv("NEURALDEEP_API_KEY") or
    "dummy-key"
)

api_base = (
    os.getenv("OPENAI_API_BASE") or 
    os.getenv("OPENAI_BASE_URL") or 
    "https://api.neuraldeep.ru/v1"
)

client = AsyncOpenAI(api_key=api_key, base_url=api_base)

# Семафор для соблюдения лимита тарифа (максимум 3 одновременных запроса)
api_semaphore = asyncio.Semaphore(3)

# Хранилище статистики
execution_results = []
results_lock = asyncio.Lock()

def get_task_directory(task_id: str) -> str:
    """Гарантированное создание и поиск уникальной подпапки для каждой задачи."""
    direct_path = os.path.join("task-dir", task_id)
    os.makedirs(direct_path, exist_ok=True)
    return direct_path

def find_task_instruction(task_dir: str, task_id: str) -> str:
    """Рекурсивный поиск текста инструкции во всех подпапках задачи."""
    if not os.path.isdir(task_dir):
        return f"Solve task {task_id}."
        
    target_names = ["instruction.txt", "prompt.txt", "README.md", "description.txt", "task.txt"]
    
    for root, _, files in os.walk(task_dir):
        for filename in files:
            if filename.lower() in target_names:
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            return content
                except Exception:
                    pass
                    
    for root, _, files in os.walk(task_dir):
        for filename in files:
            if filename.endswith((".txt", ".md", ".json")) and filename != "answer.txt":
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            return content
                except Exception:
                    pass

    return f"Solve task {task_id} and output the final result."

def minify_content(filename: str, content: str) -> str:
    """Минификация кода и данных."""
    ext = filename.split(".")[-1].lower()
    
    if ext == "py":
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(line)
        return "\n".join(lines)
        
    elif ext == "json":
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, separators=(',', ':'))
        except Exception:
            return content
            
    elif ext in ["txt", "md", "csv"]:
        lines = [line.rstrip() for line in content.splitlines() if line.strip()]
        return "\n".join(lines)
        
    return content

def smart_load_context(task_dir: str, task_id: str, instruction: str) -> str:
    """Компактная загрузка контекста (до 1500 символов)."""
    if not os.path.isdir(task_dir):
        return ""
        
    context_parts = []
    total_chars = 0
    max_chars = 1500

    for root, _, files in os.walk(task_dir):
        for file in files:
            if file == "answer.txt" or file in ["instruction.txt", "prompt.txt", "README.md"]:
                continue
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw_content = f.read()
                        minified = minify_content(file, raw_content)
                        
                        if len(minified) > 800:
                            minified = minified[:400] + "\n[...]\n" + minified[-400:]
                            
                        if total_chars + len(minified) > max_chars:
                            break
                            
                        context_parts.append(f"[{file}]:\n{minified}")
                        total_chars += len(minified)
                except Exception:
                    pass

    return "\n".join(context_parts)

def extract_pure_answer(full_text: str, task_id: str) -> str:
    """
    Чистое детерминированное извлечение ответа из *****answer*****:
    1. Находит контент между *****answer***** маркерами.
    2. Очищает от случайно выведенных XML тегов (<exact_answer> и т.д.).
    3. Вырезает рабочий Python-код для coding или первую валидную строку для остального.
    """
    raw_text = full_text.strip()
    if not raw_text:
        return "UNFEASIBLE"

    extracted = ""
    match = re.search(r'\*\*\*\*\*answer\*\*\*\*\*(.*?)\*\*\*\*\*answer\*\*\*\*\*.*', raw_text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()
    else:
        open_match = re.search(r'\*\*\*\*\*answer\*\*\*\*\*(.*)', raw_text, re.DOTALL)
        if open_match:
            extracted = open_match.group(1).strip()
        else:
            extracted = raw_text

    # Удаляем сорность XML тегов, если модель их вывела
    extracted = re.sub(r'</?exact_answer>', '', extracted).strip()

    # Специальная обработка для задач кодинга: вырезаем чистый python-код
    if "coding" in task_id:
        code_match = re.search(r'```(?:python)?\s*\n?(.*?)\n?```', extracted, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        cleaned_code = re.sub(r'^```(?:python)?\s*', '', extracted).strip()
        return cleaned_code

    # Для math, search, data_analysis — ищем первую чистую непустую строку
    lines = [l.strip() for l in extracted.splitlines() if l.strip()]
    
    # Отбрасываем заголовочный мусор и технические теги
    filtered_lines = []
    for line in lines:
        cleaned_line = line.strip("`*# ")
        if cleaned_line and not cleaned_line.startswith("<") and not cleaned_line.endswith(">"):
            if not cleaned_line.lower().startswith(("to find", "let", "here", "step", "based on", "according")):
                filtered_lines.append(cleaned_line)

    if filtered_lines:
        return filtered_lines[0]

    return extracted.strip("`*# ")

async def execute_agent_tasks(agent_id: int, assigned_task_ids: list, tasks_meta: dict):
    """Выполнение задач с адаптированными системными промптами."""
    print(f"🤖 Agent [{agent_id}] started. Queue size: {len(assigned_task_ids)}")
    
    for task_id in assigned_task_ids:
        task_info = tasks_meta.get(task_id, {})
        model = task_info.get("recommended_model", "qwen3.6-35b-a3b-noreason")
        
        task_dir = get_task_directory(task_id)
        instruction = find_task_instruction(task_dir, task_id)
        files_context = smart_load_context(task_dir, task_id, instruction)
        
        if "math" in task_id:
            max_toks = 800
        elif "search" in task_id:
            max_toks = 800
        else:
            max_toks = 1500

        print(f"\n" + "="*60)
        print(f"👉 [Agent {agent_id}] Task: {task_id} | Model: {model} | MaxTok: {max_toks}")
        print("="*60)
        
        full_response_text = ""
        tokens_used = 0
        success = False
        error_msg = ""
        
        user_content = f"[INST] {instruction} [/INST]"
        if files_context:
            user_content += f"\n[DATA]\n{files_context}"
            
        if "coding" in task_id:
            system_content = (
                "You are an expert Python developer.\n"
                "CRITICAL REQUIREMENT: Output your complete working Python solution immediately on the first lines inside the answer markers:\n"
                "*****answer*****\n"
                "```python\n"
                "# Your Python code here\n"
                "```\n"
                "*****answer*****"
            )
        else:
            system_content = (
                "You are an autonomous AI expert.\n"
                "CRITICAL REQUIREMENT: Output ONLY the raw final value (number, name, or city) inside the answer markers without XML tags:\n"
                "*****answer*****\n"
                "value\n"
                "*****answer*****"
            )
            
        try:
            async with api_semaphore:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    stream=True,
                    stream_options={"include_usage": True},
                    temperature=0.0,
                    max_tokens=max_toks
                )
                
                async for chunk in stream:
                    if hasattr(chunk, 'usage') and chunk.usage is not None:
                        if chunk.usage.total_tokens:
                            tokens_used = chunk.usage.total_tokens
                            
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        print(delta, end="", flush=True)
                        full_response_text += delta
            
            if tokens_used == 0 and full_response_text:
                tokens_used = len(user_content + full_response_text) // 4
                
            print(f"\n\n" + "-"*60)
            
            clean_answer = extract_pure_answer(full_response_text, task_id)

            answer_path = os.path.join(task_dir, "answer.txt")
            with open(answer_path, "w", encoding="utf-8") as f:
                f.write(clean_answer)
                
            success = True
            print(f"  ✅ [Agent {agent_id}] Task {task_id} done (~{tokens_used} tokens)")
            
        except Exception as e:
            error_msg = str(e)
            success = False
            print(f"  ❌ [Agent {agent_id}] Error: {error_msg}")
            
            answer_path = os.path.join(task_dir, "answer.txt")
            with open(answer_path, "w", encoding="utf-8") as f:
                f.write(f"Error: {error_msg}")
        
        async with results_lock:
            execution_results.append({
                "task_id": task_id,
                "agent_id": agent_id,
                "success": success,
                "tokens": tokens_used,
                "error": error_msg
            })

async def main():
    plan_file = "task-dir/kpi_result.json"
    if not os.path.exists(plan_file):
        print(f"❌ File {plan_file} not found!")
        return

    with open(plan_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    schedule_plan = data.get("schedule_hint", {}).get("per_agent_plan", [])
    tasks_meta = {t["task_id"]: t for t in data.get("tasks", [])}
    
    print(f"🚀 Starting Guaranteed Front-Marker Runner...")
    await Runner.start()
    
    try:
        agent_coroutines = [
            execute_agent_tasks(agent_plan["agent"], agent_plan["tasks"], tasks_meta)
            for agent_plan in schedule_plan
        ]
        await asyncio.gather(*agent_coroutines)
        
    finally:
        await Runner.stop()
        print("🛑 Runner stopped.")

    print("\n" + "=" * 70)
    print("📊 EXECUTION FINAL REPORT:")
    print("=" * 70)
    
    total_tasks = len(execution_results)
    successful_tasks = sum(1 for r in execution_results if r["success"])
    failed_tasks = total_tasks - successful_tasks
    middleware_tokens = sum(r["tokens"] for r in execution_results)
    
    for res in execution_results:
        status_str = "✅ Success" if res["success"] else "❌ Failed"
        print(f"• Task: {res['task_id']} (Agent ID: {res['agent_id']})")
        print(f"  Status: {status_str} | Tokens: {res['tokens']:,}")
        if not res["success"]:
            print(f"  Error: {res['error']}")
        print("-" * 60)
        
    print(f"\n📈 SUMMARY:")
    print(f"  Total tasks in plan : {total_tasks}")
    print(f"  Successfully solved : {successful_tasks}")
    print(f"  Failed              : {failed_tasks}")
    print(f"  Total token usage   : {middleware_tokens:,}")
    print(f"  Average per task    : {middleware_tokens // total_tasks if total_tasks else 0:,} tokens/task")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())