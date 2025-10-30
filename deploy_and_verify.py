# File: deploy_and_verify.py

import json
import os
import subprocess
import sys
import hashlib
from web3 import Web3
from solcx import compile_source, install_solc, get_solc_version

# --- 1. Configuration ---

# Define the Solidity source file
CONTRACT_SOURCE_FILE = 'DataOracle.sol'
# Define the Solidity version we are using
SOLIDITY_VERSION = '0.8.20'
# Define the local blockchain node endpoint
LOCAL_NODE_URL = 'http://127.0.0.1:8545'
# Define the output file for deployment artifacts (ABI and Address)
ARTIFACTS_FILE = 'deployment_info.json'
# Define the name of the submission script to run
SUBMISSION_SCRIPT = 'submit_to_oracle.py'


def install_and_set_solc(version):
    """
    Checks if the required solc version is installed and installs it if not.
    """
    print(f"--- Checking for solc version {version} ---")
    try:
        # Check if the exact version is already installed
        if get_solc_version() != version:
            print(f"Current version is not {version}. Installing...")
            install_solc(version)
        print(f"Solc {version} is correctly installed.")
    except Exception as e:
        print(f"Error installing solc: {e}")
        print("Please ensure you have the 'solidity-compiler' (solc) installed on your system or try installing 'py-solc-x' manually.")
        sys.exit(1)


def compile_contract(source_file, contract_name):
    """
    Reads and compiles the Solidity contract.
    Returns the ABI and Bytecode.
    """
    print(f"--- Compiling {source_file} ---")
    
    # Read the Solidity source code from the file
    with open(source_file, 'r') as f:
        source_code = f.read()

    # --- IMPORTANT FIX: Use absolute path for remapping ---
    # 1. Get the current absolute working directory.
    project_dir = os.getcwd() 
    # 2. Construct the full path to the @openzeppelin folder.
    openzeppelin_path = os.path.join(project_dir, 'node_modules', '@openzeppelin')

    # The remapping tells the compiler: when you see "@openzeppelin/", 
    # look in the absolute directory we just constructed.
    remappings = [
        f'@openzeppelin/={openzeppelin_path}/'
    ]
    
    # Compile the source code using py-solc-x
    compiled_sol = compile_source(
        source_code,
        output_values=['abi', 'bin'],
        solc_version=SOLIDITY_VERSION,
        # Pass the remappings to the compiler
        import_remappings=remappings 
    )
    
    # The output key from compile_source is <stdin>:<ContractName>
    contract_id = f'<stdin>:{contract_name}'
    
    # Check if compilation was successful
    if contract_id not in compiled_sol:
        print("Error: Contract compilation failed.")
        print("Available keys:", compiled_sol.keys())
        sys.exit(1)
        
    # Extract the ABI (Application Binary Interface)
    abi = compiled_sol[contract_id]['abi']
    # Extract the Bytecode
    bytecode = compiled_sol[contract_id]['bin']
    
    print("Contract compiled successfully.")
    return abi, bytecode


def connect_to_blockchain(node_url):
    """
    Connects to the local blockchain node.
    Returns the Web3 instance.
    """
    print(f"--- Connecting to Blockchain at {node_url} ---")
    w3 = Web3(Web3.HTTPProvider(node_url))
    
    # Check if the connection is successful
    if not w3.is_connected():
        print(f"Error: Failed to connect to the blockchain at {node_url}.")
        print("Please ensure your local blockchain (Ganache/Anvil) is running.")
        sys.exit(1)
        
    # Set the default account (the "owner") to be the first account
    # provided by the local node.
    w3.eth.default_account = w3.eth.accounts[0]
    print(f"Connected successfully. Using Owner Account: {w3.eth.default_account}")
    return w3


def deploy_contract(w3, abi, bytecode):
    """
    Deploys the contract to the blockchain.
    Returns the deployed contract address.
    """
    print("--- Deploying Contract ---")
    
    # Create the contract factory object
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # 1. Transact: Send the deployment transaction
    # We call `constructor()` which prepares the transaction data
    try:
        tx_hash = Contract.constructor().transact()
        print(f"Deployment transaction sent. Hash: {tx_hash.hex()}")
    except Exception as e:
        print(f"Error during deployment transaction: {e}")
        print("This often happens if the account has no funds or the node is not configured for signing.")
        sys.exit(1)

    # 2. Wait: Wait for the transaction to be mined
    print("Waiting for transaction receipt...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    # 3. Get Address: Extract the contract address from the receipt
    contract_address = tx_receipt.contractAddress
    
    print(f"Contract deployed successfully!")
    print(f"Contract Address: {contract_address}")
    return contract_address


def save_deployment_artifacts(abi, address, filename):
    """
    Saves the ABI and contract address to a JSON file.
    This file is used by the submission script.
    """
    print(f"--- Saving Artifacts to {filename} ---")
    deployment_info = {
        'abi': abi,
        'address': address
    }
    
    # Write the dictionary to the JSON file
    with open(filename, 'w') as f:
        json.dump(deployment_info, f, indent=4)
        
    print("Artifacts saved.")


def run_submission_script(script_name):
    """
    Runs the data submission script as a separate process.
    `check=True` ensures that if the script fails, this parent script will also exit.
    """
    print(f"--- Running Data Submission Script ({script_name}) ---")
    try:
        # Use subprocess.run to execute the python script
        # `check=True` will raise an error if the script returns a non-zero exit code
        # `sys.executable` ensures we use the same Python interpreter
        subprocess.run([sys.executable, script_name], check=True)
        print("Data submission script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error: The submission script failed with exit code {e.returncode}.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Submission script '{script_name}' not found.")
        sys.exit(1)


def verify_on_chain_data(w3, contract_address, abi):
    """
    Performs the final verification.
    It re-calculates the hashes for known data and compares them
    to the hashes stored on the blockchain.
    """
    print("--- Final On-Chain Verification ---")
    
    # Instantiate a contract object to interact with the *already deployed* contract
    oracle_contract = w3.eth.contract(address=contract_address, abi=abi)
    
    # --- Verification 1: AAPL ---
    name_aapl = "AAPL"
    date_aapl = 20231025
    # This data string must EXACTLY match the one created in `submit_to_oracle.py`
    data_string_aapl = "2023-10-25170.65173.06170.65171.8057157115AAPL"
    # Calculate the expected hash as raw bytes
    expected_hash_aapl = hashlib.sha256(data_string_aapl.encode()).digest()
    
    # Call the `getHash` view function on the contract
    on_chain_hash_aapl = oracle_contract.functions.getHash(name_aapl, date_aapl).call()
    
    # Compare the results
    if on_chain_hash_aapl == expected_hash_aapl:
        print(f"✅ VERIFICATION SUCCESS: {name_aapl} @ {date_aapl}")
    else:
        print(f"❌ VERIFICATION FAILED: {name_aapl} @ {date_aapl}")
        print(f"   Expected: {expected_hash_aapl.hex()}")
        print(f"   On-Chain: {on_chain_hash_aapl.hex()}")

    # --- Verification 2: MSFT ---
    name_msft = "MSFT"
    date_msft = 20231026
    # This data string must EXACTLY match the one created in `submit_to_oracle.py`
    data_string_msft = "2023-10-26340.54341.60327.89327.8937828715MSFT"
    # Calculate the expected hash as raw bytes
    expected_hash_msft = hashlib.sha256(data_string_msft.encode()).digest()
    
    # Call the `getHash` view function on the contract
    on_chain_hash_msft = oracle_contract.functions.getHash(name_msft, date_msft).call()

    # Compare the results
    if on_chain_hash_msft == expected_hash_msft:
        print(f"✅ VERIFICATION SUCCESS: {name_msft} @ {date_msft}")
    else:
        print(f"❌ VERIFICATION FAILED: {name_msft} @ {date_msft}")
        print(f"   Expected: {expected_hash_msft.hex()}")
        print(f"   On-Chain: {on_chain_hash_msft.hex()}")


def main():
    """
    Main orchestration function.
    """
    # Step 1: Install and set up the Solidity compiler
    install_and_set_solc(SOLIDITY_VERSION)
    
    # Step 2: Compile the contract
    abi, bytecode = compile_contract(CONTRACT_SOURCE_FILE, 'DataOracle')
    
    # Step 3: Connect to the local blockchain
    w3 = connect_to_blockchain(LOCAL_NODE_URL)
    
    # Step 4: Deploy the contract
    contract_address = deploy_contract(w3, abi, bytecode)
    
    # Step 5: Save deployment artifacts for the submission script
    save_deployment_artifacts(abi, contract_address, ARTIFACTS_FILE)
    
    # Step 6: Run the data submission script
    run_submission_script(SUBMISSION_SCRIPT)
    
    # Step 7: Verify the data on-chain
    verify_on_chain_data(w3, contract_address, abi)
    
    print("\n--- Immutable Data Oracle Deployment Complete ---")


if __name__ == "__main__":
    main()