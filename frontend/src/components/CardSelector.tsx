import React from 'react';
import { Card } from './ui/Card';

const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'];

const SUITS_INFO = [
  { char: 's', label: 'Spades', color: 'text-black', displayColor: 'Black' },
  { char: 'h', label: 'Hearts', color: 'text-red-600', displayColor: 'Red' },
  { char: 'd', label: 'Diamonds', color: 'text-blue-600', displayColor: 'Blue' },
  { char: 'c', label: 'Clubs', color: 'text-green-600', displayColor: 'Green' }
] as const;

interface CardSelectorProps {
  selectedCards: string[];
  onToggle: (card: string) => void;
}

export const CardSelector: React.FC<CardSelectorProps> = ({ selectedCards, onToggle }) => {
  return (
    <div className="p-6 bg-white rounded-xl shadow-xl border border-slate-200">
      <div className="flex flex-col sm:flex-row justify-between items-center mb-6">
        <h2 className="text-xl font-bold text-slate-800">Select Your Hand</h2>
        <span className="text-sm font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
          {selectedCards.length}/2 Cards Selected
        </span>
      </div>
      
      <div className="space-y-6">
        {SUITS_INFO.map((suit) => (
          <div key={suit.char} className="flex flex-col gap-2">
            {/* Suit Header / Legend */}
            <div className={`flex items-center gap-2 font-bold text-sm uppercase tracking-wider ${suit.color} border-b border-slate-100 pb-1`}>
              <span className="text-lg">{
                suit.char === 's' ? '♠' : 
                suit.char === 'h' ? '♥' : 
                suit.char === 'd' ? '♦' : '♣'
              }</span>
              <span>{suit.label}</span>
              <span className="text-xs opacity-60 font-normal normal-case ml-auto">({suit.displayColor})</span>
            </div>

            {/* Cards Grid */}
            <div className="flex flex-wrap gap-2 sm:gap-3 justify-start">
              {RANKS.map((rank) => {
                const cardStr = `${rank}${suit.char}`;
                const isSelected = selectedCards.includes(cardStr);
                const isDisabled = !isSelected && selectedCards.length >= 2;
                
                return (
                  <Card
                    key={cardStr}
                    rank={rank}
                    suit={suit.char as 's' | 'h' | 'd' | 'c'}
                    isSelected={isSelected}
                    isDisabled={isDisabled}
                    onClick={() => onToggle(cardStr)}
                    size="md"
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
