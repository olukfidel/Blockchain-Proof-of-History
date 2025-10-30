# File: app.py
# This single file combines all project files into one Streamlit application.
# This version reads from a local 'stock_data.csv' file.

import streamlit as st
import pandas as pd
import hashlib
import json
import os
import sys
import shutil
import io
import traceback
from web3 import Web3
from solcx import compile_source, install_solc, get_solc_version, set_solc_version

# --- 1. Embedded File Contents ---

# Content from README.md
README_CONTENT = """
# Immutable Data Oracle (Proof-of-History)

## 🚀 Overview

This project implements an "Immutable Data Oracle" based on a "Proof-of-History" philosophy. Its purpose is to create a verifiable, on-chain, auditable log that proves specific off-chain historical data (like stock prices) existed in a certain state at a certain time and has not been tampered with.

The architecture consists of:
1.  **A Solidity Smart Contract:** `DataOracle.sol` serves as the on-chain registry. It's owned by a single address and only that owner can submit data. It enforces immutability by preventing data for a given ID/date pair from ever being overwritten.
2.  **This Streamlit App:** This app manages the entire system:
    * It compiles the Solidity code in real-time.
    * It connects to your local blockchain and deploys the contract.
    * It reads a **local `stock_data.csv` file**, hashes each row, and submits the hash to the smart contract.
    * It runs an on-chain verification against the same CSV file to prove the data was stored correctly.

## 🗂️ Project Components (Viewable in Tabs)

* `DataOracle.sol`: The core Solidity smart contract that stores the hashes.
* `stock_data.csv`: **A local CSV file** you must provide, containing the sample data to be processed.
* `Python Logic`: The core logic from `deploy_and_verify.py` and `submit_to_oracle.py` has been integrated directly into this Streamlit application.
"""

# Content from DataOracle.sol
CONTRACT_SOURCE_CODE = """
// File: DataOracle.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// This import will be resolved by our Python script, which creates
// the file in a temporary directory.
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title DataOracle
 * @notice This contract serves as an immutable on-chain registry for data hashes.
 * It implements a "Proof-of-History" pattern where a trusted owner (this script)
 * can submit hashes of off-chain data.
 * Once submitted, a hash for a specific name and date cannot be altered.
 */
contract DataOracle is Ownable {
    
    // 1. State Variable: The core data structure
    // A nested mapping: string (e.g., "AAPL") -> uint256 (e.g., 20231025) -> bytes32 (the hash)
    mapping(string => mapping(uint256 => bytes32)) public dataHashes;

    // 2. Event: Logs submissions for off-chain listeners
    event DataHashSubmitted(string indexed name, uint256 indexed date, bytes32 hash);

    /**
     * @notice Creates the contract and sets the deployer as the initial owner.
     * We pass the deployer's address to the Ownable constructor.
     */
    constructor() Ownable(msg.sender) {
        // Owner is set by the Ownable constructor
    }

    /**
     * @notice Submits a data hash for a given name and date.
     * @dev This function can ONLY be called by the contract owner.
     * It enforces immutability by reverting if data already exists.
     */
    function submitDataHash(string memory name, uint256 date, bytes32 hash) 
        public 
        onlyOwner // Modifier: Ensures only the owner can call this.
    {
        // --- Security Check ---
        // This is the most critical line for immutability.
        // We check if the storage slot is empty (default is 0x0).
        require(
            dataHashes[name][date] == 0, 
            "Data for this date and name already submitted"
        );
        
        // --- State Change ---
        dataHashes[name][date] = hash;

        // --- Logging ---
        emit DataHashSubmitted(name, date, hash);
    }

    /**
     * @notice Retrieves a stored data hash for a given name and date.
     * @dev This is a public `view` function (free to call off-chain).
     * @return bytes32 The stored hash. Will return 0x0 if no hash is stored.
     */
    function getHash(string memory name, uint256 date) 
        public 
        view 
        returns (bytes32) 
    {
        // Simply return the value from the mapping.
        return dataHashes[name][date];
    }
}
"""

# --- Required OpenZeppelin Dependencies (v5.4.0) ---

# This is 'node_modules/@openzeppelin/contracts/utils/Context.sol'
OZ_CONTEXT_SOURCE = """
// SPDX-License-Identifier: MIT
// OpenZeppelin Contracts (last updated v5.0.1) (utils/Context.sol)
pragma solidity ^0.8.20;

/**
 * @dev Provides information about the current execution context, including the
 * sender of the transaction and its data. While these are generally available
 * via msg.sender and msg.data, they should not be accessed in such a direct
 * manner, since when dealing with meta-transactions the account sending and
 * paying for execution may not be the actual sender (as far as an application
 * is concerned).
 *
 * This contract is only required for intermediate, library-like contracts.
 */
abstract contract Context {
    function _msgSender() internal view virtual returns (address) {
        return msg.sender;
    }

    function _msgData() internal view virtual returns (bytes calldata) {
        return msg.data;
    }

    function _contextSuffixLength() internal view virtual returns (uint256) {
        return 0;
    }
}
"""

# This is 'node_modules/@openzeppelin/contracts/access/Ownable.sol'
OZ_OWNABLE_SOURCE = """
// SPDX-License-Identifier: MIT
// OpenZeppelin Contracts (last updated v5.0.1) (access/Ownable.sol)
pragma solidity ^0.8.20;

import "../utils/Context.sol";

/**
 * @dev Contract module which provides a basic access control mechanism, where
 * there is an account (an owner) that can be granted exclusive access to
 * specific functions.
 *
 * By default, the owner account will be the one that deploys the contract. This
 * can later be changed with {transferOwnership}.
 *
 * This module is used through inheritance. It will make available the modifier
 * `onlyOwner`, which can be applied to your functions to restrict their use to
 * the owner.
 */
abstract contract Ownable is Context {
    address private _owner;

    /**
     * @dev The caller account is not authorized to perform an operation.
     */
    error OwnableUnauthorizedAccount(address account);

    /**
     * @dev The owner is not a valid owner account. (e.g. `address(0)`)
     */
    error OwnableInvalidOwner(address owner);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    /**
     * @dev Initializes the contract setting the address provided by the deployer as the
     * initial owner.
     */
    constructor(address initialOwner) {
        if (initialOwner == address(0)) {
            revert OwnableInvalidOwner(address(0));
        }
        _transferOwnership(initialOwner);
    }

    /**
     * @dev Throws if called by any account other than the owner.
     */
    modifier onlyOwner() {
        _checkOwner();
        _;
    }

    /**
     * @dev Returns the address of the current owner.
     */
    function owner() public view virtual returns (address) {
        return _owner;
    }

    /**
     * @dev Throws if the sender is not the owner.
     */
    function _checkOwner() internal view virtual {
        if (owner() != _msgSender()) {
            revert OwnableUnauthorizedAccount(_msgSender());
        }
    }

    /**
     * @dev Leaves the contract without owner. It will not be possible to call
     * `onlyOwner` functions anymore. Can only be called by the current owner.
     *
     * NOTE: Renouncing ownership will leave the contract without an owner,
     * thereby disabling any functionality that is only available to the owner.
     */
    function renounceOwnership() public virtual onlyOwner {
        _transferOwnership(address(0));
    }

    /**
     * @dev Transfers ownership of the contract to a new account (`newOwner`).
     * Can only be called by the current owner.
     */
    function transferOwnership(address newOwner) public virtual onlyOwner {
        if (newOwner == address(0)) {
            revert OwnableInvalidOwner(address(0));
        }
        _transferOwnership(newOwner);
    }

    /**
     * @dev Transfers ownership of the contract to a new account (`newOwner`).
     * Internal function without access restriction.
     */
    function _transferOwnership(address newOwner) internal virtual {
        address oldOwner = _owner;
        _owner = newOwner;
        emit OwnershipTransferred(oldOwner, newOwner);
    }
}
"""

# --- 2. Configuration Constants ---
SOLIDITY_VERSION = '0.8.20'
CONTRACT_NAME = 'DataOracle'
TEMP_CONTRACT_DIR = 'temp_contracts'
DATA_FILE = 'stock_data.csv'


# --- 3. Core Logic Functions (Adapted from .py files) ---

def setup_temp_contracts(status_container):
    """
    Creates a temporary directory structure to hold OpenZeppelin contracts
    so the Solidity compiler can resolve the imports.
    """
    status_container.write("Setting up temporary contract directory for compilation...")
    
    # Define paths
    base_path = os.path.join(TEMP_CONTRACT_DIR, 'node_modules', '@openzeppelin', 'contracts')
    access_path = os.path.join(base_path, 'access')
    utils_path = os.path.join(base_path, 'utils')

    # Create directories
    os.makedirs(access_path, exist_ok=True)
    os.makedirs(utils_path, exist_ok=True)

    # Write the .sol files
    with open(os.path.join(access_path, 'Ownable.sol'), 'w') as f:
        f.write(OZ_OWNABLE_SOURCE)
        
    with open(os.path.join(utils_path, 'Context.sol'), 'w') as f:
        f.write(OZ_CONTEXT_SOURCE)
        
    status_container.write("Temporary OpenZeppelin contracts created.")
    return os.path.join(TEMP_CONTRACT_DIR, 'node_modules')

def cleanup_temp_contracts():
    """Removes the temporary contract directory."""
    if os.path.exists(TEMP_CONTRACT_DIR):
        shutil.rmtree(TEMP_CONTRACT_DIR)

def install_and_set_solc(version, status_container):
    """
    Installs and sets the correct solc version using py-solc-x.
    """
    status_container.write(f"--- Checking for solc version {version} ---")
    try:
        current_version = get_solc_version()
        if current_version.base_version != version:
            status_container.write(f"Current version is {current_version}. Installing {version}...")
            install_solc(version)
        set_solc_version(version)
        status_container.write(f"Solc {version} is correctly set.")
    except Exception as e:
        status_container.write(f"Error installing solc: {e}")
        st.error(f"Solc installation failed: {e}. Please ensure solc is available or py-solc-x can install it.")
        raise

def compile_contract(source_code, contract_name, remapping_path, status_container):
    """
    Reads and compiles the Solidity contract.
    Returns the ABI and Bytecode.
    """
    status_container.write(f"--- Compiling {contract_name}.sol ---")

    # The remapping tells the compiler: when you see "@openzeppelin/", 
    # look in the temporary directory we just constructed.
    remappings = [
        f'@openzeppelin/={remapping_path}/@openzeppelin/'
    ]
    
    # Compile the source code
    compiled_sol = compile_source(
        source_code,
        output_values=['abi', 'bin'],
        solc_version=SOLIDITY_VERSION,
        import_remappings=remappings 
    )
    
    contract_id = f'<stdin>:{contract_name}'
    
    if contract_id not in compiled_sol:
        status_container.write("Error: Contract compilation failed.")
        st.error(f"Compilation failed. Available keys: {compiled_sol.keys()}")
        raise Exception("Contract compilation failed")
        
    abi = compiled_sol[contract_id]['abi']
    bytecode = compiled_sol[contract_id]['bin']
    
    status_container.write("Contract compiled successfully.")
    return abi, bytecode

def connect_to_blockchain(node_url, status_container):
    """
    Connects to the local blockchain node.
    Returns the Web3 instance.
    """
    status_container.write(f"--- Connecting to Blockchain at {node_url} ---")
    w3 = Web3(Web3.HTTPProvider(node_url))
    
    if not w3.is_connected():
        status_container.write(f"Error: Failed to connect to {node_url}.")
        st.error(f"Failed to connect to blockchain. Please ensure Ganache/Anvil is running at {node_url}.")
        raise ConnectionError("Failed to connect to blockchain")
        
    w3.eth.default_account = w3.eth.accounts[0]
    status_container.write(f"Connected successfully. Using Owner Account: {w3.eth.default_account}")
    return w3

def deploy_contract(w3, abi, bytecode, status_container):
    """
    Deploys the contract to the blockchain.
    Returns the deployed contract address.
    """
    status_container.write("--- Deploying Contract ---")
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    try:
        tx_hash = Contract.constructor().transact()
        status_container.write(f"Deployment transaction sent. Hash: {tx_hash.hex()}")
    except Exception as e:
        status_container.write(f"Error during deployment: {e}")
        st.error(f"Deployment failed: {e}. Check account funds or node configuration.")
        raise
        
    status_container.write("Waiting for transaction receipt...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress
    
    status_container.write("Contract deployed successfully!")
    status_container.write(f"Contract Address: {contract_address}")
    return contract_address

def run_submission_logic(w3, abi, contract_address, status_container):
    """
    Reads local 'stock_data.csv' file and submits hashes to the oracle contract.
    This replaces 'submit_to_oracle.py'.
    """
    
    # Check if the data file exists
    if not os.path.exists(DATA_FILE):
        status_container.write(f"CRITICAL ERROR: '{DATA_FILE}' not found in the same directory.")
        st.error(f"Error: '{DATA_FILE}' not found. Please create this file in the same directory as the app.")
        raise FileNotFoundError(f"'{DATA_FILE}' not found.")
        
    status_container.write(f"--- Reading data from local file: {DATA_FILE} ---")
    
    # Instantiate the deployed contract
    oracle_contract = w3.eth.contract(address=contract_address, abi=abi)
    
    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        status_container.write(f"Error reading {DATA_FILE}: {e}")
        st.error(f"Failed to read {DATA_FILE}. Ensure it is a valid CSV. Error: {e}")
        raise

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        try:
            # 1. Format Data
            name = row['Name']
            date_uint = int(str(row['date']).replace('-', ''))
            
            # 2. Create Hash Payload (must be exact)
            data_string = (
                f"{row['date']}"
                f"{row['open']}"
                f"{row['high']}"
                f"{row['low']}"
                f"{row['close']}"
                f"{row['volume']}"
                f"{row['Name']}"
            )
            
            # 3. Calculate Hash
            data_hash_bytes = hashlib.sha256(data_string.encode()).digest()

            # 4. Submit to Blockchain
            status_container.write(f"Submitting hash for {name} on {row['date']}...")
            
            tx_hash = oracle_contract.functions.submitDataHash(
                name,
                date_uint,
                data_hash_bytes
            ).transact()
            
            w3.eth.wait_for_transaction_receipt(tx_hash)
            status_container.write(f"  -> Success! TxHash: {tx_hash.hex()}")

        except Exception as e:
            error_message = str(e)
            if "Data for this date and name already submitted" in error_message:
                status_container.write(f"  -> INFO: Data for {name} on {row['date']} already submitted. Skipping.")
            else:
                status_container.write(f"  -> ERROR submitting {name} on {row['date']}: {e}")
                st.error(f"Submission failed for {name}: {e}")
                raise

    status_container.write("--- Data submission process finished. ---")

def verify_on_chain_data(w3, contract_address, abi, status_container):
    """
    Performs the final verification by re-calculating hashes
    and comparing them to the data stored on-chain.
    This will read the *same* local CSV file used for submission.
    """
    status_container.write("--- Final On-Chain Verification ---")
    
    if not os.path.exists(DATA_FILE):
        status_container.write(f"CRITICAL ERROR: '{DATA_FILE}' not found for verification.")
        st.error(f"Error: '{DATA_FILE}' not found. Cannot run verification.")
        raise FileNotFoundError(f"'{DATA_FILE}' not found.")
        
    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        status_container.write(f"Error reading {DATA_FILE} for verification: {e}")
        st.error(f"Failed to read {DATA_FILE} for verification. Error: {e}")
        raise
        
    oracle_contract = w3.eth.contract(address=contract_address, abi=abi)
    
    all_verified = True
    
    # Verify every row in the CSV
    for index, row in df.iterrows():
        try:
            name = row['Name']
            date_uint = int(str(row['date']).replace('-', ''))
            
            # Re-create the exact hash payload
            data_string = (
                f"{row['date']}"
                f"{row['open']}"
                f"{row['high']}"
                f"{row['low']}"
                f"{row['close']}"
                f"{row['volume']}"
                f"{row['Name']}"
            )
            
            expected_hash = hashlib.sha256(data_string.encode()).digest()
            
            # Call the contract's view function
            status_container.write(f"Verifying {name} @ {date_uint}...")
            on_chain_hash = oracle_contract.functions.getHash(name, date_uint).call()
            
            # Compare
            if on_chain_hash == expected_hash:
                status_container.write(f"  -> ✅ VERIFICATION SUCCESS")
            else:
                status_container.write(f"  -> ❌ VERIFICATION FAILED")
                status_container.write(f"     Expected: {expected_hash.hex()}")
                status_container.write(f"     On-Chain: {on_chain_hash.hex()}")
                st.error(f"Verification Failed for {name} @ {date_uint}!")
                all_verified = False
                
        except Exception as e:
            status_container.write(f"  -> ❌ ERROR during verification for {name}: {e}")
            st.error(f"An error occurred during verification for {name}: {e}")
            all_verified = False
    
    if all_verified:
        status_container.write("--- All items in CSV verified successfully! ---")
    else:
        status_container.write("--- One or more verifications failed. ---")


# --- 4. Streamlit UI ---

def main():
    st.set_page_config(page_title="Immutable Data Oracle", layout="wide")
    st.title("🛡️ Immutable Data Oracle Showcase")
    st.caption("A live demonstration of a 'Proof-of-History' smart contract system.")

    # Initialize session state to store deployment info
    if 'deployment_info' not in st.session_state:
        st.session_state.deployment_info = None

    tab1, tab2, tab3 = st.tabs(["🚀 Welcome & Overview", "⚙️ Run the Demonstration", "🔬 View Source Code"])

    # --- Tab 1: Welcome ---
    with tab1:
        st.markdown(README_CONTENT)

    # --- Tab 2: The Demonstration ---
    with tab2:
        st.header("End-to-End System Test")
        st.markdown(
            "Click the button below to run the full, end-to-end process. "
            "This will compile, deploy, submit data, and verify the contract on your local blockchain."
        )
        
        st.info(
            "**Prerequisites:**\n"
            "1.  Please ensure your local blockchain (Ganache/Anvil) is running at the URL below.\n"
            f"2.  You **must** have a `{DATA_FILE}` file in the same directory as this `app.py` script.",
            icon="📡"
        )
        
        node_url = st.text_input(
            "Local Blockchain Node URL", 
            "http://127.0.0.1:8545"
        )
        
        st.warning(
            "**Note:** To run this demo *again*, you **must restart your local blockchain** "
            "(e.g., restart Ganache/Anvil) to get a fresh, empty state. "
            "Otherwise, the 'submit' step will fail (as designed) because the data already exists.", 
            icon="ℹ️"
        )

        if st.button("🚀 Run Full Deployment & Verification", type="primary", use_container_width=True):
            remapping_path = None
            try:
                # Use st.status for a clean, expanding log
                with st.status("Running end-to-end process...", expanded=True) as status:
                    
                    # Step 0: Create temp files for compilation
                    remapping_path = setup_temp_contracts(status)
                    
                    # Step 1: Install and set up the Solidity compiler
                    install_and_set_solc(SOLIDITY_VERSION, status)
                    
                    # Step 2: Compile the contract
                    abi, bytecode = compile_contract(
                        CONTRACT_SOURCE_CODE, 
                        CONTRACT_NAME, 
                        remapping_path,
                        status
                    )
                    
                    # Step 3: Connect to the local blockchain
                    w3 = connect_to_blockchain(node_url, status)
                    
                    # Step 4: Deploy the contract
                    contract_address = deploy_contract(w3, abi, bytecode, status)
                    
                    # Step 5: Save deployment artifacts to session state
                    status.update(label="Saving deployment artifacts to session...")
                    st.session_state.deployment_info = {
                        'abi': abi,
                        'address': contract_address
                    }
                    status.write(f"Artifacts saved. Address: {contract_address}")
                    
                    # Step 6: Run the data submission logic
                    status.update(label="Submitting data to the oracle contract...")
                    run_submission_logic(w3, abi, contract_address, status)
                    
                    # Step 7: Verify the data on-chain
                    status.update(label="Verifying data on-chain...")
                    verify_on_chain_data(w3, contract_address, abi, status)
                    
                    status.update(label="Process Complete!", state="complete", expanded=True)
                
                st.success("✅ End-to-end demonstration complete!")
                st.subheader("Deployment Results")
                st.json({
                    "contractAddress": st.session_state.deployment_info['address'],
                    "message": "Contract deployed, data submitted, and hashes verified."
                })
                
            except Exception as e:
                # Catch any errors during the process
                st.error(f"An error occurred: {e}")
                traceback.print_exc() # Prints full traceback to console for debugging
                if 'status' in locals():
                    status.update(label="Process Failed", state="error", expanded=True)
            
            finally:
                # Always clean up temp files
                cleanup_temp_contracts()

    # --- Tab 3: Source Code ---
    with tab3:
        st.header("Project Source Files")
        st.markdown("These are the core files that were combined to create this application.")

        st.subheader("`DataOracle.sol`")
        st.markdown("The core Solidity smart contract that acts as the on-chain registry.")
        st.code(CONTRACT_SOURCE_CODE, language="solidity")

        st.subheader(f"`{DATA_FILE}` (Local File)")
        st.markdown(
            "This application now reads data from a local file named "
            f"`{DATA_FILE}` that **must be placed in the same directory as the app.**"
        )
        st.markdown("The CSV file must have the following columns:")
        st.code("date,open,high,low,close,volume,Name", language="csv")
        st.markdown("Here is an example of what the content should look like:")
        st.code(
            "date,open,high,low,close,volume,Name\n"
            "2023-10-25,170.65,173.06,170.65,171.80,57157115,AAPL\n"
            "2023-10-26,340.54,341.60,327.89,327.89,37828715,MSFT",
            language="csv"
        )
        
        st.subheader("OpenZeppelin Dependencies")
        st.markdown(
            "The following contracts are imported by `DataOracle.sol`. "
            "They are temporarily written to disk during compilation to resolve the imports."
        )
        st.code(OZ_OWNABLE_SOURCE, language="solidity")
        st.code(OZ_CONTEXT_SOURCE, language="solidity")


if __name__ == "__main__":
    main()