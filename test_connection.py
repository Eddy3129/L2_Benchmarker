from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware # Important for many dev nodes

# Replace with the actual RPC URL if different
L2_RPC_URL = "http://localhost:8011"

def check_l2_connection(rpc_url):
    try:
        # 1. Initialize Web3 instance
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # 2. Check connection
        if not w3.is_connected():
            print(f"❌ Failed to connect to L2 node at {rpc_url}")
            return False

        print(f"✅ Successfully connected to Web3 provider at {rpc_url}!")

        # 3. Inject PoA middleware (often needed for local dev/testnet nodes)
        # This handles the "extraData" field format common in PoA chains.
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # 4. Get Chain ID
        chain_id = w3.eth.chain_id
        print(f"Connected L2 Chain ID: {chain_id}")

        # 5. Get Current Block Number
        block_number = w3.eth.block_number
        print(f"Current L2 Block Number: {block_number}")

        # 6. Get a pre-funded account balance (Arbitrum dev nodes usually have this one)
        # This is one of the pre-funded accounts from the nitro-devnode setup
        pre_funded_address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        # Ensure the address is checksummed for web3.py
        checksum_address = Web3.to_checksum_address(pre_funded_address)
        balance_wei = w3.eth.get_balance(checksum_address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        print(f"Balance of pre-funded account ({checksum_address}): {balance_eth} ETH")

        return True

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return False

if __name__ == "__main__":
    print("Attempting to connect to local L2 node...")
    check_l2_connection(L2_RPC_URL)