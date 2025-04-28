import zmq
import time
import csv
import os

def get_rss_bytes():
    with open("/proc/self/statm", "r") as f:#открываем специальный файл
        parts = f.readline().split()#читаем первую строку
        resident_pages = int(parts[1])#второе число(число активных странис RAM)
        return resident_pages * os.sysconf("SC_PAGE_SIZE")#так как число может варьироваться используем функцию

def main():
    full_start_time = time.time()# создание таймера
    context = zmq.Context()#создание объекта среды который управляет работой сокетов
    socket = context.socket(zmq.PULL)#создание сокета типа PULL, только получение данных
    socket.connect("tcp://localhost:5555")# подключение к локальному хосту на 5555 порт

    received_bytes = 0
    first_recv = True
    active_time = 0.0
    pure_start = full_start_time#таймеры
    last_log = full_start_time#таймеры

    with open("zmq_receiver_metrics.csv", "w", newline="") as log_file:
        log_writer = csv.writer(log_file)#начало записи логов
        log_writer.writerow(["active_time_sec", "wall_time_sec", "bytes_received", "rss_bytes"])

        while True:
            t1 = time.time()
            msg = socket.recv()#Приём сообщения
            t2 = time.time()

            active_time += t2 - t1

            if msg == b"DONE":# проверка на последнее сообщение
                break

            if first_recv:
                pure_start = t1
                first_recv = False

            received_bytes += len(msg)#увеличение размера полученных данных
            now = time.time()#
            if now - last_log >= 0.1:
                rss = get_rss_bytes()/(1024*1024)
                log_writer.writerow([active_time, now - full_start_time, received_bytes, rss])
                last_log = now

if __name__ == "__main__":
    main()
