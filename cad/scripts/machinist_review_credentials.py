"""Private codjiflo-compatible Anthropic pool; no OAuth extraction or key logging."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from filelock import FileLock

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")


@dataclass(frozen=True)
class Credential:
    id: str
    api_key: str = field(repr=False)
    quota_group: str
    fingerprint: str



def _windows_acl(path: Path, *, secure=False, fd=None) -> None:
    """Validate the opened NTFS inode's owner/DACL, not emulated mode bits."""
    if os.name != "nt":
        return
    try:
        import msvcrt
        import win32api
        import win32con
        import win32security
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        flags = win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION
        if secure:
            acl = win32security.ACL()
            inheritance = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE if path.is_dir() else 0
            acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, inheritance, win32con.FILE_ALL_ACCESS, sid)
            win32security.SetNamedSecurityInfo(
                str(path), win32security.SE_FILE_OBJECT,
                win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                None, None, acl, None,
            )
        descriptor = (
            win32security.GetSecurityInfo(msvcrt.get_osfhandle(fd), win32security.SE_FILE_OBJECT, flags)
            if fd is not None else win32security.GetNamedSecurityInfo(str(path), win32security.SE_FILE_OBJECT, flags)
        )
        if descriptor.GetSecurityDescriptorOwner() != sid:
            raise ValueError
        acl = descriptor.GetSecurityDescriptorDacl()
        if acl is None:
            raise ValueError
        allowed = {win32security.ConvertSidToStringSid(sid), "S-1-5-18", "S-1-5-32-544"}
        for index in range(acl.GetAceCount()):
            ace = acl.GetAce(index)
            if ace[0][0] in (win32security.ACCESS_DENIED_ACE_TYPE, win32security.ACCESS_DENIED_OBJECT_ACE_TYPE):
                continue
            if ace[0][0] not in (win32security.ACCESS_ALLOWED_ACE_TYPE, win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE):
                raise ValueError
            if win32security.ConvertSidToStringSid(ace[-1]) not in allowed:
                raise ValueError
    except Exception:
        raise ValueError("Claude credentials: Windows file must have an owner-only DACL") from None

def _private_json(path: Path):
    """Validate the opened inode, refusing symlinks and special files."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return None
    except OSError:
        raise ValueError("Claude credentials: cannot open private file") from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or (os.name != "nt" and stat.S_IMODE(info.st_mode) != 0o600)
                or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
            raise ValueError("Claude credentials: files must be owner-only regular files (0600)")
        _windows_acl(path, fd=fd)
        with os.fdopen(fd, encoding="utf-8") as stream:
            fd = -1
            try:
                return json.load(stream)
            except (ValueError, UnicodeError):
                raise ValueError("Claude credentials: invalid private JSON") from None
    finally:
        if fd >= 0:
            os.close(fd)


def _credentials(value) -> list[Credential]:
    if value is None:
        return []
    if not isinstance(value, dict) or set(value) != {"keys"} or not isinstance(value["keys"], list) or len(value["keys"]) != 3:
        raise ValueError("Claude credentials: configuration must contain exactly three keys")
    result = []
    for entry in value["keys"]:
        if (not isinstance(entry, dict) or set(entry) - {"id", "apiKey", "quotaGroup"}
                or not isinstance(entry.get("id"), str) or not _LABEL.fullmatch(entry["id"])
                or not isinstance(entry.get("apiKey"), str) or not entry["apiKey"]
                or re.search(r"[\s\x00-\x1f\x7f]", entry["apiKey"])
                or not isinstance(entry.get("quotaGroup", entry["id"]), str)
                or not _LABEL.fullmatch(entry.get("quotaGroup", entry["id"]))):
            raise ValueError("Claude credentials: invalid key configuration")
        result.append(Credential(entry["id"], entry["apiKey"], entry.get("quotaGroup", entry["id"]), hashlib.sha256(entry["apiKey"].encode()).hexdigest()))
    if (len({key.id for key in result}) != 3 or len({key.api_key for key in result}) != 3
            or any(key.api_key in {other.id, other.quota_group} for key in result for other in result)):
        raise ValueError("Claude credentials: duplicate credentials or unsafe labels")
    return result


def _directory(path: Path) -> None:
    if not path.exists():
        _directory(path.parent)
        try:
            path.mkdir(mode=0o700)
            _windows_acl(path, secure=True)
        except FileExistsError:
            pass
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Claude credentials: storage parent must be a directory")


class CredentialPool:
    def __init__(self, env=None, *, load=True):
        env = os.environ if env is None else env
        home = Path(env.get("HOME", str(Path.home())))
        self.keys_file = Path(env.get("CODJIFLO_ANTHROPIC_KEYS_FILE", home / ".config/codjiflo/anthropic-keys.json"))
        self.state_file = Path(env.get("CODJIFLO_CLAUDE_STATE_FILE", home / ".local/state/codjiflo/claude-routing.json"))
        self.credentials = _credentials(_private_json(self.keys_file)) if load else []
        self.secrets = {key.api_key for key in self.credentials}

    def redact(self, text: str) -> str:
        variants = self.secrets | {json.dumps(secret, ensure_ascii=True)[1:-1] for secret in self.secrets}
        for secret in sorted(variants, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        return text

    @staticmethod
    def _fresh(key):
        return {"fingerprint": key.fingerprint, "quotaGroup": key.quota_group, "status": "ready", "retryAt": None, "reason": None}

    @contextmanager
    def _state(self, timeout=30):
        _directory(self.state_file.parent)
        deadline = time.monotonic() + min(30, timeout)
        # Use our own advisory-lock inode: codjiflo's O_EXCL lock is not an
        # advisory lock. Its pathname remains reserved for its own lock protocol.
        lock = self.state_file.with_suffix(self.state_file.suffix + ".machinist.lock")
        with FileLock(str(lock), timeout=min(30, timeout), mode=0o600):
            # Cooperate with codjiflo's atomic-create lock as well.
            shared = Path(str(self.state_file) + ".lock")
            while True:
                try:
                    fd = os.open(shared, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    break
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        if timeout <= 30:
                            raise TimeoutError("Claude credential claim exceeded review deadline") from None
                        raise ValueError("Claude credentials: routing lock unavailable") from None
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            try:
                os.write(fd, f"pid={os.getpid()}\n".encode())
                self.credentials = _credentials(_private_json(self.keys_file))
                self.secrets.update(key.api_key for key in self.credentials)
                state = _private_json(self.state_file)
                if state is None:
                    state = {"version": 1, "cursor": 0, "keys": {}}
                self._validate_state(state)
                state["keys"] = {key.id: state["keys"].get(key.id, self._fresh(key))
                                 if state["keys"].get(key.id, {}).get("fingerprint") == key.fingerprint
                                 and state["keys"].get(key.id, {}).get("quotaGroup") == key.quota_group
                                 else self._fresh(key) for key in self.credentials}
                yield state
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.state_file.parent, delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        os.chmod(temporary, 0o600)
                        _windows_acl(temporary, secure=True)
                        json.dump(state, output)
                        output.flush()
                        os.fsync(output.fileno())
                    except BaseException:
                        temporary.unlink(missing_ok=True)
                        raise
                try:
                    temporary.replace(self.state_file)
                finally:
                    temporary.unlink(missing_ok=True)
            finally:
                os.close(fd)
                shared.unlink()

    @staticmethod
    def _validate_state(state):
        valid = (isinstance(state, dict) and set(state) == {"version", "cursor", "keys"}
                 and state["version"] == 1 and type(state["cursor"]) is int and 0 <= state["cursor"] <= 2
                 and isinstance(state["keys"], dict))
        if not valid:
            raise ValueError("Claude credentials: corrupt routing state")
        for label, entry in state["keys"].items():
            if (not _LABEL.fullmatch(label) or not isinstance(entry, dict)
                    or set(entry) != {"fingerprint", "quotaGroup", "status", "retryAt", "reason"}
                    or not isinstance(entry["fingerprint"], str) or not re.fullmatch(r"[a-f0-9]{64}", entry["fingerprint"])
                    or not isinstance(entry["quotaGroup"], str) or not _LABEL.fullmatch(entry["quotaGroup"])
                    or entry["status"] not in {"ready", "cooldown", "exhausted"}
                    or not (entry["retryAt"] is None or type(entry["retryAt"]) is int and entry["retryAt"] >= 0)
                    or not (entry["reason"] is None or isinstance(entry["reason"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", entry["reason"]))
                    or entry["status"] == "ready" and (entry["retryAt"] is not None or entry["reason"] is not None)
                    or entry["status"] == "cooldown" and entry["retryAt"] is None):
                raise ValueError("Claude credentials: corrupt routing state")

    def claim(self, excluded=(), *, required_id=None, required_fingerprint=None, timeout=30):
        if not self.credentials and required_id is None:
            return None
        with self._state(timeout=timeout) as state:
            now = int(time.time() * 1000)
            for offset in range(len(self.credentials)):
                index = (state["cursor"] + offset) % len(self.credentials)
                key = self.credentials[index]
                entry = state["keys"][key.id]
                if entry["retryAt"] is not None and entry["retryAt"] <= now:
                    entry.update(self._fresh(key))
                if required_id is not None and (key.id != required_id or key.fingerprint != required_fingerprint):
                    continue
                if key.id not in excluded and entry["status"] == "ready":
                    state["cursor"] = (index + 1) % len(self.credentials)
                    return key
        if required_id is not None:
            raise ValueError("Claude continuation credential is unavailable or rotated")
        return None

    def unavailable(self, key: Credential, quota: dict, *, timeout=30):
        with self._state(timeout=timeout) as state:
            if not any(current == key for current in self.credentials):
                return
            for current in self.credentials:
                if current.quota_group != key.quota_group:
                    continue
                entry = state["keys"][current.id]
                retry = quota["retryAt"]
                if entry["status"] != "ready" and (entry["retryAt"] is None or retry is not None and entry["retryAt"] > retry):
                    continue
                entry.update(quota)
