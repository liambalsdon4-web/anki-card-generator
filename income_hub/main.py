import argparse
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

import uvicorn
from api.routes import app
from config import settings as cfg


def _serve():
    uvicorn.run(app, host=cfg.HOST, port=cfg.PORT, log_level="error")


def main():
    parser = argparse.ArgumentParser(description=cfg.APP_NAME)
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()

    if args.server:
        uvicorn.run(app, host=cfg.HOST, port=cfg.PORT)
        return

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    time.sleep(1.5)
    url = f"http://{cfg.HOST}:{cfg.PORT}"

    if args.web:
        import webbrowser
        webbrowser.open(url)
        t.join()
    else:
        try:
            import webview
            webview.create_window(cfg.APP_NAME, url, width=1400, height=900, resizable=True)
            webview.start()
        except ImportError:
            import webbrowser
            print(f"pywebview not installed — opening in browser at {url}")
            webbrowser.open(url)
            t.join()


if __name__ == "__main__":
    main()
