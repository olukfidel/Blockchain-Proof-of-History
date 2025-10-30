# Immutable Data Oracle (Proof-of-History)

## 🚀 Overview

This project implements an "Immutable Data Oracle" based on a "Proof-of-History" philosophy. Its purpose is to create a verifiable, on-chain, auditable log that proves specific off-chain historical data (like stock prices) existed in a certain state at a certain time and has not been tampered with.

The architecture consists of:
1.  **A Solidity Smart Contract:** `DataOracle.sol` serves as the on-chain registry. It's owned by a single address and only that owner can submit data. It enforces immutability by preventing data for a given ID/date pair from ever being overwritten.
2.  **Python Scripts:** A set of Python scripts manage the system:
    * One script reads local data (e.g., a CSV), hashes each row, and submits the hash to the smart contract.
    * An orchestration script compiles, deploys, and verifies the entire system end-to-end.

## 🗂️ File Structure

* `DataOracle.sol`: The core Solidity smart contract that stores the hashes.
* `deploy_and_verify.py`: **This is the main script you run.** It compiles, deploys, and then verifies the entire system.
* `submit_to_oracle.py`: This script is **called automatically** by `deploy_and_verify.py`. It creates sample data, reads it, and pushes the data hashes to the deployed contract.
* `deployment_info.json`: (Generated) Stores the ABI and address of the deployed contract. This file acts as the "glue" between the deployment and submission scripts.
* `stock_data.csv`: (Generated) Sample stock data that is created and used by `submit_to_oracle.py`.

## ⚙️ Dependencies

* **A Local Blockchain:** You must have a local blockchain node running.
    * [Ganache](https://trufflesuite.com/ganache/) (`ganache-cli`)
    * [Anvil](https://book.getfoundry.sh/anvil/) (part of Foundry)
    * A Hardhat Node
* **Python 3:** (3.8 or newer recommended).
* **Solidity Compiler (solc):** The Python script will attempt to install the correct version for you using `py-solc-x`, but having `solc` available in your system's PATH is recommended.

## 🏁 Setup & Run Instructions

Follow these steps exactly to run the project.

### Step 1: Install Python Dependencies

Open your terminal and install the required Python libraries using `pip`.

```bash
pip install web3 pandas py-solc-x