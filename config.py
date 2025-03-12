import os
import json
import tempfile


def save_settings(app):
    settings = {
        "username": app.username.get(),
        "device_type": app.device_type.get(),
        "ip_addresses": app.ip_text.get("1.0", "end-1c"),
        "commands": app.cmd_text.get("1.0", "end-1c"),
        "thread_count": app.thread_count.get(),
    }
    temp_file = os.path.join(tempfile.gettempdir(), "net_tool_config.json")
    with open(temp_file, "w") as f:
        json.dump(settings, f)


def load_settings(app):
    temp_file = os.path.join(tempfile.gettempdir(), "net_tool_config.json")
    try:
        with open(temp_file, "r") as f:
            settings = json.load(f)
            app.username.insert(0, settings.get("username", ""))
            app.device_type.set(settings.get("device_type", "huawei"))
            app.ip_text.insert("1.0", settings.get("ip_addresses", ""))
            app.cmd_text.insert("1.0", settings.get("commands", ""))
            app.thread_count.set(settings.get("thread_count", "20"))
    except FileNotFoundError:
        pass
    return temp_file
