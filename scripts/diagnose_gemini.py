"""
Diagnostics tool for testing the Google Gemini API connection, keys, models, and quotas.
"""

import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def diagnose():
    print("=" * 60)
    print("VALUAGENT GEMINI API DIAGNOSTICS")
    print("=" * 60)

    # 1. Check environment variables
    google_key = os.environ.get("GOOGLE_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not google_key and not gemini_key:
        print("ERROR: Neither GOOGLE_API_KEY nor GEMINI_API_KEY is set in the environment.")
        print("\nHow to resolve:")
        print("1. Create a file named '.env' in your project root directory.")
        print("2. Add your API key there:")
        print("   GEMINI_API_KEY=\"your_api_key_here\"")
        print("3. Alternatively, set it in your current terminal session:")
        print("   PowerShell: $env:GEMINI_API_KEY=\"your_api_key_here\"")
        print("   CMD:        set GEMINI_API_KEY=your_api_key_here")
        print("   Linux/Mac:  export GEMINI_API_KEY=\"your_api_key_here\"")
        sys.exit(1)

    key_used = "GEMINI_API_KEY" if gemini_key else "GOOGLE_API_KEY"
    print(f"[*] Found API key in environment: {key_used}")
    print(f"[*] Value length: {len(gemini_key or google_key)} characters")

    # Try importing google-genai
    try:
        from google import genai
        from google.genai.errors import APIError
    except ImportError:
        print("ERROR: 'google-genai' SDK is not installed. Please install it using:")
        print("       pip install google-genai")
        sys.exit(1)

    print("[*] Successfully imported google-genai SDK.")
    
    # Initialize Client
    try:
        client = genai.Client()
        print("[*] Successfully initialized genai.Client.")
    except Exception as e:
        print(f"ERROR: Failed to initialize genai.Client: {e}")
        sys.exit(1)

    candidate_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
    
    print("\nTesting candidate models...")
    print("-" * 60)

    for model in candidate_models:
        print(f"[*] Testing model: {model}...")
        start_time = time.time()
        try:
            response = client.models.generate_content(
                model=model,
                contents="Write a 3-word confirmation.",
            )
            elapsed = time.time() - start_time
            print(f"    SUCCESS! Response: {repr(response.text.strip())}")
            print(f"    Time taken: {elapsed:.2f} seconds")
        except APIError as e:
            elapsed = time.time() - start_time
            print(f"    FAILED! (in {elapsed:.2f} seconds)")
            print(f"    Error code: {e.code}")
            print(f"    Error message: {e.message}")
            if e.details:
                print(f"    Error details: {e.details}")
            
            # Diagnose specific common errors
            if e.code == 429:
                print("\n    --> DIAGNOSIS: Rate limit/Quota exhausted (HTTP 429).")
                if "limit" in str(e.message).lower() or "limit" in str(e.details).lower():
                    print("        If the limit is 0, your free tier account is not yet provisioned")
                    print("        for this model/project or requires billing activation in Google Cloud Console.")
                print("        If the limit is > 0, you have made too many requests too quickly.")
                print("        The configured retry_options in agents/memo_writer_agent.py will help manage this.")
            elif e.code == 403:
                print("\n    --> DIAGNOSIS: Permission denied (HTTP 403).")
                print("        Your API key is invalid, or does not have access to this model.")
            elif e.code == 404:
                print("\n    --> DIAGNOSIS: Model not found (HTTP 404).")
                print("        The model name might be misspelled or deprecated.")
            print("-" * 60)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"    FAILED! (in {elapsed:.2f} seconds)")
            print(f"    Unexpected error: {type(e).__name__}: {e}")
            print("-" * 60)

    print("\nDiagnostics complete.")
    print("=" * 60)

if __name__ == "__main__":
    diagnose()
