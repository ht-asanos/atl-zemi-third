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
    <div className="p-4 bg-white rounded-lg shadow mt-4">
      <h2 className="text-lg font-bold mb-4">Settings</h2>
      
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Number of Players: <span className="font-bold">{numPlayers}</span>
        </label>
        <input
          type="range"
          min="2"
          max="10"
          value={numPlayers}
          onChange={(e) => setNumPlayers(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>2 (Heads-up)</span>
          <span>10 (Full Ring)</span>
        </div>
      </div>

      <div className="mb-2">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Simulations: <span className="font-bold">{numSimulations.toLocaleString()}</span>
        </label>
        <select
          value={numSimulations}
          onChange={(e) => setNumSimulations(parseInt(e.target.value))}
          className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="1000">1,000 (Fast)</option>
          <option value="10000">10,000 (Normal)</option>
          <option value="50000">50,000 (Accurate)</option>
          <option value="100000">100,000 (Max)</option>
        </select>
      </div>
    </div>
  );
};
