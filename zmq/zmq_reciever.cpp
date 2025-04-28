#include <zmq.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
#include <cstring>
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
    zmq::socket_t socket(context, ZMQ_PULL);
    socket.connect("tcp://localhost:5555");

    std::ofstream log("zmq_receiver_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_received,rss_bytes\n";

    size_t received_bytes = 0;
    auto pure_start = full_start;
    duration<double> active_time(0);
    bool first_recv = true;
    auto last_log = full_start;

    while (true) {
        zmq::message_t msg;
        auto t1 = high_resolution_clock::now();
        auto result = socket.recv(msg, zmq::recv_flags::none);
        auto t2 = high_resolution_clock::now();

        if (!result) break;
        active_time += t2 - t1;

        if (msg.size() == 4 && std::memcmp(msg.data(), "DONE", 4) == 0) break;

        if (first_recv) {
            pure_start = t1;
            first_recv = false;
        }

        received_bytes += msg.size();
        auto now = high_resolution_clock::now();
        if (duration<double>(now - last_log).count() >= 0.1) {
            double rss_mb = get_memory_rss_mb();
            log << active_time.count() << "," << duration<double>(now - full_start).count()
                << "," << received_bytes << "," << rss_mb << "\n";
            last_log = now;
        }
    }

    return 0;
}
