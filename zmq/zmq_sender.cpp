#include <zmq.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
#include <vector>
#include <fstream>
#include <unistd.h>

double get_memory_rss_mb() {
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (line.find("VmRSS:") == 0) {
            std::istringstream iss(line);
            std::string key;
            double value_kb;
            std::string unit;
            iss >> key >> value_kb >> unit;
            return value_kb / 1024.0;
        }
    }
    return 0.0;
}

int main() {
    using namespace std::chrono;
    auto full_start = high_resolution_clock::now();

    zmq::context_t context(1);
    zmq::socket_t socket(context, ZMQ_PUSH);
    socket.bind("tcp://*:5555");

    const size_t total_bytes = 10ull * 1024 * 1024 * 1024;
    const size_t chunk_size = 16 * 1024 * 1024;
    std::vector<char> data(chunk_size, 42);

    std::ofstream log("zmq_sender_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_sent,rss_bytes\n";

    size_t sent_bytes = 0;
    bool first_send = true;
    auto pure_start = full_start;
    duration<double> active_time(0);
    auto last_log = full_start;

    while (sent_bytes < total_bytes) {
        if (first_send) {
            pure_start = high_resolution_clock::now();
            first_send = false;
        }

        auto t1 = high_resolution_clock::now();
        zmq::message_t msg(data.data(), chunk_size);
        socket.send(msg, zmq::send_flags::none);
        auto t2 = high_resolution_clock::now();

        active_time += t2 - t1;
        sent_bytes += chunk_size;

        auto now = high_resolution_clock::now();
        if (duration<double>(now - last_log).count() >= 0.1) {
            double rss_mb = get_memory_rss_mb();
            log << active_time.count() << "," << duration<double>(now - full_start).count()
                << "," << sent_bytes << "," << rss_mb << "\n";
            last_log = now;
        }
    }

    zmq::message_t done_msg("DONE", 4);
    socket.send(done_msg, zmq::send_flags::none);
    return 0;
}
