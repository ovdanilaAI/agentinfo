import openjiuwen
import inspect

print("📦 Содержимое пакета openjiuwen:")
print(dir(openjiuwen))

# Если есть подмодули, посмотрим их
for name in dir(openjiuwen):
    if not name.startswith("_"):
        attr = getattr(openjiuwen, name)
        if inspect.ismodule(attr):
            print(f"  - модуль: {name}")