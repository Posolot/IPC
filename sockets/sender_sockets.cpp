#include <iostream>
#include <fstream>
#include <chrono>
#include <vector>
#include <fstream>
#include <string>
#include <unistd.h>
#include <arpa/inet.h>

double get_rss_in_mb() {
    std::ifstream statm("/proc/self/statm");
    size_t resident_pages = 0;
    statm.ignore(std::numeric_limits<std::streamsize>::max(), ' ');
    statm >> resident_pages;
    return static_cast<double>(resident_pages * sysconf(_SC_PAGESIZE)) / (1024.0 * 1024.0);
}

int main() {
    const size_t chunk_size = 16 * 1024 * 1024;
    const size_t total_size = 10ULL * 1024 * 1024 * 1024;
    std::vector<char> buffer(chunk_size, 42);
    double max_rss_mb = 0.0;

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(5000);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

    auto wall_start = std::chrono::high_resolution_clock::now();
    connect(sock, (sockaddr*)&addr, sizeof(addr));
    auto active_start = std::chrono::high_resolution_clock::now();

    size_t sent_bytes = 0;
    int iter = 0; 
    while (sent_bytes < total_size) {
        send(sock, buffer.data(), chunk_size, 0);
        sent_bytes += chunk_size;
        if (iter%100==0){
            double rss = get_rss_in_mb();
            if (rss > max_rss_mb) max_rss_mb = rss;  
        }
        iter++;
        
    }

    send(sock, "DONE", 4, 0);
    auto active_end = std::chrono::high_resolution_clock::now();
    close(sock);
    auto wall_end = std::chrono::high_resolution_clock::now();

    double active_time = std::chrono::duration<double>(active_end - active_start).count();
    double wall_time = std::chrono::duration<double>(wall_end - wall_start).count();

    std::ofstream log("socket_sender_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_sent,rss_mb\n";
    log << active_time << "," << wall_time << "," << sent_bytes << "," << max_rss_mb << "\n";

    return 0;
}
