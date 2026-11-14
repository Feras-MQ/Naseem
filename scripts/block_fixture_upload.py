"""PlatformIO/SCons guard: illustrative compile pins must never be uploaded."""
from SCons.Script import COMMAND_LINE_TARGETS
from SCons.Errors import UserError

if any(str(target).startswith("upload") or str(target) == "program"
       for target in COMMAND_LINE_TARGETS):
    raise UserError("This is a compile-only display fixture, not verified wiring. Upload is disabled.")
