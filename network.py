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
    running_event,
    log_dir,
    all_devices_log,
    failed_devices,
    lock,
):
    if not running_event.is_set():
        return

    try:
        device = {
            "device_type": device_type,
            "ip": ip,
            "username": username,
            "password": password,
            "timeout": 20,
            "session_timeout": 20,
            "fast_cli": False,
        }

        with lock:  # Синхронизация записи
            with open(all_devices_log, "a") as f_global:
                f_global.write(f"{datetime.now()} - Попытка подключения к {ip}\n")

        error_occurred = False
        result_queue.put(f"{ip}: Connecting...\n")
        with ConnectHandler(**device) as conn:
            if not running_event.is_set():
                return
            prompt = conn.find_prompt()
            hostname = prompt.strip("<>#")
            expect_string = rf"[<[]*{hostname}.*[>\]#]"

            device_log = f"{log_dir}/{hostname}_{ip}.log"

            with lock:  # Синхронизация записи
                with open(device_log, "a") as f_dev, open(
                    all_devices_log, "a"
                ) as f_global:
                    f_dev.write(
                        f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n"
                    )
                    f_global.write(
                        f"{datetime.now()} - Успешно подключились к {ip} ({hostname})\n"
                    )

            result_queue.put(f"{ip}: Connected!\n")
            conn.config_mode()

            for cmd in commands:
                if not running_event.is_set():
                    break
                result_queue.put(f"{ip}: send command {cmd}\n")
                result = conn.send_command(cmd, expect_string=expect_string)
                log_entry = f"Command: {cmd}\n{result}\n\n"
                with lock:  # Синхронизация записи
                    with open(device_log, "a") as f_dev, open(
                        all_devices_log, "a"
                    ) as f_global:
                        f_dev.write(f"{datetime.now()} - {log_entry}")
                        f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

                if "error" in result.lower() or "unrecognized" in result.lower():
                    with lock:  # Синхронизация записи
                        with open(device_log, "a") as f_dev, open(
                            all_devices_log, "a"
                        ) as f_global:
                            f_dev.write(
                                f"{datetime.now()} - Ошибка при выполнении команды. Прекращаем выполнение.\n"
                            )
                            f_global.write(
                                f"{datetime.now()} - {ip}: Ошибка при выполнении команды. Прекращаем выполнение.\n"
                            )
                    error_occurred = True
                    break
            if not error_occurred:
                # Обработка commit
                try:
                    commit_output = conn.commit()
                    log_entry = f"Commit: {commit_output}\n"
                except Exception as e:
                    commit_output = f"Failed to commit: {str(e)}"
                    log_entry = f"Commit error: {commit_output}\n"
                with lock:
                    with open(device_log, "a") as f_dev, open(
                        all_devices_log, "a"
                    ) as f_global:
                        f_dev.write(f"{datetime.now()} - {log_entry}")
                        f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

                # Обработка exit_config_mode
                try:
                    exit_output = conn.exit_config_mode()
                    log_entry = f"Exit config mode: {exit_output}\n"
                except Exception as e:
                    exit_output = f"Failed to exit config mode: {str(e)}"
                    log_entry = f"Exit config mode error: {exit_output}\n"
                with lock:
                    with open(device_log, "a") as f_dev, open(
                        all_devices_log, "a"
                    ) as f_global:
                        f_dev.write(f"{datetime.now()} - {log_entry}")
                        f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

                # Обработка save_config (оставляем как в вашем примере)
                try:
                    save_output = conn.save_config()
                    log_entry = f"Save config: {save_output}\n"
                except Exception as e:
                    save_output = f"Failed to save config: {str(e)}"
                    log_entry = f"Save config error: {save_output}\n"
                with lock:
                    with open(device_log, "a") as f_dev, open(
                        all_devices_log, "a"
                    ) as f_global:
                        f_dev.write(f"{datetime.now()} - {log_entry}")
                        f_global.write(f"{datetime.now()} - {ip}: {log_entry}")

            if running_event.is_set():
                if error_occurred:
                    result_queue.put(f"{ip}: Error during command execution\n")
                else:
                    result_queue.put(f"{ip}: Success\n")
    except Exception as e:
        error_msg = f"{ip}: Error - {str(e)}\n"
        with lock:  # Синхронизация записи в общий лог, если нужно
            with open(all_devices_log, "a") as f_global:
                f_global.write(f"{datetime.now()} - {error_msg}")
        # Добавляем IP и причину в список неудачных подключений
        reason = (
            "Authentication failed"
            if "authentication" in str(e).lower()
            else (
                "Connection timed out"
                if "tcp connection" in str(e).lower()
                else "Unknown error"
            )
        )
        failed_devices.append((ip, reason))
        result_queue.put(error_msg)
