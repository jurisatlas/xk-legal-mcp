# -*- coding: utf-8 -*-
"""JurisAtlas Interactive AI Client Selector & Setup Wizard (macOS GUI)."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import re
import shutil
import subprocess
import sys
import threading
from typing import Callable

REPO_NAME = "xk-legal-mcp"
COUNTRY_NAME = "Kosovo"

CLIENT_SPECS: list[tuple[str, str, bool]] = [
    ("codex", "ChatGPT Desktop & OpenAI Codex CLI", True),
    ("claude", "Claude Desktop & Claude Code CLI", True),
    ("cursor", "Cursor Editor", True),
    ("windsurf", "Windsurf (Codeium)", True),
    ("vscode", "VS Code (Copilot / Cline / Roo Code)", True),
    ("antigravity", "Google Antigravity & Gemini CLI", True),
    ("continue", "Perplexity / Continue.dev / LM Studio", False),
]


def get_mac_client_map(repo_name: str, home: pathlib.Path | None = None) -> dict[str, list[pathlib.Path]]:
    home_dir = home if home is not None else pathlib.Path.home()
    app_support = home_dir / "Library" / "Application Support"
    return {
        "codex": [
            app_support / "ChatGPT" / "mcp.json",
            home_dir / ".codex" / "mcp_config.json",
        ],
        "claude": [
            app_support / "Claude" / "claude_desktop_config.json",
            home_dir / ".claude.json",
        ],
        "cursor": [home_dir / ".cursor" / "mcp.json"],
        "windsurf": [home_dir / ".codeium" / "windsurf" / "mcp_config.json"],
        "vscode": [
            app_support / "Code" / "User" / "mcp.json",
            app_support / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            app_support / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
        ],
        "antigravity": [
            home_dir / ".gemini" / "config" / "mcp_config.json",
            home_dir / ".gemini" / "antigravity" / "mcp_config.json",
            home_dir / ".gemini" / "settings.json",
        ],
        "continue": [home_dir / ".continue" / "mcpServers" / f"{repo_name}.json"],
    }


def resolve_uv_binary(home: pathlib.Path | None = None) -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    home_dir = home if home is not None else pathlib.Path.home()
    for candidate in (
        home_dir / ".local" / "bin" / "uv",
        home_dir / ".cargo" / "bin" / "uv",
        pathlib.Path("/opt/homebrew/bin/uv"),
        pathlib.Path("/usr/local/bin/uv"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def upsert_json_mcp_file(
    cfg_path: pathlib.Path,
    repo_name: str,
    py_path: str,
    script_path: str,
    dry_run: bool = False,
) -> None:
    data: dict[str, object] = {}
    if cfg_path.exists() and cfg_path.stat().st_size > 0:
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            if not dry_run:
                shutil.copy2(cfg_path, cfg_path.with_name(f"{cfg_path.name}.bak"))
            data = {}

    if not isinstance(data.get("mcpServers"), dict):
        data["mcpServers"] = {}
    mcp_servers = data["mcpServers"]
    assert isinstance(mcp_servers, dict)
    mcp_servers[repo_name] = {
        "command": py_path,
        "args": [script_path],
        "env": {"PYTHONIOENCODING": "utf-8"},
    }

    if not dry_run:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def upsert_codex_toml(
    codex_toml: pathlib.Path,
    repo_name: str,
    py_path: str,
    script_path: str,
    dry_run: bool = False,
) -> None:
    existing = codex_toml.read_text(encoding="utf-8") if codex_toml.exists() else ""
    esc_py = py_path.replace("\\", "\\\\")
    esc_sc = script_path.replace("\\", "\\\\")
    block = f'[mcp_servers.{repo_name}]\ncommand = "{esc_py}"\nargs = ["{esc_sc}"]\n'
    pattern = rf"(?ms)^\[mcp_servers\.{re.escape(repo_name)}\].*?(?=^\[|\Z)"
    if re.search(pattern, existing):
        updated = re.sub(pattern, block + "\n", existing)
    else:
        updated = (existing.rstrip() + "\n\n" + block) if existing.strip() else block

    if not dry_run:
        codex_toml.parent.mkdir(parents=True, exist_ok=True)
        codex_toml.write_text(updated, encoding="utf-8")


def register_clients(
    selected_keys: list[str],
    script_dir: pathlib.Path,
    repo_name: str = REPO_NAME,
    home: pathlib.Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    home_dir = home if home is not None else pathlib.Path.home()
    venv_py = str(script_dir / ".venv" / "bin" / "python")
    main_py = str(script_dir / "mcp_server_main.py")
    client_map = get_mac_client_map(repo_name, home=home_dir)
    written: list[str] = []

    for key in selected_keys:
        if key == "codex":
            codex_toml = home_dir / ".codex" / "config.toml"
            upsert_codex_toml(codex_toml, repo_name, venv_py, main_py, dry_run=dry_run)
            written.append(str(codex_toml))
        for cfg in client_map.get(key, []):
            upsert_json_mcp_file(cfg, repo_name, venv_py, main_py, dry_run=dry_run)
            written.append(str(cfg))
    return written


def run_installation(
    selected_keys: list[str],
    script_dir: pathlib.Path,
    repo_name: str = REPO_NAME,
    home: pathlib.Path | None = None,
    dry_run: bool = False,
    progress_cb: Callable[[int, str], None] | None = None,
) -> list[str]:
    if not selected_keys:
        raise ValueError("Please select at least one AI application.")

    def report(pct: int, text: str) -> None:
        if progress_cb:
            progress_cb(pct, text)

    report(20, "Step 1/4: Checking Python runtime manager (uv)...")
    uv_bin = resolve_uv_binary(home=home)
    if not uv_bin and not dry_run:
        subprocess.run(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            check=True,
        )
        uv_bin = resolve_uv_binary(home=home)
    if not uv_bin and not dry_run:
        raise RuntimeError("Could not locate or install 'uv'.")

    report(50, "Step 2/4: Preparing isolated Python 3.12 runtime...")
    if not dry_run and uv_bin:
        find_res = subprocess.run(
            [uv_bin, "python", "find", "3.12"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if find_res.returncode != 0:
            subprocess.run([uv_bin, "python", "install", "3.12"], check=True)

    report(75, "Step 3/4: Installing legal database & archive connectors...")
    if not dry_run and uv_bin:
        sync_res = subprocess.run(
            [uv_bin, "sync", "--python", "3.12"],
            cwd=str(script_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if sync_res.returncode != 0:
            err = (sync_res.stderr or sync_res.stdout or "uv sync failed").strip()
            raise RuntimeError(err)

    report(90, "Step 4/4: Registering MCP server in selected AI applications...")
    written = register_clients(
        selected_keys,
        script_dir=script_dir,
        repo_name=repo_name,
        home=home,
        dry_run=dry_run,
    )
    report(100, "Setup Complete! Connected to your selected AI applications.")
    return written


def _bring_mac_window_to_front() -> None:
    try:
        pid = os.getpid()
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to set frontmost of the first process whose unix id is {pid} to true',
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except Exception:
        pass


def run_gui(script_dir: pathlib.Path, dry_run: bool = False) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title(f"JurisAtlas - {COUNTRY_NAME} Legal MCP Setup")
    root.geometry("580x515")
    root.minsize(560, 480)
    root.resizable(True, True)

    container = ttk.Frame(root, padding=(20, 16, 20, 16))
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=f"JurisAtlas: {COUNTRY_NAME} Legal MCP Setup",
        font=("SF Pro Text", 15, "bold"),
    ).pack(anchor="w", pady=(0, 8))

    info_box = tk.Frame(
        container,
        bg="#e0f2fe",
        highlightbackground="#7dd3fc",
        highlightthickness=1,
        padx=12,
        pady=10,
    )
    info_box.pack(fill="x", pady=(0, 12))
    tk.Label(
        info_box,
        text=(
            "Read-Only & Isolated Installation\n"
            "• Does NOT access or modify your personal files or documents.\n"
            f"• Select the AI application(s) you use below to connect {COUNTRY_NAME} legislation & multi-tier court decisions."
        ),
        bg="#e0f2fe",
        fg="#0f172a",
        justify="left",
        anchor="w",
        wraplength=510,
        font=("SF Pro Text", 10),
    ).pack(fill="x")

    group = ttk.LabelFrame(container, text="Select the AI Application(s) You Use:", padding=(12, 10))
    group.pack(fill="x", pady=(0, 12))
    group.columnconfigure(0, weight=1)
    group.columnconfigure(1, weight=1)

    client_vars: dict[str, tk.BooleanVar] = {}
    for idx, (key, label, default) in enumerate(CLIENT_SPECS):
        var = tk.BooleanVar(value=default)
        client_vars[key] = var
        ttk.Checkbutton(group, text=label, variable=var).grid(
            row=idx // 2,
            column=idx % 2,
            sticky="w",
            padx=6,
            pady=5,
        )

    status_var = tk.StringVar(value="Select your AI clients above and click Install.")
    ttk.Label(container, textvariable=status_var, font=("SF Pro Text", 10)).pack(anchor="w", pady=(2, 4))

    progress = ttk.Progressbar(container, orient="horizontal", mode="determinate", maximum=100, value=0)
    progress.pack(fill="x", pady=(0, 12))

    btn_row = ttk.Frame(container)
    btn_row.pack(fill="x")

    install_btn = ttk.Button(btn_row, text="Install to Selected AI Clients", default="active")
    install_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
    close_btn = ttk.Button(btn_row, text="Close", command=lambda: root.destroy())
    close_btn.pack(side="right")

    def on_install() -> None:
        chosen = [key for key, _, _ in CLIENT_SPECS if client_vars[key].get()]
        if not chosen:
            messagebox.showwarning(
                "No Client Selected",
                "Please select at least one AI application.",
                parent=root,
            )
            return

        install_btn.configure(state="disabled", text="Installing... Please wait")
        close_btn.configure(state="disabled")

        events: queue.Queue[tuple[str, object]] = queue.Queue()

        def on_progress(pct: int, msg: str) -> None:
            events.put(("progress", (pct, msg)))

        def worker() -> None:
            try:
                run_installation(
                    chosen,
                    script_dir=script_dir,
                    repo_name=REPO_NAME,
                    dry_run=dry_run,
                    progress_cb=on_progress,
                )
                events.put(("done", None))
            except Exception as exc:
                events.put(("error", str(exc)))

        def poll_events() -> None:
            try:
                while True:
                    kind, payload = events.get_nowait()
                    if kind == "progress":
                        pct, msg = payload  # type: ignore[misc]
                        progress.configure(value=pct)
                        status_var.set(str(msg))
                    elif kind == "done":
                        install_btn.configure(state="normal", text="Installation Complete")
                        close_btn.configure(state="normal")
                        messagebox.showinfo(
                            "JurisAtlas - Setup Complete",
                            f"{COUNTRY_NAME} Legal MCP Server ({REPO_NAME}) has been installed and connected to your selected AI application(s).\n\n"
                            "Please restart your AI application to begin using the tools.",
                            parent=root,
                        )
                        root.destroy()
                        return
                    elif kind == "error":
                        err_msg = str(payload)
                        install_btn.configure(state="normal", text="Retry Installation")
                        close_btn.configure(state="normal")
                        status_var.set("Installation failed. See details.")
                        messagebox.showerror(
                            "Setup Error",
                            f"An error occurred during setup:\n{err_msg}",
                            parent=root,
                        )
                        return
            except queue.Empty:
                pass
            if root.winfo_exists():
                root.after(50, poll_events)

        threading.Thread(target=worker, daemon=True).start()
        root.after(50, poll_events)

    install_btn.configure(command=on_install)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.lift()
    root.attributes("-topmost", True)
    topmost_id = root.after(200, lambda: root.winfo_exists() and root.attributes("-topmost", False))
    focus_id = root.after(50, _bring_mac_window_to_front)
    root.focus_force()

    orig_destroy = root.destroy

    def clean_destroy() -> None:
        for aid in (topmost_id, focus_id):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
        orig_destroy()

    root.destroy = clean_destroy  # type: ignore[method-assign]
    root.mainloop()


def run_cli(script_dir: pathlib.Path, dry_run: bool = False) -> None:
    print(f"\nJurisAtlas: {COUNTRY_NAME} Legal MCP Setup ({REPO_NAME})")
    print("Available AI Applications:")
    for idx, (_key, label, _default) in enumerate(CLIENT_SPECS, start=1):
        print(f"  [{idx}] {label}")
    print("  [A] All of the above")
    raw = input("\nSelect AI application(s) (e.g. 1,2,3 or A for all) [Default: A]: ").strip().lower()
    if not raw or raw in {"a", "all", "*"}:
        chosen = [key for key, _, _ in CLIENT_SPECS]
    else:
        tokens = [t.strip() for t in raw.replace(";", ",").split(",") if t.strip()]
        chosen = [
            CLIENT_SPECS[int(t) - 1][0]
            for t in tokens
            if t.isdigit() and 1 <= int(t) <= len(CLIENT_SPECS)
        ]
    if not chosen:
        print("No valid AI application selected. Exiting.")
        sys.exit(1)

    run_installation(
        chosen,
        script_dir=script_dir,
        repo_name=REPO_NAME,
        dry_run=dry_run,
        progress_cb=lambda pct, msg: print(f"[{pct}%] {msg}"),
    )
    print(f"\nSetup Complete! Connected {REPO_NAME}. Please restart your selected AI application(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"JurisAtlas {COUNTRY_NAME} macOS Installer")
    parser.add_argument("--cli", action="store_true", help="Use terminal fallback instead of GUI")
    parser.add_argument("--dry-run", action="store_true", help="Preview installation without writing files")
    args = parser.parse_args()

    script_dir = pathlib.Path(__file__).resolve().parent
    if not args.cli and not (os.environ.get("SSH_TTY") or os.environ.get("SSH_CONNECTION")):
        try:
            run_gui(script_dir=script_dir, dry_run=args.dry_run)
            return
        except Exception as exc:
            print(f"GUI unavailable ({exc}); switching to terminal mode.")

    run_cli(script_dir=script_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
