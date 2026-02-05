import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .poker_logic import run_simulation_task
except ImportError:
    from poker_logic import run_simulation_task

# Request/Response Models
class AnalyzeRequest(BaseModel):
    my_cards: List[str] = Field(..., min_length=2, max_length=2, description="List of 2 card strings (e.g. ['Ah', 'Kd'])")
    num_players: int = Field(..., ge=2, le=10, description="Total number of players including yourself")
    num_simulations: int = Field(10000, ge=1, description="Number of Monte Carlo simulations")

class HandPotential(BaseModel):
    rank_name: str
    probability: float

class AnalyzeResponse(BaseModel):
    hand_potential: List[HandPotential]
    win_rate: float
    tie_rate: float
    loss_rate: float
    execution_count: int

# Global ProcessPoolExecutor
executor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global executor
    # Create executor on startup
    executor = ProcessPoolExecutor()
    yield
    # Shutdown executor on shutdown
    if executor:
        executor.shutdown()

app = FastAPI(lifespan=lifespan)

# CORS Configuration
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_hand(request: AnalyzeRequest):
    # Clamp num_simulations to 100,000
    simulations = min(request.num_simulations, 100000)
    
    # Run simulation in a separate process to avoid blocking event loop and allow timeout
    loop = asyncio.get_running_loop()
    
    try:
        # Use asyncio.wait_for to handle timeout
        if executor is None:
             raise HTTPException(status_code=500, detail="Executor not initialized")

        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor, 
                run_simulation_task, 
                request.my_cards, 
                request.num_players, 
                simulations
            ),
            timeout=10.0
        )
        return result
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Simulation timed out (limit: 10 seconds)"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {str(e)}"
        )
