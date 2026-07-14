"""
IBM i user profile authentication.

Credential validation
---------------------
Calls QSYS/QSYVATUP (QsyValidateUserProfileAndPassword) via itoolkit.
This is IBM i's native credential validation API — it checks the profile
exists, is enabled, and the password is correct, without altering the
current job's profile.  itoolkit is pure Python and calls IBM i XML Service.

Group lookup
------------
After successful validation, queries QSYS2.USER_INFO using ibm_db_dbi
with a trusted local connection (no credentials needed, same pattern as
other apps on this IBM i).  Maps IBM i group profiles to portal roles
via config/groups.yaml.

Install:
    pip install itoolkit
    ibm_db + ibm_db_dbi: yum install python3-ibm_db, then symlink both .so/.py
"""
import logging
import yaml

logger = logging.getLogger(__name__)

_group_roles: dict = {}
_user_class_roles: dict = {}
_admin_users: list = []
_default_roles: list = ["portal_users"]
_ibmi_system: str = "172.16.1.2"


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def load_groups(path: str) -> None:
    global _group_roles, _user_class_roles, _admin_users, _default_roles
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _group_roles = {
            k.upper(): list(v)
            for k, v in (data.get("group_roles") or {}).items()
        }
        # User class keys keep their * prefix, uppercased
        _user_class_roles = {
            k.upper(): list(v)
            for k, v in (data.get("user_class_roles") or {}).items()
        }
        _admin_users = [u.upper() for u in (data.get("admin_users") or [])]
        _default_roles = data.get("default_roles") or ["portal_users"]
        logger.info(
            "Loaded IBM i role map: %d group(s), %d user class(es), %d admin(s) — from %s",
            len(_group_roles), len(_user_class_roles), len(_admin_users), path,
        )
    except FileNotFoundError:
        logger.warning("groups.yaml not found at %s", path)
    except Exception as exc:
        logger.error("Failed to load groups.yaml: %s", exc)


def set_ibmi_system(system: str) -> None:
    global _ibmi_system
    _ibmi_system = system


# ---------------------------------------------------------------------------
# Authentication — single entry point
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str):
    """
    Validate IBM i credentials via QSYVATUP and return user info with roles.
    Returns {"username": ..., "roles": [...]} on success, None on failure.
    """
    uname = username.strip().upper()

    if not _validate_via_qsyvatup(uname, password):
        return None

    profile = _get_ibmi_profile(uname)
    roles = _resolve_roles(uname, profile["groups"], profile["user_class"])
    return {"username": uname, "roles": roles}


# ---------------------------------------------------------------------------
# Credential validation via QSYVATUP
# ---------------------------------------------------------------------------

def _validate_via_qsyvatup(username: str, password: str) -> bool:
    """
    Call QSYS/QSYVATUP (QsyValidateUserProfileAndPassword).

    Passes an error code structure.  If bytesAvailable > 0 after the call,
    the credentials were invalid (CPF22E4 or similar message).
    Any exception during the call is treated as a failure.
    """
    try:
        from itoolkit import iToolKit, iPgm, iData, iDS
        from itoolkit.transport import DirectTransport
    except ImportError:
        logger.error("itoolkit is not installed — run: pip install itoolkit")
        return False

    pwd = password
    pwd_len = len(pwd)

    try:
        itk = iToolKit()

        pgm = iPgm("QSYVATUP", "QSYS")

        # Parm 1: user profile name — 10-char, padded
        pgm.addParm(iData("usrprf", "10A", username.ljust(10)))

        # Parm 2: password — variable length char
        pgm.addParm(iData("pwd", f"{max(pwd_len, 1)}A", pwd))

        # Parm 3: length of password — 4-byte binary
        pgm.addParm(iData("pwdLen", "10i0", str(pwd_len)))

        # Parm 4: error code structure (provide 16 bytes so API writes msgid)
        errds = iDS("errcode")
        errds.addData(iData("bytesProv",  "10i0", "16"))
        errds.addData(iData("bytesAvail", "10i0", "0"))
        errds.addData(iData("msgid",      "7A",   ""))
        errds.addData(iData("rsvd",       "1A",   ""))
        pgm.addParm(errds)

        itk.add(pgm)
        itk.call(DirectTransport())

        result = itk.dict_out("QSYVATUP")
        err    = result.get("errcode", {})

        bytes_avail = int(err.get("bytesAvail", "0") or "0")
        msg_id      = err.get("msgid", "").strip()

        if bytes_avail > 0:
            logger.warning(
                "IBM i credential check failed for %s: %s", username, msg_id
            )
            return False

        logger.info("IBM i credential check passed for %s", username)
        return True

    except Exception as exc:
        # Any exception (bad profile, locked account, XML service error)
        # is treated as authentication failure — log for diagnostics
        logger.warning(
            "IBM i credential check error for %s: %s",
            username, str(exc)[:120],
        )
        return False


# ---------------------------------------------------------------------------
# Group lookup via ibm_db_dbi (trusted local connection)
# ---------------------------------------------------------------------------

def _get_ibmi_profile(username: str) -> dict:
    """
    Query QSYS2.USER_INFO for user class, primary group, and supplemental groups.
    Returns a dict with keys: user_class, groups (list of group profile names).
    Uses ibm_db_dbi.connect() — trusted auth, no credentials needed.
    """
    try:
        import ibm_db_dbi
    except ImportError:
        logger.warning(
            "ibm_db_dbi not available — profile lookup skipped for %s", username
        )
        return {"user_class": None, "groups": []}

    conn = None
    try:
        conn = ibm_db_dbi.connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT USER_CLASS_NAME,
                   GROUP_PROFILE_NAME,
                   SUPPLEMENTAL_GROUP_LIST
            FROM   QSYS2.USER_INFO
            WHERE  USER_NAME = ?
            """,
            (username,),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            logger.warning("No QSYS2.USER_INFO row found for %s", username)
            return {"user_class": None, "groups": []}

        user_class = (row[0] or "").strip().upper() or None

        groups = []
        primary = (row[1] or "").strip().upper()
        if primary and primary not in ("*NONE", ""):
            groups.append(primary)

        supplemental = (row[2] or "").strip()
        if supplemental and supplemental.upper() not in ("*NONE", ""):
            groups.extend(
                g.strip().upper()
                for g in supplemental.split()
                if g.strip().upper() not in ("*NONE", "")
            )

        logger.debug(
            "IBM i profile for %s: class=%s groups=%s", username, user_class, groups
        )
        return {"user_class": user_class, "groups": groups}

    except Exception as exc:
        logger.error(
            "Failed to query QSYS2.USER_INFO for %s: %s", username, exc
        )
        return {"user_class": None, "groups": []}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# Keep old name as alias so middleware import still works
def _get_ibmi_groups(username: str) -> list:
    return _get_ibmi_profile(username)["groups"]


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

def _resolve_roles(username: str, groups: list, user_class: str = None) -> list:
    """
    Build the portal role list for a user.

    Checks user class first, then group profiles.  Roles accumulate from
    all matching sources.  Falls back to default_roles only if nothing matched.
    admin_users always get 'admins' appended.
    """
    roles: list = []
    matched = False

    # 1. User class (e.g. *PGMR → developers)
    if user_class:
        class_roles = _user_class_roles.get(user_class.upper(), [])
        if class_roles:
            matched = True
            for role in class_roles:
                if role not in roles:
                    roles.append(role)

    # 2. Group profiles (primary + supplemental)
    for group in groups:
        group_mapped = _group_roles.get(group.upper(), [])
        if group_mapped:
            matched = True
            for role in group_mapped:
                if role not in roles:
                    roles.append(role)

    # 3. Fallback
    if not matched:
        roles = list(_default_roles)

    # 4. Admin override
    if username in _admin_users and "admins" not in roles:
        roles.append("admins")

    return roles


# ---------------------------------------------------------------------------
# Shims
# ---------------------------------------------------------------------------

def validate_credentials(username: str, password: str) -> bool:
    return authenticate(username, password) is not None


def get_user_roles(username: str) -> list:
    roles = list(_default_roles)
    if username in _admin_users and "admins" not in roles:
        roles.append("admins")
    return roles
