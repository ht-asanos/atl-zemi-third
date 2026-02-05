from collections import Counter
import random
from treys import Card, Deck, Evaluator  # type: ignore

class PokerSimulator:
    def __init__(self):
        self.evaluator = Evaluator()
        self.rank_map = {
            1: "Straight Flush",
            2: "Four of a Kind",
            3: "Full House",
            4: "Flush",
            5: "Straight",
            6: "Three of a Kind",
            7: "Two Pair",
            8: "Pair",
            9: "High Card"
        }
        # Royal Flush is usually included in Straight Flush in treys logic for class, 
        # but let's handle standard treys output.
        # Treys rank classes are 1 (Royal Flush) to 9 (High Card) usually?
        # Let's verify with treys constants if possible, but hardcoding based on standard poker ranks 
        # is safer if we map get_rank_class output.
        # In treys:
        # 1 = Straight Flush (includes Royal)
        # 2 = Four of a Kind
        # ...
        # 9 = High Card
    
    def _normalize_rank_name(self, rank_class: int) -> str:
        # treys returns 1 for Straight Flush (and Royal Flush). 
        # We can just use the map.
        return self.rank_map.get(rank_class, "Unknown")

    def run_simulation(self, my_card_strs: list[str], num_players: int, num_simulations: int = 10000) -> dict:
        # Validation
        if len(my_card_strs) != 2:
            raise ValueError("Must provide exactly 2 cards")
        
        if len(set(my_card_strs)) != len(my_card_strs):
            raise ValueError("Duplicate cards are not allowed")
        
        # Convert strings to Card objects
        try:
            my_cards = [Card.new(c) for c in my_card_strs]
        except Exception:
             raise ValueError(f"Invalid card format: {my_card_strs}")

        # Initialize counters
        wins = 0
        ties = 0
        losses = 0
        rank_counts: Counter[str] = Counter()
        
        deck = Deck()
        
        # Remove my cards from deck logic is needed because Deck() creates full deck.
        # But treys Deck doesn't have a remove method easily accessible in older versions?
        # Standard way: draw cards from deck until we get my cards? No, inefficient.
        # Better: Get full deck, remove my card integers, then recreate deck mechanism manually 
        # OR just use deck.draw() and ignore if it's my card?
        # Treys Deck internal is just a list of integers.
        
        # Optimized Simulation Loop
        # We can't reuse the same Deck object efficiently if we have to remove specific cards every time.
        # Instead, create the "remaining deck" once.
        full_deck = deck.cards # list of ints
        remaining_deck_base = [c for c in full_deck if c not in my_cards]
        
        for _ in range(num_simulations):
            # Shuffle remaining deck
            current_deck = list(remaining_deck_base)
            random.shuffle(current_deck)
            
            # Draw Board (5 cards)
            board = current_deck[:5]
            current_deck_idx = 5
            
            # Draw Opponents Hands
            opponents_hands = []
            for _ in range(num_players - 1):
                hand = current_deck[current_deck_idx : current_deck_idx + 2]
                current_deck_idx += 2
                opponents_hands.append(hand)
            
            # Evaluate my hand
            my_score = self.evaluator.evaluate(board, my_cards)
            my_rank_class = self.evaluator.get_rank_class(my_score)
            rank_name = self._normalize_rank_name(my_rank_class)
            rank_counts[rank_name] += 1
            
            # Evaluate opponents
            opp_scores = []
            for opp_hand in opponents_hands:
                score = self.evaluator.evaluate(board, opp_hand)
                opp_scores.append(score)
            
            # Determine winner
            # Lower score is better
            min_opp_score = min(opp_scores) if opp_scores else 999999
            
            if my_score < min_opp_score:
                wins += 1
            elif my_score == min_opp_score:
                ties += 1
            else:
                losses += 1
                
        # Calculate statistics
        total = num_simulations
        
        # Format hand potential (TOP 3)
        hand_potential = []
        for rank_name, count in rank_counts.most_common(3):
            hand_potential.append({
                "rank_name": rank_name,
                "probability": round((count / total) * 100, 2)
            })
            
        result = {
            "hand_potential": hand_potential,
            "win_rate": round((wins / total) * 100, 2),
            "tie_rate": round((ties / total) * 100, 2),
            "loss_rate": round((losses / total) * 100, 2),
            "execution_count": total
        }
        
        return result

def run_simulation_task(my_card_strs: list[str], num_players: int, num_simulations: int) -> dict:
    simulator = PokerSimulator()
    return simulator.run_simulation(my_card_strs, num_players, num_simulations)
