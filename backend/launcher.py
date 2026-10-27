"""Starts HY Sales Engine: the local server plus your browser. This is the entry point of the Windows program.
Everything stays on this computer. Leave the window open while you want calls and follow-ups to run."""
import json
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

PORT = int(os.getenv("HYSE_PORT", "8765"))


def is_ours(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            return json.load(r).get("app") == "hy-sales-engine"
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main():
    url = f"http://127.0.0.1:{PORT}"
    if is_ours(PORT):                                     # already running: just open it
        print("HY Sales Engine is already running. Opening it in your browser.")
        webbrowser.open(url)
        return
    port = PORT
    while not port_free(port):
        port += 1
    url = f"http://127.0.0.1:{port}"

    import uvicorn
    from app.main import app
    from app import config

    print("=" * 62)
    print("  HY Developer Sales Engine")
    print(f"  Open:  {url}")
    print(f"  Your data is in:  {config.DATA_DIR}")
    print("  Leave this window open. Closing it stops calls and follow-ups.")
    print("=" * 62)
    if not os.getenv("HYSE_NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")      # only reachable from this computer


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:                                # keep the window readable if something goes wrong
        print("\nHY Sales Engine could not start:", e)
        if sys.platform == "win32":
            input("Press Enter to close this window.")
        raise
