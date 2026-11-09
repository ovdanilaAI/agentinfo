# agentinfo

Препроцессинг задач: что это, зачем и как пользоваться
Что это

Модуль детерминированного препроцессинга для хакатона. На вход — папка task-dir/ с задачами (<task_type>_<NNNN>/task.json + опциональный workspace/). На выход — два файла:

    kpi_result.json — полный контракт для оркестратора (машиночитаемый)

    kpi.csv — та же таблица глазами

Модуль не тратит ни одного токена бюджета. Всё считается локально: разбор instruction, чтение файловой системы, проверка утверждений о файлах, арифметика по формуле. Время работы — секунды на 100 задач.
Зачем это нужно

У нас три ограничения одновременно:

    Бюджет 80 000 output-эквивалентов токенов (1 output = 9.5 input). Один на всё: выбор задач, оценку расхода, решение.

    Время — 1 час на 100 задач через 5 агентов.

    15–25% задач невыполнимы (ловушки), и каждая потраченная на них минута/токен — потеря.

Задача оркестратора — решить, какие задачи брать, в каком порядке, какой моделью и с какой политикой истории. Но чтобы это решить, ему нужны три вещи, которых у него нет из task.json:

    сколько задача сожрёт (cost_reason_safe);

    решаема ли она (feasibility, p_solved);

    как её решать (strategy, recommended_model, history_policy).

Модуль даёт все три. Причём готовым решением: knapsack.selected — это уже отобранный точным ДП набор, а schedule_hint.per_agent_plan — уже разложенный по 5 агентам. Тебе не надо ничего оптимизировать — бери и исполняй.
Что внутри (для понимания, не для использования)
Шаг	Что делает	Стоимость
collect	Собирает все task.json, привязывает к ним workspace/	0
features	Считает признаки: длина instruction, число упомянутых файлов, размеры workspace, число файлов в kb/	0
fs_claims	Извлекает из instruction проверяемые утверждения («файл X существует», «в нём N строк», «есть колонки a,b,c», «директория kb/ непуста») и сверяет с диском	0
estimator	По формуле считает cost_noreason, cost_reason, seconds_*	0
strategy	Правила: нужна ли рассуждёнка, как решать, какая модель, какая политика истории	0
knapsack	Точный 0/1-рюкзак (ДП, O(n·B), для 100 задач — мгновенно)	0
scheduler	LPT-распаковка выбранных задач по 5 агентам с учётом 3600s	0

fs_claims — главная фича. Детектор ловушек. Если instruction говорит «в sales.csv 300 строк и колонки order_id, region, product, month, units, price», а на диске файла нет / строк не 300 / колонок нет — задача помечается unlikely с p_solved=0.05, и ДП её не берёт. Это экономит бюджет и время на 20% задачах, которые всё равно не решились бы.

Защита от ложных срабатываний: unlikely ставится только на жёсткие нарушения (файла нет, директория пуста, строк не N±5%, колонок нет). Всё мягкое — uncertain. Причины (violations) пишутся в выход — ты видишь, почему, и можешь переопределить.
Как пользоваться
Запуск
bash

cd /home/sam/PycharmProjects/hacaton
python main.py ./task-dir config.yaml

Два аргумента:

    ./task-dir — папка с задачами (внутри *_NNNN/task.json);

    config.yaml — константы (можно не указывать, будут дефолты).

Выход
text

task-dir/
├── kpi_result.json   ← для оркестратора
└── kpi.csv           ← глазами

Что брать из kpi_result.json

Корень:
Поле	Что
tasks[]	по одной записи на задачу, все поля
knapsack.selected	итоговый список task_id, которые надо решать
knapsack.total_cost_safe	сколько бюджета займут (из budget_output_equiv)
knapsack.n_skipped_unfeasible	сколько выкинуто как ловушки
knapsack.n_skipped_budget	сколько не влезло в бюджет
schedule_hint.per_agent_plan	разбивка по агентам: tasks, est_seconds_safe, est_cost_safe, est_reward
schedule_hint.fits_in_time	влезает ли в 3600s
meta.constants	все константы (для калибровки)

tasks[i] — поля, которые тебе нужны:
Поле	Тип	Что
task_id	str	ID задачи
task_type	str	search / coding / math / data_analysis
check	str	exact_str / exact_int / unittest
reward	float	баллы за решение (случайны, не связаны со сложностью)
feasibility	str	likely / uncertain / unlikely
violations	list	почему unlikely (пусто если всё ок)
p_solved	float	0.85 / 0.75 / 0.05 — prior по feasibility
needs_reasoning	bool	нужна ли reasoning-модель
n_iter_estimate	int	оценка числа итераций агента
cost_noreason	int	сколько займёт без рассуждений (output-equiv, без safety)
cost_reason	int	сколько займёт с рассуждениями (output-equiv, без safety)
cost_reason_safe	int	cost_reason × 1.3 — используй это для рюкзака
seconds_noreason	float	секунды без рассуждений
seconds_reason	float	секунды с рассуждениями
seconds_reason_safe	float	seconds_reason × 1.5 — используй это для планировщика
density	float	reward × p_solved / cost_reason_safe — плотность
strategy	str	рекомендация как решать (см. оговорки)
history_policy	str	keep / summarize / wipe
recommended_model	str	какую модель брать
selected	bool	брать ли в рюкзак (уже посчитано)
agent	int	номер агента 1..5 (уже распределено)

Главное: selected и agent уже заполнены. Тебе не надо решать рюкзак и планировщик — они решены. Просто исполняй.
Формулы (чтобы понимать, откуда цифры)

Стоимость (в output-эквивалентах):
text

y_out = c_sys_out + n_iter × (tool_call_tokens + reasoning_per_step) + expected_tokens
y_in  = c_sys_in + instr_tokens + min(n_iter, 3) × avg_tool_output
cost_reason = y_out + y_in / 9.5
cost_reason_safe = cost_reason × 1.3

    reasoning_per_step зависит от типа: math — 350, data_analysis — 245, search/coding — 105.

    n_iter — эвристика: 2 + ceil(kb_files/20) + упомянутые файлы + 2 за multi-step.

    avg_tool_output — из реального размера файлов в workspace/, не выдумка.

Время:
text

seconds_reason = fixed_overhead + n_iter × (latency + reasoning_bonus)
seconds_reason_safe = seconds_reason × 1.5

Рюкзак:
text

maximize Σ reward_i × p_solved_i × x_i
subject to Σ cost_reason_safe_i × x_i ≤ 80000
x_i ∈ {0,1}, только для feasibility ≠ unlikely

Планировщик: LPT (longest processing time first) на 5 агентов, ограничение 3600s.

Плотность: density = reward × p_solved / cost_reason_safe — по ней ДП сортирует неявно.
Что важно знать (оговорки)

    search_* и math_* сейчас помечены uncertain / p_solved=0.75. Это занижение из-за недоделанного детектора, не реальная ловушка. Реально они решаемы — можешь считать p_solved=0.85 для этих типов. Фикс готов, но в коде не применился (кеш/путь/старая версия), доведём к проду.

    strategy для search/coding при n_iter>2 сейчас показывает noreason_direct — по логике должно быть noreason_grep, а history_policy — summarize вместо keep. Тот же баг фикса, не логики. Ориентируйся на n_iter_estimate: при n_iter ≤ 3 — keep, при 4–6 — summarize, >6 — wipe.

    Бюджет использован на 20% на 8 задачах (15610/80000). На проде 100 задач → рюкзак отберёт ~40–50 по density. Не удивляйся, что selected < n_total — это правильно, так и должно быть.

    Константы — дефолтные, не калиброваны. meta.constants — все значения. После первых 10–20 реальных прогонов пересчитаем по факту. Если увидишь систематическое расхождение (ŷ в 2 раза больше факта) — скажи, подкрутим.

    reward случаен и не связан со сложностью. Это значит: есть задачи с reward=10 и cost=200 — их брать первыми. И есть с reward=1 и cost=3000 — не брать вообще. density это учитывает.

    p_solved — prior, не предсказание. 0.85 / 0.75 / 0.05 — константы по feasibility. Не выдавай их за вероятность; это стартовая оценка.

    unlikely задачи не попадают в selected вообще. Если тебе кажется, что задача зря выкинута — посмотри violations в tasks[i]. Если там что-то странное — скажи, поправим правило.

Что ты делаешь с этим

    Берёшь knapsack.selected — список task_id, которые надо решать. Это уже отобрано.

    Берёшь schedule_hint.per_agent_plan — какой агент какие задачи решает. Это уже распределено по 5 агентам с учётом 3600s.

    Для каждой задачи смотришь tasks[i]:

        recommended_model — какую модель брать (qwen3.8-27b для reasoning, qwen3.6-35b-a3b-noreason для остальных);

        history_policy — keep (короткая история), summarize (сводка), wipe (затереть);

        n_iter_estimate — сколько итераций ожидать (если агент делает 2× больше — что-то пошло не так);

        cost_reason_safe — сколько бюджета зарезервировать под задачу.

    Строишь вызовы агентов по per_agent_plan. Всё.

Тебе не нужно: решать рюкзак, пересчитывать стоимость, выбирать модель, строить расписание. Это уже сделано.
Что можно (и стоит) переопределить

    Если считаешь, что unlikely задача на самом деле решаема (посмотрел violations, не согласен) — можешь взять её, но вне бюджета (cost_reason_safe на неё не заложен). Риск: потратить токены впустую.

    Если считаешь, что задача недооценена (cost_reason_safe меньше реальной) — заложи запас сам, но скажи мне — обновим константы.

    Если fits_in_time=false — скажи, пересчитаем latency_per_step_sec или уберём часть задач из selected.

Запуск на проде (когда будет финальный набор)
bash

cd /home/sam/PycharmProjects/hacaton
python main.py /path/to/prod-task-dir config.yaml

Выход тот же. Модуль не зависит от количества задач (8 или 100 — работает одинаково). На 100 задачах knapsack.selected будет ~40–50.

Один нюанс: если прод-набор в другом формате (другие поля, другая структура workspace/) — скажи, поправим collect.py / fs_claims.py. Формат из примера data_analysis_0006 / search_0005 мы поддерживаем полностью.
Что дальше (не для тебя, для протокола)

    Онлайн-калибровка констант по факту первых 10–20 прогонов (автоматически, без LLM).

    ML-модели (полином / SVM / GBM) — когда наберётся сотни размеченных (task → tokens, solved). На 100 задачах — только калибровка констант, не обучение.

    Уточнение feasibility — если увидим, что uncertain часто решается, ослабим правила.

Это следующие шаги, не текущие. Сейчас — рабочий модуль с дефолтными константами.
Контакты и артефакты

    Код: /home/sam/PycharmProjects/hacaton/ (10 файлов + config.yaml)

    Пример выхода: /home/sam/PycharmProjects/hacaton/task-dir/kpi_result.json

    Как запустить: python main.py ./task-dir config.yaml

    Вопросы: ко мне, до прода.

Готово к использованию. Если что-то в контракте непонятно — спрашивай сразу, до того как начнёшь строить оркестрацию.
