import os
import sys
from mimo_client import call_mimo, MIMO_API_KEY

def main():
    if not MIMO_API_KEY:
        print("MiMo API is not configured or MIMO_API_KEY is missing.")
        sys.exit(1)
        
    tex_path = os.path.join(os.path.dirname(__file__), "..", "paper", "main.tex")
    if not os.path.exists(tex_path):
        print(f"LaTeX file not found at {tex_path}")
        sys.exit(1)
        
    with open(tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()
        
    print("Sending LaTeX source to MiMo V2.5 for official CUMCM format audit...")
    try:
        # We pass a truncated version or the first 800 lines if the file is extremely long, 
        # but let's pass the core parts (TOC, abstract, table structures, and bibliography)
        # to fit inside context limits if necessary. main.tex is about 800-1000 lines.
        # Let's send the full text or first 30,000 characters.
        prompt = tex_content[:40000]
        result = call_mimo(prompt, model="mimo-v2.5", task="contest-format")
        print("\n=== MiMo V2.5 Format Audit Report ===")
        print(result)
        print("=====================================")
    except Exception as e:
        print(f"Error calling MiMo: {e}")

if __name__ == "__main__":
    main()
