#!/usr/bin/env python3
import paramiko
import hashlib
import time
import sys

print("=== Teltonika Router Auto Configuration (Windows Compatible) ===\n")

# ---------------- USER INPUT ----------------
ROUTER_IP = "192.168.1.1"
SSH_USER = "root"

print(f"Default Router IP: {ROUTER_IP}")
router = input("Enter router model (RUT200/RUTM51): ").strip().upper()
current_password = input("Enter default password: ").strip()

# Take machine ID
machine_id = input("Enter machine ID: ").strip()

def generate_password(machine_id):
    """Generate MD5 hash (same as echo 'id' | md5sum)"""
    return hashlib.md5(machine_id.encode('utf-8')).hexdigest()

# Generate passwords
new_admin_password = generate_password(machine_id) + "@T"
wifi_password = generate_password(machine_id)

print(f"\nGenerated Admin Password: {new_admin_password}")
print(f"Generated WiFi Password : {wifi_password}")

wifi_ssid = machine_id  # You can change this to input() if you want custom SSID

# ---------------- SSH CONNECT ----------------
print(f"\nConnecting to {ROUTER_IP} via SSH...")

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(
        hostname=ROUTER_IP,
        username=SSH_USER,
        password=current_password,
        timeout=30,
        look_for_keys=False,
        allow_agent=False
    )

    # Open interactive shell (needed for passwd prompts)
    shell = client.invoke_shell()
    time.sleep(2)  # Give time to get shell prompt

    print("Logged in successfully.\n")

    # ---------------- CHANGE PASSWORD ----------------
    print("Updating passwords (admin & root)...")

    def send_command(cmd, wait=1.5):
        shell.send(cmd + "\n")
        time.sleep(wait)
        output = shell.recv(65535).decode('utf-8', errors='ignore')
        print(output.strip())
        return output

    # Change admin password
    send_command("passwd admin", 1)
    time.sleep(0.5)
    send_command(new_admin_password, 0.5)
    time.sleep(0.5)
    send_command(new_admin_password, 1.5)

    # Change root password (same as admin)
    send_command("passwd root", 1)
    time.sleep(0.5)
    send_command(new_admin_password, 0.5)
    time.sleep(0.5)
    send_command(new_admin_password, 1.5)

    send_command("uci set system.@system[0].initial_password_set=1")
    send_command("uci commit system")

    print("Passwords updated successfully.\n")

    if router == "RUT200":
    # ---------------- WAN → LAN ----------------
        print("Converting WAN port to LAN...")

        send_command("uci add_list network.br_lan.ports='eth0.2'")
        send_command("uci delete network.wan.device")
        send_command("uci delete network.wan6.device")
        send_command("uci commit network")

        print("Restarting network (router will be temporarily unreachable)...")
        print("Please wait up to 60 seconds...")

        # time.sleep(60)  # Give some time before connection drops

        print("Network restart triggered. Waiting for router to come back...\n")

        # ---------------- WIFI CONFIG ----------------
        # Note: We need to reconnect after network restart for WiFi changes
        print("Reconnecting to apply WiFi settings...")

        # time.sleep(25)  # Wait for router to stabilize (adjust if needed)

        # Reconnect with NEW password
        client.close()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ROUTER_IP,
            username=SSH_USER,
            password=new_admin_password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )

        shell = client.invoke_shell()
        time.sleep(2)

        print("Reconnected with new password.")

        print("Applying WiFi settings...")

        send_command(f"uci set wireless.default_radio0.ssid='{wifi_ssid}'")
        send_command(f"uci set wireless.default_radio0.key='{wifi_password}'")
        send_command("uci set wireless.default_radio0.encryption='psk2'")
        send_command("uci commit wireless")

        print("Reloading WiFi...")
        shell.send("wifi reload\n")
        time.sleep(5)

        print("\nConfiguration completed successfully!")
        print(f"New WiFi SSID : {wifi_ssid}")
        print(f"New WiFi Password: {wifi_password}")
        print(f"New Admin/Root Password: {new_admin_password}")
        print("\nReconnect to the router using the new WiFi credentials.")
        # shell.send("/etc/init.d/network restart\n")

    elif router == "RUTM51":
        print("Converting WAN port to LAN...")

        send_command("uci add_list network.br_lan.ports='wan'")
        send_command("uci delete network.wan.device")
        send_command("uci delete network.wan6.device")
        send_command("uci commit network")

        print("Restarting network (router will be temporarily unreachable)...")
        print("Please wait up to 60 seconds...")
        print("Network restart triggered. Waiting for router to come back...\n")

        # ---------------- WIFI CONFIG ----------------
        # Note: We need to reconnect after network restart for WiFi changes 
        print("Reconnecting with new password...")

        # Reconnect with NEW password
        client.close()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ROUTER_IP,
            username=SSH_USER,
            password=new_admin_password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )

        shell = client.invoke_shell()
        time.sleep(2)

        print("Reconnected with new password.")

        print("Applying WiFi settings...")

        send_command(f"uci set wireless.default_radio0.disabled='1'") #Disable 2g
        send_command(f"uci set wireless.default_radio1.ssid='{wifi_ssid}'") #Set 5g ssid
        send_command(f"uci set wireless.default_radio1.key='{wifi_password}'") #Set 5g password
        send_command("uci set wireless.default_radio1.encryption='psk2'")
        send_command("uci commit wireless")

        print("Reloading WiFi...")
        shell.send("wifi reload\n")
        time.sleep(5)

        print("\nConfiguration completed successfully!")
        print(f"New WiFi SSID : {wifi_ssid}")
        print(f"New WiFi Password: {wifi_password}")
        print(f"New Admin/Root Password: {new_admin_password}")
        print("\nReconnect to the router using the new WiFi credentials.")

except paramiko.AuthenticationException:
    print("\nError: Authentication failed. Check default password.")
except paramiko.SSHException as e:
    print(f"\nSSH Error: {e}")
except Exception as e:
    print(f"\nUnexpected Error: {e}")
finally:
    try:
        client.close()
    except:
        pass

print("\nScript finished.")