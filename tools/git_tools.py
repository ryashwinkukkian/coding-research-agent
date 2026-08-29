import subprocess

ALLOWED_SUBCOMMANDS = {"log", "ls-files", "show"}

MAX_OUTPUT_SIZE = 3 * 1024


def clone_repo(repo_url: str, dest: str) -> str:
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, dest],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        return f"Error cloning repo: {result.stderr[:500]}"
    return f"Cloned {repo_url} into {dest}"


def run_git(repo_path: str, subcommand: str, args: list[str]) -> str:
    if subcommand not in ALLOWED_SUBCOMMANDS:
        return f"Error: git subcommand '{subcommand}' is not in the allowlist {ALLOWED_SUBCOMMANDS}. Refusing to run."

    for arg in args:
        if arg.startswith("--upload-pack") or arg.startswith("--exec"):
            return "Error: argument rejected for safety."

    result = subprocess.run(
        ["git", subcommand] + args,
        cwd=repo_path, capture_output=True, text=True, timeout=15,
        encoding="utf-8", errors="replace",
    )
    output = result.stdout if result.returncode == 0 else result.stderr

    if output is None:
        return "Error: git command produced no readable output (possibly binary content)."

    if len(output.encode("utf-8")) > MAX_OUTPUT_SIZE:
        output = output.encode("utf-8")[:MAX_OUTPUT_SIZE].decode("utf-8", errors="ignore") + "\n\n[TRUNCATED]"
    return output