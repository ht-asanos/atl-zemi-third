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
    <main className="min-h-screen py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="inline-block p-3 rounded-full bg-slate-800 text-white mb-2 shadow-lg">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 6.087c0-.355.186-.676.401-.959.221-.29.349-.634.349-1.003 0-1.036-1.007-1.875-2.25-1.875s-2.25.84-2.25 1.875c0 .369.128.713.349 1.003.215.283.401.604.401.959v0a.64.64 0 0 1-.657.643 48.39 48.39 0 0 1-4.163-.3c.186 1.613.293 3.25.315 4.907a.656.656 0 0 1-.658.663v0c-.355 0-.676-.186-.959-.401a1.647 1.647 0 0 0-1.003-.349c-1.036 0-1.875 1.007-1.875 2.25s.84 2.25 1.875 2.25c.369 0 .713-.128 1.003-.349.283-.215.604-.401.959-.401v0c.31 0 .555.26.532.57a48.039 48.039 0 0 1-.642 5.056c1.518.19 3.058.309 4.616.354a.64.64 0 0 0 .663-.658v0c0-.355-.186-.676-.401-.959a1.647 1.647 0 0 0-.349-1.003c0-1.035 1.008-1.875 2.25-1.875 1.243 0 2.25.84 2.25 1.875 0 .369-.128.713-.349 1.003-.215.283-.4.604-.4.959v0c0 .333.277.599.61.58a48.1 48.1 0 0 0 5.427-.63 48.05 48.05 0 0 0 .582-4.717.532.532 0 0 0-.533-.57v0c-.355 0-.676.186-.959.401-.29.221-.634.349-1.003.349-1.035 0-1.875-1.007-1.875-2.25s.84-2.25 1.875-2.25c.37 0 .713.128 1.003.349.283.215.604.401.959.401v0a.656.656 0 0 0 .658-.663 48.422 48.422 0 0 0-.37-5.36c-1.886.342-3.81.574-5.766.689a.578.578 0 0 1-.61-.58v0Z" />
            </svg>
          </div>
          <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">
            Texas Hold'em Analyzer
          </h1>
          <p className="max-w-2xl mx-auto text-lg text-slate-600">
            Professional-grade Monte Carlo simulation for pre-flop equity calculation.
          </p>
        </div>

        {/* Main Content Area */}
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-6 md:p-8 space-y-8">
          <CardSelector selectedCards={selectedCards} onToggle={handleCardToggle} />
          
          <div className="border-t border-slate-200 my-8"></div>

          <PlayerSettings
            numPlayers={numPlayers}
            setNumPlayers={setNumPlayers}
            numSimulations={numSimulations}
            setNumSimulations={setNumSimulations}
          />
          
          <div className="pt-4 flex justify-center">
            <button
              onClick={handleAnalyze}
              disabled={selectedCards.length !== 2 || loading}
              className={`
                group relative flex items-center justify-center px-10 py-4 border border-transparent text-lg font-bold rounded-full text-white shadow-lg transition-all duration-200
                ${selectedCards.length !== 2 || loading
                  ? 'bg-slate-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 hover:shadow-xl hover:-translate-y-0.5 active:scale-95'}
              `}
            >
              {loading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Processing Simulation...
                </>
              ) : (
                <>
                  Calculate Equity
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </div>

        <ResultView result={result} loading={loading} error={error} />
      </div>
    </main>
  );
}
