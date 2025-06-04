# benchmark_runner.py
import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from lib.l2_utils import connect_to_l2, get_dynamic_gas_price
from lib.transaction_utils import (
    execute_p2p_transfer, 
    deploy_erc20_contract, 
    execute_erc20_transfer,
    deploy_nft_contract,      # Import new NFT functions
    execute_nft_mint,
    execute_nft_transfer
)

# --- Configuration ---
load_dotenv()

# Script Configuration
L2_CONFIG_NAME = "arbitrum_local_nitro"
RUN_NAME = "full_suite_test_1" # Updated run name
TRANSACTION_DELAY_SECONDS = 0.5

# P2P ETH Transfer Config
DO_P2P_ETH_TRANSFERS = True 
NUMBER_OF_P2P_TRANSACTIONS = 2
AMOUNT_TO_SEND_ETH = 0.0001

# ERC20 Token Config
DO_ERC20_OPERATIONS = True 
TOKEN_NAME = "MyBenchToken"
TOKEN_SYMBOL = "MBT"
TOKEN_INITIAL_SUPPLY = 1000000 
NUMBER_OF_ERC20_TRANSFERS = 2 # Reduced for quicker combined test
AMOUNT_TO_TRANSFER_TOKENS = 10 

# NFT (ERC721) Config
DO_NFT_OPERATIONS = True # Set to False to skip NFT operations
NFT_NAME = "MyBenchNFT"
NFT_SYMBOL = "MBN"
NUMBER_OF_NFT_MINTS = 2    # How many NFTs to mint
# Note: Transfers will be attempted for each successfully minted NFT

# Shared Config
# This recipient will receive ETH, ERC20s, and NFTs
GENERAL_RECIPIENT_ADDRESS = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf" 
# You might want a different recipient for NFTs if the general one is also the sender/owner
NFT_TRANSFER_RECIPIENT_ADDRESS = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B" # Example different address

# Load L2 configurations
try:
    with open('config/l2_nodes.json', 'r') as f: L2_CONFIGS = json.load(f)
except FileNotFoundError: print("❌ Error: config/l2_nodes.json not found."); exit()
except json.JSONDecodeError: print("❌ Error: config/l2_nodes.json is not valid JSON."); exit()

if L2_CONFIG_NAME not in L2_CONFIGS:
    print(f"❌ Error: L2 configuration '{L2_CONFIG_NAME}' not found."); exit()
CURRENT_L2_CONFIG = L2_CONFIGS[L2_CONFIG_NAME]

SENDER_PK = os.getenv("SENDER_PRIVATE_KEY_1")
if not SENDER_PK: print("❌ Error: SENDER_PRIVATE_KEY_1 not found in .env file."); exit()

# --- Main Execution Logic ---
if __name__ == "__main__":
    print(f"🚀 Starting Benchmark Run: {RUN_NAME} on L2: {L2_CONFIG_NAME}")
    
    w3 = None
    try:
        w3 = connect_to_l2(CURRENT_L2_CONFIG["rpc_url"], CURRENT_L2_CONFIG.get("chain_id")) # Use .get for optional chain_id
    except Exception as e:
        print(f"Failed to connect to L2: {e}"); exit()

    all_results = []
    transaction_counter = 0
    sender_account_for_log = w3.eth.account.from_key(SENDER_PK)
    print(f"\n--- Using Sender Account: {sender_account_for_log.address} ---")

    # --- P2P ETH Transfers ---
    if DO_P2P_ETH_TRANSFERS:
        print(f"\n--- Starting P2P ETH Transfers ({NUMBER_OF_P2P_TRANSACTIONS} transactions) ---")
        for i in range(NUMBER_OF_P2P_TRANSACTIONS):
            transaction_counter += 1; run_id = f"{RUN_NAME}_p2p_tx_{transaction_counter}"
            print(f"Attempting P2P ETH Tx {i+1}/{NUMBER_OF_P2P_TRANSACTIONS}...")
            try:
                gas_price_wei = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_p2p_transfer(w3, SENDER_PK, GENERAL_RECIPIENT_ADDRESS, AMOUNT_TO_SEND_ETH, gas_price_wei, run_identifier=run_id)
                all_results.append(result)
                if result['status'] == 'Success': print(f"✅ P2P ETH Tx {i+1} successful. Hash: {result.get('tx_hash')}")
                else: print(f"⚠️ P2P ETH Tx {i+1} failed. Reason: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error P2P ETH tx {i+1}: {e}"); all_results.append({'run_identifier': run_id, 'action': 'p2p_eth_transfer', 'status': 'CriticalError', 'error_message': str(e)})
            if i < NUMBER_OF_P2P_TRANSACTIONS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)

    # --- ERC20 Token Operations ---
    deployed_erc20_address = None
    if DO_ERC20_OPERATIONS:
        print(f"\n--- Starting ERC20 Token Operations ---")
        transaction_counter += 1; deploy_run_id = f"{RUN_NAME}_erc20_deploy_{transaction_counter}"
        print(f"Attempting to deploy ERC20 token ('{TOKEN_NAME}')...")
        try:
            gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
            deploy_result = deploy_erc20_contract(w3, SENDER_PK, gas_price_wei_deploy, TOKEN_NAME, TOKEN_SYMBOL, TOKEN_INITIAL_SUPPLY, run_identifier=deploy_run_id)
            all_results.append(deploy_result)
            if deploy_result['status'] == 'Success': deployed_erc20_address = deploy_result.get('contract_address'); print(f"✅ ERC20 Contract '{TOKEN_NAME}' deployed at: {deployed_erc20_address}")
            else: print(f"⚠️ ERC20 Contract deployment failed. Reason: {deploy_result.get('error_message', 'Unknown')}")
        except Exception as e:
            print(f"Critical error ERC20 deployment: {e}"); all_results.append({'run_identifier': deploy_run_id, 'action': 'deploy_erc20', 'status': 'CriticalError', 'error_message': str(e)})

        if deployed_erc20_address:
            print(f"\n--- Starting ERC20 Token Transfers ({NUMBER_OF_ERC20_TRANSFERS} transactions) ---")
            for i in range(NUMBER_OF_ERC20_TRANSFERS):
                transaction_counter += 1; transfer_run_id = f"{RUN_NAME}_erc20_transfer_tx_{transaction_counter}"
                print(f"Attempting ERC20 Token Tx {i+1}/{NUMBER_OF_ERC20_TRANSFERS}...")
                try:
                    gas_price_wei_transfer = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    transfer_result = execute_erc20_transfer(w3, SENDER_PK, deployed_erc20_address, GENERAL_RECIPIENT_ADDRESS, AMOUNT_TO_TRANSFER_TOKENS, gas_price_wei_transfer, run_identifier=transfer_run_id)
                    all_results.append(transfer_result)
                    if transfer_result['status'] == 'Success': print(f"✅ ERC20 Tx {i+1} successful. Hash: {transfer_result.get('tx_hash')}")
                    else: print(f"⚠️ ERC20 Tx {i+1} failed. Reason: {transfer_result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error ERC20 tx {i+1}: {e}"); all_results.append({'run_identifier': transfer_run_id, 'action': 'erc20_transfer', 'status': 'CriticalError', 'error_message': str(e)})
                if i < NUMBER_OF_ERC20_TRANSFERS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        else: print("Skipping ERC20 transfers: contract deployment failed or skipped.")

    # --- NFT (ERC721) Operations ---
    deployed_nft_address = None
    minted_token_ids = [] # To store IDs of successfully minted NFTs
    if DO_NFT_OPERATIONS:
        print(f"\n--- Starting NFT (ERC721) Operations ---")
        # 1. Deploy NFT Contract
        transaction_counter += 1; deploy_nft_run_id = f"{RUN_NAME}_nft_deploy_{transaction_counter}"
        print(f"Attempting to deploy NFT ('{NFT_NAME}')...")
        try:
            gas_price_wei_deploy_nft = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
            deploy_nft_result = deploy_nft_contract(w3, SENDER_PK, gas_price_wei_deploy_nft, NFT_NAME, NFT_SYMBOL, run_identifier=deploy_nft_run_id)
            all_results.append(deploy_nft_result)
            if deploy_nft_result['status'] == 'Success': deployed_nft_address = deploy_nft_result.get('contract_address'); print(f"✅ NFT Contract '{NFT_NAME}' deployed at: {deployed_nft_address}")
            else: print(f"⚠️ NFT Contract deployment failed. Reason: {deploy_nft_result.get('error_message', 'Unknown')}")
        except Exception as e:
            print(f"Critical error NFT deployment: {e}"); all_results.append({'run_identifier': deploy_nft_run_id, 'action': 'deploy_nft', 'status': 'CriticalError', 'error_message': str(e)})

        # 2. Mint NFTs (only if deployment was successful)
        if deployed_nft_address:
            print(f"\n--- Starting NFT Mints ({NUMBER_OF_NFT_MINTS} mints) ---")
            for i in range(NUMBER_OF_NFT_MINTS):
                transaction_counter += 1; mint_run_id = f"{RUN_NAME}_nft_mint_tx_{transaction_counter}"
                # Minting to the sender/owner themselves first
                print(f"Attempting NFT Mint {i+1}/{NUMBER_OF_NFT_MINTS} to {sender_account_for_log.address}...")
                try:
                    gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    mint_result, minted_id = execute_nft_mint(w3, SENDER_PK, deployed_nft_address, sender_account_for_log.address, gas_price_wei_mint, run_identifier=mint_run_id)
                    all_results.append(mint_result)
                    if mint_result['status'] == 'Success' and minted_id is not None:
                        minted_token_ids.append(minted_id) # Store for transfer
                        print(f"✅ NFT Mint {i+1} successful. Token ID: {minted_id}, Hash: {mint_result.get('tx_hash')}")
                    else: print(f"⚠️ NFT Mint {i+1} failed. Reason: {mint_result.get('error_message', 'Unknown or no token ID found')}")
                except Exception as e:
                    print(f"Critical error NFT mint {i+1}: {e}"); all_results.append({'run_identifier': mint_run_id, 'action': 'nft_mint', 'status': 'CriticalError', 'error_message': str(e)})
                if i < NUMBER_OF_NFT_MINTS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        else: print("Skipping NFT mints: NFT contract deployment failed or skipped.")

        # 3. Transfer Minted NFTs (only if minting happened)
        if deployed_nft_address and minted_token_ids:
            print(f"\n--- Starting NFT Transfers ({len(minted_token_ids)} transfers) ---")
            for i, token_id_to_transfer in enumerate(minted_token_ids):
                transaction_counter += 1; transfer_nft_run_id = f"{RUN_NAME}_nft_transfer_tx_{transaction_counter}_id_{token_id_to_transfer}"
                print(f"Attempting NFT Transfer {i+1}/{len(minted_token_ids)} of Token ID {token_id_to_transfer} to {NFT_TRANSFER_RECIPIENT_ADDRESS}...")
                try:
                    gas_price_wei_transfer_nft = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    transfer_nft_result = execute_nft_transfer(w3, SENDER_PK, deployed_nft_address, NFT_TRANSFER_RECIPIENT_ADDRESS, token_id_to_transfer, gas_price_wei_transfer_nft, run_identifier=transfer_nft_run_id)
                    all_results.append(transfer_nft_result)
                    if transfer_nft_result['status'] == 'Success': print(f"✅ NFT Transfer {i+1} (ID: {token_id_to_transfer}) successful. Hash: {transfer_nft_result.get('tx_hash')}")
                    else: print(f"⚠️ NFT Transfer {i+1} (ID: {token_id_to_transfer}) failed. Reason: {transfer_nft_result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error NFT transfer {i+1} (ID: {token_id_to_transfer}): {e}"); all_results.append({'run_identifier': transfer_nft_run_id, 'action': 'nft_transfer', 'token_id_transferred': token_id_to_transfer, 'status': 'CriticalError', 'error_message': str(e)})
                if i < len(minted_token_ids) - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        elif deployed_nft_address:
             print("Skipping NFT transfers: No NFTs were successfully minted or minting was skipped.")
        else:
            print("Skipping NFT transfers: NFT contract deployment failed or skipped.")


    # --- Final Results Processing ---
    print("\n--- Benchmark Run Complete ---")
    if all_results:
        results_df = pd.DataFrame(all_results)
        desired_columns = [
            'run_identifier', 'action', 'sender_address', 'nonce', 'tx_hash', 'status', 
            'contract_address', 'token_id_minted', 'token_id_transferred', 
            'block_number', 'gas_used', 'configured_gas_price_gwei', 
            'effective_gas_price_gwei', 'fee_paid_eth', 'confirmation_time_sec', 'error_message'
        ]
        existing_columns = [col for col in desired_columns if col in results_df.columns]
        results_df = results_df.reindex(columns=existing_columns)

        print(results_df.to_string())
        if not os.path.exists('results'): os.makedirs('results')
        output_filename = f"results/{RUN_NAME}_{L2_CONFIG_NAME}.csv"
        results_df.to_csv(output_filename, index=False)
        print(f"\n📊 Results saved to {output_filename}")
    else:
        print("No results collected.")