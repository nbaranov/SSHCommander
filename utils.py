import re


def validate_input(username, password, ip_text, cmd_text):
    if not username:
        return "You need enter Username"
    if not password:
        return "You need enter  Password"

    ip_pattern = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    ip_list = re.findall(ip_pattern, ip_text)
    if not ip_list:
        return "No valid IP addresses found"

    if not cmd_text.strip():
        return "Please enter at least one command"
    return None
