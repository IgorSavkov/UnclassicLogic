"""fuzzy_student — библиотека для работы с нечёткими величинами,
функция принадлежности которых имеет вид распределения Стьюдента.

Библиотека не зависит от графического интерфейса и может подключаться
к любой внешней программе:

    from fuzzy_student import StudentFuzzy, generate_set, ClusterAnalysis

    a = StudentFuzzy(2, 1, 5)
    b = StudentFuzzy(3, 0.5, 5)
    print(a + b, a * b, a < b)
"""
from .arithmetic import (OPERATION_NAMES, OPERATIONS, CutResult, OperationResult, add, divide,
                         exact_operation, fit_student, multiply, operate, operate_detailed, subtract)
from .clustering import METHODS, ClusterAnalysis, feature_vectors, fuzzy_distance
from .compare import compare, intersection_heights, necessity_ge, possibility_eq, possibility_ge
from .fuzzy_set import FuzzySet
from .generator import generate_set
from .journal import Journal
from .student import SUPPORT_ALPHA, StudentFuzzy, spread_factor

__version__ = "1.0.0"

__all__ = [
    "StudentFuzzy", "SUPPORT_ALPHA", "spread_factor",
    "operate", "operate_detailed", "add", "subtract", "multiply", "divide",
    "exact_operation", "fit_student", "CutResult", "OperationResult", "OPERATIONS", "OPERATION_NAMES",
    "compare", "possibility_eq", "possibility_ge", "necessity_ge", "intersection_heights",
    "FuzzySet", "generate_set", "ClusterAnalysis", "METHODS", "feature_vectors", "fuzzy_distance",
    "Journal",
]
