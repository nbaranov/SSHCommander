from netmiko import ConnectHandler
import os
from datetime import datetime


def process_device(
    ip,
    username,
    password,
    device_type,
    commands,
    result_queue,
    running,
    global_log_file,
):
    if not running:
        return

    log_dir = "device_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not global_log_file:
        global_log_file = f"{log_dir}/global_log_{timestamp}.log"

    try:
        device = {
            "device_type": device_type,
            "ip": ip,
            "username": username,
            "password": password,
        }

        with open(global_log_file, "a") as f_global:
            f_global.write(f"{datetime.now()} - Попытка подключения к {ip}\n")

        error_occurred = False
        result_queue.put(f"{ip}: Connecting...\n")
        with ConnectHandler(**device) as conn:
            prompt = conn.find_prompt()
            hostname = prompt.strip("<>#")
            expect_string = rf"[<[]*{hostname}.*[>\]#]*"
            device_log = f"{log_dir}/{hostname}_{ip}_{timestamp}.log"

            with open(device_log, "a") as f_dev, open(global_log_file, "a") as f_global:
                f_dev.write(
                    f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n"
                )
                f_global.write(
                    f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n"
                )

                result_queue.put(f"{ip}: Connected!\n")
                result_queue.put(f"{ip}: Config mode\n")
                conn.config_mode()
                result_queue.put(f"{ip}: Config mode active\n")

                for cmd in commands:
                    if not running:
                        break
                    result_queue.put(f"{ip}: send command {cmd}\n")
                    result = conn.send_command(cmd, expect_string=expect_string)
                    log_entry = f"Command: {cmd}\n{result}\n\n"
                    f_dev.write(f"{datetime.now()} - {log_entry}")
                    f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

                    if "error" in result.lower() or "unrecognized" in result.lower():
                        f_dev.write(
                            f"{datetime.now()} - Ошибка при выполнении команды. Прекращаем выполнение.\n"
                        )
                        f_global.write(
                            f"{datetime.now()} - {ip}: Ошибка при выполнении команды. Прекращаем выполнение.\n"
                        )
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
        with open(global_log_file, "a") as f_global:
            f_global.write(f"{datetime.now()} - {error_msg}")
        result_queue.put(error_msg)
