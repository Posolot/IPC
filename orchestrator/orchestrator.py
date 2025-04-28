
import subprocess            
import shutil               
import os                    
import time                  
import signal                
from pathlib import Path    
from datetime import datetime

import pandas as pd         
import matplotlib.pyplot as plt  

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).parent.parent

# Папка для сохранения результатов тестов
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)  # Создать папку, если её нет

# Конфигурация методов IPC
METHODS_CONFIG = {
    "posix_shared_memory": {
        "py_sender":   "python3 shm_sender.py",        # Python отправитель через POSIX shared memory
        "py_receiver": "python3 shm_reciever.py",      # Python получатель через POSIX shared memory
        "cpp_sender":  "./sender_shm",                 # C++ отправитель через POSIX shared memory
        "cpp_receiver":"./reciever_shm",               # C++ получатель через POSIX shared memory
        "sender_metric":   "shm_sender_metrics.csv",   # Файл метрик отправителя
        "receiver_metric": "shm_reciever_metrics.csv", # Файл метрик получателя
    },
    "boost_int": {
        "sender": "./boost_sender",                    # Boost.Interprocess отправитель
        "receiver": "./boost_reciever",                # Boost.Interprocess получатель
        "sender_metric":   "boost_sender_metrics.csv",  # Файл метрик отправителя
        "receiver_metric": "boost_reciever_metrics.csv",# Файл метрик получателя
    },
    "zmq": {
        "py_sender":   "python3 sender_zmq.py",        # Python отправитель через ZeroMQ
        "py_receiver": "python3 reciever_zmq.py",      # Python получатель через ZeroMQ
        "cpp_sender":  "./zmq_sender",                 # C++ отправитель через ZeroMQ
        "cpp_receiver":"./zmq_reciever",               # C++ получатель через ZeroMQ
        "sender_metric":   "zmq_sender_metrics.csv",    # Файл метрик отправителя
        "receiver_metric": "zmq_receiver_metrics.csv", # Файл метрик получателя
    },
    "sockets": {
        "py_sender":   "python3 sockets_sender.py",    # Python отправитель через сокеты
        "py_receiver": "python3 sockets_reciever.py",  # Python получатель через сокеты
        "cpp_sender":  "./sender_socket",               # C++ отправитель через сокеты
        "cpp_receiver":"./reciever_socket",             # C++ получатель через сокеты
        "sender_metric":   "socket_sender_metrics.csv", # Файл метрик отправителя
        "receiver_metric": "socket_receiver_metrics.csv",# Файл метрик получателя
    },
}

# Список комбинаций отправитель-получатель для тестирования
SENDER_RECEIVER_PAIRS = [
    ("py_sender", "py_receiver"),  # Python → Python
    ("py_sender", "cpp_receiver"), # Python → C++
    ("cpp_sender", "py_receiver"), # C++ → Python
    ("cpp_sender", "cpp_receiver"),# C++ → C++
]

def run_boost(method_name, method_config, output_root):
    code_dir = PROJECT_ROOT / method_name
    output_subdir = output_root / f"{method_name}_run"
    output_subdir.mkdir()

    sender_cmd = method_config["sender"]
    receiver_cmd = method_config["receiver"]
    print(f"[INFO] Запуск {method_name}: отправитель -> {sender_cmd}, получатель -> {receiver_cmd}")

    sender_proc = subprocess.Popen(sender_cmd, cwd=code_dir, shell=True, preexec_fn=os.setsid)
    time.sleep(0.2)
    receiver_proc = subprocess.Popen(receiver_cmd, cwd=code_dir, shell=True, preexec_fn=os.setsid)

    try:
        receiver_proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        print("[WARN] Получатель завис, убиваем процесс")
        os.killpg(os.getpgid(receiver_proc.pid), signal.SIGKILL)

    for role in ("sender", "receiver"):
        metric_file = method_config[f"{role}_metric"]
        source_file = code_dir / metric_file
        if source_file.exists():
            shutil.copy(source_file, output_subdir / metric_file)


def run_method(method_name, method_config, output_root):

    code_dir = PROJECT_ROOT / method_name

    if method_name == "posix_shared_memory":
        tasks = [(s_key, method_config[s_key], r_key, method_config[r_key], 0.2)
                 for s_key, r_key in SENDER_RECEIVER_PAIRS]
        start_sender_first = True
    else:
        tasks = [(s_key, method_config.get(s_key), r_key, method_config.get(r_key), 0.2)
                 for s_key, r_key in SENDER_RECEIVER_PAIRS]
        start_sender_first = False

    for sender_key, sender_cmd, receiver_key, receiver_cmd, delay in tasks:
        if not sender_cmd or not receiver_cmd:
            continue

        run_tag = f"{method_name}_{sender_key}_{receiver_key}"
        output_subdir = output_root / run_tag
        output_subdir.mkdir()

        if start_sender_first:
            print(f"[INFO] Запуск отправителя ({sender_key}): {sender_cmd}")
            subprocess.Popen(sender_cmd, cwd=code_dir, shell=True, preexec_fn=os.setsid)
            time.sleep(delay)
            print(f"[INFO] Запуск получателя ({receiver_key}): {receiver_cmd}")
            receiver_proc = subprocess.Popen(receiver_cmd, cwd=code_dir, shell=True, preexec_fn=os.setsid)
        else:
            print(f"[INFO] Запуск получателя ({receiver_key}): {receiver_cmd}")
            receiver_proc = subprocess.Popen(receiver_cmd, cwd=code_dir, shell=True, preexec_fn=os.setsid)
            time.sleep(delay)
            print(f"[INFO] Запуск отправителя ({sender_key}): {sender_cmd}")
            subprocess.run(sender_cmd, cwd=code_dir, shell=True)

        try:
            receiver_proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            print("[WARN] Получатель завис, убиваем процесс")
            os.killpg(os.getpgid(receiver_proc.pid), signal.SIGKILL)

        for role in ("sender", "receiver"):
            metric_file = method_config[f"{role}_metric"]
            source_file = code_dir / metric_file
            if source_file.exists():
                shutil.copy(source_file, output_subdir / metric_file)


def run_all_tests():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")#получаем данные даты и времени для имени папки
    current_run_dir = RESULTS_DIR / timestamp# создаём команду для создания папки
    current_run_dir.mkdir()#создаём папку с датой внутри папки results

    for method_name, method_config in METHODS_CONFIG.items():#цикл для прохождения всех методов во всех комбинациях
        if method_name == "boost_int":# так как boost имеет только c++ скрипты то для него отдельая функция
            run_boost(method_name, method_config, current_run_dir)
        else:
            run_method(method_name, method_config, current_run_dir)

    return current_run_dir# возвращаем путь к папке для построения графиков


def plot_results(results_dir):
    def short_label(run_tag: str) -> str:
        # Карты для префиксов методов
        prefix_map = {
            'posix_shared_memory': 'shm',
            'boost_int': 'boost',
            'zmq': 'zmq',
            'sockets': 'sock'
        }

        # Карты для коротких обозначений ролей
        role_map = {
            'py_sender': 'py',
            'cpp_sender': 'c++',
            'py_receiver': 'py',
            'cpp_receiver': 'c++'
        }

        # Определяем префикс метода по началу строки
        method_prefix = None
        for key in prefix_map:
            if run_tag.startswith(key):
                method_prefix = prefix_map[key]
                break
        if method_prefix is None:
            # Не нашли подходящий метод
            return run_tag

        # Ищем роли по наличию точных строк
        sender_role = None
        receiver_role = None

        for role_str, short_name in role_map.items():
            if role_str in run_tag:
                if 'sender' in role_str:
                    sender_role = short_name
                elif 'receiver' in role_str:
                    receiver_role = short_name

        # Если роли не найдены, оставляем как есть
        s = sender_role if sender_role else ''
        r = receiver_role if receiver_role else ''

        return f"{method_prefix}_{s}->{r}"

    # Подготовка накопителей
    throughput_records   = []  # (run_tag, role, mbps)
    memory_records       = []  # (run_tag, role, memory_mb)
    speeds_by_method     = {}  # { method_name: [ (run_tag, mbps), ... ] }
    memory_by_method     = {}  # { method_name: [ (run_tag, memory_mb), ... ] }

    # Сбор данных из CSV
    for run_subdir in results_dir.iterdir():
        if not run_subdir.is_dir():
            continue

        sender_file = next(run_subdir.glob("*sender*metrics.csv"), None)
        receiver_file = (
            next(run_subdir.glob("*receiver*metrics.csv"), None)
            or next(run_subdir.glob("*reciever*metrics.csv"), None)
        )
        run_tag = run_subdir.name

        def parse_metrics(file_path, role):
            df = pd.read_csv(file_path)
            if 'active_time_sec' in df.columns and 'wall_time_sec' in df.columns:
                active_time = df['active_time_sec'].iloc[-1]
                byte_count  = (
                    df['bytes_sent'].iloc[-1]
                    if role == 'sender'
                    else df['bytes_received'].iloc[-1]
                )
                # память
                if 'rss_mb_max' in df.columns:
                    mem_usage = df['rss_mb_max'].iloc[-1]
                elif 'rss_mb' in df.columns:
                    mem_usage = df['rss_mb'].iloc[-1]
                else:
                    mem_usage = None

                # скорость
                if active_time > 0:
                    speed_mbps = (byte_count / 1024**2) / active_time
                    throughput_records.append((run_tag, role, speed_mbps))
                else:
                    speed_mbps = None

                # память по ролям
                if mem_usage is not None:
                    memory_records.append((run_tag, role, mem_usage))

                # группировка по методам
                method_prefix = next(
                    (m for m in METHODS_CONFIG if run_tag.startswith(m)),
                    None
                )
                if method_prefix:
                    if speed_mbps is not None:
                        speeds_by_method.setdefault(method_prefix, []).append((run_tag, speed_mbps))
                    if mem_usage is not None:
                        memory_by_method.setdefault(method_prefix, []).append((run_tag, mem_usage))

        if sender_file:
            parse_metrics(sender_file, 'sender')
        if receiver_file:
            parse_metrics(receiver_file, 'receiver')
    if throughput_records:
        df_tp = pd.DataFrame(throughput_records, columns=('run', 'role', 'mbps'))

        # отправители
        sender_df = df_tp[df_tp.role == 'sender']
        if not sender_df.empty:
            plt.figure(figsize=(12, 6))
            labels = [short_label(tag) for tag in sender_df.run]
            plt.bar(labels, sender_df.mbps, alpha=0.7)
            plt.xticks(rotation=90, fontsize=8)
            plt.ylabel('MB/s')
            plt.title('Пропускная способность отправителей')
            plt.tight_layout()
            plt.savefig(results_dir / "throughput_sender.png")
            plt.close()
            print("[INFO] Сохранён throughput_sender.png")

        # получатели
        receiver_df = df_tp[df_tp.role == 'receiver']
        if not receiver_df.empty:
            plt.figure(figsize=(12, 6))
            labels = [short_label(tag) for tag in receiver_df.run]
            plt.bar(labels, receiver_df.mbps, alpha=0.7)
            plt.xticks(rotation=90, fontsize=8)
            plt.ylabel('MB/s')
            plt.title('Пропускная способность получателей')
            plt.tight_layout()
            plt.savefig(results_dir / "throughput_receiver.png")
            plt.close()
            print("[INFO] Сохранён throughput_receiver.png")

    if memory_records:
        df_mem = pd.DataFrame(memory_records, columns=('run', 'role', 'mb'))
        plt.figure(figsize=(12, 6))
        for role in ('sender', 'receiver'):
            subset = df_mem[df_mem.role == role]
            labels = [short_label(tag) for tag in subset.run]
            plt.bar(labels, subset.mb, alpha=0.7, label=role)
        plt.xticks(rotation=90, fontsize=8)
        plt.ylabel('MB')
        plt.title('Использование памяти по ролям (все методы)')
        plt.legend(
            loc='upper left',
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0
        )
        plt.tight_layout()
        plt.subplots_adjust(right=0.8)
        plt.savefig(results_dir / 'memory_usage_comparison.png')
        plt.close()
        print("[INFO] Сохранён memory_usage_comparison.png")

    for method_name, mem_list in memory_by_method.items():
        if method_name == 'boost_int':
            continue
        df_m = pd.DataFrame(mem_list, columns=('run', 'mb'))
        plt.figure(figsize=(8, 4))
        labels = [short_label(tag) for tag in df_m.run]
        plt.bar(labels, df_m.mb)
        plt.xticks(rotation=30, ha='right', fontsize=8)
        plt.ylabel('MB')
        plt.title(f'Использование памяти: {method_name}')
        plt.tight_layout()
        plt.savefig(results_dir / f'{method_name}_memory.png')
        plt.close()
        print(f"[INFO] Сохранён {method_name}_memory.png")

    for method_name, sp_list in speeds_by_method.items():
        if method_name == 'boost_int':
            continue
        df_s = pd.DataFrame(sp_list, columns=('run', 'mbps'))
        plt.figure(figsize=(8, 4))
        labels = [short_label(tag) for tag in df_s.run]
        plt.bar(labels, df_s.mbps)
        plt.xticks(rotation=30, ha='right', fontsize=8)
        plt.ylabel('MB/s')
        plt.title(f'Пропускная способность: {method_name}')
        plt.tight_layout()
        plt.savefig(results_dir / f"{method_name}_throughput.png")
        plt.close()
        print(f"[INFO] Сохранён {method_name}_throughput.png")

def main():

    current_run_dir = run_all_tests()
    plot_results(current_run_dir)


if __name__ == "__main__":
    main()
