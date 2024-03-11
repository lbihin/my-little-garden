import unittest

from activities.models import Fertilizer


class TestFertilizerMethods(unittest.TestCase):

    def setUp(self):
        self.sample_fertilizer = Fertilizer(
            name="sample_fertilizer",
            company="sample_company",
            organic=True,
            n_rate=10.0,
            p_rate=10.0,
            k_rate=10.0
        )

    def test_str_method(self):
        result = str(self.sample_fertilizer)
        expected = "sample_company sample_fertilizer (N=10.0%, P=10.0%, K=10.0%)"
        self.assertEqual(result, expected, "Invalid __str__ method")

    def test_get_element_base_composition(self):
        result = self.sample_fertilizer.get_element_base_composition()
        expected = {'N': 10.0, 'P': 10.0, 'K': 10.0}
        self.assertEqual(result, expected, "Invalid get_element_base_composition method")


if __name__ == "__main__":
    unittest.main()
