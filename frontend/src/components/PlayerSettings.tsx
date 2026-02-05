import React from 'react';

interface PlayerSettingsProps {
  numPlayers: number;
  setNumPlayers: (n: number) => void;
  numSimulations: number;
  setNumSimulations: (n: number) => void;
}

export const PlayerSettings: React.FC<PlayerSettingsProps> = ({
  numPlayers,
  setNumPlayers,
  numSimulations,
  setNumSimulations,
}) => {
  return (
    <div className="p-6 bg-white rounded-xl shadow-xl border border-slate-200">
      <h2 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6 text-slate-500">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
        </svg>
        Simulation Settings
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Number of Players */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-3">
            Number of Players: <span className="text-blue-600 font-bold text-lg">{numPlayers}</span>
          </label>
          <div className="relative pt-1">
            <input
              type="range"
              min="2"
              max="10"
              value={numPlayers}
              onChange={(e) => setNumPlayers(parseInt(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
            />
            <div className="flex justify-between text-xs font-medium text-slate-400 mt-2">
              <span>2 (Heads-up)</span>
              <span>6 (6-Max)</span>
              <span>10 (Full Ring)</span>
            </div>
          </div>
        </div>

        {/* Number of Simulations */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-3">
            Simulations Accuracy
          </label>
          <div className="relative">
            <select
              value={numSimulations}
              onChange={(e) => setNumSimulations(parseInt(e.target.value))}
              className="block w-full px-4 py-3 pr-8 bg-slate-50 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-700 font-medium appearance-none transition-all hover:bg-slate-100"
            >
              <option value="1000">1,000 (Fastest / Rough Estimate)</option>
              <option value="10000">10,000 (Standard / Good for Preflop)</option>
              <option value="50000">50,000 (High Precision)</option>
              <option value="100000">100,000 (Maximum Accuracy)</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
              <svg className="h-4 w-4 fill-current" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
              </svg>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Higher simulations take longer but produce more stable results.
          </p>
        </div>
      </div>
    </div>
  );
};
