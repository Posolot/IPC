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

shm = posix_ipc.SharedMemory(SHM_NAME)#подключения к уже существующей разделяемой памяти
mapfile = mmap.mmap(shm.fd, CHUNK_SIZE)# маппинг файла , то есть подключение к виртуальному адресному пространству
os.close(shm.fd)#закрытие файлового дескриптора

sem_empty = posix_ipc.Semaphore(SEM_EMPTY)#открываем оба семафора
sem_full = posix_ipc.Semaphore(SEM_FULL)#открываем оба семафора

start = time.time()
active_start = time.time()
max_rss = 0.0
received = 0

for i in range(0, TOTAL_SIZE, CHUNK_SIZE):
    sem_full.acquire()# ожидаем семафор full со значением 1 и уменьшаем его до 0
    mapfile.seek(0)# перемещаемся в начало файла
    data = mapfile.read(CHUNK_SIZE)#читаем информацию из файла
    sem_empty.release()#увеличиваем семафор empty до 1
    received += CHUNK_SIZE#сохраняем информацию

    if i % (CHUNK_SIZE * 100) == 0:#проверка необходимая для замера нагрузки на оперативную память
        rss = get_rss_mb()
        if rss > max_rss:
            max_rss = rss

active_end = time.time()
wall_end = time.time()

with open("shm_reciever_metrics.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["active_time_sec", "wall_time_sec", "bytes_received", "rss_mb"])
    w.writerow([f"{active_end - active_start:.6f}", f"{wall_end - start:.6f}", received, f"{max_rss:.2f}"])

mapfile.close()
sem_empty.close()
sem_full.close()
