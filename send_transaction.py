from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware # Corrected middleware
import time
import pandas as pd # For collecting results

# --- Configuration ---
L2_RPC_URL = "http://localhost:8547"
SENDER_PRIVATE_KEY = "0xb6b15c8cb491557369f3c7d2c287b053eb229daa9c22138887752191c9520659"  # <--- PASTE YOUR ACTUAL PRIVATE KEY HERE
# If you generated a recipient address:
# RECIPIENT_ADDRESS = "0xTHE_GENERATED_RECIPIENT_ADDRESS_HERE"
# Or use another known dev address:
RECIPIENT_ADDRESS = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf" # Example, replace if needed

AMOUNT_TO_SEND_ETH = 0.001 # Reduced amount for multiple sends
NUMBER_OF_TRANSACTIONS = 5 # How many times to run the transfer

# --- Reusable Function ---
def execute_p2p_transfer(w3_instance, sender_pk, recipient_address, amount_eth, current_nonce=None):
    """
    Executes a single P2P ETH transfer and returns a dictionary of results.
    Optionally takes current_nonce to avoid repeated RPC calls in a loop.
    """
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address = sender_account.address
        checksum_recipient_address = Web3.to_checksum_address(recipient_address)

        # Get nonce for the sender account
        # If nonce is provided, use it, otherwise fetch it
        if current_nonce is None:
            nonce = w3_instance.eth.get_transaction_count(sender_address)
        else:
            nonce = current_nonce
        
        # Gas price (can be adjusted based on L2)
        # For Arbitrum Nitro devnode, 0.1 Gwei is often the base fee.
        # For other L2s or if dynamic, you might use w3_instance.eth.gas_price
        gas_price = w3_instance.to_wei('0.1', 'gwei')

        tx_details = {
            'to': checksum_recipient_address,
            'value': w3_instance.to_wei(amount_eth, 'ether'),
            'gas': 21000,  # Standard gas limit for ETH transfer
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': w3_instance.eth.chain_id
        }

        signed_tx = w3_instance.eth.account.sign_transaction(tx_details, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction) # Corrected attribute
        
        start_time = time.time()
        # Increased timeout slightly for safety in loops, though local should be fast
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price) # Fallback if not present
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_number': nonce, # Or a separate counter if you prefer
            'tx_hash': tx_hash.hex(),
            'status': 'Success' if tx_receipt.status == 1 else 'Failed',
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'effective_gas_price_gwei': w3_instance.from_wei(effective_gas_price, 'gwei'),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6) # Rounded for readability
        }
        return result, nonce + 1 # Return next expected nonce
    
    except Exception as e:
        print(f"❌ Error during P2P transfer (Nonce: {current_nonce if current_nonce is not None else 'N/A'}): {e}")
        # import traceback # Uncomment for full traceback during debugging
        # traceback.print_exc()
        return {'status': 'Error', 'error_message': str(e), 'run_number': current_nonce if current_nonce is not None else 'N/A'}, \
               (current_nonce + 1 if current_nonce is not None else None) # Still increment nonce on error to avoid getting stuck

# --- Main Execution Logic ---
if __name__ == "__main__":
    if SENDER_PRIVATE_KEY == "0xYOUR_PRIVATE_KEY_HERE":
        print("🚨 PLEASE UPDATE 'SENDER_PRIVATE_KEY' in the script with your actual private key!")
    else:
        print(f"Attempting to connect to L2 node at {L2_RPC_URL}...")
        w3 = Web3(Web3.HTTPProvider(L2_RPC_URL))
        if not w3.is_connected():
            print(f"❌ Failed to connect to L2 node. Exiting.")
            exit()
        
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0) # Corrected middleware
        print(f"✅ Connected to L2. Chain ID: {w3.eth.chain_id}\n")

        all_results = []
        
        # Get initial nonce before the loop
        sender_address_for_nonce = w3.eth.account.from_key(SENDER_PRIVATE_KEY).address
        current_nonce = w3.eth.get_transaction_count(sender_address_for_nonce)
        print(f"Starting nonce for {sender_address_for_nonce}: {current_nonce}\n")

        for i in range(NUMBER_OF_TRANSACTIONS):
            print(f"--- Sending Transaction {i+1}/{NUMBER_OF_TRANSACTIONS} (Using Nonce: {current_nonce}) ---")
            # Pass the w3 instance and current_nonce to the function
            result, next_nonce = execute_p2p_transfer(
                w3, 
                SENDER_PRIVATE_KEY, 
                RECIPIENT_ADDRESS, 
                AMOUNT_TO_SEND_ETH,
                current_nonce=current_nonce
            )
            all_results.append(result)
            
            if result['status'] == 'Success':
                print(f"✅ Tx {i+1} successful. Hash: {result['tx_hash']}, Time: {result['confirmation_time_sec']}s, Fee: {result['fee_paid_eth']:.8f} ETH")
            else:
                print(f"⚠️ Tx {i+1} failed or errored. Message: {result.get('error_message', 'Unknown error')}")
            
            current_nonce = next_nonce # Update nonce for the next iteration
            print("-" * 40)
            time.sleep(0.5) # Small delay between transactions, can be adjusted or removed

        print("\n--- All Transaction Results ---")
        results_df = pd.DataFrame(all_results)
        print(results_df.to_string()) # .to_string() prints the full DataFrame

        # Optional: Save to CSV
        results_df.to_csv("p2p_transfer_benchmark_results.csv", index=False)
        print("\nResults saved to p2p_transfer_benchmark_results.csv")