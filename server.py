import re
import sys
import os
import time
import json
import random
import socket
import string
import threading
import subprocess
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, quote, unquote

HOST = "0.0.0.0"
PORT = 8080
CPP_BINARY = "./engine/hilltops_server"
UNAMBIGUOUS_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

games_lock = threading.Lock()
games = {}

def recv_line_from_sock(s):
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(1)
        if not chunk:
            break
        buf += chunk
    return buf.decode("utf-8").strip()

def generate_game_key():
    while True:
        key = "".join(random.choices(UNAMBIGUOUS_CHARS, k=6))
        if key not in games:
            return key

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class GameSession:
    def __init__(self, game_id, matrix, timeout_seconds=3600, game_mode="human"):
        self.game_id = game_id
        self.matrix = matrix
        self.game_mode = game_mode  # "human" or "bot"
        self.rows = len(matrix)
        self.cols = len(matrix[0])
        self.timeout_seconds = timeout_seconds
        self.created_at = time.time()
        self.expired_at = self.created_at + timeout_seconds
        
        self.players = {}
        self.status = "active"
        self.leaderboard = {"ok": [], "not_ok": []}
        self.version = 0
        self.cond = threading.Condition()
        
        self.cpp_port = find_free_port()
        self.matrix_file = f"matrix_{self.game_id}.txt"
        self._write_matrix_file()
        
        self.proc = subprocess.Popen(
            [CPP_BINARY, str(self.cpp_port), self.matrix_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.1)

    def _write_matrix_file(self):
        with open(self.matrix_file, "w") as f:
            f.write(f"{self.rows} {self.cols}\n")
            for row in self.matrix:
                f.write(" ".join(map(str, row)) + "\n")

    def notify_change(self):
        with self.cond:
            self.version += 1
            self.cond.notify_all()

    def compute_evaluation_matrices(self, swaps):
        grid = [row[:] for row in self.matrix]
        for sw in swaps:
            x1, y1, x2, y2 = sw["x1"], sw["y1"], sw["x2"], sw["y2"]
            grid[x1][y1], grid[x2][y2] = grid[x2][y2], grid[x1][y1]

        R, C = self.rows, self.cols
        min_val = min(min(row) for row in grid)

        reachable = [[False] * C for _ in range(R)]
        queue = []
        for r in range(R):
            for c in range(C):
                if grid[r][c] == min_val:
                    reachable[r][c] = True
                    queue.append((r, c))

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while queue:
            r, c = queue.pop(0)
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < R and 0 <= nc < C:
                    if not reachable[nr][nc] and grid[nr][nc] >= grid[r][c]:
                        reachable[nr][nc] = True
                        queue.append((nr, nc))

        memo = {}
        def dfs_worst(r, c, visited):
            if not reachable[r][c]:
                return -1
            if grid[r][c] == min_val:
                return 0
            if (r, c) in memo:
                return memo[(r, c)]

            visited.add((r, c))
            max_sub = -1
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < R and 0 <= nc < C:
                    if grid[nr][nc] <= grid[r][c] and reachable[nr][nc] and (nr, nc) not in visited:
                        res = dfs_worst(nr, nc, visited)
                        if res != -1:
                            max_sub = max(max_sub, res)
            visited.remove((r, c))

            memo[(r, c)] = -1 if max_sub == -1 else max_sub + 1
            return memo[(r, c)]

        worst_dist = [[dfs_worst(r, c, set()) for c in range(C)] for r in range(R)]
        return reachable, worst_dist

    def submit_swaps_to_cpp(self, player_name, swaps):
        try:
            with socket.create_connection(("127.0.0.1", self.cpp_port), timeout=5) as s:
                greet = recv_line_from_sock(s)
                if not greet.startswith("CONNECTED"):
                    return {"ok": False, "swaps": -1, "max_worst": -1, "error": "Invalid greeting"}

                encoded_name = quote(player_name)
                s.sendall(f"PLAY {encoded_name}\n".encode())
                header = recv_line_from_sock(s)
                parts = header.split()
                if len(parts) != 2:
                    return {"ok": False, "swaps": -1, "max_worst": -1, "error": "Invalid matrix header"}
                R, C = int(parts[0]), int(parts[1])

                for _ in range(R):
                    recv_line_from_sock(s)

                token = recv_line_from_sock(s)
                if token != "SEND_SWAPS":
                    return {"ok": False, "swaps": -1, "max_worst": -1, "error": f"Expected SEND_SWAPS, got {token}"}

                s.sendall(f"{len(swaps)}\n".encode())
                for sw in swaps:
                    s.sendall(f"{sw['x1']} {sw['y1']} {sw['x2']} {sw['y2']}\n".encode())

                verdict = recv_line_from_sock(s)
                _ = recv_line_from_sock(s)

                if verdict.startswith("OK"):
                    vparts = verdict.split()
                    return {"ok": True, "swaps": int(vparts[1]), "max_worst": int(vparts[2])}
                else:
                    return {"ok": False, "swaps": -1, "max_worst": -1}
        except Exception as e:
            return {"ok": False, "swaps": -1, "max_worst": -1, "error": str(e)}

    def finalize_game(self):
        if self.status == "completed":
            return
        
        self.status = "completed"
        ok_list, not_ok_list = [], []
        recorded_players = set()

        try:
            with socket.create_connection(("127.0.0.1", self.cpp_port), timeout=5) as s:
                _ = recv_line_from_sock(s)
                s.sendall(b"RESULTS\n")
                
                parsing = False
                while True:
                    line = recv_line_from_sock(s)
                    if line == "RESULTS_BEGIN":
                        parsing = True
                        continue
                    if line == "END" or not line:
                        break
                    if not parsing:
                        continue

                    parts = line.split()
                    if not parts:
                        continue
                    pname = unquote(parts[0])
                    recorded_players.add(pname)

                    if len(parts) == 3:
                        ok_list.append({"name": pname, "swaps": int(parts[1]), "max_worst": int(parts[2])})
                    else:
                        not_ok_list.append({"name": pname, "swaps": -1})
        except Exception as e:
            print(f"Error getting results: {e}")

        for pname in self.players.keys():
            if pname not in recorded_players:
                not_ok_list.append({"name": pname, "swaps": -1})

        self.leaderboard = {"ok": ok_list, "not_ok": not_ok_list}
        self._cleanup()
        self.notify_change()

    def _cleanup(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        if os.path.exists(self.matrix_file):
            try: os.remove(self.matrix_file)
            except OSError: pass

class HilltopsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

    def _send_json(self, data, code=200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _parse_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/game/state":
            query = parse_qs(parsed.query)
            game_id = query.get("id", [None])[0]
            client_version = int(query.get("v", [0])[0])
            
            with games_lock:
                game = games.get(game_id)
            
            if not game:
                return self._send_json({"error": "Game not found"}, 404)

            with game.cond:
                # Auto-finalize game if timeout expired while active
                if time.time() > game.expired_at and game.status != "completed":
                    game.finalize_game()
                if game.version == client_version and game.status != "completed":
                    game.cond.wait(timeout=15)
                
                data = {
                    "game_id": game.game_id,
                    "matrix": game.matrix,
                    "status": game.status,
                    "game_mode": game.game_mode,
                    "version": game.version,
                    "players": game.players,
                    "leaderboard": game.leaderboard,
                    "expired": time.time() > game.expired_at
                }
                return self._send_json(data)

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._parse_body()

        if parsed.path == "/api/game/create":
            matrix = body.get("matrix")
            rows = body.get("rows")
            cols = body.get("cols")
            timeout = body.get("timeout", 3600)
            game_mode = body.get("game_mode", "human")

            if matrix is not None:
                if not isinstance(matrix, list) or len(matrix) == 0:
                    return self._send_json({"error": "Matrix must be a non-empty list of rows"}, 400)
                
                expected_cols = len(matrix[0]) if isinstance(matrix[0], list) else 0
                if expected_cols == 0:
                    return self._send_json({"error": "Matrix rows cannot be empty"}, 400)

                for row in matrix:
                    if not isinstance(row, list) or len(row) != expected_cols:
                        return self._send_json({"error": "Matrix invalid: All rows must have identical column counts"}, 400)
                    for val in row:
                        if isinstance(val, bool) or not isinstance(val, (int, float)):
                            return self._send_json({"error": "Matrix invalid: All values must be numeric"}, 400)

            else:
                if not rows or not cols or rows <= 0 or cols <= 0:
                    return self._send_json({"error": "Valid rows and cols dimensions required"}, 400)
                vals = list(range(1, rows * cols + 1))
                random.shuffle(vals)
                matrix = [vals[i * cols : (i + 1) * cols] for i in range(rows)]

            with games_lock:
                game_id = generate_game_key()
                game = GameSession(game_id, matrix, timeout, game_mode)
                games[game_id] = game

            return self._send_json({"game_id": game_id})

        elif parsed.path == "/api/game/join":
            game_id = body.get("game_id")
            player_name = body.get("player_name", "").strip()
            client_type = body.get("client_type", "human")

            if not player_name or not re.match(r"^[a-zA-Z0-9 ]{1,20}$", player_name):
                return self._send_json({"error": "Invalid name: Must be 1-20 alphanumeric characters (no spaces or symbols)"}, 400)

            with games_lock: game = games.get(game_id)
            if not game: return self._send_json({"error": "Game not found"}, 404)

            with game.cond:
                if player_name in game.players:
                    return self._send_json({"error": "Name already taken"}, 400)
                
                game.players[player_name] = {
                    "type": client_type,
                    "submitted": False,
                    "swaps": [],
                    "score": None,
                    "reachability_matrix": [],
                    "worst_distance_matrix": []
                }
                game.notify_change()
            return self._send_json({"ok": True})

        elif parsed.path == "/api/game/submit":
            game_id = body.get("game_id")
            player_name = body.get("player_name")
            swaps = body.get("swaps", [])
            client_error = body.get("error") # New: Allow bot scripts to report their own crashes

            with games_lock: game = games.get(game_id)
            if not game: return self._send_json({"error": "Game not found"}, 404)

            if time.time() > game.expired_at:
                return self._send_json({"error": "Game timeout expired"}, 408)

            with game.cond:
                player = game.players.get(player_name)
                if not player: return self._send_json({"error": "Player not in game"}, 400)
                if player["submitted"]: return self._send_json({"error": "Already submitted"}, 409)

                # Handle either a reported client error OR a server-side processing error
                if client_error:
                    player["submitted"] = True
                    player["error"] = str(client_error)
                    score = {"ok": False, "error": str(client_error)}
                else:
                    try:
                        score = game.submit_swaps_to_cpp(player_name, swaps)
                        if score.get("error"):
                            raise Exception(score["error"])
                        
                        reachability, worst_dist = game.compute_evaluation_matrices(swaps)

                        player["submitted"] = True
                        player["swaps"] = swaps
                        player["score"] = score
                        player["reachability_matrix"] = reachability
                        player["worst_distance_matrix"] = worst_dist
                    except Exception as e:
                        player["submitted"] = True
                        player["error"] = f"Evaluation failed: {str(e)}"
                        score = {"ok": False, "error": str(e)}

                # (Keep the fix we made earlier here!)
                if game.game_mode != "bot" and all(p["submitted"] for p in game.players.values()):
                    game.finalize_game()
                else:
                    game.notify_change()

            return self._send_json({"ok": True, "score": score})

        elif parsed.path == "/api/game/end":
            game_id = body.get("game_id")
            with games_lock: game = games.get(game_id)
            if not game: return self._send_json({"error": "Game not found"}, 404)

            game.finalize_game()
            return self._send_json({"ok": True})

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), HilltopsHandler)
    print(f"Hilltops Web Server running on http://{get_local_ip()}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()