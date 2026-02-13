"""RADIUS server synchronization and CoA helpers."""
import os
from typing import Optional

from fastapi import HTTPException
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import DisconnectACK, DisconnectNAK, DisconnectRequest
from pyrad.client import Timeout as PyradTimeout

from db import execute_radius


RADIUS_RELAY_ID = os.getenv("RADIUS_RELAY_ID", "bng-01")
RADIUS_USERGROUP_PRIORITY = int(os.getenv("RADIUS_USERGROUP_PRIORITY", 1))
RADIUS_CHECK_PASSWORD = os.getenv("RADIUS_CHECK_PASSWORD", "testing123")

RADIUS_DOWNLOAD_ATTRIBUTE = os.getenv("RADIUS_DOWNLOAD_ATTRIBUTE", "OSS-Download-Speed")
RADIUS_UPLOAD_ATTRIBUTE = os.getenv("RADIUS_UPLOAD_ATTRIBUTE", "OSS-Upload-Speed")
RADIUS_ATTRIBUTE_OP = os.getenv("RADIUS_ATTRIBUTE_OP", ":=")

COA_PORT = int(os.getenv("COA_PORT", 3799))
COA_SECRET = os.getenv("RADIUS_SECRET", "testing123").encode()
COA_DICTIONARY = os.getenv("COA_DICTIONARY", "/opt/backend/radius/dictionary")


def service_username(circuit_id: str, remote_id: str, relay_id: str | None = None) -> str:
    """Build RADIUS username from service identifiers."""
    rid = relay_id or RADIUS_RELAY_ID
    return f"{rid}/{remote_id}/{circuit_id}".replace("|", "=7C")


def sync_radius_group_for_plan(plan_name: str, download_speed: int, upload_speed: int) -> None:
    """Sync plan speed attributes to RADIUS group."""
    execute_radius(
        "DELETE FROM radgroupreply WHERE groupname = %(groupname)s "
        "AND attribute IN (%(download_attr)s, %(upload_attr)s)",
        {
            "groupname": plan_name,
            "download_attr": RADIUS_DOWNLOAD_ATTRIBUTE,
            "upload_attr": RADIUS_UPLOAD_ATTRIBUTE,
        },
    )
    execute_radius(
        """
        INSERT INTO radgroupreply (groupname, attribute, op, value)
        VALUES
          (%(groupname)s, %(download_attr)s, %(op)s, %(download_value)s),
          (%(groupname)s, %(upload_attr)s, %(op)s, %(upload_value)s)
        """,
        {
            "groupname": plan_name,
            "download_attr": RADIUS_DOWNLOAD_ATTRIBUTE,
            "upload_attr": RADIUS_UPLOAD_ATTRIBUTE,
            "op": RADIUS_ATTRIBUTE_OP,
            "download_value": str(download_speed),
            "upload_value": str(upload_speed),
        },
    )


def delete_radius_group_for_plan(plan_name: str) -> None:
    """Delete RADIUS group for plan."""
    execute_radius(
        "DELETE FROM radgroupreply WHERE groupname = %(groupname)s",
        {"groupname": plan_name},
    )
    # Backward-compat cleanup for prior versions that wrote speeds into groupcheck.
    execute_radius(
        "DELETE FROM radgroupcheck WHERE groupname = %(groupname)s",
        {"groupname": plan_name},
    )


def upsert_radius_usergroup(username: str, plan_name: str) -> None:
    """Associate RADIUS user with a plan group."""
    execute_radius(
        "DELETE FROM radusergroup WHERE username = %(username)s",
        {"username": username},
    )
    execute_radius(
        """
        INSERT INTO radusergroup (username, groupname, priority)
        VALUES (%(username)s, %(groupname)s, %(priority)s)
        """,
        {
            "username": username,
            "groupname": plan_name,
            "priority": RADIUS_USERGROUP_PRIORITY,
        },
    )


def delete_radius_usergroup(username: str) -> None:
    """Remove RADIUS user from all groups."""
    execute_radius(
        "DELETE FROM radusergroup WHERE username = %(username)s",
        {"username": username},
    )


def upsert_radius_usercheck(username: str) -> None:
    """Set RADIUS user password."""
    execute_radius(
        "DELETE FROM radcheck WHERE username = %(username)s AND attribute = 'Cleartext-Password'",
        {"username": username},
    )
    execute_radius(
        """
        INSERT INTO radcheck (username, attribute, op, value)
        VALUES (%(username)s, 'Cleartext-Password', ':=', %(password)s)
        """,
        {"username": username, "password": RADIUS_CHECK_PASSWORD},
    )


def delete_radius_usercheck(username: str) -> None:
    """Delete RADIUS user password entry."""
    execute_radius(
        "DELETE FROM radcheck WHERE username = %(username)s",
        {"username": username},
    )


def send_disconnect_request(nas_ip: str, session_id: str, username: Optional[str] = None) -> dict:
    """Send CoA Disconnect-Request to a NAS."""
    if not os.path.exists(COA_DICTIONARY):
        raise HTTPException(status_code=500, detail=f"RADIUS dictionary not found: {COA_DICTIONARY}")

    client = Client(
        server=nas_ip,
        coaport=COA_PORT,
        secret=COA_SECRET,
        dict=Dictionary(COA_DICTIONARY),
        retries=1,
        timeout=2,
    )

    req = client.CreateCoAPacket(code=DisconnectRequest)
    req["Acct-Session-Id"] = session_id
    req["NAS-IP-Address"] = nas_ip
    if username:
        req["User-Name"] = username

    try:
        reply = client.SendPacket(req)
    except PyradTimeout:
        raise HTTPException(status_code=504, detail="CoA disconnect timeout")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"CoA disconnect send failed: {e}")

    if reply.code == DisconnectACK:
        return {"success": True, "reply_code": "Disconnect-ACK"}
    if reply.code == DisconnectNAK:
        return {"success": False, "reply_code": "Disconnect-NAK"}
    return {"success": False, "reply_code": f"Unexpected-{reply.code}"}
