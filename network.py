from netmiko import ConnectHandler
import os
from datetime import datetime


def process_device(ip, username, password, device_type, commands, result_queue, running, log_dir, all_devices_log, failed_log_file, lock):
    if not running:
        return
    
    try:
        device = {
            "device_type": device_type,
            "ip": ip,
            "username": username,
            "password": password,
            "timeout": 20,
            "session_timeout": 20,
            "fast_cli": False 
        }

        with lock:  # Синхронизация записи
            with open(all_devices_log, "a") as f_global:
                f_global.write(f"{datetime.now()} - Попытка подключения к {ip}\n")

        error_occurred = False
        result_queue.put(f"{ip}: Connecting...\n")
        with ConnectHandler(**device) as conn:
            prompt = conn.find_prompt()
            hostname = prompt.strip("<>#")
            expect_string = rf"[<[]*{hostname}.*[>\]#]"

            device_log = f"{log_dir}/{hostname}_{ip}.log"

            with lock:  # Синхронизация записи
                with open(device_log, "a") as f_dev, open(all_devices_log, "a") as f_global:
                    f_dev.write(f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n")
                    f_global.write(f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n")

            result_queue.put(f"{ip}: Connected!\n")
            conn.config_mode()

            for cmd in commands:
                if not running:
                    break
                result_queue.put(f"{ip}: send command {cmd}\n")
                result = conn.send_command(cmd, expect_string=expect_string)
                log_entry = f"Command: {cmd}\n{result}\n\n"
                with lock:  # Синхронизация записи
                    with open(device_log, "a") as f_dev, open(all_devices_log, "a") as f_global:
                        f_dev.write(f"{datetime.now()} - {log_entry}")
                        f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

                if "error" in result.lower() or "unrecognized" in result.lower():
                    with lock:  # Синхронизация записи
                        with open(device_log, "a") as f_dev, open(all_devices_log, "a") as f_global:
                            f_dev.write(f"{datetime.now()} - Ошибка при выполнении команды. Прекращаем выполнение.\n")
                            f_global.write(f"{datetime.now()} - {ip}: Ошибка при выполнении команды. Прекращаем выполнение.\n")
                    error_occurred = True
                    break
            if not error_occurred:
                conn.save_config()

            if running:
                if error_occurred:
                    result_queue.put(f"{ip}: Error during command execution\n")
                else:
                    result_queue.put(f"{ip}: Success\n")
    except Exception as e:
        error_msg = f"{ip}: Error - {str(e)}\n"
        with lock:  # Синхронизация записи
            with open(all_devices_log, "a") as f_global:
                f_global.write(f"{datetime.now()} - {error_msg}")
            with open(failed_log_file, "a", newline='') as f_failed:
                reason = ("Authentication failed" if "authentication" in str(e).lower() else
                          "Connection timed out" if "tcp connection" in str(e).lower() else
                          "Unknown error")
                f_failed.write(f"{ip},{reason}\n")
        result_queue.put(error_msg)