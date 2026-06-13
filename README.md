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
| **Platforms** | Per-device Netmiko types: `cisco_ios`, `cisco_xe`, `cisco_nxos`, `cisco_xr`, `cisco_asa`, `cisco_s300`. Show commands parsed to tables via TextFSM where templates exist. |

### Control Center workflow (today)

1. **Choose targets** — filter by Location and Group; select all or individual devices (grouped under 📍 headers).
2. **Choose an action** — pick a category tab (Diagnostics, Port Config, Switch Config, Custom), then a task.
3. **Configure** — fill parameters; port tasks use the visual picker instead of typing `GigabitEthernet1/0/1`.
4. **Review** — toggle CLI Preview to see exact IOS syntax.
5. **Execute** — confirm config changes; push to all selected devices in parallel.

---

## PoE switches

**Not implemented yet.** CiscoMan does not currently expose Power over Ethernet (PoE) actions
such as `power inline auto`, per-port PoE budgets, or `show power inline`.

PoE-capable switches (e.g. Catalyst with inline power) will be supported via new **Action
Cards** in `actions.py` — same pattern as VLAN/trunk tasks: plain-English explanation,
visual port selection, CLI preview, then push. Typical IOS commands to add:

- `power inline auto` / `power inline never` — enable or disable PoE on a port
- `show power inline` — see which ports draw power and how much
- `show power inline police` — PoE budget / allocation (platform-dependent)

If your switch model uses different syntax (IOS vs IOS‑XE vs legacy `power inline`), the
per-device `device_type` field selects the right Netmiko driver.

---

## Roadmap — simpler UI & “learn as you go”

Based on [Cisco SD-WAN UX guidance](https://www.cisco.com/c/en/us/support/docs/routers/sd-wan/222297-quick-start-guide-simplified-configura.html)
(workflow-based config, smart defaults, minimal knobs) and admin-panel UX research
([UX Collective — Designing an Admin Panel](https://uxdesign.cc/designing-an-admin-panel-3e77c19870f4)):

| Principle | Planned direction |
|-----------|-------------------|
| **Task-first, not CLI-first** | “I want to…” wizard: pick ports (checkbox grid) → pick intent (VLAN / PoE / description / shutdown) → preview → run. Fewer nested controls. |
| **Visual port selection** | Checkbox grid or switch-face layout loaded from `show interfaces status`, with status/VLAN/PoE columns — replace multiselect where possible. |
| **Smart defaults** | Pre-fill VLAN IDs, PoE mode, and interface type from live device data when available. |
| **Contextual help** | Inline explanations on every control (already started via Action Cards). |
| **Cheat sheet / Coach** | Searchable reference: network admin terms, IOS commands by category, plain-English “what this does”, linked to executable Action Cards. |
| **Keyword search** | User types e.g. “VLAN”, “PoE”, “trunk” → matching tasks + glossary entries appear together. |
| **Learning loop** | Optional “Practice mode”: CLI preview required before push; post-run output annotated with term definitions. |

PoE, cheat sheet, and the simplified port-checkbox workflow are **planned** — not in this
release. See [Extending](#extending) for adding actions today.

---

## Project layout

| File | Responsibility |
|------|----------------|
| `config.py` | Settings, `.env` loading, PBKDF2 key derivation, Fernet encrypt/decrypt |
| `database.py` | SQLite schema, encrypted CRUD, locations/groups, audit, snapshots, CSV, demo seed |
| `network_utils.py` | TCP scanner, Netmiko exec/config, concurrent engine, demo routing |
| `actions.py` | Action Card catalog — explanations + Jinja2 CLI templates |
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
