import uvicorn
import os
import sys

def main():
    # Ensure project root is in path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    print("\n🚀 Starting Lirox Web Server...")
    print("📍 Local URL: http://127.0.0.1:8000")
    print("🔧 API Docs:  http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop.\n")
    
    uvicorn.run("lirox.server.app:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
