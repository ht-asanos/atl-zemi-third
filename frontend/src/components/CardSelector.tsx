import React from 'react';

const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'];
// Let's stick to standard colors: Hearts/Diamonds Red, Spades/Clubs Black.
// But usually 4-color deck is preferred in online poker: Spades=Black, Hearts=Red, Clubs=Green, Diamonds=Blue.
const SUITS_4COLOR = [
  { char: 's', label: '♠', color: 'text-black' },
  { char: 'h', label: '♥', color: 'text-red-600' },
  { char: 'd', label: '♦', color: 'text-blue-600' },
  { char: 'c', label: '♣', color: 'text-green-600' }
];

interface CardSelectorProps {
  selectedCards: string[];
  onToggle: (card: string) => void;
}

export const CardSelector: React.FC<CardSelectorProps> = ({ selectedCards, onToggle }) => {
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-lg font-bold mb-4">Select Your Hand (2 Cards)</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SUITS_4COLOR.map((suit) => (
          <div key={suit.char} className="flex flex-col gap-2">
            <div className={`font-bold text-xl text-center ${suit.color}`}>{suit.label}</div>
            <div className="grid grid-cols-4 gap-2">
              {RANKS.map((rank) => {
                const cardStr = `${rank}${suit.char}`;
                const isSelected = selectedCards.includes(cardStr);
                const isDisabled = !isSelected && selectedCards.length >= 2;
                
                return (
                  <button
                    key={cardStr}
                    onClick={() => onToggle(cardStr)}
                    disabled={isDisabled}
                    className={`
                      h-10 w-full rounded border font-mono font-bold
                      ${suit.color}
                      ${isSelected ? 'bg-yellow-200 ring-2 ring-yellow-400' : 'bg-gray-50 hover:bg-gray-100'}
                      ${isDisabled ? 'opacity-30 cursor-not-allowed' : ''}
                    `}
                  >
                    {rank}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
