import socket
import time
import resource
import os

CHUNK_SIZE = 16 * 1024 * 1024
TOTAL_SIZE = 10 * 1024**3

def get_rss_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024

def send_data():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# создание объекта сокета

    wall_start = time.perf_counter()#начало отсчёта времени
    sock.connect(("localhost", 5000))# подключение по локальному хосту на 5000 порт
    active_start = time.perf_counter()# начало отсчёта активного времени

    total_sent = 0 # переменная для подсчёта отправленных данных
    chunk = b'\x42' * CHUNK_SIZE # имитация чанка для отправки
    iter = 0
    max_rss = 0
    while total_sent < TOTAL_SIZE:
        sock.sendall(chunk) #отправка чанка в цикле
        total_sent += CHUNK_SIZE #подсчёт размера отправленного файла
        if iter % 100 == 0:
            rss = get_rss_mb()
            if rss > max_rss:
                max_rss = rss# нагрузки на память на каждой сотой итерации цикла
        iter += 1

    sock.sendall(b"DONE")# команда чтобы приёмник понял что отправка данных окончена
    sock.shutdown(socket.SHUT_WR)  # Закрытие стороны отправителя
    active_end = time.perf_counter()
    wall_end = time.perf_counter()

    active_time = active_end - active_start
    wall_time = wall_end - wall_start

    with open("socket_sender_metrics.csv", "w") as f:
        f.write("active_time_sec,wall_time_sec,bytes_sent,rss_mb\n")
        f.write(f"{active_time:.6f},{wall_time:.6f},{total_sent},{max_rss:.2f}\n")

    sock.close()

if __name__ == "__main__":
    send_data()
