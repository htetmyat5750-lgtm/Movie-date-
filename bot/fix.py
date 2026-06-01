"""
Patch hydrogram.errors so pytgcalls can find GroupcallInvalid etc.
Import this before anything else.
"""
import hydrogram.errors as _mod
import hydrogram.errors.exceptions as _exc

_NEED = [
    "GroupcallInvalid", "GroupcallForbidden", "GroupcallAlreadyDiscarded",
    "GroupcallAlreadyStarted", "GroupcallJoinMissing", "GroupcallNotModified",
    "GroupcallSsrcDuplicateMuch", "GroupcallAddParticipantsFailed",
]
for _name in _NEED:
    _src = getattr(_exc, _name, None) or getattr(_exc, _name.replace("call", "Call"), None)
    if _src:
        if not hasattr(_mod, _name):
            setattr(_mod, _name, _src)
        if not hasattr(_exc, _name):
            setattr(_exc, _name, _src)
