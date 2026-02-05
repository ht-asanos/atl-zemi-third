import React from 'react';

export interface CardProps {
  rank: string;
  suit: 's' | 'h' | 'd' | 'c';
  isSelected?: boolean;
  isDisabled?: boolean;
  onClick?: () => void;
  size?: 'sm' | 'md' | 'lg';
}

const SUIT_CONFIG = {
  s: { symbol: '♠', color: 'text-black', label: 'Spades' },
  h: { symbol: '♥', color: 'text-red-600', label: 'Hearts' },
  d: { symbol: '♦', color: 'text-blue-600', label: 'Diamonds' },
  c: { symbol: '♣', color: 'text-green-600', label: 'Clubs' },
};

export const Card: React.FC<CardProps> = ({
  rank,
  suit,
  isSelected = false,
  isDisabled = false,
  onClick,
  size = 'md',
}) => {
  const config = SUIT_CONFIG[suit];

  // Size definitions
  const sizeClasses = {
    sm: 'w-10 h-14 text-xs',
    md: 'w-14 h-20 text-sm sm:w-16 sm:h-24 sm:text-base', // Responsive: larger on sm+ screens
    lg: 'w-20 h-28 text-lg',
  };

  const baseClasses = `
    relative flex flex-col justify-between p-1 rounded-lg border shadow-sm
    select-none transition-all duration-200
    bg-white
    font-mono font-bold
  `;

  const stateClasses = isDisabled
    ? 'opacity-40 cursor-not-allowed bg-gray-100'
    : isSelected
      ? 'ring-2 ring-yellow-400 -translate-y-1 shadow-md cursor-pointer'
      : 'hover:-translate-y-0.5 hover:shadow-md cursor-pointer border-gray-200';

  return (
    <button
      type="button"
      onClick={!isDisabled ? onClick : undefined}
      disabled={isDisabled}
      className={`
        ${baseClasses}
        ${sizeClasses[size]}
        ${config.color}
        ${stateClasses}
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
      `}
      aria-label={`${rank} of ${config.label}`}
    >
      {/* Top Left Rank/Suit */}
      <div className="flex flex-col leading-none items-center">
        <span>{rank}</span>
        <span className="text-[0.8em]">{config.symbol}</span>
      </div>

      {/* Center Suit (Only visible on md/lg) */}
      {size !== 'sm' && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
          <span className="text-4xl">{config.symbol}</span>
        </div>
      )}

      {/* Bottom Right Rank/Suit (Rotated) */}
      <div className="flex flex-col leading-none items-center rotate-180">
        <span>{rank}</span>
        <span className="text-[0.8em]">{config.symbol}</span>
      </div>
    </button>
  );
};
