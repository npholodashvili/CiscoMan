# 🛰️ CiscoMan - Windows Native Desktop Application

A secure, native Windows desktop application for automating **Cisco IOS** devices (switches/routers) without touching the CLI. Built with **PySide6 + Netmiko + SQLite + Cryptography (Fernet)**.

## ✨ What's New in v2.0

- **Native Windows GUI** built with PySide6 (replaces Streamlit web interface)
- **%LOCALAPPDATA% data storage** - database, logs, and SSH known hosts stored in `%LOCALAPPDATA%\CiscoMan`
- **Enhanced security**:
  - Secrets redacted from audit logs
  - SSH host key verification (Trust-On-First-Use)
  - Input validation (IP addresses, VLANs, interface names)
  - Running-config outputs not stored in audit log (size/security)
- **Worker threads** for device operations - UI never freezes
- **Optional Windows Credential Manager** integration (keyring) to remember master password
- **Optional system tray** icon and single-instance lock
- **H3C Comware** (hp_comware) device type support
- **PyInstaller + Inno Setup** packaging - one-click installer

## 📦 Installation

### Option 1: Installer (Recommended)

1. Download `CiscoMan-2.0.0-Setup.exe` from the [Releases](../../releases) page or [GitHub Actions artifacts](../../actions)
2. Run the installer
3. Launch CiscoMan from the Start menu or desktop shortcut

### Option 2: From Source

Requirements:
- **Windows 10/11** (64-bit)
- **Python 3.11+**

```powershell
# Clone the repository
git clone https://github.com/owner/ciscoman.git
cd ciscoman

# Install dependencies
pip install -r requirements-pinned.txt

# Run the application
python -m ciscoman_gui.main
```

## 🚀 First Run

1. **Launch CiscoMan**
2. **Create a master password** (8+ characters)
   - This encrypts all stored device credentials
   - The key is derived from this password and **never saved to disk**
   - ⚠️ **If you lose it, stored credentials are unrecoverable**

3. **Data Location:**
   - **Database**: `%LOCALAPPDATA%\CiscoMan\network_inventory.db`
   - **Logs**: `%LOCALAPPDATA%\CiscoMan\logs\ciscoman.log`
   - **SSH known hosts**: `%LOCALAPPDATA%\CiscoMan\ssh_known_hosts`

   On most systems: `C:\Users\<YourName>\AppData\Local\CiscoMan\`

## 📁 Data Migration

### Migrating from Streamlit Version (v1.x)

If you have an existing `network_inventory.db` from the Streamlit version:

1. **Copy your old database** to the new location:
   ```powershell
   copy "C:\path\to\old\network_inventory.db" "%LOCALAPPDATA%\CiscoMan\network_inventory.db"
   ```

2. **Launch CiscoMan** and log in with your **existing master password**

3. The app will automatically use the migrated database

### Fresh Install

If you're starting fresh:
- CiscoMan will create a new database on first run
- Use the Scanner or manually add devices via Inventory
- Or add **demo devices** (🧪 button) for offline testing

## 🎯 Features

| Area | What you get |
|------|----------------|
| **Security** | Master password gates the app. Fernet key is derived (PBKDF2, 600k iterations) and never stored. SSH passwords, enable secrets, and config snapshots are encrypted at rest. Auto-logout on inactivity. SSH host-key verification (TOFU). Secrets redacted from audit logs. |
| **Discovery** | Privilege-free TCP port-22 scan (works on Windows, no admin/Npcap). CIDR, single IP, or `a.b.c.d-e` ranges. Optional auto-add with explicit opt-in. |
| **Inventory** | Encrypted device store with Location → Group hierarchy, per-device `device_type`, connection test, CSV import/export (secrets never exported). |
| **Control Center** | Category tabs, task radio buttons, visual port picker (load ports from switch or build by type/stack/module/port), multi-port and range support, explanation panel, CLI Preview, concurrent mass execution with progress + per-device output. *(GUI in progress - use Streamlit app.py for now)* |
| **Demo mode** | 🧪 Offline simulator — 5 demo switches across 3 locations, stateful config (changes show up in `show run`), no real SSH. |
| **Backups** | Encrypted `show running-config` snapshots + unified diff. |
| **Audit** | Every command/config push logged with redacted secrets. Running-config outputs excluded for security. |
| **Coach** | Searchable cheat sheet: network terms, plain-English definitions, keyword search, jump to Control Center tasks. *(GUI in progress)* |
| **PoE** | Show PoE status; enable/disable `power inline auto/never` on ports. |
| **Routing & Tunnels** | SVI, static routes, GRE tunnel, IPsec site-to-site wizard, show IP/crypto route. |
| **Layer 2** | DHCP snooping, portfast, BPDU guard, QoS trust DSCP, show STP/DHCP snooping. |
| **Security** | Extended ACL rules, 802.1X port-control auto. |
| **Quick Wizard** | Simplest flow: pick devices → tick ports → choose intent → run. |
| **Platforms** | Per-device Netmiko types: `cisco_ios`, `cisco_xe`, `cisco_nxos`, `cisco_xr`, `cisco_asa`, `cisco_s300`, `hp_comware`. Show commands parsed to tables via TextFSM where templates exist. |

## 🏗️ Architecture

```
ciscoman/
├── ciscoman_core/          # Reusable business logic
│   ├── actions.py          # Action Card catalog (CLI templates + explanations)
│   ├── database.py         # SQLite persistence with encryption
│   ├── config.py           # Settings, key derivation, secret redaction
│   ├── network_utils.py    # TCP scanner, Netmiko exec/config, mass execution
│   ├── simulator.py        # Offline stateful simulator for demo devices
│   ├── wizard.py           # Quick Wizard intent definitions
│   ├── tunnel_wizard.py    # DMVPN hub/spoke wizard
│   ├── cheatsheet.py       # Searchable glossary + keyword index
│   ├── port_panel.py       # Visual switch-face port grid
│   ├── input_validation.py # IP/VLAN/interface validation
│   └── ssh_hostkeys.py     # SSH host key TOFU store
│
├── ciscoman_gui/           # PySide6 native GUI
│   ├── main.py             # Entry point
│   ├── windows/            # Main window, pages (login, scanner, inventory, ...)
│   ├── widgets/            # Reusable UI components
│   └── workers/            # QThread workers for device operations
│
├── tests/                  # pytest test suite
│   ├── test_actions.py     # Action rendering tests
│   ├── test_crypto.py      # Encryption/decryption round-trip tests
│   └── test_validation.py  # Input validation tests
│
├── installer/              # Inno Setup installer script
├── ciscoman.spec           # PyInstaller build spec
├── requirements-pinned.txt # Pinned dependencies for reproducible builds
├── app.py                  # Legacy Streamlit web app (still functional)
└── README-WINDOWS.md       # This file
```

## 🧪 Demo Mode (No Hardware Required)

1. Open **Inventory**
2. Click **🧪 Add demo devices**
3. Five simulated switches appear across three locations (`HQ Tbilisi`, `Branch Batumi`, `Warehouse Rustavi`)
4. They respond to real commands via `simulator.py`, including stateful config changes
5. Marked 🧪; never opens SSH

## 🔧 Development

### Running from Source

```powershell
python -m ciscoman_gui.main
```

### Running Tests

```powershell
pytest tests/ -v
```

### Building Executable

```powershell
# Build with PyInstaller
pyinstaller ciscoman.spec

# Output: dist/CiscoMan/CiscoMan.exe
```

### Building Installer

1. Install [Inno Setup 6.2+](https://jrsoftware.org/isinfo.php)
2. Compile `installer\ciscoman-setup.iss`
3. Output: `installer\Output\CiscoMan-2.0.0-Setup.exe`

## 🤖 CI/CD

GitHub Actions workflow (`.github/workflows/build-windows.yml`):
- Runs on `windows-latest`
- Installs dependencies
- Runs pytest tests
- Builds exe with PyInstaller
- Builds installer with Inno Setup
- Uploads both as artifacts

Artifacts are retained for 90 days and available on the [Actions](../../actions) page.

## 🔐 Security Notes

- **Run on localhost only** if using the legacy Streamlit web app (app.py)
- **Master password loss = unrecoverable encrypted credentials** (by design)
- `network_inventory.db`, `.env`, `*.key` are git-ignored — never commit them
- Config snapshots may contain sensitive data; encrypted at rest with your session key
- **SSH host key verification** (TOFU) protects against MITM attacks
- **Secrets redacted** from audit logs (PSKs, passwords, SNMP communities, etc.)
- **Running-config outputs** not logged in audit (size + security)
- **Input validation** prevents command injection (IP, VLAN, interface names)

## 🛠️ Extending

Add an `Action` to `ACTIONS` in `ciscoman_core/actions.py`:
- Plain-English `explanation`
- Jinja2 `template` for CLI commands
- Typed `params` (use `kind="interface"` for port fields)

UI, preview, execution, and audit logging pick it up automatically.

Example categories: Diagnostics, Port Config, PoE, Switch Config, Routing & Tunnels, Layer 2, Security, Custom.

## 📝 Known Limitations (v2.0 Beta)

- **GUI migration in progress**: Login, Scanner, and Inventory are functional. Other pages (Control Center, Wizards, Coach, Backups, Audit, Settings) show placeholders. Use the legacy Streamlit app (`streamlit run app.py`) for full functionality until GUI migration is complete.
- **Worker threads not yet implemented**: Device operations will block the UI. This will be fixed before the final v2.0 release.
- **Windows Credential Manager (keyring) support**: Implemented in `ciscoman_core` but not yet wired to GUI.
- **System tray icon**: Planned but not yet implemented.
- **Single-instance lock**: Planned but not yet implemented.
- **H3C Comware actions**: Device type added to config, but no platform-specific actions yet.

## 📄 License

Private / internal use unless otherwise specified by the repository owner.

---

**Questions?** Open an issue on GitHub or check the logs at `%LOCALAPPDATA%\CiscoMan\logs\ciscoman.log`.
