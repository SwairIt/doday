"""Real redeploy: git pull + clear pyc + restart."""

import subprocess
import time

import paramiko

SSH_PASS = ""
with open(".env") as f:
    for line in f:
        if line.startswith("SSH_PASS="):
            SSH_PASS = line.split("=", 1)[1].strip()
            break

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507 — deploy script, host known
c.connect(
    "getdoday.ru",
    port=22,
    username="getdoday",
    password=SSH_PASS,
    timeout=20,
    look_for_keys=False,
    allow_agent=False,
)

print(">>> git pull")
stdin, stdout, stderr = c.exec_command(
    "cd /var/www/getdoday/data/www/getdoday.ru/app && "
    "git fetch origin --quiet 2>&1 && "
    "git reset --hard origin/master 2>&1 | tail -1 && "
    "git log -1 --oneline",
    timeout=30,
)
print(stdout.read().decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))

print(">>> clear pyc")
c.exec_command(
    "find /var/www/getdoday/data/www/getdoday.ru/app -name '__pycache__' -type d "
    "-exec rm -rf {} + 2>/dev/null",
    timeout=10,
)[1].read()

print(">>> kill")
stdin, stdout, stderr = c.exec_command(
    "for pid in $(lsof -ti:8011 2>/dev/null); do kill -9 $pid; done; sleep 1; "
    "ss -tln | grep ':8011' && echo STILL || echo CLEAN",
    timeout=10,
)
print(stdout.read().decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))

print(">>> start")
stdin, stdout, stderr = c.exec_command(
    "python3 /var/www/getdoday/data/start_uvicorn.py", timeout=10
)
print("PID:", stdout.read().decode().strip())

time.sleep(4)
print(">>> /health")
stdin, stdout, stderr = c.exec_command("curl -sS -m 5 http://127.0.0.1:8011/health", timeout=10)
print(stdout.read().decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))

c.close()

print(">>> external smoke-test https://getdoday.ru")
rc = subprocess.run(
    ["uv", "run", "python", "scripts/smoke_test.py", "https://getdoday.ru"],  # noqa: S607 — uv on PATH
    check=False,
).returncode
if rc != 0:
    print("!!! smoke-test failed — investigate before continuing", flush=True)
    raise SystemExit(rc)
print(">>> smoke-test green")
