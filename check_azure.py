import os
import requests

# Load Speech-specific environment variables
AZURE_SPEECH_KEY="BlizIYQp5RXsdONS9uBruWUMdjYFUNe36y6fFcnMUTEhn8TyNhBpJQQJ99BEACYeBjFXJ3w3AAAYACOGAJUY"
AZURE_SPEECH_REGION="eastus"

# Azure Speech-to-Text endpoint for verification
SPEECH_ENDPOINT_TEMPLATE = "https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

def validate_env_vars(key: str, region: str) -> bool:
    if not key or key == "YOUR_SPEECH_KEY":
        print("❌ Error: Speech key is missing or set to placeholder.")
        return False
    if not region or region == "YOUR_SPEECH_REGION":
        print("❌ Error: Speech region is missing or set to placeholder.")
        return False
    return True

def check_speech_key_and_region(key: str, region: str) -> bool:
    if not validate_env_vars(key, region):
        return False

    # Using a dummy request (GET) to Speech service token endpoint for validation
    endpoint = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issuetoken"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Length": "0"
    }

    print(f"🔍 Checking Azure Speech key and region via token endpoint:\n{endpoint}\n")

    try:
        response = requests.post(endpoint, headers=headers, timeout=10)

        if response.status_code == 200:
            print("✅ Success: Speech key and region are valid and working.")
            return True

        print(f"❌ API Error: Status Code {response.status_code}")
        try:
            error_json = response.json()
            if "error" in error_json:
                error_info = error_json["error"]
                print(f"Code: {error_info.get('code', 'N/A')}")
                print(f"Message: {error_info.get('message', 'N/A')}")
            elif "code" in error_json and "message" in error_json:
                print(f"Code: {error_json['code']}")
                print(f"Message: {error_json['message']}")
            else:
                print("Response details:", error_json)
        except Exception:
            print("⚠️ Could not parse error details. Raw response:")
            print(response.text)

        status_reasons = {
            401: "Unauthorized – The key is likely invalid or expired.",
            403: "Forbidden – The key may not have access or region is incorrect.",
            404: "Not Found – The region may be invalid or endpoint doesn’t exist.",
            429: "Too Many Requests – You’ve hit a rate limit. Try again later."
        }
        reason = status_reasons.get(response.status_code, "Unknown error. Check your key, region, and network.")
        print(f"📌 Reason: {reason}")
        return False

    except requests.exceptions.RequestException as req_err:
        print(f"🌐 Network error: {req_err}")
        print("⚠️ Cannot reach Azure endpoint. Check internet, region format, or firewall settings.")
        return False

    except Exception as e:
        print(f"❗ Unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Azure Speech Key & Region Validation Tool")
    print("-------------------------------------------")
    result = check_speech_key_and_region(AZURE_SPEECH_KEY, AZURE_SPEECH_REGION)
    if result:
        print("🎯 Your Azure Speech key is valid and ready to use.")
    else:
        print("❗ Validation failed. Please review the errors above.")
