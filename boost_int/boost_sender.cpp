#include <boost/interprocess/managed_shared_memory.hpp> // Для управления разделяемой памятью
#include <boost/interprocess/sync/interprocess_semaphore.hpp> // Для межпроцессных семафоров
#include <chrono> // Для измерения времени
#include <cstring> // Для memcpy
#include <fstream> // Для работы с файлами (логирование)
#include <iostream> // Для вывода в консоль (может быть неиспользовано)
#include <sstream> // Для обработки строк
#include <unistd.h> // Для функций POSIX, например sleep

using namespace boost::interprocess; // Пространство имён Boost Interprocess

// Константы для размеров буфера и общего объёма данных
static constexpr std::size_t BUFFER_SIZE    = 16 * 1024ul * 1024; // Размер буфера 16 МБ
static constexpr std::size_t TOTAL_SIZE     = 10ul * 1024 * 1024 * 1024; // Общий объём данных 10 ГБ
static constexpr std::size_t NUM_ITERATIONS = TOTAL_SIZE / BUFFER_SIZE; // Количество итераций


struct shm_buf {
    interprocess_semaphore mem_lock; // Семафор для доступа к буферу
    interprocess_semaphore client_ready; // Семафор для сигнала клиента о готовности данных
    interprocess_semaphore server_ready; // Семафор для сигнала сервера о завершении обработки
    char data[BUFFER_SIZE]; // Буфер данных
    shm_buf() : mem_lock(1), client_ready(0), server_ready(0) {} // Конструктор инициализирует семафоры
};

// Функция получения текущего использования RSS (Resident Set Size) в мегабайтах
double get_rss_in_mb() {
    std::ifstream status_file("/proc/self/status"); // Открываем файл статуса процесса
    std::string line;
    while (std::getline(status_file, line)) { // Читаем построчно
        if (line.find("VmRSS:") == 0) { // Ищем строку с RSS
            std::istringstream iss(line);
            std::string key, unit;
            double value;
            iss >> key >> value >> unit; // Парсим строку
            return value / 1024.0; // Конвертация из KB в MB
        }
    }
    return 0.0; // Если не нашли, возвращаем 0
}

int main() {
    // Удаляем ранее существующий разделяемый сегмент памяти с именем "BoostSharedMem"
    shared_memory_object::remove("BoostSharedMem");
    // Создаём новый сегмент памяти с размером, достаточным для структуры и небольшого запаса
    managed_shared_memory segment(create_only, "BoostSharedMem", sizeof(shm_buf) + 1024);
    // Создаём объект shm_buf в сегменте памяти
    shm_buf *shm = segment.construct<shm_buf>("Buffer")();

    // Открываем файл для логирования метрик
    std::ofstream log("boost_sender_metrics.csv");
    log << "active_time_sec,wall_time_sec,bytes_sent,rss_mb\n"; // Заголовки колонок

    // Выделяем буфер для отправки данных
    char *buf = new char[BUFFER_SIZE];
    std::memset(buf, 'A', BUFFER_SIZE); // Заполняем буфер символами 'A'

    std::size_t sent = 0; // Общее количество отправленных байт
    double active_time = 0.0; // Время активной передачи
    double max_rss = 0.0; // Максимальное использование RSS

    auto wall_start = std::chrono::high_resolution_clock::now(); // Время начала общего таймера

    // Основной цикл отправки данных
    for (std::size_t i = 0; i < NUM_ITERATIONS; ++i) {
        shm->mem_lock.wait(); // Захватываем мьютекс для доступа к буферу

        auto t0 = std::chrono::high_resolution_clock::now(); // Засекаем время начала передачи
        std::memcpy(shm->data, buf, BUFFER_SIZE); // Копируем данные в разделяемый буфер
        shm->client_ready.post(); // Сигналим клиенту, что данные готовы
        auto t1 = std::chrono::high_resolution_clock::now(); // Засекаем время завершения копирования

        shm->server_ready.wait(); // Ждём подтверждения от клиента о завершении обработки

        // Накапливаем активное время передачи
        active_time += std::chrono::duration<double>(t1 - t0).count();
        // Обновляем количество отправленных байт
        sent += BUFFER_SIZE;

        // Каждые 100 итераций проверяем использование RSS
        if (i % 100 == 0) {
            double current_rss = get_rss_in_mb();
            if (current_rss > max_rss)
                max_rss = current_rss; // Обновляем максимум
        }
    }

    auto wall_end = std::chrono::high_resolution_clock::now(); // Время окончания общего таймера
    double total_time = std::chrono::duration<double>(wall_end - wall_start).count(); // Общее время

    // Записываем метрики в лог-файл
    log << active_time << "," << total_time << "," << sent << "," << max_rss << "\n";
    log.close();

    // Расчёт скоростей
    double mbps_active  = (sent / (1024.0 * 1024.0)) / active_time;
    double gbps_active  = (sent * 8.0) / (1e9 * active_time);
    double mbps_overall = (sent / (1024.0 * 1024.0)) / total_time;
    double gbps_overall = (sent * 8.0) / (1e9 * total_time);

    delete[] buf; // Освобождение буфера
    segment.destroy<shm_buf>("Buffer"); // Удаление объекта из сегмента
    shared_memory_object::remove("BoostSharedMem"); // Удаление сегмента из системы
    return 0; // Завершение программы
}