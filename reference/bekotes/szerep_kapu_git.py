"""git options that rewrite history or settings (for szerep_kapu._bash): force-push, -c, config, sparse-checkout."""


def _git(words, root, cwd):
    out, i = [], 1
    while i < len(words) and words[i].startswith("-"):
        if words[i] in ("-c", "--config-env") or words[i].startswith("--config-env="):
            out.append("git-config")
        i += 2 if words[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    sub, rest = (words[i], words[i + 1:]) if i < len(words) else ("", [])
    if sub == "push" and any(w in ("-f", "--mirror") or w.startswith(("--force", "+")) for w in rest):
        out.append("force-push")
    if sub == "config" and not (set(rest) & {"--get", "--get-all", "--list", "-l", "--get-regexp"}
                                or set(rest) & {"user.name", "user.email"}):
        out.append("git-config")
    if sub == "sparse-checkout" and rest[:1] != ["list"]:
        out.append("git-config")
    return out
