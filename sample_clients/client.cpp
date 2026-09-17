#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <thread>
#include <chrono>
#include <exception>
#include <functional>
#include <cstring>

#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>

struct Swap {
    int r1, c1, r2, c2;
};

std::string http_request(const std::string& method, const std::string& host, int port, const std::string& path, const std::string& body = "") {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return "";

    struct hostent* server = gethostbyname(host.c_str());
    if (!server) { close(sock); return ""; }

    struct sockaddr_in serv_addr{};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    std::memcpy(&serv_addr.sin_addr.s_addr, server->h_addr, server->h_length);

    if (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        close(sock);
        return "";
    }

    std::ostringstream req;
    req << method << " " << path << " HTTP/1.1\r\n"
        << "Host: " << host << ":" << port << "\r\n"
        << "Content-Type: application/json\r\n"
        << "Content-Length: " << body.length() << "\r\n"
        << "Connection: close\r\n\r\n"
        << body;

    std::string req_str = req.str();
    send(sock, req_str.c_str(), req_str.length(), 0);

    std::string response;
    char buffer[1024];
    int bytes;
    while ((bytes = recv(sock, buffer, sizeof(buffer) - 1, 0)) > 0) {
        buffer[bytes] = '\0';
        response += buffer;
    }
    close(sock);
    
    size_t body_pos = response.find("\r\n\r\n");
    return (body_pos != std::string::npos) ? response.substr(body_pos + 4) : "";
}

std::vector<std::vector<int>> parse_matrix(const std::string& json) {
    std::vector<std::vector<int>> matrix;
    size_t pos = json.find("\"matrix\":");
    if (pos == std::string::npos) return matrix;

    size_t start = json.find("[[", pos);
    if (start == std::string::npos) return matrix;
    size_t end = json.find("]]", start);

    std::string mat_str = json.substr(start + 2, end - start - 2);
    std::stringstream ss(mat_str);
    std::string row_str;

    while (std::getline(ss, row_str, ']')) {
        size_t bracket = row_str.find('[');
        if (bracket != std::string::npos) row_str = row_str.substr(bracket + 1);
        if (row_str.empty() || row_str == ",") continue;

        std::stringstream row_ss(row_str);
        std::string val_str;
        std::vector<int> row;
        while (std::getline(row_ss, val_str, ',')) {
            if (!val_str.empty()) row.push_back(std::stoi(val_str));
        }
        if (!row.empty()) matrix.push_back(row);
    }
    return matrix;
}

void run_bot(const std::string& game_id, const std::string& player_name, 
             std::function<std::vector<Swap>(const std::vector<std::vector<int>>&)> solve_func, 
             const std::string& host = "127.0.0.1", int port = 8080) {

    std::cout << "[" << player_name << "] Joining game " << game_id << "...\n";

    // 1. Join Game
    std::string join_payload = "{\"game_id\":\"" + game_id + "\",\"player_name\":\"" + player_name + "\",\"client_type\":\"bot\"}";
    http_request("POST", host, port, "/api/game/join", join_payload);

    // 2. Wait for Matrix
    std::vector<std::vector<int>> matrix;
    while (matrix.empty()) {
        try {
            std::string res = http_request("GET", host, port, "/api/game/state?id=" + game_id + "&v=0");
            matrix = parse_matrix(res);
        } catch (...) {}
        if (matrix.empty()) std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    std::cout << "[" << player_name << "] Matrix received! Calculating swaps...\n";

    // 3. Run solver & format swaps
    std::vector<std::vector<int>> matrix_copy = matrix;
    try {
        std::vector<Swap> swaps = solve_func(matrix);

        std::ostringstream swaps_json;
        swaps_json << "[";
        for (size_t i = 0; i < swaps.size(); ++i) {
            const auto& s = swaps[i];
            int val1 = matrix_copy[s.r1][s.c1];
            int val2 = matrix_copy[s.r2][s.c2];

            swaps_json << "{\"x1\":" << s.r1 << ",\"y1\":" << s.c1 
                       << ",\"x2\":" << s.r2 << ",\"y2\":" << s.c2 
                       << ",\"val1\":" << val1 << ",\"val2\":" << val2 << "}";
            if (i + 1 < swaps.size()) swaps_json << ",";

            matrix_copy[s.r1][s.c1] = val2;
            matrix_copy[s.r2][s.c2] = val1;
        }
        swaps_json << "]";

        // 4. Submit
        std::string submit_payload = "{\"game_id\":\"" + game_id + "\",\"player_name\":\"" + player_name + "\",\"swaps\":" + swaps_json.str() + "}";
        http_request("POST", host, port, "/api/game/submit", submit_payload);
        std::cout << "[" << player_name << "] Submitted " << swaps.size() << " swaps successfully!\n";

    } catch (const std::exception& e) {
        std::string err_payload = "{\"game_id\":\"" + game_id + "\",\"player_name\":\"" + player_name + "\",\"error\":\"" + e.what() + "\"}";
        http_request("POST", host, port, "/api/game/submit", err_payload);
    }
}

std::vector<Swap> my_solver(const std::vector<std::vector<int>>& matrix) {
    std::vector<Swap> swaps;
    swaps.push_back({0, 0, 0, 8}); // Example swap
    return swaps;
}

int main() {
    run_bot("MPLX8U", "MyName59", my_solver);
    return 0;
}