import os
import json
import shutil
import tempfile
import logging

from dotenv import load_dotenv
from openai import OpenAI

from tools.filesystem import list_files, read_file
from tools.git_tools import clone_repo, run_git

load_dotenv()

logging.basicConfig(
    filename="agent.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

MODEL = "openai/gpt-oss-120b"
MAX_ITERATIONS = 15
MAX_TOOL_RESULTS_KEPT = 3  # only the most recent N tool outputs stay in full context

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the repo, optionally under a subdirectory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {"type": "string", "description": "Subdirectory to list, default '.' for repo root."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a specific file in the repo. Refuses files over 100KB and binary files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path relative to repo root, e.g. 'app/main.py'."}
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_git",
            "description": "Run a read-only git command. Only 'log', 'ls-files', and 'show' are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subcommand": {"type": "string", "enum": ["log", "ls-files", "show"]},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Extra arguments, e.g. ['--oneline', '-10'] for log."}
                },
                "required": ["subcommand"],
            },
        },
    },
]


def execute_tool(repo_path: str, name: str, args: dict) -> str:
    if name == "list_files":
        return list_files(repo_path, args.get("subpath", "."))
    elif name == "read_file":
        return read_file(repo_path, args["file_path"])
    elif name == "run_git":
        return run_git(repo_path, args["subcommand"], args.get("args", []))
    else:
        return f"Error: unknown tool '{name}'"


def trim_old_tool_messages(messages):
    """Keep only the most recent MAX_TOOL_RESULTS_KEPT tool outputs in full.
    Older ones are replaced with a short placeholder so a long exploration
    doesn't accumulate unbounded context (and blow past Groq's free-tier
    tokens-per-minute limit)."""
    def _role(m):
        return m.get("role") if isinstance(m, dict) else getattr(m, "role", None)

    tool_indices = [i for i, m in enumerate(messages) if _role(m) == "tool"]
    to_trim = tool_indices[:-MAX_TOOL_RESULTS_KEPT] if len(tool_indices) > MAX_TOOL_RESULTS_KEPT else []
    for i in to_trim:
        if messages[i]["content"] != "[older tool output trimmed to save context]":
            messages[i]["content"] = "[older tool output trimmed to save context]"


def run_agent(repo_path: str, question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a coding research agent. You have tools to explore a cloned git "
                "repository and answer questions about its architecture. Use list_files to "
                "orient yourself, read_file to inspect specific files, and run_git for history "
                "context. Give a clear, specific final answer once you have enough information — "
                "don't keep exploring longer than necessary."
            ),
        },
        {"role": "user", "content": question},
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )
        except Exception as e:
            return f"Stopped after {iteration - 1} iterations due to an API error: {e}"

        msg = response.choices[0].message

        if not msg.tool_calls:
            # model gave a final answer — done
            return msg.content

        messages.append(msg)

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            logging.info(json.dumps({
                "iteration": iteration,
                "tool": call.function.name,
                "arguments": args,
            }))
            print(f"[{iteration}/{MAX_ITERATIONS}] Calling {call.function.name}({args})")

            result = execute_tool(repo_path, call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

        trim_old_tool_messages(messages)

    return "Reached the 15-iteration cap without a final answer. Try a more specific question."


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ask questions about a GitHub repo's architecture.")
    parser.add_argument("repo_url", help="GitHub repo URL to clone and analyze")
    parser.add_argument("question", help="Natural-language question about the repo")
    args = parser.parse_args()

    tmp_dir = tempfile.mkdtemp(prefix="coding_agent_")
    try:
        clone_result = clone_repo(args.repo_url, tmp_dir)
        print(clone_result)
        if "Error" in clone_result:
            return

        answer = run_agent(tmp_dir, args.question)
        print("\n--- ANSWER ---")
        print(answer)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()