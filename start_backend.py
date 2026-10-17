import uvicorn
import os
import sys

# Add the current directory to sys.path to allow importing backend.app
sys.path.append(os.path.join(os.getcwd(), "backend"))

if __name__ == "__main__":
    print("--- Starting MathModel-Engine Backend ---")
    print("API Documentation will be available at: http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
