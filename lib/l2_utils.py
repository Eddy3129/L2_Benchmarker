# lib/l2_utils.py
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

def connect_to_l2(rpc_url, expected_chain_id=None):
    """Connects to an L2 node and returns the web3 instance."""
    print(f"Attempting to connect to L2 node at {rpc_url}...")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to L2 node at {rpc_url}")

    # Inject PoA middleware (common for local dev/testnet nodes)
    # This might need to be conditional if you connect to non-PoA mainnets
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    actual_chain_id = w3.eth.chain_id
    print(f"✅ Connected to L2. Actual Chain ID: {actual_chain_id}")

    if expected_chain_id is not None and actual_chain_id != expected_chain_id:
        raise ValueError(
            f"Chain ID mismatch! Expected {expected_chain_id}, but connected to {actual_chain_id}."
        )
    return w3

def get_dynamic_gas_price(w3, strategy="fetch", fixed_gwei=0.1):
    """Gets gas price based on strategy."""
    if strategy == "fetch":
        gas_price_wei = w3.eth.gas_price
        # For some devnets, eth_gasPrice might return 0 or a very low value.
        # Add a floor if it's too low, e.g., 0.01 Gwei, or use the fixed as fallback.
        if gas_price_wei < w3.to_wei('0.01', 'gwei'): # Adjust floor as needed
            print(f"Fetched gas price ({w3.from_wei(gas_price_wei, 'gwei')} Gwei) is very low, using fallback fixed price.")
            return w3.to_wei(fixed_gwei, 'gwei')
        return gas_price_wei
    elif strategy == "fixed":
        return w3.to_wei(fixed_gwei, 'gwei')
    else:
        raise ValueError(f"Unknown gas price strategy: {strategy}")