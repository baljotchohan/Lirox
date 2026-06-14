"""
[WEB-7] Web server entry point.
Usage: python -m lirox.main_web
   or: lirox --web
"""
import uvicorn
from lirox.server.app import create_app


def main_web():
    import os
    import sys
    import subprocess
    from pathlib import Path

    web_dir = Path(__file__).resolve().parent / "web"
    dist_dir = web_dir / "dist"

    if not dist_dir.exists():
        print("\n  [Lirox] Web UI not built yet. Setting up automatically...")
        try:
            if not (web_dir / "node_modules").exists():
                print("  [Lirox] Installing frontend dependencies (this may take a minute)...")
                subprocess.run(["npm", "install"], cwd=str(web_dir), check=True)
            
            print("  [Lirox] Building optimized static UI...")
            subprocess.run(["npm", "run", "build"], cwd=str(web_dir), check=True)
            print("  [Lirox] Build complete!\n")
        except FileNotFoundError:
            print("\n  [!] Error: 'npm' is not installed. Please install Node.js to use the Web UI.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"\n  [!] Error building web UI: {e}")
            sys.exit(1)

    app = create_app()
    print("\n  ✦ Lirox Web UI running at http://localhost:3210")
    print("  (Press Ctrl+C to stop)\n")
    uvicorn.run(app, host="0.0.0.0", port=3210, log_level="warning")


if __name__ == "__main__":
    main_web()
