import unittest
from poker_logic import run_simulation_task

class TestPokerLogic(unittest.TestCase):
    def test_run_simulation_basic(self):
        # AA (Aces) vs 1 opponent
        my_cards = ["Ah", "As"]
        num_players = 2
        num_simulations = 1000
        
        result = run_simulation_task(my_cards, num_players, num_simulations)
        
        self.assertIn("hand_potential", result)
        self.assertIn("win_rate", result)
        self.assertIn("tie_rate", result)
        self.assertIn("loss_rate", result)
        self.assertEqual(result["execution_count"], num_simulations)
        
        # AA should have high win rate against 1 random hand (usually > 80%)
        # But random variation exists, so check basic range
        self.assertGreater(result["win_rate"], 70.0)
        
        # Check sum is roughly 100 (floating point issues aside)
        total_rate = result["win_rate"] + result["tie_rate"] + result["loss_rate"]
        self.assertAlmostEqual(total_rate, 100.0, delta=0.1)

    def test_invalid_cards(self):
        with self.assertRaises(ValueError):
            run_simulation_task(["XX", "YY"], 2, 100)

    def test_duplicate_cards(self):
        with self.assertRaises(ValueError):
            run_simulation_task(["Ah", "Ah"], 2, 100)

if __name__ == '__main__':
    unittest.main()
