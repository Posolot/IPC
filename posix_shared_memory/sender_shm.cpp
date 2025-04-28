
#include <fcntl.h>
#include <semaphore.h>
#include <sys/mman.h>
#include <unistd.h>

#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>

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
    int shm_fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
    if (ftruncate(shm_fd, CHUNK_SIZE) == -1) {
        perror("ftruncate");
        return 1;
    }
    void* ptr = mmap(0, CHUNK_SIZE, PROT_WRITE, MAP_SHARED, shm_fd, 0);

    sem_t* sem_empty = sem_open(SEM_EMPTY_NAME, O_CREAT, 0666, 1);
    sem_t* sem_full = sem_open(SEM_FULL_NAME, O_CREAT, 0666, 0);

    char* data = new char[CHUNK_SIZE];
    memset(data, 'A', CHUNK_SIZE);

    auto wall_start = std::chrono::high_resolution_clock::now();
    double active_time = 0.0;

    double max_rss = 0.0;
    size_t sent = 0;

    for (size_t i = 0; i < TOTAL_SIZE; i += CHUNK_SIZE) {
        sem_wait(sem_empty);

        auto active_start = std::chrono::high_resolution_clock::now();
        memcpy(ptr, data, CHUNK_SIZE);
        auto active_end = std::chrono::high_resolution_clock::now();

        active_time += std::chrono::duration<double>(active_end - active_start).count();
        sem_post(sem_full);

        sent += CHUNK_SIZE;
        if (i % (100 * CHUNK_SIZE) == 0) {
            double current_rss = get_rss_in_mb();
            if (current_rss > max_rss) max_rss = current_rss;
        }
    }

    auto wall_end = std::chrono::high_resolution_clock::now();
    double wall_time = std::chrono::duration<double>(wall_end - wall_start).count();

    std::ofstream log("shm_sender_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_sent,rss_mb\n";
    log << active_time << "," << wall_time << "," << sent << "," << max_rss << "\n";

    delete[] data;
    munmap(ptr, CHUNK_SIZE);
    close(shm_fd);
    shm_unlink(SHM_NAME);
    sem_close(sem_empty);
    sem_close(sem_full);
    sem_unlink(SEM_EMPTY_NAME);
    sem_unlink(SEM_FULL_NAME);

    return 0;
}
