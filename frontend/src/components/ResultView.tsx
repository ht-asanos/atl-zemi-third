import React, { useEffect, useState } from 'react';
import { AnalyzeResponse } from '../utils/api';

interface ResultViewProps {
  result: AnalyzeResponse | null;
  loading: boolean;
  error: string | null;
}

const RANK_NAME_MAP: Record<string, string> = {
  "Straight Flush": "ストレートフラッシュ",
  "Four of a Kind": "フォーカード",
  "Full House": "フルハウス",
  "Flush": "フラッシュ",
  "Straight": "ストレート",
  "Three of a Kind": "スリーカード",
  "Two Pair": "ツーペア",
  "Pair": "ワンペア",
  "High Card": "ハイカード",
  "Royal Flush": "ロイヤルフラッシュ"
};

const ProgressBar: React.FC<{ value: number; colorClass: string }> = ({ value, colorClass }) => {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    // Small delay to trigger animation after mount
    const timer = setTimeout(() => {
      setWidth(value);
    }, 100);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="overflow-hidden h-3 mb-2 text-xs flex rounded-full bg-slate-200">
      <div
        style={{ width: `${width}%` }}
        className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-1000 ease-out ${colorClass}`}
      ></div>
    </div>
  );
};

export const ResultView: React.FC<ResultViewProps> = ({ result, loading, error }) => {
  if (loading) {
    return (
      <div className="p-12 bg-white/80 rounded-xl shadow-lg border border-slate-200 mt-8 text-center backdrop-blur-sm">
        <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-6"></div>
        <p className="text-xl font-medium text-slate-700 animate-pulse">
          Calculating probabilities...
        </p>
        <p className="text-sm text-slate-500 mt-2">Running Monte Carlo simulation</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl mt-8 flex items-start gap-4 shadow-sm">
        <div className="text-red-500 bg-red-100 p-2 rounded-full">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-bold text-red-800">Simulation Error</h3>
          <p className="text-red-700 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return null;
  }

  return (
    <div className="space-y-6 mt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="p-6 bg-white rounded-xl shadow-xl border border-slate-200">
        <div className="flex justify-between items-center border-b border-slate-100 pb-4 mb-6">
          <h2 className="text-2xl font-bold text-slate-800">Analysis Result</h2>
          <span className="text-xs font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded">
            {result.execution_count.toLocaleString()} sims
          </span>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* Win/Loss Rates */}
          <div>
            <h3 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
              <span className="w-2 h-6 bg-blue-500 rounded-full"></span>
              Outcome Probabilities
            </h3>
            <div className="space-y-6">
              {/* WIN */}
              <div>
                <div className="flex mb-2 items-center justify-between">
                  <span className="text-sm font-bold uppercase text-slate-600">
                    Win
                  </span>
                  <span className="text-lg font-bold text-green-600">
                    {result.win_rate}%
                  </span>
                </div>
                <ProgressBar value={result.win_rate} colorClass="bg-green-500" />
              </div>

              {/* TIE */}
              <div>
                <div className="flex mb-2 items-center justify-between">
                  <span className="text-sm font-bold uppercase text-slate-600">
                    Tie
                  </span>
                  <span className="text-lg font-bold text-yellow-600">
                    {result.tie_rate}%
                  </span>
                </div>
                <ProgressBar value={result.tie_rate} colorClass="bg-yellow-500" />
              </div>

              {/* LOSS */}
              <div>
                <div className="flex mb-2 items-center justify-between">
                  <span className="text-sm font-bold uppercase text-slate-600">
                    Loss
                  </span>
                  <span className="text-lg font-bold text-red-600">
                    {result.loss_rate}%
                  </span>
                </div>
                <ProgressBar value={result.loss_rate} colorClass="bg-red-500" />
              </div>
            </div>
          </div>

          {/* Hand Potentials */}
          <div>
            <h3 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
              <span className="w-2 h-6 bg-purple-500 rounded-full"></span>
              Top 3 Likely Hands
            </h3>
            <div className="space-y-3">
              {result.hand_potential.map((hand, idx) => (
                <div 
                  key={idx} 
                  className="flex justify-between items-center p-4 bg-slate-50 rounded-lg border border-slate-100 hover:border-blue-200 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className={`
                      flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold
                      ${idx === 0 ? 'bg-yellow-100 text-yellow-700' : 
                        idx === 1 ? 'bg-slate-200 text-slate-600' : 
                        'bg-orange-100 text-orange-700'}
                    `}>
                      #{idx + 1}
                    </span>
                    <span className="font-semibold text-slate-800">
                      {RANK_NAME_MAP[hand.rank_name] || hand.rank_name}
                    </span>
                  </div>
                  <span className="font-bold text-blue-600 text-lg">
                    {hand.probability}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
