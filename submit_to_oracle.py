# File: submit_to_oracle.py

import json
import hashlib
import pandas as pd
import sys  # Required for sys.exit
import os   # <-- THIS IS THE CRITICAL MISSING IMPORT
from web3 import Web3

# --- 1. Configuration ---

# The artifacts file created by the deployment script
ARTIFACTS_FILE = 'deployment_info.json'
# The data file this script will READ from the current directory
DATA_FILE = 'stock_data.csv'
# The local blockchain node endpoint
LOCAL_NODE_URL = 'http://127.0.0.1:8545'

# --- 2. Main Logic ---

def main():
    """
    Main function to read data from the local CSV, hash it, and submit it to the oracle.
    """
    
    # Check if the data file exists before proceeding.
    # This line (24 in the previous traceback) requires the 'os' module to be imported.
    if not os.path.exists(DATA_FILE):
        print(f"--- Data File Not Found ---")
        print(f"CRITICAL ERROR: The required data file '{DATA_FILE}' was not found.")
        print(f"Please create '{DATA_FILE}' in this directory with the columns: date,open,high,low,close,volume,Name")
        sys.exit(1) # Exit cleanly if the file is missing

    # Step 1: Load Configuration from the deployment artifacts
    print(f"--- Loading configuration from {ARTIFACTS_FILE} ---")
    try:
        with open(ARTIFACTS_FILE, 'r') as f:
            deployment_info = json.load(f)
            
        contract_address = deployment_info['address']
        contract_abi = deployment_info['abi']
    except FileNotFoundError:
        print(f"Error: {ARTIFACTS_FILE} not found.")
        print("Please run the 'deploy_and_verify.py' script first.")
        return
    except KeyError:
        print(f"Error: {ARTIFACTS_FILE} is malformed. Missing 'address' or 'abi'.")
        return

    # Step 2: Connect to the blockchain
    print(f"--- Connecting to Blockchain at {LOCAL_NODE_URL} ---")
    w3 = Web3(Web3.HTTPProvider(LOCAL_NODE_URL))
    if not w3.is_connected():
        print("Error: Could not connect to the blockchain.")
        return
    
    # Set the default account (the "owner")
    w3.eth.default_account = w3.eth.accounts[0]
    print(f"Using Owner Account: {w3.eth.default_account}")

    # Step 3: Instantiate the deployed contract
    print(f"--- Loading contract at {contract_address} ---")
    oracle_contract = w3.eth.contract(
        address=contract_address, 
        abi=contract_abi
    )

    # Step 4: Process and Submit Data
    print(f"--- Reading and processing data from {DATA_FILE} ---")
    
    # Load the CSV data into a Pandas DataFrame
    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Check for required columns
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'Name']
    if not all(col in df.columns for col in required_cols):
        print(f"Error: {DATA_FILE} is missing required columns. Expected: {required_cols}")
        return

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        try:
            # --- A: Format Data ---
            
            # 1. Get the stock name (e.g., "AAPL")
            name = row['Name']
            
            # 2. Convert the date string (e.g., "2023-10-25") into
            #    a uint256 number (e.g., 20231025) for the contract
            date_uint = int(str(row['date']).replace('-', ''))
            
            # --- B: Create Hash Payload ---
            
            # 3. Concatenate all fields into a single, exact string.
            data_string = (
                f"{row['date']}"
                f"{row['open']}"
                f"{row['high']}"
                f"{row['low']}"
                f"{row['close']}"
                f"{row['volume']}"
                f"{row['Name']}"
            )
            
            # --- C: Calculate Hash ---
            
            # 4. Calculate the SHA-256 hash and get the raw bytes for bytes32
            data_hash_bytes = hashlib.sha256(data_string.encode()).digest()

            # --- D: Submit to Blockchain ---
            
            print(f"Submitting hash for {name} on {row['date']}...")
            
            # 5. Call the `submitDataHash` function on the smart contract.
            tx_hash = oracle_contract.functions.submitDataHash(
                name,
                date_uint,
                data_hash_bytes
            ).transact()
            
            # 6. Wait for the transaction to be mined and confirmed.
            w3.eth.wait_for_transaction_receipt(tx_hash)
            
            print(f"  -> Success! TxHash: {tx_hash.hex()}")

        except Exception as e:
            # Handle potential errors.
            error_message = str(e)
            if "Data for this date and name already submitted" in error_message:
                print(f"  -> INFO: Data for {name} on {row['date']} already submitted. Skipping.")
            else:
                print(f"  -> ERROR submitting {name} on {row['date']}: {e}")

    print("--- Data submission process finished. ---")


if __name__ == "__main__":
    main()
