"""Build OUI database from IEEE data.

Downloads the latest IEEE OUI registry and builds a SQLite database.
Run this to update the bundled OUI database.
"""

import sqlite3
import re
import sys
from pathlib import Path

# Sample OUI data - in production this would download from IEEE
# For now, include common network vendors
SAMPLE_OUI_DATA = """
00:00:0C	Cisco Systems, Inc
00:01:42	Cisco Systems, Inc
00:01:43	Cisco Systems, Inc
00:01:63	Cisco Systems, Inc
00:01:64	Cisco Systems, Inc
00:01:96	Cisco Systems, Inc
00:01:97	Cisco Systems, Inc
00:01:C7	Cisco Systems, Inc
00:01:C9	Cisco Systems, Inc
00:02:16	Cisco Systems, Inc
00:02:17	Cisco Systems, Inc
00:02:3D	Cisco Systems, Inc
00:02:4A	Cisco Systems, Inc
00:02:4B	Cisco Systems, Inc
00:02:7D	Cisco Systems, Inc
00:02:7E	Cisco Systems, Inc
00:02:B9	Cisco Systems, Inc
00:02:BA	Cisco Systems, Inc
00:02:FC	Cisco Systems, Inc
00:02:FD	Cisco Systems, Inc
00:03:31	Cisco Systems, Inc
00:03:32	Cisco Systems, Inc
00:03:6B	Cisco Systems, Inc
00:03:6C	Cisco Systems, Inc
00:03:9F	Cisco Systems, Inc
00:03:A0	Cisco Systems, Inc
00:03:E3	Cisco Systems, Inc
00:03:E4	Cisco Systems, Inc
00:03:FD	Cisco Systems, Inc
00:03:FE	Cisco Systems, Inc
00:04:27	Cisco Systems, Inc
00:04:28	Cisco Systems, Inc
00:04:4D	Cisco Systems, Inc
00:04:4E	Cisco Systems, Inc
00:04:6D	Cisco Systems, Inc
00:04:6E	Cisco Systems, Inc
00:04:9A	Cisco Systems, Inc
00:04:9B	Cisco Systems, Inc
00:04:C0	Cisco Systems, Inc
00:04:C1	Cisco Systems, Inc
00:04:DD	Cisco Systems, Inc
00:04:DE	Cisco Systems, Inc
00:05:00	Cisco Systems, Inc
00:05:01	Cisco Systems, Inc
00:05:31	Cisco Systems, Inc
00:05:32	Cisco Systems, Inc
00:05:5E	Cisco Systems, Inc
00:05:5F	Cisco Systems, Inc
00:05:73	Cisco Systems, Inc
00:05:74	Cisco Systems, Inc
00:05:9A	Cisco Systems, Inc
00:05:9B	Cisco Systems, Inc
00:05:DC	Cisco Systems, Inc
00:05:DD	Cisco Systems, Inc
00:06:28	Cisco Systems, Inc
00:06:52	Cisco Systems, Inc
00:06:53	Cisco Systems, Inc
00:06:7C	Cisco Systems, Inc
00:06:C1	Cisco Systems, Inc
00:06:D6	Cisco Systems, Inc
00:06:D7	Cisco Systems, Inc
00:06:F6	Cisco Systems, Inc
00:07:0D	Cisco Systems, Inc
00:07:0E	Cisco Systems, Inc
00:07:4F	Cisco Systems, Inc
00:07:50	Cisco Systems, Inc
00:07:7D	Cisco Systems, Inc
00:07:84	Cisco Systems, Inc
00:07:85	Cisco Systems, Inc
00:07:B3	Cisco Systems, Inc
00:07:B4	Cisco Systems, Inc
00:07:EB	Cisco Systems, Inc
00:07:EC	Cisco Systems, Inc
001C:0E	Juniper Networks
001C:F0	Juniper Networks
001D:B5	Juniper Networks
0019:E2	Juniper Networks
001B:C0	Juniper Networks
2C:21:72	Juniper Networks
2C:6B:F5	Juniper Networks
3C:61:04	Juniper Networks
3C:8A:B0	Juniper Networks
3C:94:D5	Juniper Networks
40:B4:F0	Juniper Networks
44:F4:77	Juniper Networks
4C:96:14	Juniper Networks
54:1E:56	Juniper Networks
54:4B:8C	Juniper Networks
5C:45:27	Juniper Networks
5C:5E:AB	Juniper Networks
64:64:9B	Juniper Networks
64:87:88	Juniper Networks
78:19:F7	Juniper Networks
78:FE:3D	Juniper Networks
84:18:88	Juniper Networks
84:B5:9C	Juniper Networks
88:A2:5E	Juniper Networks
88:E0:F3	Juniper Networks
00:01:E6	Hewlett Packard
00:01:E7	Hewlett Packard
00:02:A5	Hewlett Packard
00:04:EA	Hewlett Packard
00:08:02	Hewlett Packard
00:08:83	Hewlett Packard
00:0D:9D	Hewlett Packard
00:0E:7F	Hewlett Packard
00:0F:20	Hewlett Packard
00:0F:61	Hewlett Packard
00:10:83	Hewlett Packard
00:10:E3	Hewlett Packard
00:11:0A	Hewlett Packard
00:11:85	Hewlett Packard
00:12:79	Hewlett Packard
00:13:21	Hewlett Packard
00:14:38	Hewlett Packard
00:14:C2	Hewlett Packard
00:15:60	Hewlett Packard
00:15:E9	Hewlett Packard
00:16:35	Hewlett Packard
00:16:B9	Hewlett Packard
00:17:08	Hewlett Packard
00:17:A4	Hewlett Packard
00:18:71	Hewlett Packard
00:18:FE	Hewlett Packard
00:19:BB	Hewlett Packard
00:1A:4B	Hewlett Packard
00:1B:3F	Hewlett Packard
00:1B:78	Hewlett Packard
00:1C:2E	Hewlett Packard
00:1C:C4	Hewlett Packard
00:1E:0B	Hewlett Packard
00:1F:28	Hewlett Packard
00:1F:29	Hewlett Packard
00:1F:FE	Hewlett Packard
00:21:5A	Hewlett Packard
00:21:F7	Hewlett Packard
00:22:64	Hewlett Packard
00:23:7D	Hewlett Packard
00:23:CD	Aruba, a Hewlett Packard Enterprise Company
00:24:6C	Aruba, a Hewlett Packard Enterprise Company
00:25:61	Aruba, a Hewlett Packard Enterprise Company
00:26:5A	Aruba, a Hewlett Packard Enterprise Company
00:1A:1E	H3C Technologies Co., Limited
00:E0:FC	H3C Technologies Co., Limited
48:0E:EC	H3C Technologies Co., Limited
54:89:98	H3C Technologies Co., Limited
58:69:6C	H3C Technologies Co., Limited
70:5A:0F	H3C Technologies Co., Limited
74:54:7D	H3C Technologies Co., Limited
78:D3:8D	H3C Technologies Co., Limited
88:3F:D3	H3C Technologies Co., Limited
9C:8E:99	H3C Technologies Co., Limited
A4:4C:11	H3C Technologies Co., Limited
A4:DC:BE	H3C Technologies Co., Limited
B8:AF:67	H3C Technologies Co., Limited
BC:3F:8F	H3C Technologies Co., Limited
D0:54:A6	H3C Technologies Co., Limited
D4:85:64	H3C Technologies Co., Limited
D8:49:0B	H3C Technologies Co., Limited
E4:D3:F1	H3C Technologies Co., Limited
F0:7E:62	H3C Technologies Co., Limited
F4:4E:05	H3C Technologies Co., Limited
00:01:6C	Foxconn
00:02:72	Intel Corporation
00:03:47	Intel Corporation
00:04:23	Intel Corporation
00:07:E9	Intel Corporation
00:0C:F1	Intel Corporation
00:0D:3A	Intel Corporation
00:0E:0C	Intel Corporation
00:11:11	Intel Corporation
00:12:F0	Intel Corporation
00:13:02	Intel Corporation
00:13:20	Intel Corporation
00:13:CE	Intel Corporation
00:13:E8	Intel Corporation
00:15:00	Intel Corporation
00:15:17	Intel Corporation
00:16:6F	Intel Corporation
00:16:76	Intel Corporation
00:16:EA	Intel Corporation
00:16:EB	Intel Corporation
00:18:DE	Intel Corporation
00:19:D1	Intel Corporation
00:19:D2	Intel Corporation
00:1B:21	Intel Corporation
00:1B:77	Intel Corporation
00:1C:BF	Intel Corporation
00:1D:E0	Intel Corporation
00:1D:E1	Intel Corporation
00:1E:64	Intel Corporation
00:1E:65	Intel Corporation
00:1E:67	Intel Corporation
00:1F:3A	Intel Corporation
00:1F:3B	Intel Corporation
00:1F:3C	Intel Corporation
00:21:5C	Intel Corporation
00:21:5D	Intel Corporation
00:21:6A	Intel Corporation
00:21:6B	Intel Corporation
00:22:FA	Intel Corporation
00:22:FB	Intel Corporation
00:23:14	Intel Corporation
00:23:15	Intel Corporation
00:24:D6	Intel Corporation
00:24:D7	Intel Corporation
00:25:64	Intel Corporation
00:25:65	Intel Corporation
00:26:82	Intel Corporation
00:27:0E	Intel Corporation
00:27:10	Intel Corporation
00:27:19	Intel Corporation
00:27:1A	Intel Corporation
00:50:56	VMware, Inc.
00:0C:29	VMware, Inc.
00:05:69	VMware, Inc.
00:1C:14	VMware, Inc.
"""


def build_oui_database(output_path: Path):
    """Build OUI SQLite database."""
    print(f"Building OUI database at {output_path}")
    
    # Create database
    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oui (
            prefix TEXT PRIMARY KEY,
            vendor TEXT NOT NULL
        )
    """)
    
    # Parse and insert OUI data
    count = 0
    for line in SAMPLE_OUI_DATA.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        
        # Format: "00:00:0C	Cisco Systems, Inc"
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        
        prefix = parts[0].replace(':', '').replace('-', '').upper()
        vendor = parts[1].strip()
        
        if len(prefix) == 6:
            cursor.execute(
                "INSERT OR REPLACE INTO oui (prefix, vendor) VALUES (?, ?)",
                (prefix, vendor)
            )
            count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Inserted {count} OUI entries")
    print(f"Database created successfully: {output_path}")


if __name__ == "__main__":
    output = Path("oui.db")
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    
    build_oui_database(output)
