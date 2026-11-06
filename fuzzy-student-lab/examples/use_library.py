"""Пример: библиотека fuzzy_student подключается к внешней программе без GUI.

Запуск из корня проекта:  python examples/use_library.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fuzzy_student import (ClusterAnalysis, Journal, StudentFuzzy, generate_set, operate_detailed,
                           possibility_ge)

journal = Journal(Path(__file__).with_name("example_log.txt"))

# 1. Величины и α-срезы
a = StudentFuzzy(2.0, 0.5, 5, "A")
b = StudentFuzzy(3.0, 0.8, 5, "B")
journal.info(f"Заданы {a} и {b}")
print("μ_A(2.5) =", round(a.membership(2.5), 4))
print("α-срез A на уровне 0.5:", a.alpha_cut(0.5))

# 2. Операции
for op in "+-*/":
    r = operate_detailed(a, b, op)
    note = "точно" if r.exact else f"приближение, ошибка {r.error:.2%}"
    print(f"A {op} B = {r.value}  ({note})")
    journal.info(f"A {op} B = {r.value}")

# 3. Сравнение
print("A < B:", a < b, "| Poss(A >= B) =", round(possibility_ge(a, b), 4))

# 4. Генерация и кластеризация
fs = generate_set(200, groups=4, seed=1)
ca = ClusterAnalysis(fs, method="ward")
for k in (4, 2):
    labels = ca.labels_for_k(k)
    sizes = [row["size"] for row in ca.summary(labels)]
    print(f"k = {k}: размеры кластеров {sizes}, срез дерева на высоте {ca.threshold_for(k):.2f}")
    journal.info(f"Кластеризация k = {k}: {sizes}")

# 5. Подмножество по α
subset = fs.alpha_subset(0.6, reference=fs[0])
print(f"С {fs[0].name} на уровне α = 0.6 совместимы {len(subset)} величин из {len(fs)}")
print("Журнал:", journal.path)
