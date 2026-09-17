import urllib.request
import json
import time
import copy
import traceback

def run_bot(game_id, player_name, solve_func, base_url):
    print(f"[{player_name}] Joining game {game_id}...")
    
    # Helper to send a POST request with JSON
    def post_json(endpoint, payload):
        req = urllib.request.Request(
            f"{base_url}{endpoint}", 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            body = response.read()
            return json.loads(body.decode('utf-8')) if body else None

    # Helper to send a GET request
    def get_json(endpoint):
        req = urllib.request.Request(f"{base_url}{endpoint}")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))

    # 1. Join Game
    post_json("/api/game/join", {
        "game_id": game_id,
        "player_name": player_name,
        "client_type": "bot"
    })

    # 2. Wait for matrix
    matrix = None
    while True:
        try:
            res = get_json(f"/api/game/state?id={game_id}&v=0")
            if res and res.get('matrix'):
                matrix = res['matrix']
                break
        except Exception:
            pass # Ignore temporary network/parsing errors while polling
        time.sleep(0.5)
        
    print(f"[{player_name}] Matrix received! Calculating swaps...")

    # 3. User algorithm runs
    matrix_copy = copy.deepcopy(matrix)

    try:
        swaps = solve_func(matrix)

        # 4. Format payload (auto-filling val1 and val2)
        formatted_swaps = []
        for (r1, c1, r2, c2) in swaps:
            val1 = matrix_copy[r1][c1]
            val2 = matrix_copy[r2][c2]
            formatted_swaps.append({
                "x1": r1, "y1": c1, 
                "x2": r2, "y2": c2, 
                "val1": val1, "val2": val2
            })
            # Update local tracking matrix so sequential swap values are correct
            matrix_copy[r1][c1], matrix_copy[r2][c2] = val2, val1

        # 5. Submit
        post_json("/api/game/submit", {
            "game_id": game_id,
            "player_name": player_name,
            "swaps": formatted_swaps
        })
        print(f"[{player_name}] Submitted {len(swaps)} swaps successfully!")
    except Exception as e:
        post_json("/api/game/submit", {
            "game_id": game_id,
            "player_name": player_name,
            "error": traceback.format_exc(),
        })


# ==========================================
# USER CODE EXAMPLE
# ==========================================
def my_solver(matrix):
    swaps = []
    
    # Example logic: Swap the element at (0,0) with (0,1)
    swaps.append((0, 0, 0, 1)) 
    
    return swaps

if __name__ == "__main__":
    run_bot(
        game_id="MPLX8U",
        player_name="Emil",
        solve_func=my_solver,
        base_url="http://localhost:8080",
    )