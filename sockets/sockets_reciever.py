import socket
import time
import resource
import os

CHUNK_SIZE = 16 * 1024 * 1024

def get_rss_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024 if os.name != 'darwin' else usage.ru_maxrss  # MacOS использует байты

def receive_data():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    max_retries = 30  # количество попыток
    retry_delay = 2   # задержка между попытками в секундах

    for attempt in range(max_retries):
        try:
            sock.bind(("localhost", 5000))
            print("Bind successful")
            break  # успешно, выходим из цикла
        except OSError as e:
            if e.errno == 98:  # Address already in use
                print(f"Address in use, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                # Другие ошибки — пробрасываем дальше
                raise
    else:
        # Если после всех попыток не удалось — выводим сообщение и завершаем
        print("Failed to bind socket after multiple retries.")
        sock.close()
        exit(1)

    sock.listen(1)
    wall_start = time.perf_counter()#таймеры
    conn, _ = sock.accept()# программа находится в ожидании пока не придёт первое сообщение
    active_start = time.perf_counter()#таймеры

    total_received = 0 #кол-во принятых данных
    iter = 0
    max_rss = 0
    while True:
        data = conn.recv(CHUNK_SIZE)
        if data == b"DONE":  # Сначала проверяем на "DONE"
            conn.shutdown(socket.SHUT_RD)  # Закрытие стороны получения данных
            break
        if not data:  # Проверка на завершение соединения
            break
        total_received += len(data)
        if iter % 100 == 0:
            rss = get_rss_mb()
            if rss > max_rss:
                max_rss = rss# вся проверка выше необходима для проверки нагрузки на память на каждой сотой итерации цикла
        iter += 1

    active_end = time.perf_counter()
    wall_end = time.perf_counter()

    active_time = active_end - active_start
    wall_time = wall_end - wall_start

    with open("socket_receiver_metrics.csv", "w") as f:
        f.write("active_time_sec,wall_time_sec,bytes_received,rss_mb\n")
        f.write(f"{active_time:.6f},{wall_time:.6f},{total_received},{max_rss:.2f}\n")#логирование

    conn.close()
    sock.close()

if __name__ == "__main__":
    receive_data()
