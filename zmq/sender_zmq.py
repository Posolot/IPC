import zmq
import time
import csv
import os

def get_rss_bytes():
    with open("/proc/self/statm", "r") as f:
        parts = f.readline().split()
        resident_pages = int(parts[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")

def main():
    full_start_time = time.time()# создание таймера
    context = zmq.Context()#создание объекта среды который управляет работой сокетов
    socket = context.socket(zmq.PUSH)#создание сокета типа PUSH, только отправка данных
    socket.bind("tcp://*:5555")# подключение к локальному хосту на 5555 порт

    total_bytes = 10 * 1024 * 1024 * 1024 #10Gb
    chunk_size = 16 * 1024 * 1024  #16Mb
    data = bytearray(b'A' * chunk_size)# массив с данными

    with open("zmq_sender_metrics.csv", "w", newline="") as log_file:
        log_writer = csv.writer(log_file)#начало записи логов
        log_writer.writerow(["active_time_sec", "wall_time_sec", "bytes_sent", "rss_bytes"])

        sent_bytes = 0
        first_send = True
        active_time = 0.0
        pure_start = full_start_time#таймеры
        last_log = full_start_time#таймеры

        while sent_bytes < total_bytes:#цикл постоянной проверки отправлены ли данные
            if first_send:
                pure_start = time.time()
                first_send = False

            t1 = time.time()
            socket.send(data)#отправка данных
            t2 = time.time()

            active_time += t2 - t1
            sent_bytes += chunk_size
            now = time.time()
            if now - last_log >= 0.1:
                rss = get_rss_bytes()/(1024*1024)
                log_writer.writerow([active_time, now - full_start_time, sent_bytes, rss])
                last_log = now

        socket.send(b"DONE")#отправка финального сообщения

if __name__ == "__main__":
    main()
