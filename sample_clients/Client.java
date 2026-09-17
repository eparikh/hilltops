import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.util.*;

public class Client {

    public static class Swap {
        public int r1, c1, r2, c2;
        public Swap(int r1, int c1, int r2, int c2) {
            this.r1 = r1; this.c1 = c1; this.r2 = r2; this.c2 = c2;
        }
    }

    public static void runBot(String gameId, String playerName, java.util.function.Function<int[][], List<Swap>> solveFunc, String baseUrl) {
        HttpClient client = HttpClient.newHttpClient();
        System.out.println("[" + playerName + "] Joining game " + gameId + "...");

        try {
            // 1. Join Game
            String joinBody = String.format("{\"game_id\":\"%s\",\"player_name\":\"%s\",\"client_type\":\"bot\"}", gameId, playerName);
            HttpRequest joinReq = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/api/game/join"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(joinBody))
                    .build();
            client.send(joinReq, HttpResponse.BodyHandlers.ofString());

            // 2. Poll for Matrix
            int[][] matrix = null;
            while (matrix == null) {
                try {
                    HttpRequest stateReq = HttpRequest.newBuilder()
                            .uri(URI.create(baseUrl + "/api/game/state?id=" + gameId + "&v=0"))
                            .GET().build();
                    HttpResponse<String> res = client.send(stateReq, HttpResponse.BodyHandlers.ofString());
                    matrix = parseMatrix(res.body());
                } catch (Exception ignored) {}
                if (matrix == null) Thread.sleep(500);
            }

            System.out.println("[" + playerName + "] Matrix received! Calculating swaps...");

            // 3. User algorithm & matrix copy
            int[][] matrixCopy = deepCopy(matrix);
            List<Swap> swaps = solveFunc.apply(matrix);

            // 4. Format swaps payload
            StringBuilder swapsJson = new StringBuilder("[");
            for (int i = 0; i < swaps.size(); i++) {
                Swap s = swaps.get(i);
                int val1 = matrixCopy[s.r1][s.c1];
                int val2 = matrixCopy[s.r2][s.c2];

                swapsJson.append(String.format(
                    "{\"x1\":%d,\"y1\":%d,\"x2\":%d,\"y2\":%d,\"val1\":%d,\"val2\":%d}",
                    s.r1, s.c1, s.r2, s.c2, val1, val2
                ));
                if (i < swaps.size() - 1) swapsJson.append(",");

                matrixCopy[s.r1][s.c1] = val2;
                matrixCopy[s.r2][s.c2] = val1;
            }
            swapsJson.append("]");

            // 5. Submit
            String submitBody = String.format("{\"game_id\":\"%s\",\"player_name\":\"%s\",\"swaps\":%s}", gameId, playerName, swapsJson.toString());
            HttpRequest subReq = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/api/game/submit"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(submitBody))
                    .build();
            client.send(subReq, HttpResponse.BodyHandlers.ofString());
            System.out.println("[" + playerName + "] Submitted " + swaps.size() + " swaps successfully!");

        } catch (Exception e) {
            StringWriter sw = new StringWriter();
            e.printStackTrace(new PrintWriter(sw));
            String errBody = String.format("{\"game_id\":\"%s\",\"player_name\":\"%s\",\"error\":%s}",
                    gameId, playerName, escapeJson(sw.toString()));
            try {
                HttpRequest errReq = HttpRequest.newBuilder()
                        .uri(URI.create(baseUrl + "/api/game/submit"))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(errBody))
                        .build();
                client.send(errReq, HttpResponse.BodyHandlers.ofString());
            } catch (Exception ignored) {}
        }
    }

    private static int[][] deepCopy(int[][] original) {
        int[][] copy = new int[original.length][];
        for (int i = 0; i < original.length; i++) copy[i] = original[i].clone();
        return copy;
    }

    private static String escapeJson(String raw) {
        return "\"" + raw.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "") + "\"";
    }

    private static int[][] parseMatrix(String json) {
        if (!json.contains("\"matrix\":")) return null;
        int idx = json.indexOf("\"matrix\":");
        int start = json.indexOf("[[", idx);
        if (start == -1) return null;
        int end = json.indexOf("]]", start) + 2;
        String matStr = json.substring(start, end).replaceAll("\\s+", "");
        String[] rows = matStr.substring(2, matStr.length() - 2).split("\\]\\,\\[");
        int[][] matrix = new int[rows.length][];
        for (int i = 0; i < rows.length; i++) {
            String[] vals = rows[i].split(",");
            matrix[i] = new int[vals.length];
            for (int j = 0; j < vals.length; j++) matrix[i][j] = Integer.parseInt(vals[j]);
        }
        return matrix;
    }

    public static void main(String[] args) {
        runBot("MPLX8U", "MyName59", Client::mySolver, "http://localhost:8080");
    }

    public static List<Swap> mySolver(int[][] matrix) {
        List<Swap> swaps = new ArrayList<>();
        swaps.add(new Swap(0, 0, 0, 8)); // Example swap
        return swaps;
    }
}