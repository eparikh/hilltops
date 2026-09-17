# Hilltops

Server, web UI and bot clients for the Hilltops game. As of this writing, only the sample Python client has been tested.

Author: Emil Parikh

The server is plain Python with no dependencies (I used Python 3.10, but earlier might work).

## Getting Started
### Server (only if others are connecting to you)
1. **Build the binary**: If it's your first time, head to `/engine` to build the C++ `hilltops_server` binary for your system.
```sh
# From the root of the project
cd engine
make clean
make
```

2. **Start the server**

```sh
# From the root of the project
python3 server.py
```

The console will print the server's host:port that others on the same network can connect to.

### Creating a client (for bot mode)
1. See the sample clients in `sample_clients`. Only Python is tested as of this writing. If your language of choice is there, open it, update the params, and run it.
2. If you want another language, ask your AI model of choice to create it based on one of those samples, or create your own by hand following the structure of the sample clients

#### Structure of sample clients
In the client, you need to write your solver function
* Param matrix: 2D list of ints
* Returns swaps: A list of 4-tuples (r1, c1, r2, c2) where (r1, c1) and (r2, c2) are the coordinates in the matrix of the numbers being swapped.

**Caution**: If your language list indexes start with 1, confirm that matrix copy and the swaps display as expected. ***Actually, maybe that would be better as a TODO for me to take a "0 or 1 based index" param on submit so I can subtract 1 from swap indexes instead of forcing the user to track that.***

1. Join the game
```sh
POST /api/game/join
{
    "game_id": game_id,
    "player_name": player_name,
    "client_type": "bot"
}
```

2. Get the game state to get the matrix
```sh
GET /api/game/state?id={game_id}&v=0
{
    "game_id": game_id,
    "player_name": player_name,
    "client_type": "bot"
}
```

3. Deep copy the matrix so that you still have the original state

4. Run your solver function (takes a matrix, returns swaps) and save to a variable

5. Format the swaps and submit
```sh
POST /api/game/submit
{
    "game_id": game_id,
    "player_name": player_name,
    "swaps": [
        {
            "x1": r1, "y1": c1, 
            "x2": r2, "y2": c2, 
            "val1": val1, "val2": val2
        },
        ...,
        ...,
    ]
}
```

Steps 4-6 should be wrapped in exception handling, and in the exception block, you should still submit; however, instead of submitting swaps, submit the error message to whatever level of detail you'd like. Anything from the stack trace to a generic error message. e.g.,

```sh
POST /api/game/submit
{
    "game_id": game_id,
    "player_name": player_name,
    "error": traceback.format_exc(),
}
```

## The Game
### Create a new game
1. Choose mode: Human or Bot
2. Enter a custom matrix or generate a random one

```sh
# Custom matrix formats
[[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# OR

1 2 3
4 5 6
7 8 9
```

3. Click button to create game. This will generate a new game url that can be joied by others in the same network.

### Human Mode
1. Visit the game url
2. Enter your name and join
3. Swap numbers, undo, reset
4. Submit
5. Wait for host to show results


### Bot Mode
1. In your client, set the game_id, player_name, solve_func, and base_url.
2. Run your client (on run, the client should join the game, calculate swaps, and submit)
3. Wait for host to show results

## Results
Once the host shows the results, there will be a leaderborard showed in the left panel.

* **Hilltop complete**: Users displayed in descending order by number of swaps and max distance from target
* **Incomplete**: Users who did not achieve hilltop complete
* **No submission**: Users whose code never submitted, perhaps long-running code.

Anyone can view the results of a user by clicking their name on the leaderboard. You can see:
* Their swaps
* Which cells, if any, cannot reach the target
* The max distances of each cell to the target
* The stack trace if there was an error on submission