# 🛰️ CiscoMan

A secure, GUI-first network management web app for automating **Cisco IOS** devices
(switches/routers) without touching the CLI. Scan your network, build an encrypted
device inventory, and push commands or config to one or many devices at once — with
plain-English explanations and a live CLI preview so you always know what you're sending.

Built with **Streamlit + Netmiko + SQLite + Cryptography (Fernet)**.

CiscoMan is designed for **system administrators who prefer a GUI over the CLI** —
especially those with general networking experience but limited Cisco IOS exposure.

---

## Features (current)

| Area | What you get |
|------|----------------|
| **Security** | Master password gates the app. Fernet key is **derived** from it (PBKDF2, 600k iterations) and never stored on disk. SSH passwords, enable secrets, and config snapshots are encrypted at rest. Auto-logout on inactivity. |
| **Discovery** | Privilege-free **TCP port-22 scan** (works on Windows, no admin/Npcap). CIDR, single IP, or `a.b.c.d-e` ranges. |
| **Inventory** | Encrypted device store with **Location → Group** hierarchy, per-device `device_type`, connection test, CSV import/export (secrets never exported). |
| **Control Center** | Category **tabs**, task radio buttons, **visual port picker** (load ports from switch or build by type/stack/module/port), multi-port and range support, explanation panel, **Show CLI Preview**, concurrent mass execution with progress + per-device output. |
| **Demo mode** | 🧪 Offline simulator — 5 demo switches across 3 locations, stateful config (changes show up in `show run`), no real SSH. |
| **Backups** | Encrypted `show running-config` snapshots + unified diff. |
| **Audit** | Every command/config push logged with output and status. |
| **Coach** | Searchable **cheat sheet**: network terms, plain-English definitions, keyword search, jump to Control Center tasks. |
| **PoE** | Show PoE status; enable/disable `power inline auto/never` on ports (Action Cards). |
| **Routing & Tunnels** | SVI IP assignment, static routes, GRE tunnel wizard, show IP route. |
| **Security** | Extended ACL rule builder (permit/deny lines). |

| **Platforms** | Per-device Netmiko types: `cisco_ios`, `cisco_xe`, `cisco_nxos`, `cisco_xr`, `cisco_asa`, `cisco_s300`. Show commands parsed to tables via TextFSM where templates exist. |

### Port selection (Control Center)

- **Checkbox from switch** — load live port list, tick checkboxes (All / Connected only shortcuts).
- **Build port name** — type + stack/module/port number inputs, range support.
- **Load VLAN list** — pick VLAN from device for SVI and access-VLAN tasks.

---

## Implementation phases

| Phase | Status | Scope |
|-------|--------|--------|
| **1** | Done | Security, scan, inventory, locations, Control Center, demo simulator, backups, audit |
| **2** | Done | Checkbox port picker, Coach/cheat sheet search, PoE, SVI, static routes |
| **3** | Started | GRE tunnels, extended ACLs; IPsec/DMVPN wizards planned |
| **4** | Planned | QoS, spanning-tree, DHCP snooping, 802.1X, NX-OS/ASA subsets |

**North star:** expose essentially all CLI capability through guided UI — built incrementally via Action Cards. Use **Custom** commands for anything not yet templated.

### Control Center workflow

1. **Choose targets** — filter by Location and Group; select devices (grouped under 📍 headers).
2. **Choose an action** — category tabs (Diagnostics, Port Config, **PoE**, Switch Config, **Routing & Tunnels**, **Security**, Custom).
3. **Configure** — checkbox port picker, VLAN loader, or manual fields.
4. **Review** — CLI Preview shows exact IOS syntax.
5. **Execute** — confirm config changes; concurrent push with per-device output.

Use **Coach** to search terms (e.g. “PoE”, “tunnel”) and jump here pre-filled.

---

## PoE switches

**Implemented (Phase 2):** `show power inline`, enable/disable PoE per port via Action Cards
with checkbox port selection. Demo simulator models PoE state in running-config.

Still planned: PoE budget policing, per-class limits (platform-specific).

---

## Roadmap — simpler UI & “learn as you go”

| Principle | Status |
|-----------|--------|
| Checkbox port selection | Done |
| Cheat sheet / Coach with keyword search | Done |
| Task-first “I want to…” wizard | Planned (next UX pass) |
| IPsec/DMVPN tunnel wizards | Planned (Phase 3+) |
| Full CLI parity via Action Cards | Ongoing — add actions in `actions.py` |

PoE, cheat sheet, and checkbox ports shipped in this release. Next: unified intent wizard
and deeper tunnel/crypto workflows.

---

## Project layout

| File | Responsibility |
|------|----------------|
| `config.py` | Settings, `.env` loading, PBKDF2 key derivation, Fernet encrypt/decrypt |
| `database.py` | SQLite schema, encrypted CRUD, locations/groups, audit, snapshots, CSV, demo seed |
| `network_utils.py` | TCP scanner, Netmiko exec/config, concurrent engine, demo routing |
| `actions.py` | Action Card catalog — explanations + Jinja2 CLI templates |
| `cheatsheet.py` | Searchable glossary + keyword index linking terms to Action Cards |
| `simulator.py` | Offline stateful Cisco IOS simulator for demo/testing |
| `app.py` | Streamlit UI — Login, Scanner, Inventory, Control Center, Backups, Audit, Settings |

---

## Setup

```powershell
cd C:\Users\nphol\Projects\CiscoMan

# Optional: virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Optional tuning
copy .env.example .env

python -m streamlit run app.py
```

### First launch

- **First-time setup** — create a master password (8+ characters). There is **no default
  password. This is the only credential that unlocks stored device secrets.
- **Forgot password?** Delete `network_inventory.db` in the project folder and restart
  the app to run setup again (stored device passwords become unrecoverable — by design).

### Demo mode (no hardware)

**Inventory → 🧪 Add demo devices** seeds five simulated switches across three locations
(`HQ Tbilisi`, `Branch Batumi`, `Warehouse Rustavi`). They respond to real commands via
`simulator.py`, including stateful config changes. Marked 🧪; never opens SSH.

---

## Security notes

- Stores live SSH credentials. **Run on localhost only** — do not expose Streamlit to the LAN.
- Master password loss = unrecoverable encrypted credentials.
- `network_inventory.db`, `.env`, and `*.key` are git-ignored — never commit them.
- Config snapshots may contain sensitive data; encrypted at rest with your session key.

---

## Extending

Add an `Action` to `ACTIONS` in `actions.py` — explanation, Jinja2 `template`, typed
`params` (use `kind="interface"` for port fields). UI, preview, execution, and audit
logging pick it up automatically.

Example categories already in the catalog: Diagnostics, Port Config, Switch Config,
Custom (17 tasks). PoE actions will follow the same pattern when added.

---

## License

Private / internal use unless otherwise specified by the repository owner.
