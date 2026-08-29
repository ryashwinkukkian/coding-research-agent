import os

MAX_FILE_SIZE = 100 * 1024
MAX_OUTPUT_SIZE = 3 * 1024

IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}

BINARY_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".svg",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".class", ".o",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".db", ".sqlite", ".sqlite3",
    ".whl",
}


def _truncate(text: str) -> str:
    if len(text.encode("utf-8")) <= MAX_OUTPUT_SIZE:
        return text
    truncated = text.encode("utf-8")[:MAX_OUTPUT_SIZE].decode("utf-8", errors="ignore")
    return truncated + f"\n\n[TRUNCATED — output exceeded {MAX_OUTPUT_SIZE} bytes]"


def list_files(repo_path: str, subpath: str = ".") -> str:
    target = os.path.join(repo_path, subpath)
    if not os.path.isdir(target):
        return f"Error: '{subpath}' is not a directory in this repo."

    lines = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_root = os.path.relpath(root, repo_path)
        for f in files:
            lines.append(os.path.join(rel_root, f))

    return _truncate("\n".join(sorted(lines)))


def read_file(repo_path: str, file_path: str) -> str:
    full_path = os.path.join(repo_path, file_path)

    ext = os.path.splitext(file_path)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return f"Error: '{file_path}' appears to be a binary file ({ext}). This tool only reads text files."

    if not os.path.isfile(full_path):
        return f"Error: '{file_path}' does not exist."

    size = os.path.getsize(full_path)
    if size > MAX_FILE_SIZE:
        return f"Error: '{file_path}' is {size} bytes, which exceeds the {MAX_FILE_SIZE}-byte limit. Refusing to read (likely a minified bundle or generated file)."

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading '{file_path}': {e}"

    return _truncate(content)
def largest_files(repo_path: str, subpath: str = ".", top_n: int = 10) -> str:
    target = os.path.join(repo_path, subpath)
    sizes = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            full = os.path.join(root, f)
            try:
                size = os.path.getsize(full)
                sizes.append((os.path.relpath(full, repo_path), size))
            except OSError:
                continue
    sizes.sort(key=lambda x: -x[1])
    lines = [f"{p} — {s:,} bytes" for p, s in sizes[:top_n]]
    return _truncate("\n".join(lines))
