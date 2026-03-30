import requests
import time
import subprocess
import os
import signal

def run_smoke_test():
    print("🚦 Starting Web UI Smoke Test...")
    
    # 1. Start server in background
    server_process = subprocess.Popen(
        ["python3", "-m", "lirox.web"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    
    time.sleep(5)  # Wait for boot
    
    try:
        # 2. Health check
        print("🔍 Checking /api/health...")
        res = requests.get("http://127.0.0.1:8000/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        print("✅ Health OK")
        
        # 3. Profile check
        print("🔍 Checking /api/profile...")
        res = requests.get("http://127.0.0.1:8000/api/profile")
        assert res.status_code == 200
        print(f"✅ Profile OK: {res.json().get('agent_name')}")
        
        # 4. Providers check
        print("🔍 Checking /api/providers...")
        res = requests.get("http://127.0.0.1:8000/api/providers")
        assert res.status_code == 200
        print(f"✅ Providers OK: {len(res.json()['all'])} listed")
        
        print("\n🎉 SMOKE TEST PASSED!")
        
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {str(e)}")
        # Print server logs if failed
        out, err = server_process.communicate()
        print(f"STDOUT: {out.decode()}")
        print(f"STDERR: {err.decode()}")
        
    finally:
        # Kill server
        os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
        print("🛑 Server stopped.")

if __name__ == "__main__":
    run_smoke_test()
