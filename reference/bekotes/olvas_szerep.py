"""The active role's Read denials, applied by `olvas` itself (h1-16, 20261022-192044).

The role guard sees only the Bash command `bekotes.py olvas …`, not the files olvas opens,
so olvas checks every file against the same deny list (szerep_rules.match). The role is
resolved the way the guard resolves it (MENTAT_ROLE if installed, else roles.default);
any resolution error refuses the read (fail closed)."""
import szerep_pin
import szerep_rules

import hely


def rules(repo):
    """(role, Read-deny rules); (None, []) when the agent has no roles."""
    try:
        res = szerep_pin.resolve(repo)
        if not res.get("role"):
            return None, []
        deny = szerep_rules.parse_deny(szerep_pin.role_file(repo, res).read_text())
    except (szerep_rules.GuardError, OSError, ValueError, KeyError, TypeError) as e:
        raise hely.HelyError("a szerep nem oldható fel (%s), ezért az olvas nem olvas" % e)
    return res["role"], [r for r in deny if r.startswith("Read(")]


def denied(repo, deny, path):
    """The first Read rule that forbids `path`, else None."""
    return next((r for r in deny if szerep_rules.match(r, "Read", {"file_path": str(path)}, repo, fold=True)), None)
