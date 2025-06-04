from web3 import Web3
import time
from web3.logs import DISCARD 

# Assuming contract_loader.py is in the same 'lib' directory
from .contract_loader import load_contract_artifact

# --- Load Contract Artifacts ---
# ERC20 Tokens (from the article's simpleCPMM repo)
MY_NFT_ABI, MY_NFT_BYTECODE = load_contract_artifact("MyNFT.sol")
MY_NFT_ABI, MY_NFT_BYTECODE = load_contract_artifact("MyNFT.sol")
TOKEN_A_ABI, TOKEN_A_BYTECODE = load_contract_artifact("TokenA.sol")
TOKEN_B_ABI, TOKEN_B_BYTECODE = load_contract_artifact("TokenB.sol")

# AMM Pool Contract (from the article's simpleCPMM repo)
BASIC_POOL_ABI, BASIC_POOL_BYTECODE = load_contract_artifact("BasicPool.sol")

# --- Existing P2P ETH Transfer Function ---
def execute_p2p_transfer(w3_instance, sender_pk, recipient_address, amount_eth, gas_price_wei, run_identifier="N/A"):
   
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        checksum_recipient_address = Web3.to_checksum_address(recipient_address)
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        tx_details = {'to': checksum_recipient_address, 'value': w3_instance.to_wei(amount_eth, 'ether'), 'gas': 21000, 'gasPrice': gas_price_wei, 'nonce': nonce_val, 'chainId': w3_instance.eth.chain_id}
        signed_tx = w3_instance.eth.account.sign_transaction(tx_details, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time; effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'p2p_eth_transfer', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success' if tx_receipt.status == 1 else 'Failed','block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'p2p_eth_transfer','sender_address': sender_address_val, 'nonce': nonce_val,'status': 'Error', 'error_message': str(e)}

# --- ERC20 Deployment Function (Generic for TokenA/TokenB) ---
def deploy_simple_erc20(w3_instance, sender_pk, gas_price_wei, 
                        token_abi, token_bytecode, initial_owner_address, token_log_name,
                        run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        Contract = w3_instance.eth.contract(abi=token_abi, bytecode=token_bytecode)
        # TokenA.sol and TokenB.sol from simpleCPMM take `initialOwner` as constructor arg
        constructor_tx_data = Contract.constructor(Web3.to_checksum_address(initial_owner_address)).build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 2000000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(constructor_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Deploying {token_log_name} contract... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception(f"{token_log_name} contract deployment failed.")
        contract_address = tx_receipt.contractAddress
        print(f"{token_log_name} Contract deployed at: {contract_address}")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': f'deploy_{token_log_name.lower()}', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': f'deploy_{token_log_name.lower()}', 'sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}

def execute_erc20_transfer(w3_instance, sender_pk, gas_price_wei,
                          token_contract_address, token_abi,
                          recipient_address, amount_to_transfer, # amount in full units
                          run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        token_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(token_contract_address), abi=token_abi)
        
        transfer_tx_data = token_contract.functions.transfer(
            Web3.to_checksum_address(recipient_address),
            amount_to_transfer 
        ).build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 100000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(transfer_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transferring {amount_to_transfer} tokens from {sender_address_val} to {recipient_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("ERC20 transfer failed.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'erc20_transfer', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': token_contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'erc20_transfer','sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}
    
# --- ERC20 Mint Function (for TokenA/TokenB from simpleCPMM) ---
def execute_simple_erc20_mint(w3_instance, sender_pk, gas_price_wei, 
                              token_contract_address, token_abi,
                              recipient_address, amount_to_mint, # amount_to_mint in full units (e.g., 1000 * 10**18)
                              run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        token_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(token_contract_address), abi=token_abi)
        
        mint_tx_data = token_contract.functions.mint(
            Web3.to_checksum_address(recipient_address),
            amount_to_mint # This contract's mint takes the full value
        ).build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 150000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(mint_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Minting tokens on {token_contract_address} to {recipient_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("Token minting failed.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'erc20_mint', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': token_contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'erc20_mint','sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}

# --- ERC20 Approve Function ---
def execute_approve_erc20(w3_instance, owner_pk, gas_price_wei,
                          token_contract_address, token_abi,
                          spender_address, amount_to_approve, # amount in full units
                          run_identifier="N/A"):
    owner_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        owner_account = w3_instance.eth.account.from_key(owner_pk); owner_address_val = owner_account.address
        nonce_val = w3_instance.eth.get_transaction_count(owner_address_val)
        token_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(token_contract_address), abi=token_abi)
        
        approve_tx_data = token_contract.functions.approve(
            Web3.to_checksum_address(spender_address),
            amount_to_approve 
        ).build_transaction({
            'from': owner_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 100000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(approve_tx_data, owner_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Approving {spender_address} for {amount_to_approve} tokens on {token_contract_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("ERC20 approve failed.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'erc20_approve', 'sender_address': owner_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': token_contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'erc20_approve','sender_address': owner_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}


# --- AMM Pool (BasicPool.sol) Deployment ---
def deploy_amm_pool_contract(w3_instance, sender_pk, gas_price_wei,
                             run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        Contract = w3_instance.eth.contract(abi=BASIC_POOL_ABI, bytecode=BASIC_POOL_BYTECODE)
        # BasicPool.sol constructor takes no arguments
        constructor_tx_data = Contract.constructor().build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 4000000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(constructor_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Deploying AMM Pool contract... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("AMM Pool contract deployment failed.")
        contract_address = tx_receipt.contractAddress
        print(f"AMM Pool Contract deployed at: {contract_address}")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'deploy_amm_pool', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'deploy_amm_pool','sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}

# --- AMM Pool: Set Tokens (if needed after deployment) ---
def execute_pool_set_tokens(w3_instance, owner_pk, gas_price_wei,
                            pool_contract_address, token_a_address, token_b_address,
                            run_identifier="N/A"):
    owner_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        owner_account = w3_instance.eth.account.from_key(owner_pk); owner_address_val = owner_account.address
        nonce_val = w3_instance.eth.get_transaction_count(owner_address_val)
        pool_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(pool_contract_address), abi=BASIC_POOL_ABI)
        
        # Call setTokenA
        tx_set_a_data = pool_contract.functions.setTokenA(Web3.to_checksum_address(token_a_address)).build_transaction({
            'from': owner_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 100000
        })
        signed_tx_a = w3_instance.eth.account.sign_transaction(tx_set_a_data, owner_pk)
        tx_hash_a = w3_instance.eth.send_raw_transaction(signed_tx_a.raw_transaction)
        print(f"Setting TokenA on pool {pool_contract_address}... Tx Hash: {tx_hash_a.hex()}")
        tx_receipt_a = w3_instance.eth.wait_for_transaction_receipt(tx_hash_a, timeout=180)
        if tx_receipt_a.status != 1: raise Exception("Pool setTokenA failed.")
        
        # Increment nonce for the next transaction
        nonce_val += 1 

        # Call setTokenB
        tx_set_b_data = pool_contract.functions.setTokenB(Web3.to_checksum_address(token_b_address)).build_transaction({
            'from': owner_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 100000
        })
        signed_tx_b = w3_instance.eth.account.sign_transaction(tx_set_b_data, owner_pk)
        tx_hash_b = w3_instance.eth.send_raw_transaction(signed_tx_b.raw_transaction)
        print(f"Setting TokenB on pool {pool_contract_address}... Tx Hash: {tx_hash_b.hex()}")
        tx_receipt_b = w3_instance.eth.wait_for_transaction_receipt(tx_hash_b, timeout=180)
        if tx_receipt_b.status != 1: raise Exception("Pool setTokenB failed.")
        
        print(f"Tokens set successfully for pool {pool_contract_address}")
        # For simplicity, this function just confirms success; detailed metrics could be added per call
        return {'run_identifier': run_identifier, 'action': 'pool_set_tokens', 'status': 'Success', 'contract_address': pool_contract_address}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'pool_set_tokens', 'status': 'Error', 'error_message': str(e)}


# --- AMM Pool: Add Liquidity ---
def execute_add_liquidity(w3_instance, sender_pk, gas_price_wei,
                          pool_contract_address,
                          amount_a_to_add, amount_b_to_add, # amounts in full units
                          run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        pool_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(pool_contract_address), abi=BASIC_POOL_ABI)
        
        add_liquidity_tx_data = pool_contract.functions.addLiquidity(
            amount_a_to_add, amount_b_to_add
        ).build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 500000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(add_liquidity_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Adding liquidity to pool {pool_contract_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("Add liquidity failed.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'amm_add_liquidity', 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': pool_contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'amm_add_liquidity','sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}

# --- AMM Pool: Swap Tokens ---
def execute_amm_swap(w3_instance, sender_pk, gas_price_wei,
                     pool_contract_address,
                     token_in_address, amount_token_in, # amount in full units
                     token_out_address, min_amount_out, # min_amount_out in full units
                     recipient_address,
                     run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        pool_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(pool_contract_address), abi=BASIC_POOL_ABI)

        # Determine which swap function to call based on token_in
        # This assumes BasicPool.sol has swapAForB and swapBForA
        # And that tokenA from BasicPool corresponds to the first token set, tokenB to the second.
        pool_token_a = pool_contract.functions.tokenA().call()
        # pool_token_b = pool_contract.functions.tokenB().call() # Not strictly needed for this logic

        if Web3.to_checksum_address(token_in_address) == Web3.to_checksum_address(pool_token_a):
            swap_function = pool_contract.functions.swapAForB(amount_token_in, min_amount_out)
            action_name = 'amm_swap_A_for_B'
        else: # Assuming token_in is tokenB
            swap_function = pool_contract.functions.swapBForA(amount_token_in, min_amount_out)
            action_name = 'amm_swap_B_for_A'
        
        swap_tx_data = swap_function.build_transaction({
            'from': sender_address_val, 'nonce': nonce_val, 'gasPrice': gas_price_wei, 'gas': 300000 # Adjust gas
        })
        signed_tx = w3_instance.eth.account.sign_transaction(swap_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Executing AMM swap on {pool_contract_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception(f"AMM swap ({action_name}) failed.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': action_name, 'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': pool_contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'amm_swap_generic_error','sender_address': sender_address_val, 'nonce': nonce_val, 'status': 'Error', 'error_message': str(e)}


# --- Existing NFT Functions ---
# (Keep your deploy_nft_contract, execute_nft_mint, execute_nft_transfer functions here)
# Make sure they use MY_NFT_ABI and MY_NFT_BYTECODE
def deploy_nft_contract(w3_instance, sender_pk, gas_price_wei, nft_name, nft_symbol, run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        if not MY_NFT_ABI or not MY_NFT_BYTECODE: raise ValueError("NFT ABI or Bytecode not loaded.")
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        Contract = w3_instance.eth.contract(abi=MY_NFT_ABI, bytecode=MY_NFT_BYTECODE)
        constructor_tx_data = Contract.constructor(nft_name, nft_symbol).build_transaction({'from': sender_address_val,'nonce': nonce_val,'gasPrice': gas_price_wei,'gas': 3500000})
        signed_tx = w3_instance.eth.account.sign_transaction(constructor_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Deploying NFT ('{nft_name}') contract... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("NFT contract deployment failed.")
        contract_address = tx_receipt.contractAddress; print(f"NFT Contract '{nft_name}' deployed successfully at: {contract_address}")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'deploy_nft','sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': contract_address,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'deploy_nft','sender_address': sender_address_val, 'nonce': nonce_val,'status': 'Error', 'error_message': str(e)}

def execute_nft_mint(w3_instance, sender_pk, nft_contract_address, mint_to_address, gas_price_wei,run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'; minted_token_id = None
    try:
        if not MY_NFT_ABI: raise ValueError("NFT ABI not loaded.")
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        nft_contract_instance = w3_instance.eth.contract(address=Web3.to_checksum_address(nft_contract_address), abi=MY_NFT_ABI)
        mint_tx_data = nft_contract_instance.functions.safeMint(Web3.to_checksum_address(mint_to_address)).build_transaction({'from': sender_address_val,'nonce': nonce_val,'gasPrice': gas_price_wei,'gas': 250000})
        signed_tx = w3_instance.eth.account.sign_transaction(mint_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Minting NFT to {mint_to_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception("NFT minting transaction failed (receipt status not 1).")
        transfer_events = nft_contract_instance.events.Transfer().process_receipt(tx_receipt, errors=DISCARD)
        found_mint_event = False
        for event in transfer_events:
            if event.args['from'] == '0x0000000000000000000000000000000000000000' and event.args['to'] == Web3.to_checksum_address(mint_to_address):
                minted_token_id = event.args.tokenId; found_mint_event = True; print(f"NFT Mint event processed. Token ID: {minted_token_id}"); break
        if not found_mint_event: print(f"Warning: Could not find definitive Transfer event for mint in tx {tx_hash.hex()} logs.")
        print(f"NFT minted. Tx Status: Success. Token ID (from event processing): {minted_token_id if minted_token_id is not None else 'Not reliably found'}")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'nft_mint','sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': nft_contract_address, 'token_id_minted': minted_token_id,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}, minted_token_id
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'nft_mint','sender_address': sender_address_val, 'nonce': nonce_val,'status': 'Error', 'error_message': str(e)}, None

def execute_nft_transfer(w3_instance, sender_pk, nft_contract_address, transfer_to_address, token_id, gas_price_wei,run_identifier="N/A"):
    sender_address_val = 'N/A'; nonce_val = 'N/A'
    try:
        if not MY_NFT_ABI: raise ValueError("NFT ABI not loaded.")
        sender_account = w3_instance.eth.account.from_key(sender_pk); sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        nft_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(nft_contract_address), abi=MY_NFT_ABI)
        transfer_tx_data = nft_contract.functions.safeTransferFrom(sender_address_val, Web3.to_checksum_address(transfer_to_address),token_id).build_transaction({'from': sender_address_val,'nonce': nonce_val,'gasPrice': gas_price_wei,'gas': 150000})
        signed_tx = w3_instance.eth.account.sign_transaction(transfer_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transferring NFT ID {token_id} to {transfer_to_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time(); tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180); end_time = time.time()
        confirmation_time = end_time - start_time
        if tx_receipt.status != 1: raise Exception(f"NFT (ID: {token_id}) transfer failed.")
        print(f"NFT ID {token_id} transferred successfully.")
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price; fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')
        return {'run_identifier': run_identifier, 'action': 'nft_transfer','sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),'status': 'Success', 'contract_address': nft_contract_address, 'token_id_transferred': token_id,'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)}
    except Exception as e:
        return {'run_identifier': run_identifier, 'action': 'nft_transfer','sender_address': sender_address_val, 'nonce': nonce_val, 'token_id_transferred': token_id,'status': 'Error', 'error_message': str(e)}
