"""Action Cards module for CiscoMan."""

from actions.base import Action, Param
from actions.cisco import CISCO_ACTIONS
from actions.fiberstore_fsosv2 import FSOS_ACTIONS
from actions.fiberstore_networkos import NETWORKOS_ACTIONS

# Combined list for backward compatibility
ALL_ACTIONS = CISCO_ACTIONS + FSOS_ACTIONS + NETWORKOS_ACTIONS
ACTIONS_BY_ID = {a.id: a for a in ALL_ACTIONS}

def get_actions_for_device(device_type: str) -> list[Action]:
    """Return actions that support the given device type."""
    if device_type.startswith("cisco") or device_type in ["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"]:
        return CISCO_ACTIONS
    elif device_type == "fiberstore_fsosv2":
        return FSOS_ACTIONS
    elif device_type == "fiberstore_networkos":
        return NETWORKOS_ACTIONS
    else:
        # Fallback to all actions (filtered by platform in app)
        return ALL_ACTIONS

def get_action(action_id: str) -> Action:
    return ACTIONS_BY_ID[action_id]

def platform_family(device_type: str) -> str:
    mapping = {
        "cisco_ios": "ios",
        "cisco_xe": "ios",
        "cisco_nxos": "nxos",
        "cisco_xr": "xr",
        "cisco_asa": "asa",
        "cisco_s300": "ios",
        "fiberstore_fsosv2": "fiberstore_fsosv2",
        "fiberstore_networkos": "fiberstore_networkos",
    }
    return mapping.get(device_type, "ios")

def action_visible(action: Action, device_types: set[str]) -> bool:
    if "all" in action.platforms:
        return True
    families = {platform_family(dt) for dt in device_types}
    return bool(families & set(action.platforms))

def filter_actions(action_list: list[Action], device_types: set[str]) -> list[Action]:
    if not device_types:
        return action_list
    return [a for a in action_list if action_visible(a, device_types)]

# Backward compatibility exports
ACTIONS = ALL_ACTIONS
CATEGORIES = list(dict.fromkeys(a.category for a in ALL_ACTIONS))