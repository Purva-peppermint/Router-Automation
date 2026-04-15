#!/usr/bin/env python3
import subprocess
import pexpect
# import getpass
import sys

print("=== Teltonika RUT200 Auto Configuration ===\n")

# ---------------- USER INPUT ----------------
ROUTER_IP = input("Enter router IP address: ").strip()
SSH_USER = "root"

current_password = input("Enter default password: ")

# 🔹 Take machine ID
machine_id = input("Enter machine ID: ").strip()

def generate_password(machine_id):
    cmd = f"echo '{machine_id}' | md5sum"
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True
    )
    return result.stdout.split()[0] 
# 🔹 Generate passwords
new_admin_password = generate_password(machine_id) + "@T"
wifi_password = generate_password(machine_id)

print(f"\nGenerated Admin Password: {new_admin_password}")
print(f"Generated WiFi Password : {wifi_password}")

wifi_ssid = input("Enter new WiFi SSID: ").strip()

# ---------------- SSH CONNECT ----------------
print(f"\nConnecting to {ROUTER_IP}...")

try:
    ssh = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {SSH_USER}@{ROUTER_IP}",
        encoding='utf-8',
        timeout=30
    )
    ssh.logfile = sys.stdout

    i = ssh.expect([
        "Are you sure you want to continue connecting",
        "[Pp]assword:",
        "#",
        pexpect.EOF,
        pexpect.TIMEOUT
    ])

    if i == 0:
        ssh.sendline("yes")
        ssh.expect("[Pp]assword:")
        ssh.sendline(current_password)
    elif i == 1:
        ssh.sendline(current_password)
    elif i == 2:
        pass
    else:
        print("SSH connection failed.")
        sys.exit(1)

    ssh.expect("#")
    print("\nLogged in successfully.")

    # ---------------- CHANGE PASSWORD ----------------
    print("\nUpdating passwords...")

    ssh.sendline("passwd admin")
    ssh.expect("New password:", timeout=10)
    ssh.sendline(new_admin_password)
    ssh.expect("Retype password:", timeout=10)
    ssh.sendline(new_admin_password)
    ssh.expect("#")

    ssh.sendline("passwd root")
    ssh.expect("New password:", timeout=10)
    ssh.sendline(new_admin_password)
    ssh.expect("Retype password:", timeout=10)
    ssh.sendline(new_admin_password)
    ssh.expect("#")

    ssh.sendline("uci set system.@system[0].initial_password_set=1")
    ssh.expect("#")
    ssh.sendline("uci commit system")
    ssh.expect("#")

    print("Password updated.")

    # ---------------- WAN → LAN ----------------
    print("\nConverting WAN to LAN...")

    ssh.sendline("uci add_list network.br_lan.ports='eth0.2'")
    ssh.expect("#")
    ssh.sendline("uci delete network.wan.device")
    ssh.expect("#")
    ssh.sendline("uci delete network.wan6.device")
    ssh.expect("#")
    ssh.sendline("uci commit network")
    ssh.expect("#")

    print("Restarting network, Router will be temporarily unreachable...")
    print("This may take up to 1 minute. Please wait...")

    ssh.sendline("/etc/init.d/network restart")

    try:
        ssh.expect("#", timeout=100)
    except:
        print("Network restart triggered.")

    # ---------------- WIFI CONFIG ----------------
    print("\nApplying WiFi settings...")

    ssh.sendline(f"uci set wireless.default_radio0.ssid='{wifi_ssid}'")
    ssh.expect("#")
    ssh.sendline(f"uci set wireless.default_radio0.key='{wifi_password}'")
    ssh.expect("#")
    ssh.sendline("uci set wireless.default_radio0.encryption='psk2'")
    ssh.expect("#")
    ssh.sendline("uci commit wireless")
    ssh.expect("#")

    ssh.sendline("wifi reload")

    try:
        ssh.expect("#", timeout=60)
    except:
        print("WiFi reload triggered.")

    # ---------------- EXIT ----------------
    ssh.sendline("exit")
    

    print("\nConfiguration completed successfully!")
    print("Reconnect to the router using new WiFi credentials.")

    ssh.expect(pexpect.EOF)

# except pexpect.exceptions.TIMEOUT:
#     print("\nTimeout: Router may be slow or rebooting.")

except pexpect.exceptions.EOF:
    print("\nDisconnected (expected if network restarted).")

except Exception as e:
    print(f"\nError: {e}")

finally:
    try:
        ssh.close()
    except:
        pass