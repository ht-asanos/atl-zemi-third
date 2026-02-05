'use client';

import React, { useState } from 'react';
import { CardSelector } from '../components/CardSelector';
import { PlayerSettings } from '../components/PlayerSettings';
import { ResultView } from '../components/ResultView';
import { analyzeHand, AnalyzeResponse } from '../utils/api';

export default function Home() {
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [numPlayers, setNumPlayers] = useState<number>(6);
  const [numSimulations, setNumSimulations] = useState<number>(10000);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleCardToggle = (card: string) => {
    setSelectedCards((prev) => {
      if (prev.includes(card)) {
        return prev.filter((c) => c !== card);
      }
      if (prev.length >= 2) {
        return prev;
      }
      return [...prev, card];
    });
  };

  const handleAnalyze = async () => {
    if (selectedCards.length !== 2) {
      setError('Please select exactly 2 cards.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await analyzeHand({
        my_cards: selectedCards,
        num_players: numPlayers,
        num_simulations: numSimulations,
      });
      setResult(res);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An error occurred during simulation.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-extrabold text-gray-900">
            Texas Holdem Pre-flop Analyzer
          </h1>
          <p className="mt-2 text-gray-600">
            Calculate your odds and hand potential with Monte Carlo simulation.
          </p>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-lg">
          <CardSelector selectedCards={selectedCards} onToggle={handleCardToggle} />
          
          <PlayerSettings
            numPlayers={numPlayers}
            setNumPlayers={setNumPlayers}
            numSimulations={numSimulations}
            setNumSimulations={setNumSimulations}
          />
          
          <div className="mt-6 flex justify-center">
            <button
              onClick={handleAnalyze}
              disabled={selectedCards.length !== 2 || loading}
              className={`
                px-8 py-3 rounded-full font-bold text-white text-lg shadow-md transition-all
                ${selectedCards.length !== 2 || loading
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 hover:shadow-lg active:scale-95'}
              `}
            >
              {loading ? 'Analyzing...' : 'Calculate Odds'}
            </button>
          </div>
        </div>

        <ResultView result={result} loading={loading} error={error} />
      </div>
    </main>
  );
}
