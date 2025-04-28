import mmap
import os
import posix_ipc
import time
import csv

TOTAL_SIZE = 10 * 1024 * 1024 * 1024  # 4 GB
CHUNK_SIZE = 16 * 1024 * 1024
SHM_NAME = "/my_shm"
SEM_EMPTY = "/sem_empty"
SEM_FULL = "/sem_full"

def get_rss_mb():
    with open("/proc/self/statm") as f:
        parts = f.readline().split()
        rss_pages = int(parts[1])
    return rss_pages * os.sysconf("SC_PAGE_SIZE") / (1024 ** 2)

shm = posix_ipc.SharedMemory(SHM_NAME, posix_ipc.O_CREX, size=CHUNK_SIZE)#создание ячейки разделяемой памяти
mapfile = mmap.mmap(shm.fd, CHUNK_SIZE)#маппим разделяемую память, то есть помещаем в виртуальное адресное пространство процесса
os.close(shm.fd)# закрываем дескриптор так как можем рабоать через мапнутую часть

sem_empty = posix_ipc.Semaphore(SEM_EMPTY, posix_ipc.O_CREX, initial_value=1)#инициализируем семафор empty со значением 1
sem_full = posix_ipc.Semaphore(SEM_FULL, posix_ipc.O_CREX, initial_value=0)#инициализируем семафор full со значением 0

data = b"A" * CHUNK_SIZE

start = time.time()
active_start = time.time()
max_rss = 0.0
sent = 0

for i in range(0, TOTAL_SIZE, CHUNK_SIZE):
    sem_empty.acquire()# ожидаем семафор empty со значением 1 и обнуляем его
    mapfile.seek(0)# ставим курсор на начало файла
    mapfile.write(data)# пишем наш чанк информации в начало разделяемой памяти
    sem_full.release()#увеличиваем значение семафора full до 1 давая знак приёмнику что он может работать
    sent += CHUNK_SIZE

    if i % (CHUNK_SIZE * 100) == 0:
        rss = get_rss_mb()
        if rss > max_rss:
            max_rss = rss

active_end = time.time()
wall_end = time.time()

with open("shm_sender_metrics.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["active_time_sec", "wall_time_sec", "bytes_sent", "rss_mb"])
    w.writerow([f"{active_end - active_start:.6f}", f"{wall_end - start:.6f}", sent, f"{max_rss:.2f}"])

mapfile.close()
sem_empty.close()
sem_full.close()
posix_ipc.unlink_shared_memory(SHM_NAME)
posix_ipc.unlink_semaphore(SEM_EMPTY)
posix_ipc.unlink_semaphore(SEM_FULL)
