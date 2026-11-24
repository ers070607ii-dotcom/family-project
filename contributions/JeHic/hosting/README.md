# Family Budget Tracker — Local hosting

This contribution provides a repeatable way to host the existing website on a team member's PC using Python and Waitress (a WSGI server). The original project ZIP is not changed. A separate local runtime holds the extracted application, virtual environment, SQLite database and uploads. Runtime files are excluded from Git.

## Ubuntu / Linux

From the root of the family-project repository:

```bash
sudo apt install python3 python3-venv python3-pip
cd contributions/JeHic/hosting
python3 deploy.py setup
python3 deploy.py check
python3 deploy.py start
```

Open http://127.0.0.1:8000 on the host. Stop with Ctrl+C. Setup requires internet access to install Python dependencies. It is only necessary once, unless dependencies change.

## Windows

Install Python 3 from python.org with the Python launcher, then run in PowerShell from the repository root:

```powershell
cd contributions/JeHic/hosting
py -3 deploy.py setup
py -3 deploy.py check
py -3 deploy.py start
```

Application dependencies must support the installed Python version and operating system. Linux commands below use `python3`; substitute `py -3` on Windows.

## Access from another PC or phone

1. Connect both devices to the same trusted Wi-Fi/network. Stop the local server, then run `python3 deploy.py start --lan` on the host.
2. On Ubuntu, run `hostname -I` in another terminal. On Windows, use `ipconfig`. Identify the IPv4 address of the active Wi-Fi/Ethernet connection (for example, 192.168.1.42).
3. On the other device, open `http://192.168.1.42:8000` (replace the example IP). Test with dummy data. The browser connects to the same app and database on the host.
4. If the connection fails, check the host firewall, correct network/IP, and whether the Wi-Fi isolates clients. A personal hotspot can be a useful alternative if permitted.

If UFW is enabled on Ubuntu, permit only the local subnet; adapt the example to your actual network:

```bash
sudo ufw status
sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp
```

Remove this example rule when no longer needed:

```bash
sudo ufw delete allow from 192.168.1.0/24 to any port 8000 proto tcp
```

On Windows, restrict any firewall exception to the private network/local subnet. Do not disable the firewall. Do not forward router ports or expose this service to the public internet. LAN mode listens on all IPv4 interfaces; restrict access with the firewall. HTTP is unencrypted, so use test accounts and dummy budget data only. Before real use, review the original app's secrets, authentication, authorization, CSRF protections and upload handling; configure HTTPS and secure storage.

If port 8000 is occupied, use `python3 deploy.py start --port 8080 --lan` and change the browser URL accordingly.

## Data and maintenance

- `.runtime/website/budget.db`: local SQLite database (if the app uses the bundled path).
- `.runtime/website/static/uploads/`: local uploaded files.
- `.runtime/venv/`: installed Python dependencies.
- Running setup again does not overwrite the existing website or database. It reinstalls dependencies from the extracted requirements file. To deploy a newer website archive, stop the server, back up the runtime (particularly the database and uploads), and review any database migrations before replacing the extracted site. Do not commit runtime data.
- For a consistent simple file backup, stop the server first, then copy the database and uploads to a secure backup location. For live SQLite backups use its backup API or a tested backup solution. One PC should be the active host; multiple independent copies do not synchronize automatically.
- The host must remain powered on, awake and connected. Ctrl+C stops the service.

## Optional automatic startup on Linux

After setup and manual testing, create `~/.config/systemd/user/family-budget.service` (create the directory if needed). Replace the example `ExecStart` path with the absolute path to this contribution's deploy.py; the quotes are needed if the path has spaces.

```ini
[Unit]
Description=Family Budget Tracker

[Service]
Type=simple
ExecStart=/usr/bin/python3 "/home/USER/Desktop/family-host/contributions/JeHic/hosting/deploy.py" start --lan
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now family-budget.service
systemctl --user status family-budget.service
```

This starts at user login by default. Stop and disable with `systemctl --user disable --now family-budget.service`. See logs with `journalctl --user -u family-budget.service`. Do not run a second manual instance on the same port. Omit `--lan` for local-only service.

## Assignment verification

- Show successful `deploy.py setup` and `deploy.py check` output.
- Show the server running and the website in the host browser.
- Show the website opened from a second device using the host's LAN IP and a dummy record visible on both devices.
- Explain that Waitress serves the Python application, the host stores the SQLite database, and clients use HTTP through the local network.

## Compatibility note

The launcher expects the archive and directory names currently used by the repository and an importable WSGI object named `app` in `app.py`. If the original application initializes its database only inside `if __name__ == '__main__'`, needs extra system packages, or uses another entry point, the application may need an adjustment. The check command verifies imports; a browser test is still required. The hosting scripts do not change application source code or claim to fix application security.
