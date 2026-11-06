"""Тесты библиотеки fuzzy_student.  Запуск:  python -m unittest discover tests"""
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from fuzzy_student import (ClusterAnalysis, FuzzySet, Journal, StudentFuzzy, compare, exact_operation,
                           fit_student, fuzzy_distance, generate_set, necessity_ge, operate_detailed,
                           possibility_eq, possibility_ge)


class StudentFuzzyTest(unittest.TestCase):
    def test_peak_is_one_at_center(self):
        a = StudentFuzzy(3, 2, 4)
        self.assertAlmostEqual(a.membership(3), 1.0)
        self.assertLess(a.membership(5), 1.0)
        self.assertAlmostEqual(a.membership(1), a.membership(5))  # симметрия

    def test_alpha_cut_bounds_have_membership_alpha(self):
        a = StudentFuzzy(-1, 0.7, 3)
        for alpha in (0.05, 0.3, 0.5, 0.9):
            left, right = a.alpha_cut(alpha)
            self.assertAlmostEqual(a.membership(left), alpha, places=9)
            self.assertAlmostEqual(a.membership(right), alpha, places=9)

    def test_alpha_one_cut_is_center(self):
        self.assertEqual(StudentFuzzy(2, 1, 5).alpha_cut(1.0), (2.0, 2.0))

    def test_cuts_shrink_when_alpha_grows(self):
        a = StudentFuzzy(0, 1, 5)
        widths = [a.half_width(x) for x in (0.1, 0.4, 0.7, 1.0)]
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_cauchy_case(self):  # ν = 1: μ = 1 / (1 + t²)
        a = StudentFuzzy(0, 1, 1)
        self.assertAlmostEqual(a.membership(2), 1 / 5)

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            StudentFuzzy(0, 0, 5)
        with self.assertRaises(ValueError):
            StudentFuzzy(0, 1, -1)
        with self.assertRaises(ValueError):
            StudentFuzzy(0, 1, 5).alpha_cut(0)

    def test_sampling_center(self):
        a = StudentFuzzy(5, 1, 10)
        self.assertAlmostEqual(float(np.median(a.sample(20000, rng=1))), 5, delta=0.05)

    def test_dict_roundtrip(self):
        a = StudentFuzzy(1.5, 0.3, 7, "A")
        self.assertEqual(StudentFuzzy.from_dict(a.to_dict()), a)


class ArithmeticTest(unittest.TestCase):
    def test_sum_same_nu_is_exact(self):
        a, b = StudentFuzzy(1, 1, 5), StudentFuzzy(2, 0.5, 5)
        r = operate_detailed(a, b, "+")
        self.assertTrue(r.exact)
        self.assertEqual(r.value, StudentFuzzy(3, 1.5, 5))
        # совпадает с интервальной арифметикой по α-срезам
        np.testing.assert_allclose(r.value.alpha_cuts(r.cuts.alphas)[0], r.cuts.left, atol=1e-9)

    def test_difference_spreads_add(self):
        r = StudentFuzzy(5, 1, 5) - StudentFuzzy(2, 2, 5)
        self.assertEqual(r, StudentFuzzy(3, 3, 5))

    def test_sum_different_nu_is_approximated_well(self):
        r = operate_detailed(StudentFuzzy(0, 1, 3), StudentFuzzy(1, 1, 20), "+")
        self.assertFalse(r.exact)
        self.assertAlmostEqual(r.value.x0, 1)
        self.assertLess(r.error, 0.05)

    def test_fit_recovers_student(self):
        a = StudentFuzzy(4, 2, 7)
        cuts = exact_operation(a, 0.0, "+")
        fitted, err = fit_student(cuts)
        self.assertAlmostEqual(fitted.x0, 4)
        self.assertAlmostEqual(fitted.s, 2, delta=0.02)
        self.assertAlmostEqual(fitted.nu, 7, delta=0.3)
        self.assertLess(err, 1e-2)

    def test_multiplication_core(self):
        r = StudentFuzzy(3, 0.2, 10) * StudentFuzzy(4, 0.1, 10)
        self.assertAlmostEqual(r.x0, 12)

    def test_division(self):
        r = StudentFuzzy(10, 0.2, 10) / StudentFuzzy(5, 0.1, 10)
        self.assertAlmostEqual(r.x0, 2)

    def test_division_by_value_containing_zero(self):
        with self.assertRaises(ZeroDivisionError):
            StudentFuzzy(1, 1, 5) / StudentFuzzy(0.5, 1, 5)

    def test_scalar_operations(self):
        a = StudentFuzzy(2, 1, 5)
        self.assertEqual(a + 1, StudentFuzzy(3, 1, 5))
        self.assertEqual(10 - a, StudentFuzzy(8, 1, 5))
        self.assertEqual(a * -2, StudentFuzzy(-4, 2, 5))
        self.assertEqual(a / 4, StudentFuzzy(0.5, 0.25, 5))
        with self.assertRaises(ZeroDivisionError):
            a / 0


class CompareTest(unittest.TestCase):
    def test_compare_by_center(self):
        a, b = StudentFuzzy(1, 1, 5), StudentFuzzy(2, 1, 5)
        self.assertEqual(compare(a, b), -1)
        self.assertTrue(a < b and b > a and a <= a)

    def test_possibility_eq_is_intersection_height(self):
        a, b = StudentFuzzy(0, 1, 5), StudentFuzzy(2, 1, 5)
        h = possibility_eq(a, b)
        self.assertAlmostEqual(h, a.membership(1.0), places=9)  # пересечение в середине
        self.assertAlmostEqual(possibility_eq(a, a), 1.0)

    def test_possibility_ge(self):
        a, b = StudentFuzzy(0, 1, 5), StudentFuzzy(2, 1, 5)
        self.assertEqual(possibility_ge(b, a), 1.0)
        self.assertAlmostEqual(possibility_ge(a, b), possibility_eq(a, b))
        self.assertAlmostEqual(necessity_ge(b, a), 1 - possibility_eq(a, b))


class FuzzySetTest(unittest.TestCase):
    def test_generate_count_and_seed(self):
        s1 = generate_set(150, seed=7)
        s2 = generate_set(150, seed=7)
        self.assertEqual(len(s1), 150)
        self.assertEqual(s1.to_list(), s2.to_list())
        self.assertEqual(len(set(s1.names())), 150)

    def test_unique_names(self):
        fs = FuzzySet([StudentFuzzy(0, 1, 5, "A"), StudentFuzzy(1, 1, 5, "A")])
        self.assertEqual(len(set(fs.names())), 2)

    def test_alpha_subset_shrinks_with_alpha(self):
        fs = generate_set(200, seed=3)
        ref = fs[0]
        sizes = [len(fs.alpha_subset(a, reference=ref)) for a in (0.05, 0.3, 0.6, 0.9, 1.0)]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertGreater(sizes[0], sizes[-1])
        self.assertIn(0, fs.alpha_subset(1.0, reference=ref))  # сама величина всегда проходит

    def test_alpha_subset_by_point(self):
        fs = FuzzySet([StudentFuzzy(0, 1, 5), StudentFuzzy(10, 1, 5)])
        self.assertEqual(fs.alpha_subset(0.5, point=0.2), [0])

    def test_save_and_load(self):
        fs = generate_set(100, seed=1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "set.json"
            fs.save(path)
            self.assertEqual(FuzzySet.load(path).to_list(), fs.to_list())


class ClusteringTest(unittest.TestCase):
    def setUp(self):
        self.fs = generate_set(200, groups=5, seed=11)
        self.ca = ClusterAnalysis(self.fs)

    def test_requested_number_of_clusters(self):
        for k in (1, 2, 3, 7, 12):
            self.assertEqual(len(set(self.ca.labels_for_k(k))), k)

    def test_threshold_gives_same_partition(self):
        for k in (2, 5, 7):
            by_k = self.ca.labels_for_k(k)
            by_h = self.ca.labels_for_threshold(self.ca.threshold_for(k))
            np.testing.assert_array_equal(by_k, by_h)

    def test_labels_sorted_by_center(self):
        rows = self.ca.summary(self.ca.labels_for_k(4))
        means = [r["x0_mean"] for r in rows]
        self.assertEqual(means, sorted(means))
        self.assertEqual(sum(r["size"] for r in rows), 200)

    def test_node_labels_root_is_mixed(self):
        nodes = self.ca.node_labels(self.ca.labels_for_k(3))
        self.assertEqual(nodes[-1], -1)
        self.assertTrue(np.all(self.ca.node_labels(self.ca.labels_for_k(1)) == 0))

    def test_distance_is_metric_like(self):
        a, b = StudentFuzzy(0, 1, 5), StudentFuzzy(3, 1, 5)
        self.assertAlmostEqual(fuzzy_distance(a, a), 0)
        self.assertAlmostEqual(fuzzy_distance(a, b), fuzzy_distance(b, a))
        # одинаковая форма, сдвиг на 3: d = sqrt(2 · 3² · (1 - 0.05))
        self.assertAlmostEqual(fuzzy_distance(a, b), math.sqrt(2 * 9 * 0.95), places=9)


class JournalTest(unittest.TestCase):
    def test_writes_file_and_notifies(self):
        with tempfile.TemporaryDirectory() as d:
            j = Journal(Path(d) / "log" / "j.txt")
            got = []
            j.subscribe(got.append)
            j.info("привет")
            self.assertIn("привет", j.read())
            self.assertEqual(len(got), 1)


if __name__ == "__main__":
    unittest.main()
