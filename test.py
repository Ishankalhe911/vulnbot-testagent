import os
from dotenv import load_dotenv
from algosdk import mnemonic, logic, account

# Load environment variables
load_dotenv()

print("\n🔍 Fetching Algorand Addresses for Dispenser...\n")

# 1. Get Agent (Deployer) Address
deployer_mnemonic = os.getenv("DEPLOYER_MNEMONIC")
if deployer_mnemonic:
    try:
        # Get private key first, then derive public address
        private_key = mnemonic.to_private_key(deployer_mnemonic)
        agent_address = account.address_from_private_key(private_key)
        
        print(f"🏦 1. Agent Wallet Address (from DEPLOYER_MNEMONIC):")
        print(f"👉 {agent_address}\n")
    except Exception as e:
        print(f"❌ Error reading mnemonic: {e}\n")
else:
    print("❌ DEPLOYER_MNEMONIC not found in .env file.\n")

# 2. Get Smart Contract (App) Address
app_id_str = os.getenv("APP_ID", "762641798") # Defaults to your current App ID
if app_id_str:
    try:
        app_id = int(app_id_str)
        app_address = logic.get_application_address(app_id)
        
        print(f"🤖 2. Smart Contract Address (for App ID {app_id}):")
        print(f"👉 {app_address}\n")
    except Exception as e:
        print(f"❌ Error getting App Address: {e}\n")
else:
    print("❌ APP_ID not found.\n")