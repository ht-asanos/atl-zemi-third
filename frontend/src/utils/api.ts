export interface AnalyzeRequest {
  my_cards: string[];
  num_players: number;
  num_simulations: number;
}

export interface HandPotential {
  rank_name: string;
  probability: number;
}

export interface AnalyzeResponse {
  hand_potential: HandPotential[];
  win_rate: number;
  tie_rate: number;
  loss_rate: number;
  execution_count: number;
}

const API_BASE_URL = 'http://localhost:8000/api';

export const analyzeHand = async (req: AnalyzeRequest): Promise<AnalyzeResponse> => {
  const res = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || 'API request failed');
  }
  
  return res.json();
};
