import os
import shutil
from pathlib import Path

def cleanup():
    base = Path("/Users/baljotchohan/Desktop/LIROX/Lirox")
    
    # Moves
    moves = [
        (base / "lirox/designer/intent.py", base / "lirox/pipeline/intent.py"),
        (base / "lirox/quality/validator.py", base / "lirox/pipeline/validator.py"),
        (base / "lirox/learning/extractor.py", base / "lirox/memory/extractor.py"),
    ]
    
    for src, dst in moves:
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved {src} to {dst}")

    # Directory deletions
    dirs_to_delete = [
        "lirox/autonomy/",
        "lirox/agent/",
        "lirox/specialists/",
        "lirox/security/",
        "lirox/context/",
        "lirox/thinking/",
        "lirox/core/",
        "lirox/designer/",
        "lirox/quality/",
        "lirox/learning/",
        "lirox/mind/",
        "scratch/",
    ]
    
    for d in dirs_to_delete:
        path = base / d
        if path.exists():
            shutil.rmtree(str(path))
            print(f"Deleted {path}")

    # File deletions
    files_to_delete = [
        "apply_fixes_1.py",
        "verify_fixes.py",
        "check_syntax.py",
        "health_check.py",
        "test_bridge.py",
        "test_classifier.py",
        "test_export.json",
        "test_llm.py",
        "test_planner.py",
        "test_regex.py",
    ]
    
    for f in files_to_delete:
        path = base / f
        if path.exists():
            os.remove(str(path))
            print(f"Deleted {path}")

if __name__ == "__main__":
    cleanup()
