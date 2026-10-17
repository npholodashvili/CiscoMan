"""Quick Wizard intents — map user-friendly tasks to Action Cards.

Used by the Quick Wizard page: pick ports → pick intent → fill minimal fields → run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    from ciscoman_core import actions
except ImportError:
    import actions


@dataclass
class WizardIntent:
    id: str
    label: str
    explanation: str
    action_id: str
    """Action Card to render CLI from."""
    extra_params: list[str] = field(default_factory=list)
    """Param keys on the Action Card filled by the wizard (besides interface)."""


INTENTS: list[WizardIntent] = [
    WizardIntent(
        "vlan",
        "Change access VLAN",
        "Assign selected ports to an access VLAN.",
        "set_access_vlan",
        ["vlan"],
    ),
    WizardIntent(
        "description",
        "Set port description",
        "Label ports so you remember what is plugged in.",
        "set_description",
        ["description"],
    ),
    WizardIntent(
        "poe_on",
        "Enable PoE",
        "Turn on Power over Ethernet on selected ports.",
        "poe_enable",
        [],
    ),
    WizardIntent(
        "poe_off",
        "Disable PoE",
        "Stop delivering power on selected ports.",
        "poe_disable",
        [],
    ),
    WizardIntent(
        "port_up",
        "Enable port (no shutdown)",
        "Administratively turn ports on.",
        "port_updown",
        [],  # enable=True handled in wizard
    ),
    WizardIntent(
        "port_down",
        "Disable port (shutdown)",
        "Administratively turn ports off.",
        "port_updown",
        [],
    ),
    WizardIntent(
        "portfast",
        "Enable spanning-tree portfast",
        "Skip STP listening/learning on access ports — standard for end-user ports.",
        "set_portfast",
        [],
    ),
    WizardIntent(
        "bpduguard",
        "Enable BPDU guard",
        "Disable port if it receives BPDUs — protects against rogue switches.",
        "set_bpduguard",
        [],
    ),
    WizardIntent(
        "dhcp_trust",
        "Trust DHCP snooping",
        "Trust DHCP messages on port (for phones/APs behind the switch).",
        "set_dhcp_snoop_trust",
        [],
    ),
    WizardIntent(
        "trust_dscp",
        "Trust QoS DSCP",
        "Honor DSCP markings on incoming frames for QoS queuing.",
        "set_trust_dscp",
        [],
    ),
    WizardIntent(
        "dot1x",
        "Enable 802.1X (port-control auto)",
        "Require authentication before port opens (needs RADIUS server configured).",
        "dot1x_port",
        [],
    ),
]

INTENTS_BY_ID = {i.id: i for i in INTENTS}


def build_cli(intent_id: str, interface_expr: str, values: dict) -> tuple[actions.Action, list[str]]:
    intent = INTENTS_BY_ID[intent_id]
    action = actions.get_action(intent.action_id)
    payload = {"interface": interface_expr, **values}
    if intent_id == "port_up":
        payload["enable"] = True
    elif intent_id == "port_down":
        payload["enable"] = False
    return action, action.render(payload)
