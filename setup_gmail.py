"""
Run this ONCE to authorize Gmail access and generate token.json.
After that, main.py handles token refresh automatically.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

if not os.path.exists("credentials.json"):
    print(
        "ERROR: credentials.json not found.\n"
        "Steps:\n"
        "  1. Go to https://console.cloud.google.com/\n"
        "  2. Create a project and enable Gmail API\n"
        "  3. Create OAuth2 credentials (Desktop app type)\n"
        "  4. Download and save as 'credentials.json' in this folder\n"
    )
    raise SystemExit(1)

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("✓ token.json created. Gmail authorization complete.")
print("  You can now run: python main.py")
