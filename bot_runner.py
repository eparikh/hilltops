import sys
import subprocess
import tempfile
import os
import urllib.request
import json
import time
import copy
import traceback
from multiprocessing import Pool

PYTHON_WRAPPER = """
# --- USER CODE BEGINS ---
{USER_CODE}
# --- USER CODE ENDS ---

import sys
def __hidden_wrapper_main():
    input_data = sys.stdin.read().split()
    if not input_data: return
    R, C = int(input_data[0]), int(input_data[1])
    idx = 2
    matrix = [[int(input_data[idx + r*C + c]) for c in range(C)] for r in range(R)]
    
    swaps = get_swaps(matrix)
    print(len(swaps))
    for s in swaps: print(f"{s[0]} {s[1]} {s[2]} {s[3]}")

if __name__ == '__main__':
    __hidden_wrapper_main()
"""

CPP_WRAPPER = """
// --- USER CODE BEGINS ---
{USER_CODE}
// --- USER CODE ENDS ---

#include <iostream>
#include <vector>

int main() {
    int R, C;
    if (!(std::cin >> R >> C)) return 0;
    std::vector<std::vector<int>> matrix(R, std::vector<int>(C));
    for (int r = 0; r < R; ++r) {
        for (int c = 0; c < C; ++c) {
            std::cin >> matrix[r][c];
        }
    }
    
    std::vector<std::vector<int>> swaps = get_swaps(matrix);
    std::cout << swaps.size() << "\\n";
    for (const auto& s : swaps) {
        std::cout << s[0] << " " << s[1] << " " << s[2] << " " << s[3] << "\\n";
    }
    return 0;
}
"""

C_WRAPPER = """
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int r1, c1, r2, c2;
} Swap;

// --- USER CODE BEGINS ---
{USER_CODE}
// --- USER CODE ENDS ---

int main() {
    int R, C;
    if (scanf("%d %d", &R, &C) != 2) return 0;
    
    int** matrix = (int**)malloc(R * sizeof(int*));
    for (int r = 0; r < R; ++r) {
        matrix[r] = (int*)malloc(C * sizeof(int));
        for (int c = 0; c < C; ++c) scanf("%d", &matrix[r][c]);
    }
    
    int num_swaps = 0;
    Swap* swaps = get_swaps(matrix, R, C, &num_swaps);
    
    printf("%d\\n", num_swaps);
    if (swaps != NULL) {
        for (int i = 0; i < num_swaps; ++i) {
            printf("%d %d %d %d\\n", swaps[i].r1, swaps[i].c1, swaps[i].r2, swaps[i].c2);
        }
        free(swaps);
    }
    
    for (int r = 0; r < R; ++r) free(matrix[r]);
    free(matrix);
    return 0;
}
"""

JULIA_WRAPPER = """
# --- USER CODE BEGINS ---
{USER_CODE}
# --- USER CODE ENDS ---

function __hidden_wrapper_main()
    input_data = split(read(stdin, String))
    if isempty(input_data) return end
    R = parse(Int, input_data[1])
    C = parse(Int, input_data[2])
    idx = 3
    matrix = Array{Int}(undef, R, C)
    for r in 1:R
        for c in 1:C
            matrix[r, c] = parse(Int, input_data[idx])
            idx += 1
        end
    end
    
    swaps = get_swaps(matrix)
    println(length(swaps))
    for s in swaps println("$(s[1]-1) $(s[2]-1) $(s[3]-1) $(s[4]-1)") end
end

__hidden_wrapper_main()
"""

class Language:
    PYTHON = "python"
    CPP = "cpp"
    C = "c"
    JULIA = "julia"

class BotConfig:
    def __init__(self, name, file_path, language):
        self.name = name
        self.file_path = file_path
        self.language = language

class Bot:
    def __init__(self, timeout=5.0):
        self.timeout = timeout

    def _matrix_to_stdin(self, matrix):
        R, C = len(matrix), len(matrix[0])
        parts = [f"{R} {C}"]
        for row in matrix:
            parts.extend(map(str, row))
        return " ".join(parts) + "\n"

    def _parse_stdout_to_swaps(self, stdout, matrix):
        lines = stdout.strip().split('\n')
        if not lines or not lines[0].strip():
            return []
        
        try:
            num_swaps = int(lines[0].strip())
            # swaps = []
            # for i in range(1, num_swaps + 1):
            #     r1, c1, r2, c2 = map(int, lines[i].split())
            #     val1 = matrix[r1][c1]
            #     val2 = matrix[r2][c2]
            #     swaps.append({
            #         "x1": r1, "y1": c1, "x2": r2, "y2": c2,
            #         "val1": val1, "val2": val2
            #     })
            # return swaps
            return [map(int, lines[i].split()) for i in range(1, num_swaps + 1)]
        except Exception as e:
            raise ValueError(f"Failed to parse bot output: {e}\nOutput was: {stdout}")

    def get_swaps(self, config: BotConfig, matrix):
        with open(config.file_path, 'r') as f:
            user_code = f.read()

        stdin_data = self._matrix_to_stdin(matrix)

        with tempfile.TemporaryDirectory() as tmpdir:
            if config.language == Language.PYTHON:
                code = PYTHON_WRAPPER.replace("{USER_CODE}", user_code)
                script_path = os.path.join(tmpdir, "wrapper.py")
                with open(script_path, "w") as f: f.write(code)
                cmd = ["python3", script_path]

            elif config.language == Language.CPP:
                code = CPP_WRAPPER.replace("{USER_CODE}", user_code)
                src_path = os.path.join(tmpdir, "wrapper.cpp")
                exe_path = os.path.join(tmpdir, "wrapper_exec")
                with open(src_path, "w") as f: f.write(code)
                
                comp = subprocess.run(["g++", src_path, "-o", exe_path, "-O3"], capture_output=True, text=True)
                if comp.returncode != 0:
                    raise Exception(f"C++ Compilation Failed:\n{comp.stderr}")
                cmd = [exe_path]

            elif config.language == Language.C:
                code = C_WRAPPER.replace("{USER_CODE}", user_code)
                src_path = os.path.join(tmpdir, "wrapper.c")
                exe_path = os.path.join(tmpdir, "wrapper_exec")
                with open(src_path, "w") as f: f.write(code)
                
                comp = subprocess.run(["gcc", src_path, "-o", exe_path, "-O3"], capture_output=True, text=True)
                if comp.returncode != 0:
                    raise Exception(f"C Compilation Failed:\n{comp.stderr}")
                cmd = [exe_path]

            elif config.language == Language.JULIA:
                code = JULIA_WRAPPER.replace("{USER_CODE}", user_code)
                script_path = os.path.join(tmpdir, "wrapper.jl")
                with open(script_path, "w") as f: f.write(code)
                cmd = ["julia", script_path]
            
            else:
                raise ValueError(f"Unsupported language: {config.language}")

            try:
                proc = subprocess.run(cmd, input=stdin_data, text=True, capture_output=True, timeout=self.timeout)
                if proc.returncode != 0:
                    raise Exception(f"Runtime Error:\n{proc.stderr}")
                
                return self._parse_stdout_to_swaps(proc.stdout, matrix)
            
            except subprocess.TimeoutExpired:
                raise Exception(f"Execution exceeded the {self.timeout} second timeout limit.")


def run_bot(game_id: str, base_url: str, bot: Bot, config: BotConfig):
    print(f"[{config.name}] Joining game {game_id}...")
    
    # Helper to send a POST request with JSON
    def post_json(endpoint, payload):
        req = urllib.request.Request(
            f"{base_url}{endpoint}", 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            print(f"\nSERVER ERROR MESSAGE: {e.read().decode()}\n") # This is the golden ticket
            raise

    # Helper to send a GET request
    def get_json(endpoint):
        req = urllib.request.Request(f"{base_url}{endpoint}")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))

    # 1. Join Game
    post_json("/api/game/join", {
        "game_id": game_id,
        "player_name": config.name,
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
        
    print(f"[{config.name}] Matrix received! Calculating swaps...")

    # 3. User algorithm runs
    matrix_copy = copy.deepcopy(matrix)

    try:
        swaps = bot.get_swaps(config, matrix)

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
            "player_name": config.name,
            "swaps": formatted_swaps
        })
        print(f"[{config.name}] Submitted {len(swaps)} swaps successfully!")
    except Exception as e:
        post_json("/api/game/submit", {
            "game_id": game_id,
            "player_name": config.name,
            "error": traceback.format_exc(),
        })

bot_configs = [
    BotConfig(name="PythonBot", file_path="sample_bots/bot.py", language=Language.PYTHON),
    BotConfig(name="JuliaBot", file_path="sample_bots/bot.jl", language=Language.JULIA),
    BotConfig(name="CBot", file_path="sample_bots/bot.c", language=Language.C),
    BotConfig(name="CppBot", file_path="sample_bots/bot.cpp", language=Language.CPP),
]

if __name__ == "__main__":
    # Ensure the user provided the argument to prevent an IndexError
    if len(sys.argv) > 1:
        game_id = sys.argv[1]
        base_url = "http://localhost:33333"
        bot = Bot()

        with Pool() as pool:
            pool.starmap(run_bot, [(game_id, base_url, bot, config) for config in bot_configs])

    else:
        print("Please provide a name. Usage: python3 bot_runner.py [game_id]")
