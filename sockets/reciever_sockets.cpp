#include <iostream>
#include <fstream>
#include <chrono>
#include <vector>
#include <limits>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <sys/types.h>

// Функция чтения текущего RSS (Resident Set Size) в мегабайтах
double get_rss_in_mb() {
    std::ifstream statm("/proc/self/statm");
    size_t resident_pages = 0;
    // Пропускаем первое поле (размер), читаем второе — resident
    statm.ignore(std::numeric_limits<std::streamsize>::max(), ' ');
    statm >> resident_pages;
    // Переводим страницы в байты, затем в МБ
    return static_cast<double>(resident_pages * sysconf(_SC_PAGESIZE)) 
           / (1024.0 * 1024.0);
}

int main() {
    const size_t CHUNK_SIZE = 16 * 1024 * 1024;               // размер буфера (16 МБ)
    std::vector<char> buffer(CHUNK_SIZE);                     // буфер приёма
    double max_rss_mb = 0;                                    // макс. потребление памяти

    // 1) Создаём TCP-сокет
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    // 2) Включаем опцию SO_REUSEADDR, чтобы перепривязываться к порту сразу после закрытия
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("setsockopt(SO_REUSEADDR)");
        close(server_fd);
        return 1;
    }
    // (Опционально на Linux можно также включить SO_REUSEPORT)
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt)) < 0) {
        perror("setsockopt(SO_REUSEPORT)");
        // не критично, продолжаем работу
    }

    // 3) Задаём адрес и порт для bind()
    sockaddr_in addr{};
    addr.sin_family = AF_INET;                // IPv4
    addr.sin_port = htons(5000);              // порт 5000, сетевой порядок байт
    addr.sin_addr.s_addr = INADDR_ANY;        // слушать все интерфейсы

    if (bind(server_fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(server_fd);
        return 1;
    }

    // 4) Переводим в режим прослушивания с очередью 1
    if (listen(server_fd, 1) < 0) {
        perror("listen");
        close(server_fd);
        return 1;
    }

    // 5) Засекаем wall-clock время до accept()
    auto wall_start = std::chrono::high_resolution_clock::now();

    // 6) Ждём входящее соединение
    int client_fd = accept(server_fd, nullptr, nullptr);
    if (client_fd < 0) {
        perror("accept");
        close(server_fd);
        return 1;
    }

    // 7) Засекаем active время после установления соединения
    auto active_start = std::chrono::high_resolution_clock::now();

    // 8) Цикл приёма данных
    size_t total_received = 0;
    int iter = 0;
    while (true) {
        ssize_t bytes = recv(client_fd, buffer.data(), buffer.size(), 0);
        if (bytes < 0) {
            perror("recv");
            break;
        }
        if (bytes == 4 && std::memcmp(buffer.data(), "DONE", 4) == 0) {
            break;
        }
        if (bytes == 0) {
            break;
        }
        total_received += bytes;

        // Обновляем пиковое потребление памяти раз в 100 итераций
        if (iter % 100 == 0) {
            double rss = get_rss_in_mb();
            if (rss > max_rss_mb) {
                max_rss_mb = rss;
            }
        }
        iter++;
    }

    // 9) Засекаем время окончания передачи
    auto active_end = std::chrono::high_resolution_clock::now();

    // 10) Корректно закрываем соединение
    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);
    close(server_fd);

    // 11) Засекаем окончательное wall-clock время
    auto wall_end = std::chrono::high_resolution_clock::now();

    // 12) Вычисляем дельты времени
    double active_time = std::chrono::duration<double>(active_end - active_start).count();
    double wall_time   = std::chrono::duration<double>(wall_end - wall_start).count();

    // 13) Логируем метрики в CSV
    std::ofstream log("socket_receiver_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_received,rss_mb\n";
    log << active_time << "," 
        << wall_time   << "," 
        << total_received << "," 
        << max_rss_mb  << "\n";

    return 0;
}
