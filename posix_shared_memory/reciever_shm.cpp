// receiver.cpp
#include <fcntl.h>
#include <semaphore.h>
#include <sys/mman.h>
#include <unistd.h>

#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
#include <cstring>

const size_t TOTAL_SIZE = 10ULL * 1024 * 1024 * 1024;  // 10 GB
const size_t CHUNK_SIZE = 16 * 1024 * 1024;
const char* SHM_NAME = "/my_shm";
const char* SEM_EMPTY_NAME = "/sem_empty";
const char* SEM_FULL_NAME = "/sem_full";

double get_rss_in_mb() {
    std::ifstream statm("/proc/self/statm");
    size_t resident_pages = 0;
    statm.ignore(std::numeric_limits<std::streamsize>::max(), ' ');
    statm >> resident_pages;
    return (resident_pages * sysconf(_SC_PAGESIZE)) / (1024.0 * 1024.0);
}

int main() {
    int shm_fd = shm_open(SHM_NAME, O_RDWR, 0666);
    void* ptr = mmap(0, CHUNK_SIZE, PROT_READ, MAP_SHARED, shm_fd, 0);

    sem_t* sem_empty = sem_open(SEM_EMPTY_NAME, 0);
    sem_t* sem_full = sem_open(SEM_FULL_NAME, 0);

    char* buffer = new char[CHUNK_SIZE];

    auto wall_start = std::chrono::high_resolution_clock::now();
    double active_time = 0.0;

    double max_rss = 0.0;
    size_t received = 0;

    for (size_t i = 0; i < TOTAL_SIZE; i += CHUNK_SIZE) {
        sem_wait(sem_full);

        auto active_start = std::chrono::high_resolution_clock::now();
        memcpy(buffer, ptr, CHUNK_SIZE);
        auto active_end = std::chrono::high_resolution_clock::now();

        active_time += std::chrono::duration<double>(active_end - active_start).count();
        sem_post(sem_empty);

        received += CHUNK_SIZE;
        if (i % (100 * CHUNK_SIZE) == 0) {
            double current_rss = get_rss_in_mb();
            if (current_rss > max_rss) max_rss = current_rss;
        }
    }

    auto wall_end = std::chrono::high_resolution_clock::now();
    double wall_time = std::chrono::duration<double>(wall_end - wall_start).count();

    std::ofstream log("shm_reciever_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_received,rss_mb\n";
    log << active_time << "," << wall_time << "," << received << "," << max_rss << "\n";

    delete[] buffer;
    munmap(ptr, CHUNK_SIZE);
    close(shm_fd);
    sem_close(sem_empty);
    sem_close(sem_full);

    return 0;
}
