import json
import os
from datetime import datetime

POS_FILE = os.path.join(os.path.dirname(__file__), 'positions.json')

def load_positions():
    if not os.path.exists(POS_FILE):
        return []
    with open(POS_FILE, 'r') as f:
        return json.load(f)

def save_positions(positions):
    with open(POS_FILE, 'w') as f:
        json.dump(positions, f, indent=2)

def add_position(symbol: str, price: float):
    positions = load_positions()
    positions.append({
        "symbol": symbol,
        "entry_price": price,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_positions(positions)
