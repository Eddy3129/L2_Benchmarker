#!/usr/bin/env python3
import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from web3 import Web3 # For Web3.to_wei, Web3.to_checksum_address etc.

# Assuming contract_loader.py is in lib/
from lib.l2_utils import connect_to_l2, get_dynamic_gas_price
from lib.transaction_utils import (
    execute_p2p_transfer, 
    deploy_simple_erc20,    
    execute_simple_erc20_mint,
    execute_approve_erc20, 
    execute_erc20_transfer,
    deploy_amm_pool_contract,
    execute_pool_set_tokens,  
    execute_add_liquidity,
    execute_amm_swap,  
    deploy_nft_contract,
    execute_nft_mint,
    execute_nft_transfer
)
# Import ABIs directly for contract interactions if needed for setup (e.g. decimals)
from lib.transaction_utils import TOKEN_A_ABI, TOKEN_A_BYTECODE, TOKEN_B_ABI, TOKEN_B_BYTECODE

# --- Configuration ---
load_dotenv()

# Script Configuration
L2_CONFIG_NAME = "arbitrum_local_nitro"
RUN_NAME = "amm_full_test_v1" 
TRANSACTION_DELAY_SECONDS = 0.5 # General delay

# P2P ETH Transfer Config
DO_P2P_ETH_TRANSFERS = True 
AMOUNT_TO_SEND_ETH = 0.01
NUMBER_OF_P2P_TRANSACTIONS = 1 # Keep low for combined test

# AMM Test Scenario Config
DO_AMM_OPERATIONS = True
TOKEN_A_LOG_NAME = "TokenA" # For logging
TOKEN_B_LOG_NAME = "TokenB" # For logging
# Amounts for minting (in full units, script will convert based on 18 decimals)
MINT_AMOUNT_TOKEN_A_UNITS = 10000 
MINT_AMOUNT_TOKEN_B_UNITS = 10000
# Amounts for adding liquidity (in full units)
LIQUIDITY_TOKEN_A_UNITS = 1000
LIQUIDITY_TOKEN_B_UNITS = 1000
# Amounts for swap (TokenA for TokenB)
SWAP_AMOUNT_TOKEN_A_IN_UNITS = 100
MIN_AMOUNT_TOKEN_B_OUT_UNITS = 1 # Slippage protection: min B tokens expected
NUMBER_OF_SWAPS = 2

# NFT (ERC721) Config (keep if you want to run these as well)
DO_NFT_OPERATIONS = True 
NFT_NAME = "MyBenchNFT"
NFT_SYMBOL = "MBN"
NUMBER_OF_NFT_MINTS = 1
NFT_TRANSFER_RECIPIENT_ADDRESS = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B" 

# Shared Config
GENERAL_RECIPIENT_ADDRESS = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"

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
        w3 = connect_to_l2(CURRENT_L2_CONFIG["rpc_url"], CURRENT_L2_CONFIG.get("chain_id"))
    except Exception as e:
        print(f"Failed to connect to L2: {e}"); exit()

    all_results = []
    transaction_counter = 0
    sender_address = w3.eth.account.from_key(SENDER_PK).address
    print(f"\n--- Using Sender Account: {sender_address} ---")

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
                print(f"Critical error P2P ETH tx {i+1}: {e}"); all_results.append({'run_identifier': run_id, 'action': 'p2p_eth_transfer', 'sender_address': sender_address, 'status': 'CriticalError', 'error_message': str(e)})
            if i < NUMBER_OF_P2P_TRANSACTIONS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)


    # --- AMM Operations ---
    deployed_token_a_address = None
    deployed_token_b_address = None
    deployed_amm_pool_address = None

    if DO_AMM_OPERATIONS:
        print(f"\n--- Starting AMM Operations ---")
        token_decimals = 18 # Assuming standard 18 decimals for TokenA/B

        # 1. Deploy TokenA
        transaction_counter += 1; deploy_ta_id = f"{RUN_NAME}_deploy_tokenA_{transaction_counter}"
        print(f"Attempting to deploy {TOKEN_A_LOG_NAME}...")
        try:
            gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
            result = deploy_simple_erc20(w3, SENDER_PK, gas_price_wei_deploy, TOKEN_A_ABI, TOKEN_A_BYTECODE, sender_address, TOKEN_A_LOG_NAME, run_identifier=deploy_ta_id)
            all_results.append(result)
            if result['status'] == 'Success': deployed_token_a_address = result.get('contract_address'); print(f"✅ {TOKEN_A_LOG_NAME} deployed: {deployed_token_a_address}")
            else: print(f"⚠️ {TOKEN_A_LOG_NAME} deployment failed: {result.get('error_message', 'Unknown')}")
        except Exception as e:
            print(f"Critical error deploying {TOKEN_A_LOG_NAME}: {e}"); all_results.append({'run_identifier': deploy_ta_id, 'action': f'deploy_{TOKEN_A_LOG_NAME.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
        time.sleep(TRANSACTION_DELAY_SECONDS)

        # 2. Deploy TokenB
        if deployed_token_a_address: # Proceed only if TokenA deployed
            transaction_counter += 1; deploy_tb_id = f"{RUN_NAME}_deploy_tokenB_{transaction_counter}"
            print(f"Attempting to deploy {TOKEN_B_LOG_NAME}...")
            try:
                gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = deploy_simple_erc20(w3, SENDER_PK, gas_price_wei_deploy, TOKEN_B_ABI, TOKEN_B_BYTECODE, sender_address, TOKEN_B_LOG_NAME, run_identifier=deploy_tb_id)
                all_results.append(result)
                if result['status'] == 'Success': deployed_token_b_address = result.get('contract_address'); print(f"✅ {TOKEN_B_LOG_NAME} deployed: {deployed_token_b_address}")
                else: print(f"⚠️ {TOKEN_B_LOG_NAME} deployment failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error deploying {TOKEN_B_LOG_NAME}: {e}"); all_results.append({'run_identifier': deploy_tb_id, 'action': f'deploy_{TOKEN_B_LOG_NAME.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

        # 3. Deploy AMM Pool (BasicPool)
        if deployed_token_a_address and deployed_token_b_address:
            transaction_counter += 1; deploy_pool_id = f"{RUN_NAME}_deploy_amm_pool_{transaction_counter}"
            print(f"Attempting to deploy AMM Pool...")
            try:
                gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                # BasicPool.sol constructor takes no arguments
                result = deploy_amm_pool_contract(w3, SENDER_PK, gas_price_wei_deploy, run_identifier=deploy_pool_id)
                all_results.append(result)
                if result['status'] == 'Success': deployed_amm_pool_address = result.get('contract_address'); print(f"✅ AMM Pool deployed: {deployed_amm_pool_address}")
                else: print(f"⚠️ AMM Pool deployment failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error deploying AMM Pool: {e}"); all_results.append({'run_identifier': deploy_pool_id, 'action': 'deploy_amm_pool', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

            # 3b. Set Tokens for AMM Pool (if pool constructor was empty and requires separate setting)
            # The BasicPool.sol from simpleCPMM requires setTokenA and setTokenB to be called by owner.
            if deployed_amm_pool_address:
                transaction_counter += 1; set_tokens_id = f"{RUN_NAME}_pool_set_tokens_{transaction_counter}"
                print(f"Attempting to set tokens for AMM Pool {deployed_amm_pool_address}...")
                try:
                    gas_price_wei_set = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    result = execute_pool_set_tokens(w3, SENDER_PK, gas_price_wei_set, deployed_amm_pool_address, deployed_token_a_address, deployed_token_b_address, run_identifier=set_tokens_id)
                    all_results.append(result)
                    if result['status'] == 'Success': print(f"✅ Tokens set for AMM Pool.")
                    else: print(f"⚠️ Failed to set tokens for AMM Pool: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error setting tokens for AMM Pool: {e}"); all_results.append({'run_identifier': set_tokens_id, 'action': 'pool_set_tokens', 'status': 'CriticalError', 'error_message': str(e)})
                time.sleep(TRANSACTION_DELAY_SECONDS)

        # 4. Mint TokenA and TokenB to Sender
        if deployed_token_a_address and deployed_token_b_address:
            print(f"\n--- Minting initial tokens to sender {sender_address} ---")
            amount_a_to_mint_wei = MINT_AMOUNT_TOKEN_A_UNITS * (10**token_decimals)
            amount_b_to_mint_wei = MINT_AMOUNT_TOKEN_B_UNITS * (10**token_decimals)

            for token_addr, token_abi, amount_wei, log_name in [
                (deployed_token_a_address, TOKEN_A_ABI, amount_a_to_mint_wei, TOKEN_A_LOG_NAME),
                (deployed_token_b_address, TOKEN_B_ABI, amount_b_to_mint_wei, TOKEN_B_LOG_NAME)
            ]:
                transaction_counter += 1; mint_id = f"{RUN_NAME}_mint_{log_name.lower()}_{transaction_counter}"
                print(f"Minting {MINT_AMOUNT_TOKEN_A_UNITS if log_name == TOKEN_A_LOG_NAME else MINT_AMOUNT_TOKEN_B_UNITS} {log_name} to {sender_address}...")
                try:
                    gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    result = execute_simple_erc20_mint(w3, SENDER_PK, gas_price_wei_mint, token_addr, token_abi, sender_address, amount_wei, run_identifier=mint_id)
                    all_results.append(result)
                    if result['status'] == 'Success': print(f"✅ {log_name} minted.")
                    else: print(f"⚠️ {log_name} minting failed: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error minting {log_name}: {e}"); all_results.append({'run_identifier': mint_id, 'action': f'mint_{log_name.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
                time.sleep(TRANSACTION_DELAY_SECONDS)

        # 4.5. ERC20 Transfers (after minting, before approval)
        if deployed_token_a_address and deployed_token_b_address:
            print(f"\n--- Starting ERC20 Transfers ---")
            # Transfer some TokenA to the general recipient
            transfer_amount_units = 100  # Amount to transfer
            transfer_amount_wei = transfer_amount_units * (10**token_decimals)
            
            for token_addr, token_abi, log_name in [
                (deployed_token_a_address, TOKEN_A_ABI, TOKEN_A_LOG_NAME),
                (deployed_token_b_address, TOKEN_B_ABI, TOKEN_B_LOG_NAME)
            ]:
                transaction_counter += 1
                transfer_id = f"{RUN_NAME}_transfer_{log_name.lower()}_{transaction_counter}"
                print(f"Transferring {transfer_amount_units} {log_name} to {GENERAL_RECIPIENT_ADDRESS}...")
                try:
                    gas_price_wei_transfer = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    result = execute_erc20_transfer(w3, SENDER_PK, gas_price_wei_transfer, token_addr, token_abi, GENERAL_RECIPIENT_ADDRESS, transfer_amount_wei, run_identifier=transfer_id)
                    all_results.append(result)
                    if result['status'] == 'Success':
                        print(f"✅ {log_name} transfer successful. Hash: {result.get('tx_hash')}")
                    else:
                        print(f"⚠️ {log_name} transfer failed: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error transferring {log_name}: {e}")
                    all_results.append({'run_identifier': transfer_id, 'action': f'transfer_{log_name.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
                time.sleep(TRANSACTION_DELAY_SECONDS)
        
        # 5. Approve AMM Pool to spend TokenA and TokenB
        if deployed_token_a_address and deployed_token_b_address and deployed_amm_pool_address:
            print(f"\n--- Approving AMM Pool {deployed_amm_pool_address} to spend tokens ---")
            # Approve a large amount (max uint256)
            approve_amount_wei = w3.to_int(hexstr="0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")

            for token_addr, token_abi, log_name in [
                (deployed_token_a_address, TOKEN_A_ABI, TOKEN_A_LOG_NAME),
                (deployed_token_b_address, TOKEN_B_ABI, TOKEN_B_LOG_NAME)
            ]:
                transaction_counter += 1; approve_id = f"{RUN_NAME}_approve_{log_name.lower()}_for_pool_{transaction_counter}"
                print(f"Approving AMM Pool for {log_name}...")
                try:
                    gas_price_wei_approve = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    result = execute_approve_erc20(w3, SENDER_PK, gas_price_wei_approve, token_addr, token_abi, deployed_amm_pool_address, approve_amount_wei, run_identifier=approve_id)
                    all_results.append(result)
                    if result['status'] == 'Success': print(f"✅ AMM Pool approved for {log_name}.")
                    else: print(f"⚠️ AMM Pool approval for {log_name} failed: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error approving AMM Pool for {log_name}: {e}"); all_results.append({'run_identifier': approve_id, 'action': f'approve_{log_name.lower()}_for_pool', 'status': 'CriticalError', 'error_message': str(e)})
                time.sleep(TRANSACTION_DELAY_SECONDS)

        # 6. Add Liquidity to AMM Pool
        if deployed_amm_pool_address and deployed_token_a_address and deployed_token_b_address:
            transaction_counter += 1; add_liq_id = f"{RUN_NAME}_add_liquidity_{transaction_counter}"
            print(f"Attempting to add liquidity ({LIQUIDITY_TOKEN_A_UNITS} {TOKEN_A_LOG_NAME}, {LIQUIDITY_TOKEN_B_UNITS} {TOKEN_B_LOG_NAME})...")
            try:
                amount_a_add_wei = LIQUIDITY_TOKEN_A_UNITS * (10**token_decimals)
                amount_b_add_wei = LIQUIDITY_TOKEN_B_UNITS * (10**token_decimals)
                gas_price_wei_add_liq = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_add_liquidity(w3, SENDER_PK, gas_price_wei_add_liq, deployed_amm_pool_address, amount_a_add_wei, amount_b_add_wei, run_identifier=add_liq_id)
                all_results.append(result)
                if result['status'] == 'Success': print(f"✅ Liquidity added to AMM Pool.")
                else: print(f"⚠️ Failed to add liquidity: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error adding liquidity: {e}"); all_results.append({'run_identifier': add_liq_id, 'action': 'amm_add_liquidity', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

        # 7. Perform Swaps (TokenA for TokenB)
        if deployed_amm_pool_address and deployed_token_a_address and deployed_token_b_address:
            print(f"\n--- Starting AMM Swaps ({NUMBER_OF_SWAPS} swaps of {TOKEN_A_LOG_NAME} for {TOKEN_B_LOG_NAME}) ---")
            for i in range(NUMBER_OF_SWAPS):
                transaction_counter += 1; swap_id = f"{RUN_NAME}_amm_swap_A_for_B_tx_{transaction_counter}"
                print(f"Attempting AMM Swap {i+1}/{NUMBER_OF_SWAPS}...")
                try:
                    amount_a_in_wei = SWAP_AMOUNT_TOKEN_A_IN_UNITS * (10**token_decimals)
                    min_amount_b_out_wei = MIN_AMOUNT_TOKEN_B_OUT_UNITS * (10**token_decimals)
                    gas_price_wei_swap = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    
                    result = execute_amm_swap(
                        w3, SENDER_PK, gas_price_wei_swap, deployed_amm_pool_address,
                        deployed_token_a_address, amount_a_in_wei,
                        deployed_token_b_address, min_amount_b_out_wei,
                        sender_address, # Swap output goes back to sender
                        run_identifier=swap_id
                    )
                    all_results.append(result)
                    if result['status'] == 'Success': print(f"✅ AMM Swap {i+1} successful. Hash: {result.get('tx_hash')}")
                    else: print(f"⚠️ AMM Swap {i+1} failed: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error during AMM Swap {i+1}: {e}"); all_results.append({'run_identifier': swap_id, 'action': 'amm_swap_A_for_B', 'status': 'CriticalError', 'error_message': str(e)})
                if i < NUMBER_OF_SWAPS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        else:
            print("Skipping AMM setup (token deployment, pool deployment, liquidity, swaps) due to earlier failures or config.")

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
                print(f"Attempting NFT Mint {i+1}/{NUMBER_OF_NFT_MINTS} to {sender_address}...")
                try:
                    gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    mint_result, minted_id = execute_nft_mint(w3, SENDER_PK, deployed_nft_address, sender_address, gas_price_wei_mint, run_identifier=mint_run_id)
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