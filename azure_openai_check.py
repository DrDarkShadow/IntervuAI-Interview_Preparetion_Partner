import os
import requests

# Load environment variables
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "YOUR_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "YOUR_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

def validate_env():
    missing = []
    if AZURE_OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
        missing.append("AZURE_OPENAI_API_KEY")
    if AZURE_OPENAI_ENDPOINT == "YOUR_OPENAI_ENDPOINT":
        missing.append("AZURE_OPENAI_ENDPOINT")
    if AZURE_OPENAI_DEPLOYMENT_NAME == "YOUR_DEPLOYMENT_NAME":
        missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")
    if AZURE_OPENAI_API_VERSION == "":
        missing.append("AZURE_OPENAI_API_VERSION")

    if missing:
        print(f"❌ Missing or placeholder environment variables: {', '.join(missing)}")
        return False
    return True

def check_azure_openai_key():
    if not validate_env():
        return False

    # Construct endpoint URL
    endpoint = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Ping"}
        ],
        "temperature": 0.2,
        "max_tokens": 10
    }

    print(f"🔍 Validating Azure OpenAI credentials via:\n{endpoint}\n")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Success: Azure OpenAI credentials are valid.")
            return True

        print(f"❌ API Error: Status Code {response.status_code}")
        try:
            error = response.json().get("error", {})
            print(f"Code: {error.get('code', 'N/A')}")
            print(f"Message: {error.get('message', 'N/A')}")
        except Exception:
            print("⚠️ Could not parse error response. Raw text:")
            print(response.text)

        known_issues = {
            401: "Unauthorized – The key may be invalid or expired.",
            403: "Forbidden – You may not have access to this resource or deployment.",
            404: "Not Found – The endpoint or deployment name may be incorrect.",
            429: "Too Many Requests – Rate limit exceeded.",
        }
        print("📌 Reason:", known_issues.get(response.status_code, "Unknown error."))

        return False

    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error: {e}")
        return False
    except Exception as e:
        print(f"❗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Azure OpenAI Key & Endpoint Validation Tool")
    print("---------------------------------------------")
    result = check_azure_openai_key()
    if result:
        print("🎯 Your Azure OpenAI deployment is ready to use.")
    else:
        print("❗ Validation failed. Please check the details above.")
