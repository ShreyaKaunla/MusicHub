import os
import sys
import subprocess

def activate_backend():
    print("⚡ Initializing MusicHub Server Environment...")
    
    # Check common virtual environment naming conventions dynamically
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_pythons = [
        os.path.join(base_dir, "env", "Scripts", "python.exe"),
        os.path.join(base_dir, "venv", "Scripts", "python.exe"),
        sys.executable # Fallback to active shell python if env folders are manually loaded
    ]
    
    env_python = next((p for p in possible_pythons if os.path.exists(p)), sys.executable)
    print(f"🚀 Using Python engine context: {env_python}")
    
    # Fire up the standard server pool process loop
    subprocess.run([env_python, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"])

if __name__ == "__main__":
    activate_backend()
