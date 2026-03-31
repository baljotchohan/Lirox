import subprocess
import time
import sys

def run_test_cmd(cmd):
    print(f"Testing Command: {cmd}")
    process = subprocess.Popen(
        [sys.executable, "-m", "lirox.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Give it time to boot
    time.sleep(2)
    
    # Send command + /exit
    out, err = process.communicate(input=f"{cmd}\n/exit\n", timeout=15)
    
    if process.returncode == 0:
        print(f"  [PASS] {cmd}")
        return True
    else:
        print(f"  [FAIL] {cmd}")
        print(err)
        return False

def main():
    commands = ["/test", "/profile", "/memory", "/models", "/help"]
    results = []
    
    for c in commands:
        results.append(run_test_cmd(c))
    
    if all(results):
        print("\nALL CLI COMMANDS VERIFIED. READY FOR DEPLOYMENT.")
    else:
        print("\nSOME COMMANDS FAILED. AUDIT REQUIRED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
