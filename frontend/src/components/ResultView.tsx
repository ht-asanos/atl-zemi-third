import React from 'react';
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

export const ResultView: React.FC<ResultViewProps> = ({ result, loading, error }) => {
  if (loading) {
    return (
      <div className="p-8 bg-white rounded-lg shadow mt-4 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-600">Calculating probabilities via Monte Carlo simulation...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg mt-4 text-red-700">
        Error: {error}
      </div>
    );
  }

  if (!result) {
    return null;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow mt-4 space-y-6">
      <h2 className="text-xl font-bold border-b pb-2">Analysis Result</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Win/Loss Rates */}
        <div>
          <h3 className="font-semibold text-gray-700 mb-2">Outcome Probabilities</h3>
          <div className="space-y-3">
            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-green-600 bg-green-200">
                    Win (Single Best)
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block text-green-600">
                    {result.win_rate}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-green-100">
                <div style={{ width: `${result.win_rate}%` }} className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-green-500"></div>
              </div>
            </div>

            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-yellow-600 bg-yellow-200">
                    Tie (Split Pot)
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block text-yellow-600">
                    {result.tie_rate}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-yellow-100">
                <div style={{ width: `${result.tie_rate}%` }} className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-yellow-500"></div>
              </div>
            </div>

            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-red-600 bg-red-200">
                    Loss (Beaten)
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block text-red-600">
                    {result.loss_rate}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-red-100">
                <div style={{ width: `${result.loss_rate}%` }} className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-red-500"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Hand Potentials */}
        <div>
          <h3 className="font-semibold text-gray-700 mb-2">My Top 3 Likely Hands</h3>
          <ul className="space-y-2">
            {result.hand_potential.map((hand, idx) => (
              <li key={idx} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                <span className="font-medium">{RANK_NAME_MAP[hand.rank_name] || hand.rank_name}</span>
                <span className="font-bold text-blue-600">{hand.probability}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      
      <div className="text-xs text-gray-400 text-right mt-4">
        Simulated {result.execution_count.toLocaleString()} times
      </div>
    </div>
  );
};
