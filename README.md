
# Immutable Data Oracle (Proof-of-History)

## 🚀 Overview

This project implements an "Immutable Data Oracle" using a "Proof-of-History" philosophy. Its purpose is to create a verifiable, on-chain, auditable log that proves specific off-chain historical data (like stock prices) existed in a certain state at a certain time and has not been tampered with.

The architecture has been consolidated into two main components:

1.  **A Solidity Smart Contract:** `DataOracle.sol` logic is embedded within the Streamlit app. It serves as the on-chain registry, owned by a single address. It enforces immutability by preventing data for a given ID/date pair from ever being overwritten.
2.  **A Streamlit Application:** A single `app.py` file provides a full web UI to manage the entire system. This app handles:
      * Real-time compilation of the Solidity code.
      * Connection to your local blockchain.
      * Deployment of the `DataOracle` contract.
      * Reading a local `stock_data.csv` file.
      * Hashing each row and submitting the hashes to the smart contract.
      * Verifying the on-chain data against the local file.

## 🗂️ File Structure

  * `app.py`: **This is the all-in-one Streamlit application you run.** It contains all the Python logic, the Solidity contract code, and the web interface.
  * `stock_data.csv`: **(User-Provided)** This is the local data file that the Streamlit app will read. You must create this file in the same directory as `app.py`.

## ⚙️ Dependencies

  * **A Local Blockchain:** You must have a local blockchain node running at `http://127.0.0.1:8545`.
      * [Ganache](https://trufflesuite.com/ganache/)
      * [Anvil](https://book.getfoundry.sh/anvil/) (part of Foundry)
  * **Python 3:** (3.8 or newer recommended).
  * **Python Libraries:** `streamlit`, `web3`, `pandas`, `py-solc-x`.

## 🏁 Setup & Run Instructions

Follow these steps exactly to run the project.

### Step 1: Install Python Dependencies

Open your terminal and install the required Python libraries using `pip`.

```bash
pip install streamlit web3 pandas py-solc-x
```

### Step 2: Create Your Data File

In the *same directory* where you will save `app.py`, you must create a file named `stock_data.csv`.

The file **must** contain the columns: `date,open,high,low,close,volume,Name`.

*Example `stock_data.csv` content:*

```csv
date,open,high,low,close,volume,Name
2023-10-25,170.65,173.06,170.65,171.80,57157115,AAPL
2023-10-26,340.54,341.60,327.89,327.89,37828715,MSFT
```

### Step 3: Run Your Local Blockchain

Start your local blockchain (Ganache, Anvil, etc.). Ensure it is running and accessible at `http://127.0.0.1:8545`.

### Step 4: Run the Streamlit Application

In your terminal, navigate to the directory containing `app.py` and `stock_data.csv`. Run the following command:

```bash
streamlit run app.py
```

Your web browser will automatically open, displaying the application. You can then navigate to the "⚙️ Run the Demonstration" tab to deploy and verify the system.
