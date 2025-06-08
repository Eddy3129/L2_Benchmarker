# zksync_benchmark_runner.py
import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from web3 import Web3

from lib.l2_utils import connect_to_zksync_l2
from lib.zksync_transaction_utils import (
    execute_zksync_p2p_transfer,
    deploy_zksync_simple_erc20,
    execute_zksync_erc20_mint,
    execute_zksync_approve_erc20,
    deploy_zksync_amm_pool_contract,
    deploy_zksync_nft_contract
)

# --- Configuration ---
load_dotenv()

# Script Configuration
L2_CONFIG_NAME = "anvil-zksync"
RUN_NAME = "zksync-era-full-suite"
TRANSACTION_DELAY_SECONDS = 0.2

# P2P ETH Transfer Config
DO_P2P_ETH_TRANSFERS = True
NUMBER_OF_P2P_TRANSACTIONS = 50
AMOUNT_TO_SEND_ETH_P2P = 0.00001

# AMM Test Scenario Config
DO_AMM_OPERATIONS = True
TOKEN_A_LOG_NAME = "TokenA"
TOKEN_B_LOG_NAME = "TokenB"
MINT_AMOUNT_TOKEN_UNITS = 10000
LIQUIDITY_TOKEN_A_UNITS = 1000
LIQUIDITY_TOKEN_B_UNITS = 1000
SWAP_AMOUNT_TOKEN_A_IN_UNITS = 100
MIN_AMOUNT_TOKEN_B_OUT_UNITS = 1
NUMBER_OF_SWAPS = 20

# NFT (ERC721) Config
DO_NFT_OPERATIONS = True
NFT_NAME = "ZKsyncBenchNFT"
NFT_SYMBOL = "ZKBN"
NUMBER_OF_NFT_MINTS = 20
NFT_TRANSFER_RECIPIENT_ADDRESS = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

# Sustained Load Test Config
DO_SUSTAINED_LOAD_TEST = True
SUSTAINED_LOAD_DURATION_SECONDS = 120
SUSTAINED_LOAD_TPS_TARGET = 2
AMOUNT_TO_SEND_ETH_SUSTAINED = 0.000001
DELAY_SUSTAINED_TX_SECONDS = 1.0 / SUSTAINED_LOAD_TPS_TARGET if SUSTAINED_LOAD_TPS_TARGET > 0 else 1.0

# Shared Config
GENERAL_RECIPIENT_ADDRESS = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"

# Load L2 configurations
try:
    with open('config/l2_nodes.json', 'r') as f:
        L2_CONFIGS = json.load(f)
except FileNotFoundError:
    print("❌ Error: config/l2_nodes.json not found.")
    exit()
except json.JSONDecodeError:
    print("❌ Error: config/l2_nodes.json is not valid JSON.")
    exit()

if L2_CONFIG_NAME not in L2_CONFIGS:
    print(f"❌ Error: L2 configuration '{L2_CONFIG_NAME}' not found.")
    exit()

CURRENT_L2_CONFIG = L2_CONFIGS[L2_CONFIG_NAME]

SENDER_PK = os.getenv("ZKSYNC_PRIVATE_KEY")
if not SENDER_PK:
    print("❌ Error: ZKSYNC_PRIVATE_KEY not found in .env file.")
    exit()

# --- Main Execution Logic ---
if __name__ == "__main__":
    print(f"🚀 Starting ZKsync Benchmark Run: {RUN_NAME} on L2: {L2_CONFIG_NAME}")
    
    zk_web3 = None
    try:
        zk_web3 = connect_to_zksync_l2(
            CURRENT_L2_CONFIG["rpc_url"],
            CURRENT_L2_CONFIG.get("chain_id")
        )
    except Exception as e:
        print(f"Failed to connect to ZKsync L2: {e}")
        exit()

    all_results = []
    transaction_counter = 0
    sender_address = Web3().eth.account.from_key(SENDER_PK).address
    print(f"\n--- Using Sender Account: {sender_address} ---")

    # --- P2P ETH Transfers (TS-001) ---
    if DO_P2P_ETH_TRANSFERS:
        print(f"\n--- Starting ZKsync P2P ETH Transfers ({NUMBER_OF_P2P_TRANSACTIONS} transactions) ---")
        for i in range(NUMBER_OF_P2P_TRANSACTIONS):
            transaction_counter += 1
            run_id = f"{RUN_NAME}_p2p_tx_{transaction_counter}"
            print(f"Attempting ZKsync P2P ETH Tx {i+1}/{NUMBER_OF_P2P_TRANSACTIONS}...")
            
            try:
                result = execute_zksync_p2p_transfer(
                    zk_web3,
                    SENDER_PK,
                    GENERAL_RECIPIENT_ADDRESS,
                    zk_web3.to_wei(AMOUNT_TO_SEND_ETH_P2P, 'ether'),
                    run_identifier=run_id
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync P2P ETH Tx {i+1} successful. Hash: {result.get('tx_hash')}")
                else:
                    print(f"⚠️ ZKsync P2P ETH Tx {i+1} failed. Reason: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error ZKsync P2P ETH tx {i+1}: {e}")
                all_results.append({
                    'run_identifier': run_id,
                    'action': 'zksync_p2p_eth_transfer',
                    'sender_address': sender_address,
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            if i < NUMBER_OF_P2P_TRANSACTIONS - 1:
                time.sleep(TRANSACTION_DELAY_SECONDS)

    # --- AMM Operations (TS-004) ---
    deployed_token_a_address = None
    deployed_token_b_address = None
    deployed_amm_pool_address = None
    token_decimals = 18

    if DO_AMM_OPERATIONS:
        print(f"\n--- Starting ZKsync AMM Operations ---")
        
        # 1. Deploy TokenA
        transaction_counter += 1
        deploy_ta_id = f"{RUN_NAME}_deploy_tokenA_{transaction_counter}"
        print(f"Attempting to deploy ZKsync {TOKEN_A_LOG_NAME}...")
        
        try:
            result = deploy_zksync_simple_erc20(
                zk_web3,
                SENDER_PK,
                TOKEN_A_LOG_NAME,
                "TKA",
                1000000 * (10**token_decimals),
                run_identifier=deploy_ta_id
            )
            all_results.append(result)
            
            if result.get('status') == 'Success':
                deployed_token_a_address = result.get('contract_address')
                print(f"✅ ZKsync {TOKEN_A_LOG_NAME} deployed: {deployed_token_a_address}")
            else:
                print(f"⚠️ ZKsync {TOKEN_A_LOG_NAME} deployment failed: {result.get('error_message', 'Unknown')}")
                
        except Exception as e:
            print(f"Critical error deploying ZKsync {TOKEN_A_LOG_NAME}: {e}")
            all_results.append({
                'run_identifier': deploy_ta_id,
                'action': f'deploy_zksync_{TOKEN_A_LOG_NAME.lower()}',
                'status': 'CriticalError',
                'error_message': str(e)
            })
            
        time.sleep(TRANSACTION_DELAY_SECONDS)

        # 2. Deploy TokenB
        if deployed_token_a_address:
            transaction_counter += 1
            deploy_tb_id = f"{RUN_NAME}_deploy_tokenB_{transaction_counter}"
            print(f"Attempting to deploy ZKsync {TOKEN_B_LOG_NAME}...")
            
            try:
                result = deploy_zksync_simple_erc20(
                    zk_web3,
                    SENDER_PK,
                    TOKEN_B_LOG_NAME,
                    "TKB",
                    1000000 * (10**token_decimals),
                    run_identifier=deploy_tb_id
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    deployed_token_b_address = result.get('contract_address')
                    print(f"✅ ZKsync {TOKEN_B_LOG_NAME} deployed: {deployed_token_b_address}")
                else:
                    print(f"⚠️ ZKsync {TOKEN_B_LOG_NAME} deployment failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error deploying ZKsync {TOKEN_B_LOG_NAME}: {e}")
                all_results.append({
                    'run_identifier': deploy_tb_id,
                    'action': f'deploy_zksync_{TOKEN_B_LOG_NAME.lower()}',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

        # 3. Deploy AMM Pool
        if deployed_token_a_address and deployed_token_b_address:
            transaction_counter += 1
            deploy_pool_id = f"{RUN_NAME}_deploy_amm_pool_{transaction_counter}"
            print(f"Attempting to deploy ZKsync AMM Pool...")
            
            try:
                result = deploy_zksync_amm_pool_contract(
                    zk_web3,
                    SENDER_PK,
                    run_identifier=deploy_pool_id
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    deployed_amm_pool_address = result.get('contract_address')
                    print(f"✅ ZKsync AMM Pool deployed: {deployed_amm_pool_address}")
                else:
                    print(f"⚠️ ZKsync AMM Pool deployment failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error deploying ZKsync AMM Pool: {e}")
                all_results.append({
                    'run_identifier': deploy_pool_id,
                    'action': 'deploy_zksync_amm_pool',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

        # 4. Mint tokens to sender
        if deployed_token_a_address and deployed_token_b_address:
            print(f"\n--- Minting initial ZKsync tokens to sender {sender_address} ---")
            amount_a_to_mint_wei = MINT_AMOUNT_TOKEN_UNITS * (10**token_decimals)
            amount_b_to_mint_wei = MINT_AMOUNT_TOKEN_UNITS * (10**token_decimals)
            
            # Mint Token A
            transaction_counter += 1
            mint_id_a = f"{RUN_NAME}_mint_{TOKEN_A_LOG_NAME.lower()}_{transaction_counter}"
            print(f"Minting {MINT_AMOUNT_TOKEN_UNITS} ZKsync {TOKEN_A_LOG_NAME} to {sender_address}...")
            
            try:
                result = execute_zksync_erc20_mint(
                    zk_web3,
                    SENDER_PK,
                    deployed_token_a_address,
                    sender_address,
                    amount_a_to_mint_wei,
                    run_identifier=mint_id_a
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync {TOKEN_A_LOG_NAME} minted.")
                else:
                    print(f"⚠️ ZKsync {TOKEN_A_LOG_NAME} minting failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error minting ZKsync {TOKEN_A_LOG_NAME}: {e}")
                all_results.append({
                    'run_identifier': mint_id_a,
                    'action': f'mint_zksync_{TOKEN_A_LOG_NAME.lower()}',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

            # Mint Token B
            transaction_counter += 1
            mint_id_b = f"{RUN_NAME}_mint_{TOKEN_B_LOG_NAME.lower()}_{transaction_counter}"
            print(f"Minting {MINT_AMOUNT_TOKEN_UNITS} ZKsync {TOKEN_B_LOG_NAME} to {sender_address}...")
            
            try:
                result = execute_zksync_erc20_mint(
                    zk_web3,
                    SENDER_PK,
                    deployed_token_b_address,
                    sender_address,
                    amount_b_to_mint_wei,
                    run_identifier=mint_id_b
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync {TOKEN_B_LOG_NAME} minted.")
                else:
                    print(f"⚠️ ZKsync {TOKEN_B_LOG_NAME} minting failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error minting ZKsync {TOKEN_B_LOG_NAME}: {e}")
                all_results.append({
                    'run_identifier': mint_id_b,
                    'action': f'mint_zksync_{TOKEN_B_LOG_NAME.lower()}',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

        # 5. Approve AMM Pool to spend tokens
        if deployed_token_a_address and deployed_token_b_address and deployed_amm_pool_address:
            print(f"\n--- Approving ZKsync AMM Pool {deployed_amm_pool_address} to spend tokens ---")
            approve_amount_wei = 2**256 - 1  # Max uint256
            
            # Approve Token A
            transaction_counter += 1
            approve_id_a = f"{RUN_NAME}_approve_{TOKEN_A_LOG_NAME.lower()}_for_pool_{transaction_counter}"
            print(f"Approving ZKsync AMM Pool for {TOKEN_A_LOG_NAME}...")
            
            try:
                result = execute_zksync_approve_erc20(
                    zk_web3,
                    SENDER_PK,
                    deployed_token_a_address,
                    deployed_amm_pool_address,
                    approve_amount_wei,
                    run_identifier=approve_id_a
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync AMM Pool approved for {TOKEN_A_LOG_NAME}.")
                else:
                    print(f"⚠️ ZKsync AMM Pool approval for {TOKEN_A_LOG_NAME} failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error approving ZKsync AMM Pool for {TOKEN_A_LOG_NAME}: {e}")
                all_results.append({
                    'run_identifier': approve_id_a,
                    'action': f'approve_zksync_{TOKEN_A_LOG_NAME.lower()}_for_pool',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

            # Approve Token B
            transaction_counter += 1
            approve_id_b = f"{RUN_NAME}_approve_{TOKEN_B_LOG_NAME.lower()}_for_pool_{transaction_counter}"
            print(f"Approving ZKsync AMM Pool for {TOKEN_B_LOG_NAME}...")
            
            try:
                result = execute_zksync_approve_erc20(
                    zk_web3,
                    SENDER_PK,
                    deployed_token_b_address,
                    deployed_amm_pool_address,
                    approve_amount_wei,
                    run_identifier=approve_id_b
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync AMM Pool approved for {TOKEN_B_LOG_NAME}.")
                else:
                    print(f"⚠️ ZKsync AMM Pool approval for {TOKEN_B_LOG_NAME} failed: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error approving ZKsync AMM Pool for {TOKEN_B_LOG_NAME}: {e}")
                all_results.append({
                    'run_identifier': approve_id_b,
                    'action': f'approve_zksync_{TOKEN_B_LOG_NAME.lower()}_for_pool',
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            time.sleep(TRANSACTION_DELAY_SECONDS)

    # --- NFT (ERC721) Operations (TS-003) ---
    deployed_nft_address = None
    minted_token_ids = []
    
    if DO_NFT_OPERATIONS:
        print(f"\n--- Starting ZKsync NFT (ERC721) Operations ---")
        transaction_counter += 1
        deploy_nft_run_id = f"{RUN_NAME}_nft_deploy_{transaction_counter}"
        print(f"Attempting to deploy ZKsync NFT ('{NFT_NAME}')...")
        
        try:
            deploy_nft_result = deploy_zksync_nft_contract(
                zk_web3,
                SENDER_PK,
                NFT_NAME,
                NFT_SYMBOL,
                run_identifier=deploy_nft_run_id
            )
            all_results.append(deploy_nft_result)
            
            if deploy_nft_result.get('status') == 'Success':
                deployed_nft_address = deploy_nft_result.get('contract_address')
                print(f"✅ ZKsync NFT Contract '{NFT_NAME}' deployed at: {deployed_nft_address}")
            else:
                print(f"⚠️ ZKsync NFT Contract deployment failed. Reason: {deploy_nft_result.get('error_message', 'Unknown')}")
                
        except Exception as e:
            print(f"Critical error ZKsync NFT deployment: {e}")
            all_results.append({
                'run_identifier': deploy_nft_run_id,
                'action': 'deploy_zksync_nft',
                'status': 'CriticalError',
                'error_message': str(e)
            })
            
        time.sleep(TRANSACTION_DELAY_SECONDS)

    # --- Sustained Load Test (TS-005) ---
    if DO_SUSTAINED_LOAD_TEST:
        print(f"\n--- Starting ZKsync Sustained Load Test ({SUSTAINED_LOAD_DURATION_SECONDS}s at {SUSTAINED_LOAD_TPS_TARGET} TPS) ---")
        sustained_start_time = time.time()
        sustained_tx_count = 0
        
        while (time.time() - sustained_start_time) < SUSTAINED_LOAD_DURATION_SECONDS:
            transaction_counter += 1
            sustained_tx_count += 1
            run_id = f"{RUN_NAME}_sustained_tx_{transaction_counter}"
            
            try:
                result = execute_zksync_p2p_transfer(
                    zk_web3,
                    SENDER_PK,
                    GENERAL_RECIPIENT_ADDRESS,
                    zk_web3.to_wei(AMOUNT_TO_SEND_ETH_SUSTAINED, 'ether'),
                    run_identifier=run_id
                )
                all_results.append(result)
                
                if result.get('status') == 'Success':
                    print(f"✅ ZKsync Sustained Tx {sustained_tx_count} successful. Hash: {result.get('tx_hash')}")
                else:
                    print(f"⚠️ ZKsync Sustained Tx {sustained_tx_count} failed. Reason: {result.get('error_message', 'Unknown')}")
                    
            except Exception as e:
                print(f"Critical error ZKsync sustained tx {sustained_tx_count}: {e}")
                all_results.append({
                    'run_identifier': run_id,
                    'action': 'zksync_sustained_p2p_transfer',
                    'sender_address': sender_address,
                    'status': 'CriticalError',
                    'error_message': str(e)
                })
                
            # Wait for next transaction based on target TPS
            time.sleep(DELAY_SUSTAINED_TX_SECONDS)

    # --- Save Results ---
    print(f"\n--- Saving ZKsync Benchmark Results ---")
    if all_results:
        df = pd.DataFrame(all_results)
        csv_filename = f"zksync_{RUN_NAME}_benchmark_results.csv"
        df.to_csv(csv_filename, index=False)
        print(f"✅ ZKsync Benchmark results saved to {csv_filename}")
        
        # Print summary
        success_count = len(df[df['status'] == 'Success'])
        error_count = len(df[df['status'] == 'Error'])
        critical_error_count = len(df[df['status'] == 'CriticalError'])
        
        print(f"\n--- ZKsync Benchmark Summary ---")
        print(f"Total Transactions: {len(df)}")
        print(f"Successful: {success_count}")
        print(f"Errors: {error_count}")
        print(f"Critical Errors: {critical_error_count}")
        print(f"Success Rate: {(success_count/len(df)*100):.2f}%")
        
        if success_count > 0:
            successful_txs = df[df['status'] == 'Success']
            avg_confirmation_time = successful_txs['confirmation_time_sec'].mean()
            avg_gas_used = successful_txs['gas_used'].mean()
            avg_fee_paid = successful_txs['fee_paid_eth'].mean()
            
            print(f"Average Confirmation Time: {avg_confirmation_time:.4f}s")
            print(f"Average Gas Used: {avg_gas_used:.0f}")
            print(f"Average Fee Paid: {avg_fee_paid:.8f} ETH")
    else:
        print("⚠️ No results to save.")
        
    print(f"\n🎉 ZKsync Benchmark Run '{RUN_NAME}' completed!")