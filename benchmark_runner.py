# benchmark_runner.py
import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from web3 import Web3 

from lib.l2_utils import connect_to_l2, get_dynamic_gas_price
from lib.transaction_utils import (
    execute_p2p_transfer, 
    deploy_simple_erc20,      
    execute_simple_erc20_mint,
    execute_approve_erc20,    
    deploy_amm_pool_contract, 
    execute_pool_set_tokens,  
    execute_add_liquidity,    
    execute_amm_swap,         
    deploy_nft_contract,
    execute_nft_mint,
    execute_nft_transfer
)

# --- Configuration ---
load_dotenv()

# Script Configuration
L2_CONFIG_NAME = "arbitrum_local_nitro"
RUN_NAME = "full_suite_plus_sustained_v2_extended" 
TRANSACTION_DELAY_SECONDS = 0.2 # General delay between different phases/major ops

# P2P ETH Transfer Config (for individual tests) - INCREASED
DO_P2P_ETH_TRANSFERS = True 
NUMBER_OF_P2P_TRANSACTIONS = 50  # Increased from 1 to 50
AMOUNT_TO_SEND_ETH_P2P = 0.00001 # Renamed to avoid conflict

# AMM Test Scenario Config
DO_AMM_OPERATIONS = True
TOKEN_A_LOG_NAME = "TokenA"; TOKEN_B_LOG_NAME = "TokenB"
MINT_AMOUNT_TOKEN_UNITS = 10000 
LIQUIDITY_TOKEN_A_UNITS = 1000; LIQUIDITY_TOKEN_B_UNITS = 1000
SWAP_AMOUNT_TOKEN_A_IN_UNITS = 100
MIN_AMOUNT_TOKEN_B_OUT_UNITS = 1 
NUMBER_OF_SWAPS = 20  # Increased from 1 to 20

# NFT (ERC721) Config - INCREASED
DO_NFT_OPERATIONS = True 
NFT_NAME = "MyBenchNFT"; NFT_SYMBOL = "MBN"
NUMBER_OF_NFT_MINTS = 20  # Increased from 1 to 20
NFT_TRANSFER_RECIPIENT_ADDRESS = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B" 

# TS-005: Sustained Low-Intensity Load Test Config - INCREASED
DO_SUSTAINED_LOAD_TEST = True
SUSTAINED_LOAD_DURATION_SECONDS = 120  # Increased from 20 to 120 seconds
SUSTAINED_LOAD_TPS_TARGET = 2       # Target transactions per second
AMOUNT_TO_SEND_ETH_SUSTAINED = 0.000001 # Small amount for sustained test
# Calculated delay for sustained load:
DELAY_SUSTAINED_TX_SECONDS = 1.0 / SUSTAINED_LOAD_TPS_TARGET if SUSTAINED_LOAD_TPS_TARGET > 0 else 1.0

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
    transaction_counter = 0 # Global counter for unique run_identifiers
    sender_address = w3.eth.account.from_key(SENDER_PK).address
    print(f"\n--- Using Sender Account: {sender_address} ---")

    # --- P2P ETH Transfers (TS-001) ---
    if DO_P2P_ETH_TRANSFERS:
        print(f"\n--- Starting P2P ETH Transfers ({NUMBER_OF_P2P_TRANSACTIONS} transactions) ---")
        for i in range(NUMBER_OF_P2P_TRANSACTIONS):
            transaction_counter += 1; run_id = f"{RUN_NAME}_p2p_tx_{transaction_counter}"
            print(f"Attempting P2P ETH Tx {i+1}/{NUMBER_OF_P2P_TRANSACTIONS}...")
            try:
                gas_price_wei = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_p2p_transfer(w3, SENDER_PK, GENERAL_RECIPIENT_ADDRESS, AMOUNT_TO_SEND_ETH_P2P, gas_price_wei, run_identifier=run_id)
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ P2P ETH Tx {i+1} successful. Hash: {result.get('tx_hash')}")
                else: print(f"⚠️ P2P ETH Tx {i+1} failed. Reason: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error P2P ETH tx {i+1}: {e}"); all_results.append({'run_identifier': run_id, 'action': 'p2p_eth_transfer', 'sender_address': sender_address, 'status': 'CriticalError', 'error_message': str(e)})
            if i < NUMBER_OF_P2P_TRANSACTIONS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)

    # --- AMM Operations (TS-004) ---
    deployed_token_a_address = None
    deployed_token_b_address = None
    deployed_amm_pool_address = None
    token_decimals = 18 # Standard assumption

    if DO_AMM_OPERATIONS:
        print(f"\n--- Starting AMM Operations ---")
        # 1. Deploy TokenA
        transaction_counter += 1; deploy_ta_id = f"{RUN_NAME}_deploy_tokenA_{transaction_counter}"
        print(f"Attempting to deploy {TOKEN_A_LOG_NAME}...")
        try:
            gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
            # TOKEN_A_ABI and TOKEN_A_BYTECODE are used internally by deploy_simple_erc20
            result = deploy_simple_erc20(w3, SENDER_PK, gas_price_wei_deploy, "TokenA.sol", sender_address, TOKEN_A_LOG_NAME, run_identifier=deploy_ta_id)
            all_results.append(result)
            if result.get('status') == 'Success': deployed_token_a_address = result.get('contract_address'); print(f"✅ {TOKEN_A_LOG_NAME} deployed: {deployed_token_a_address}")
            else: print(f"⚠️ {TOKEN_A_LOG_NAME} deployment failed: {result.get('error_message', 'Unknown')}")
        except Exception as e:
            print(f"Critical error deploying {TOKEN_A_LOG_NAME}: {e}"); all_results.append({'run_identifier': deploy_ta_id, 'action': f'deploy_{TOKEN_A_LOG_NAME.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
        time.sleep(TRANSACTION_DELAY_SECONDS)

        # 2. Deploy TokenB
        if deployed_token_a_address:
            transaction_counter += 1; deploy_tb_id = f"{RUN_NAME}_deploy_tokenB_{transaction_counter}"
            print(f"Attempting to deploy {TOKEN_B_LOG_NAME}...")
            try:
                gas_price_wei_deploy = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                # TOKEN_B_ABI and TOKEN_B_BYTECODE are used internally by deploy_simple_erc20
                result = deploy_simple_erc20(w3, SENDER_PK, gas_price_wei_deploy, "TokenB.sol", sender_address, TOKEN_B_LOG_NAME, run_identifier=deploy_tb_id)
                all_results.append(result)
                if result.get('status') == 'Success': deployed_token_b_address = result.get('contract_address'); print(f"✅ {TOKEN_B_LOG_NAME} deployed: {deployed_token_b_address}")
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
                result = deploy_amm_pool_contract(w3, SENDER_PK, gas_price_wei_deploy, run_identifier=deploy_pool_id)
                all_results.append(result)
                if result.get('status') == 'Success': deployed_amm_pool_address = result.get('contract_address'); print(f"✅ AMM Pool deployed: {deployed_amm_pool_address}")
                else: print(f"⚠️ AMM Pool deployment failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error deploying AMM Pool: {e}"); all_results.append({'run_identifier': deploy_pool_id, 'action': 'deploy_amm_pool', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

            if deployed_amm_pool_address: 
                transaction_counter += 1; set_tokens_id = f"{RUN_NAME}_pool_set_tokens_{transaction_counter}"
                print(f"Attempting to set tokens for AMM Pool {deployed_amm_pool_address}...")
                try:
                    gas_price_wei_set = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    result = execute_pool_set_tokens(w3, SENDER_PK, gas_price_wei_set, deployed_amm_pool_address, deployed_token_a_address, deployed_token_b_address, run_identifier=set_tokens_id)
                    all_results.append(result)
                    if result.get('status') == 'Success': print(f"✅ Tokens set for AMM Pool.")
                    else: print(f"⚠️ Failed to set tokens for AMM Pool: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error setting tokens for AMM Pool: {e}"); all_results.append({'run_identifier': set_tokens_id, 'action': 'pool_set_tokens', 'status': 'CriticalError', 'error_message': str(e)})
                time.sleep(TRANSACTION_DELAY_SECONDS)

        # 4. Mint TokenA and TokenB to Sender
        if deployed_token_a_address and deployed_token_b_address and deployed_amm_pool_address: 
            print(f"\n--- Minting initial tokens to sender {sender_address} ---")
            amount_a_to_mint_wei = MINT_AMOUNT_TOKEN_UNITS * (10**token_decimals)
            amount_b_to_mint_wei = MINT_AMOUNT_TOKEN_UNITS * (10**token_decimals)
            
            # Mint Token A
            transaction_counter += 1; mint_id_a = f"{RUN_NAME}_mint_{TOKEN_A_LOG_NAME.lower()}_{transaction_counter}"
            print(f"Minting {MINT_AMOUNT_TOKEN_UNITS} {TOKEN_A_LOG_NAME} to {sender_address}...")
            try:
                gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                # Pass "TokenA.sol" to load correct ABI/Bytecode internally
                result = execute_simple_erc20_mint(w3, SENDER_PK, gas_price_wei_mint, deployed_token_a_address, "TokenA.sol", sender_address, amount_a_to_mint_wei, run_identifier=mint_id_a)
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ {TOKEN_A_LOG_NAME} minted.")
                else: print(f"⚠️ {TOKEN_A_LOG_NAME} minting failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error minting {TOKEN_A_LOG_NAME}: {e}"); all_results.append({'run_identifier': mint_id_a, 'action': f'mint_{TOKEN_A_LOG_NAME.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

            # Mint Token B
            transaction_counter += 1; mint_id_b = f"{RUN_NAME}_mint_{TOKEN_B_LOG_NAME.lower()}_{transaction_counter}"
            print(f"Minting {MINT_AMOUNT_TOKEN_UNITS} {TOKEN_B_LOG_NAME} to {sender_address}...")
            try:
                gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                # Pass "TokenB.sol" to load correct ABI/Bytecode internally
                result = execute_simple_erc20_mint(w3, SENDER_PK, gas_price_wei_mint, deployed_token_b_address, "TokenB.sol", sender_address, amount_b_to_mint_wei, run_identifier=mint_id_b)
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ {TOKEN_B_LOG_NAME} minted.")
                else: print(f"⚠️ {TOKEN_B_LOG_NAME} minting failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error minting {TOKEN_B_LOG_NAME}: {e}"); all_results.append({'run_identifier': mint_id_b, 'action': f'mint_{TOKEN_B_LOG_NAME.lower()}', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)
        
        # 5. Approve AMM Pool to spend TokenA and TokenB
        if deployed_token_a_address and deployed_token_b_address and deployed_amm_pool_address:
            print(f"\n--- Approving AMM Pool {deployed_amm_pool_address} to spend tokens ---")
            approve_amount_wei = w3.to_int(hexstr="0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
            
            # Approve Token A
            transaction_counter += 1; approve_id_a = f"{RUN_NAME}_approve_{TOKEN_A_LOG_NAME.lower()}_for_pool_{transaction_counter}"
            print(f"Approving AMM Pool for {TOKEN_A_LOG_NAME}...")
            try:
                gas_price_wei_approve = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_approve_erc20(w3, SENDER_PK, gas_price_wei_approve, deployed_token_a_address, "TokenA.sol", deployed_amm_pool_address, approve_amount_wei, run_identifier=approve_id_a)
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ AMM Pool approved for {TOKEN_A_LOG_NAME}.")
                else: print(f"⚠️ AMM Pool approval for {TOKEN_A_LOG_NAME} failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error approving AMM Pool for {TOKEN_A_LOG_NAME}: {e}"); all_results.append({'run_identifier': approve_id_a, 'action': f'approve_{TOKEN_A_LOG_NAME.lower()}_for_pool', 'status': 'CriticalError', 'error_message': str(e)})
            time.sleep(TRANSACTION_DELAY_SECONDS)

            # Approve Token B
            transaction_counter += 1; approve_id_b = f"{RUN_NAME}_approve_{TOKEN_B_LOG_NAME.lower()}_for_pool_{transaction_counter}"
            print(f"Approving AMM Pool for {TOKEN_B_LOG_NAME}...")
            try:
                gas_price_wei_approve = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_approve_erc20(w3, SENDER_PK, gas_price_wei_approve, deployed_token_b_address, "TokenB.sol", deployed_amm_pool_address, approve_amount_wei, run_identifier=approve_id_b)
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ AMM Pool approved for {TOKEN_B_LOG_NAME}.")
                else: print(f"⚠️ AMM Pool approval for {TOKEN_B_LOG_NAME} failed: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error approving AMM Pool for {TOKEN_B_LOG_NAME}: {e}"); all_results.append({'run_identifier': approve_id_b, 'action': f'approve_{TOKEN_B_LOG_NAME.lower()}_for_pool', 'status': 'CriticalError', 'error_message': str(e)})
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
                if result.get('status') == 'Success': print(f"✅ Liquidity added to AMM Pool.")
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
                    result = execute_amm_swap(w3, SENDER_PK, gas_price_wei_swap, deployed_amm_pool_address, deployed_token_a_address, amount_a_in_wei, deployed_token_b_address, min_amount_b_out_wei, sender_address, run_identifier=swap_id)
                    all_results.append(result)
                    if result.get('status') == 'Success': print(f"✅ AMM Swap {i+1} successful. Hash: {result.get('tx_hash')}")
                    else: print(f"⚠️ AMM Swap {i+1} failed: {result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error during AMM Swap {i+1}: {e}"); all_results.append({'run_identifier': swap_id, 'action': 'amm_swap_A_for_B', 'status': 'CriticalError', 'error_message': str(e)})
                if i < NUMBER_OF_SWAPS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        else:
            print("Skipping AMM setup (token deployment, pool deployment, liquidity, swaps) due to earlier failures or config.")

    # --- NFT (ERC721) Operations (TS-003) ---
    deployed_nft_address = None
    minted_token_ids = [] 
    if DO_NFT_OPERATIONS:
        print(f"\n--- Starting NFT (ERC721) Operations ---")
        transaction_counter += 1; deploy_nft_run_id = f"{RUN_NAME}_nft_deploy_{transaction_counter}"
        print(f"Attempting to deploy NFT ('{NFT_NAME}')...")
        try:
            gas_price_wei_deploy_nft = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
            deploy_nft_result = deploy_nft_contract(w3, SENDER_PK, gas_price_wei_deploy_nft, NFT_NAME, NFT_SYMBOL, run_identifier=deploy_nft_run_id)
            all_results.append(deploy_nft_result)
            if deploy_nft_result.get('status') == 'Success': deployed_nft_address = deploy_nft_result.get('contract_address'); print(f"✅ NFT Contract '{NFT_NAME}' deployed at: {deployed_nft_address}")
            else: print(f"⚠️ NFT Contract deployment failed. Reason: {deploy_nft_result.get('error_message', 'Unknown')}")
        except Exception as e:
            print(f"Critical error NFT deployment: {e}"); all_results.append({'run_identifier': deploy_nft_run_id, 'action': 'deploy_nft', 'status': 'CriticalError', 'error_message': str(e)})
        time.sleep(TRANSACTION_DELAY_SECONDS)

        if deployed_nft_address:
            print(f"\n--- Starting NFT Mints ({NUMBER_OF_NFT_MINTS} mints) ---")
            for i in range(NUMBER_OF_NFT_MINTS):
                transaction_counter += 1; mint_run_id = f"{RUN_NAME}_nft_mint_tx_{transaction_counter}"
                print(f"Attempting NFT Mint {i+1}/{NUMBER_OF_NFT_MINTS} to {sender_address}...")
                try:
                    gas_price_wei_mint = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    mint_result, minted_id = execute_nft_mint(w3, SENDER_PK, deployed_nft_address, sender_address, gas_price_wei_mint, run_identifier=mint_run_id)
                    all_results.append(mint_result)
                    if mint_result.get('status') == 'Success' and minted_id is not None:
                        minted_token_ids.append(minted_id); print(f"✅ NFT Mint {i+1} successful. Token ID: {minted_id}, Hash: {mint_result.get('tx_hash')}")
                    else: print(f"⚠️ NFT Mint {i+1} failed. Reason: {mint_result.get('error_message', 'Unknown or no token ID found')}")
                except Exception as e:
                    print(f"Critical error NFT mint {i+1}: {e}"); all_results.append({'run_identifier': mint_run_id, 'action': 'nft_mint', 'status': 'CriticalError', 'error_message': str(e)})
                if i < NUMBER_OF_NFT_MINTS - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        else: print("Skipping NFT mints: NFT contract deployment failed or skipped.")

        if deployed_nft_address and minted_token_ids:
            print(f"\n--- Starting NFT Transfers ({len(minted_token_ids)} transfers) ---")
            for i, token_id_to_transfer in enumerate(minted_token_ids):
                transaction_counter += 1; transfer_nft_run_id = f"{RUN_NAME}_nft_transfer_tx_{transaction_counter}_id_{token_id_to_transfer}"
                print(f"Attempting NFT Transfer {i+1}/{len(minted_token_ids)} of Token ID {token_id_to_transfer} to {NFT_TRANSFER_RECIPIENT_ADDRESS}...")
                try:
                    gas_price_wei_transfer_nft = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                    transfer_nft_result = execute_nft_transfer(w3, SENDER_PK, deployed_nft_address, NFT_TRANSFER_RECIPIENT_ADDRESS, token_id_to_transfer, gas_price_wei_transfer_nft, run_identifier=transfer_nft_run_id)
                    all_results.append(transfer_nft_result)
                    if transfer_nft_result.get('status') == 'Success': print(f"✅ NFT Transfer {i+1} (ID: {token_id_to_transfer}) successful. Hash: {transfer_nft_result.get('tx_hash')}")
                    else: print(f"⚠️ NFT Transfer {i+1} (ID: {token_id_to_transfer}) failed. Reason: {transfer_nft_result.get('error_message', 'Unknown')}")
                except Exception as e:
                    print(f"Critical error NFT transfer {i+1} (ID: {token_id_to_transfer}): {e}"); all_results.append({'run_identifier': transfer_nft_run_id, 'action': 'nft_transfer', 'token_id_transferred': token_id_to_transfer, 'status': 'CriticalError', 'error_message': str(e)})
                if i < len(minted_token_ids) - 1: time.sleep(TRANSACTION_DELAY_SECONDS)
        elif deployed_nft_address: print("Skipping NFT transfers: No NFTs were successfully minted or minting was skipped.")
        else: print("Skipping NFT transfers: NFT contract deployment failed or skipped.")


    # --- Sustained Low-Intensity Load Test (TS-005) ---
    if DO_SUSTAINED_LOAD_TEST:
        print(f"\n--- Starting Sustained Low-Intensity Load Test ---")
        print(f"Duration: {SUSTAINED_LOAD_DURATION_SECONDS} seconds, Target TPS: {SUSTAINED_LOAD_TPS_TARGET}, Delay: {DELAY_SUSTAINED_TX_SECONDS:.3f}s")
        
        start_test_time = time.time()
        sustained_tx_count = 0
        
        while (time.time() - start_test_time) < SUSTAINED_LOAD_DURATION_SECONDS:
            loop_start_time = time.time()
            transaction_counter += 1
            sustained_tx_count += 1
            run_id = f"{RUN_NAME}_sustained_tx_{transaction_counter}"
            
            print(f"Sustained Tx {sustained_tx_count} (Global Tx {transaction_counter})... ", end="", flush=True)
            try:
                gas_price_wei = get_dynamic_gas_price(w3, CURRENT_L2_CONFIG.get("gas_price_strategy", "fetch"), CURRENT_L2_CONFIG.get("fixed_gas_price_gwei", 0.1))
                result = execute_p2p_transfer(w3, SENDER_PK, GENERAL_RECIPIENT_ADDRESS, AMOUNT_TO_SEND_ETH_SUSTAINED, gas_price_wei, run_identifier=run_id)
                result['action'] = 'sustained_p2p_transfer' 
                all_results.append(result)
                if result.get('status') == 'Success': print(f"✅ Success. Hash: ...{result.get('tx_hash', '')[-8:]}")
                else: print(f"⚠️ Failed. Reason: {result.get('error_message', 'Unknown')}")
            except Exception as e:
                print(f"Critical error Sustained Tx {sustained_tx_count}: {e}")
                all_results.append({'run_identifier': run_id, 'action': 'sustained_p2p_transfer', 'sender_address': sender_address, 'status': 'CriticalError', 'error_message': str(e)})
            
            time_elapsed_in_loop = time.time() - loop_start_time
            sleep_duration = DELAY_SUSTAINED_TX_SECONDS - time_elapsed_in_loop
            if sleep_duration > 0:
                time.sleep(sleep_duration)
        
        actual_duration = time.time() - start_test_time
        actual_tps = sustained_tx_count / actual_duration if actual_duration > 0 else 0
        print(f"Sustained load test finished. Sent {sustained_tx_count} transactions in {actual_duration:.2f}s. Actual TPS: {actual_tps:.2f}")


    # --- Final Results Processing ---
    print("\n--- Benchmark Run Complete ---")
    if all_results:
        print(f"\n--- Processing {len(all_results)} transaction results ---")
        
        # Updated desired_columns to include L1 fee data
        desired_columns = [
            'run_identifier', 'action', 'status', 'sender_address', 'nonce', 'tx_hash',
            'block_number', 'gas_used', 'configured_gas_price_gwei', 'effective_gas_price_gwei',
            'fee_paid_eth', 'confirmation_time_sec', 'contract_address', 'token_id_minted', 'token_id_transferred',
            # New L1 fee columns
            'l1_fee_wei', 'l1_fee_eth', 'l1_gas_used', 'l1_gas_price_gwei', 'l1_fee_scalar'
        ]
        
        df = pd.DataFrame(all_results)
        
        # Ensure all desired columns exist (fill missing with None)
        for col in desired_columns:
            if col not in df.columns:
                df[col] = None
        
        df_ordered = df[desired_columns]
        
        # Create results directory if it doesn't exist
        os.makedirs('results', exist_ok=True)
        
        # Save to CSV with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        csv_filename = f"results/benchmark_results_{RUN_NAME}_{timestamp}.csv"
        df_ordered.to_csv(csv_filename, index=False)
        print(f"✅ Results saved to: {csv_filename}")
        
        # Display summary statistics
        print(f"\n--- Summary Statistics ---")
        print(f"Total transactions: {len(df_ordered)}")
        successful_txs = df_ordered[df_ordered['status'] == 'Success']
        print(f"Successful transactions: {len(successful_txs)}")
        print(f"Failed transactions: {len(df_ordered) - len(successful_txs)}")
        
        if len(successful_txs) > 0:
            print(f"\n--- Gas Usage Statistics (Successful Transactions) ---")
            print(f"Average gas used: {successful_txs['gas_used'].mean():.0f}")
            print(f"Median gas used: {successful_txs['gas_used'].median():.0f}")
            print(f"Average confirmation time: {successful_txs['confirmation_time_sec'].mean():.4f} seconds")
            print(f"Median confirmation time: {successful_txs['confirmation_time_sec'].median():.4f} seconds")
            
            # L1 fee statistics (if available)
            l1_fee_txs = successful_txs[successful_txs['l1_fee_eth'].notna()]
            if len(l1_fee_txs) > 0:
                print(f"\n--- L1 Fee Statistics (Transactions with L1 data) ---")
                print(f"Transactions with L1 fee data: {len(l1_fee_txs)}")
                print(f"Average L1 fee: {l1_fee_txs['l1_fee_eth'].mean():.8f} ETH")
                print(f"Median L1 fee: {l1_fee_txs['l1_fee_eth'].median():.8f} ETH")
                print(f"Total L1 fees paid: {l1_fee_txs['l1_fee_eth'].sum():.8f} ETH")
            else:
                print(f"\n--- L1 Fee Statistics ---")
                print(f"No L1 fee data found in transaction receipts.")
                print(f"This might be normal for your L2 implementation or the field names might be different.")
        
        # Display first few rows for verification
        print(f"\n--- Sample Results (First 5 rows) ---")
        print(df_ordered.head().to_string(index=False))
        
    else:
        print("⚠️ No transaction results to process.")
    
    print(f"\n🎉 Benchmark run '{RUN_NAME}' completed!")