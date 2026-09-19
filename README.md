# Hilltops

Server, web UI and bot clients for the Hilltops game. As of this writing, only the sample Python client has been tested.

Author: Emil Parikh

The server is plain Python with no dependencies (I used Python 3.10, but earlier might work).

## Getting Started
### Server
1. **Build the binary**: If it's your first time, head to `engine/` to build the C++ `hilltops_server` binary for your system.
```sh
# From the root of the project
cd engine/
make clean
make
```

2. **Start the server**

```sh
# From the root of the project
# 
# Note: If using using Windows Subsystem for Linux (WSL)
# to build the C++ hilltops_server binary, this server should
# also be started from WSL and not from a standard Windows
# terminal.
python3 server.py
```

The console will print the server's host:port.

### Creating a bot (for bot mode)
See the sample bots in `sample_bots/`. As of this writing,
Python, C++, C, and Julia are working. A "bot" file is realy just a function called `get_swaps` which takes a matrix and returns a list of swaps in the form of a 2D list of (r1, c1, r2, c2). In `bot_runner.py`, these functions are injected into wrappers that will call the functions.

To make sure your bot is recognized, add it to `bot_configs` in `bot_runner.py`.

```sh
bot_configs = [
    BotConfig(name="PythonBot", file_path="sample_bots/bot.py", language=Language.PYTHON),
    BotConfig(name="JuliaBot", file_path="sample_bots/bot.jl", language=Language.JULIA),
    BotConfig(name="CBot", file_path="sample_bots/bot.c", language=Language.C),
    BotConfig(name="CppBot", file_path="sample_bots/bot.cpp", language=Language.CPP),
]
```

**Note:** I was testing this out on crunchy5.cims.nyu.edu where all these languages are installed. When testing locally, you might want to comment out any bots for languages you don't have installed, though not strictly necessary since I gracefully handle + display the errors in the frontend.

**Note:** for Julia language and any other language with list indexing that is 1-based, you should return the swap indexes in the language's standard. The bot_runner will handle converting to 0-based index for Python.

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
1. After you've written your `get_swaps` function and added it to the list of `bot_configs` in `bot_runner.py`
```sh
# From the root of the project
# The script will loop through all of the bots, and for each it will
#  - join the game,
#  - retrieve the matrix from the server,
#  - submit the swaps.
# Note, if the url is http://localhost:33333/#BN72UN,
# the game id is BN72UN.
python3 bot_runner.py game_id
```
2. Wait for host to show results

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