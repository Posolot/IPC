#include <boost/interprocess/managed_shared_memory.hpp> // Для работы с разделяемой памятью
#include <boost/interprocess/sync/interprocess_semaphore.hpp> // Для межпроцессных семафоров
#include <chrono> // Для измерения времени
#include <cstring> // Для memcpy
#include <fstream> // Для логирования
#include <iostream> // Для вывода (может быть неиспользовано)
#include <sstream> // Для обработки строк
#include <unistd.h> // Для POSIX функций

using namespace boost::interprocess; // Пространство имён Boost Interprocess

// Константы размеров
static constexpr std::size_t BUFFER_SIZE    = 16 * 1024ul * 1024; // 16 МБ
static constexpr std::size_t TOTAL_SIZE     = 10ul * 1024 * 1024 * 1024; // 10 ГБ
static constexpr std::size_t NUM_ITERATIONS = TOTAL_SIZE / BUFFER_SIZE; // Количество итераций

// Структура разделяемой памяти, содержащая семафоры и буфер
struct shm_buf {
    interprocess_semaphore mem_lock; // Мьютекс для доступа к буферу
    interprocess_semaphore client_ready; // Семафор для сигнала о готовности данных
    interprocess_semaphore server_ready; // Семафор для подтверждения обработки
    char data[BUFFER_SIZE]; // Буфер данных
};

// Функция получения использования RSS в мегабайтах
double get_rss_in_mb() {
    std::ifstream status_file("/proc/self/status");
    std::string line;
    while (std::getline(status_file, line)) {
        if (line.find("VmRSS:") == 0) {
            std::istringstream iss(line);
            std::string key, unit;
            double value;
            iss >> key >> value >> unit;
            return value / 1024.0; // KB → MB
        }
    }
    return 0.0; // Если не нашли, возвращаем 0
}

int main() {
    // Открываем существующий сегмент памяти
    managed_shared_memory segment(open_only, "BoostSharedMem");
    // Находим объект shm_buf по имени
    shm_buf* shm = segment.find<shm_buf>("Buffer").first;

    // Открываем лог-файл для метрик
    std::ofstream metrics_log("boost_reciever_metrics.csv");
    metrics_log << "active_time_sec,wall_time_sec,bytes_received,rss_mb\n"; // Заголовки

    // Выделяем буфер для приёма данных
    char* buf = new char[BUFFER_SIZE];
    std::size_t received = 0; // Общее полученное количество байт
    double active_time = 0.0; // Время активной обработки
    double max_rss = 0.0; // Максимальное использование RSS

    auto wall_start = std::chrono::high_resolution_clock::now(); // Время начала общего таймера

    // Основной цикл получения данных
    for (std::size_t i = 0; i < NUM_ITERATIONS; ++i) {
        shm->client_ready.wait(); // Ждём сигнала о готовности данных от отправителя

        auto t0 = std::chrono::high_resolution_clock::now(); // Засекаем время начала обработки
        std::memcpy(buf, shm->data, BUFFER_SIZE); // Копируем данные из разделяемого буфера
        shm->mem_lock.post(); // Освобождаем мьютекс
        shm->server_ready.post(); // Сигналим отправителю, что обработка завершена
        auto t1 = std::chrono::high_resolution_clock::now(); // Засекаем время окончания обработки

        // Накапливаем активное время
        active_time += std::chrono::duration<double>(t1 - t0).count();
        // Обновляем количество полученных байт
        received += BUFFER_SIZE;

        // Каждые 100 итераций проверяем использование RSS
        if (i % 100 == 0) {
            double current_rss = get_rss_in_mb();
            if (current_rss > max_rss)
                max_rss = current_rss; // Обновляем максимум
        }
    }

    auto wall_end = std::chrono::high_resolution_clock::now(); // Время окончания общего таймера
    double total_time = std::chrono::duration<double>(wall_end - wall_start).count(); // Общее время

    // Записываем метрики
    metrics_log << active_time << "," << total_time << "," << received << "," << max_rss << "\n";
    metrics_log.close();

    // Расчёт скоростей
    double mbps_active  = (received / (1024.0 * 1024.0)) / active_time;
    double gbps_active  = (received * 8.0) / (1e9 * active_time);
    double mbps_overall = (received / (1024.0 * 1024.0)) / total_time;
    double gbps_overall = (received * 8.0) / (1e9 * total_time);

    delete[] buf; // Освобождение буфера
    return 0; // Завершение программы
}