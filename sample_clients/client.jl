using HTTP
using JSON

struct Swap
    r1::Int
    c1::Int
    r2::Int
    c2::Int
end

function run_bot(game_id::String, player_name::String, solve_func::Function, base_url::String="http://localhost:8080")
    println("[$player_name] Joining game $game_id...")

    # 1. Join Game
    HTTP.post("$base_url/api/game/join", 
        ["Content-Type" => "application/json"],
        JSON.json(Dict("game_id" => game_id, "player_name" => player_name, "client_type" => "bot"))
    )

    # 2. Wait for matrix
    matrix = nothing
    while isnothing(matrix)
        try
            res = HTTP.get("$base_url/api/game/state?id=$game_id&v=0")
            data = JSON.parse(String(res.body))
            if haskey(data, "matrix") && !isnothing(data["matrix"])
                matrix = data["matrix"]
                break
            end
        catch
            # Ignore temporary network errors
        end
        sleep(0.5)
    end

    println("[$player_name] Matrix received! Calculating swaps...")

    matrix_copy = deepcopy(matrix)

    try
        swaps = solve_func(matrix)

        formatted_swaps = []
        for s in swaps
            # Julia uses 1-based array indexing internally (+1 offset)
            val1 = matrix_copy[s.r1 + 1][s.c1 + 1]
            val2 = matrix_copy[s.r2 + 1][s.c2 + 1]

            push!(formatted_swaps, Dict(
                "x1" => s.r1, "y1" => s.c1,
                "x2" => s.r2, "y2" => s.c2,
                "val1" => val1, "val2" => val2
            ))

            matrix_copy[s.r1 + 1][s.c1 + 1] = val2
            matrix_copy[s.r2 + 1][s.c2 + 1] = val1
        end

        # 3. Submit
        HTTP.post("$base_url/api/game/submit",
            ["Content-Type" => "application/json"],
            JSON.json(Dict(
                "game_id" => game_id,
                "player_name" => player_name,
                "swaps" => formatted_swaps
            ))
        )
        println("[$player_name] Submitted $(length(swaps)) swaps successfully!")

    catch e
        bt = stacktrace(catch_backtrace())
        err_msg = sprint(showerror, e, bt)

        HTTP.post("$base_url/api/game/submit",
            ["Content-Type" => "application/json"],
            JSON.json(Dict(
                "game_id" => game_id,
                "player_name" => player_name,
                "error" => err_msg
            ))
        )
    end
end

function my_solver(matrix)
    swaps = [Swap(0, 0, 0, 8)]
    return swaps
end

run_bot("MPLX8U", "MyName59", my_solver, "http://localhost:8080")