# lib/transaction_utils.py
from web3 import Web3
import time
from contracts.erc20_details import MY_TOKEN_ABI, MY_TOKEN_BYTECODE # Import ABI and Bytecode
from contracts.nft_details import MY_NFT_ABI, MY_NFT_BYTECODE
from web3.logs import DISCARD

def execute_p2p_transfer(w3_instance, sender_pk, recipient_address, amount_eth, gas_price_wei, run_identifier="N/A"):
    sender_address_val = 'N/A' # Default in case of early error
    nonce_val = 'N/A' # Default in case of early error
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address
        checksum_recipient_address = Web3.to_checksum_address(recipient_address)
        
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)
        
        tx_details = {
            'to': checksum_recipient_address,
            'value': w3_instance.to_wei(amount_eth, 'ether'),
            'gas': 21000,
            'gasPrice': gas_price_wei,
            'nonce': nonce_val,
            'chainId': w3_instance.eth.chain_id
        }

        signed_tx = w3_instance.eth.account.sign_transaction(tx_details, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier,
            'action': 'p2p_eth_transfer', # Ensure this is present
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success' if tx_receipt.status == 1 else 'Failed',
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result
    
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'p2p_eth_transfer', # Ensure this is present
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error', 
            'error_message': str(e)
        }


def deploy_erc20_contract(w3_instance, sender_pk, gas_price_wei, 
                          token_name, token_symbol, initial_supply_tokens, 
                          run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)

        Contract = w3_instance.eth.contract(abi=MY_TOKEN_ABI, bytecode=MY_TOKEN_BYTECODE)

        constructor_tx_data = Contract.constructor(token_name, token_symbol, initial_supply_tokens).build_transaction({
            'from': sender_address_val,
            'nonce': nonce_val,
            'gasPrice': gas_price_wei,
            'gas': 3000000 
        })

        signed_tx = w3_instance.eth.account.sign_transaction(constructor_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Deploying ERC20 ('{token_name}') contract... Tx Hash: {tx_hash.hex()}")
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        confirmation_time = end_time - start_time

        if tx_receipt.status != 1:
            revert_reason = "Deployment failed, reason not available."
            # Basic attempt to get revert reason (can be unreliable)
            try:
                failed_tx = w3_instance.eth.get_transaction(tx_hash)
                revert_call_result = w3_instance.eth.call({
                    'to': failed_tx.get('to'), 
                    'from': failed_tx['from'],
                    'value': failed_tx['value'],
                    'data': failed_tx['input'],
                    'gas': failed_tx['gas'],
                    'gasPrice': failed_tx['gasPrice'],
                }, failed_tx.blockNumber -1 if failed_tx.blockNumber else None)
            except Exception:
                pass # Ignore errors trying to get revert reason
            raise Exception(revert_reason)

        contract_address = tx_receipt.contractAddress
        print(f"ERC20 Contract '{token_name}' deployed successfully at address: {contract_address}")

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier,
            'action': 'deploy_erc20',
            'sender_address': sender_address_val, # Added
            'nonce': nonce_val, # Added
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result

    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'deploy_erc20',
            'sender_address': sender_address_val, # Added
            'nonce': nonce_val, # Added
            'status': 'Error',
            'error_message': str(e)
        }

def execute_erc20_transfer(w3_instance, sender_pk, contract_address, 
                           recipient_address, amount_tokens, gas_price_wei,
                           run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)

        token_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(contract_address), abi=MY_TOKEN_ABI)
        
        try:
            token_decimals = token_contract.functions.decimals().call()
        except Exception as call_e:
            print(f"Warning: Could not fetch token decimals for {contract_address}, assuming 18. Error: {call_e}")
            token_decimals = 18

        amount_in_wei_equivalent = int(amount_tokens * (10**token_decimals))

        transfer_tx_data = token_contract.functions.transfer(
            Web3.to_checksum_address(recipient_address),
            amount_in_wei_equivalent
        ).build_transaction({
            'from': sender_address_val,
            'nonce': nonce_val,
            'gasPrice': gas_price_wei,
            'gas': 100000 
        })

        signed_tx = w3_instance.eth.account.sign_transaction(transfer_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Sending ERC20 transfer... Tx Hash: {tx_hash.hex()}")
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time

        if tx_receipt.status != 1:
            raise Exception("ERC20 token transfer failed.")

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier,
            'action': 'erc20_transfer',
            'sender_address': sender_address_val, # Added
            'nonce': nonce_val, # Added
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result

    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'erc20_transfer',
            'sender_address': sender_address_val, # Added
            'nonce': nonce_val, # Added
            'status': 'Error',
            'error_message': str(e)
        }


# --- New NFT Functions ---
def deploy_nft_contract(w3_instance, sender_pk, gas_price_wei, 
                        nft_name, nft_symbol, 
                        run_identifier="N/A"):
    """Deploys the MyNFT ERC721 contract."""
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)

        Contract = w3_instance.eth.contract(abi=MY_NFT_ABI, bytecode=MY_NFT_BYTECODE)

        constructor_tx_data = Contract.constructor(nft_name, nft_symbol).build_transaction({
            'from': sender_address_val,
            'nonce': nonce_val,
            'gasPrice': gas_price_wei,
            'gas': 3500000  # Start generous for NFT deployment, then optimize
        })

        signed_tx = w3_instance.eth.account.sign_transaction(constructor_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Deploying NFT ('{nft_name}') contract... Tx Hash: {tx_hash.hex()}")
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        confirmation_time = end_time - start_time

        if tx_receipt.status != 1: raise Exception("NFT contract deployment failed.")
        contract_address = tx_receipt.contractAddress
        print(f"NFT Contract '{nft_name}' deployed successfully at: {contract_address}")

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier, 'action': 'deploy_nft',
            'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),
            'status': 'Success', 'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result
    except Exception as e:
        return {
            'run_identifier': run_identifier, 'action': 'deploy_nft',
            'sender_address': sender_address_val, 'nonce': nonce_val,
            'status': 'Error', 'error_message': str(e)
        }


def execute_nft_mint(w3_instance, sender_pk, nft_contract_address, 
                     mint_to_address, gas_price_wei,
                     run_identifier="N/A"):
    """Mints an NFT using the deployed MyNFT contract's safeMint function."""
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    minted_token_id = None # Initialize
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)

        nft_contract_instance = w3_instance.eth.contract(address=Web3.to_checksum_address(nft_contract_address), abi=MY_NFT_ABI)
        
        mint_tx_data = nft_contract_instance.functions.safeMint(
            Web3.to_checksum_address(mint_to_address)
        ).build_transaction({
            'from': sender_address_val,
            'nonce': nonce_val,
            'gasPrice': gas_price_wei,
            'gas': 250000  # Adjust if needed
        })

        signed_tx = w3_instance.eth.account.sign_transaction(mint_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Minting NFT to {mint_to_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time

        if tx_receipt.status != 1: 
            raise Exception("NFT minting transaction failed (receipt status not 1).")
        
        # More robust way to get the minted token ID using process_receipt
        transfer_events = nft_contract_instance.events.Transfer().process_receipt(tx_receipt, errors=DISCARD)
        
        found_mint_event = False
        for event in transfer_events:
            # For a mint, the 'from' address is the zero address
            if event.args['from'] == '0x0000000000000000000000000000000000000000' and \
               event.args['to'] == Web3.to_checksum_address(mint_to_address): # Ensure it's minted to the right address
                minted_token_id = event.args.tokenId
                found_mint_event = True
                print(f"NFT Mint event processed. Token ID: {minted_token_id}")
                break
        
        if not found_mint_event:
             print(f"Warning: Could not find definitive Transfer event for mint in tx {tx_hash.hex()} logs. Receipt logs: {tx_receipt.logs}")
             # Fallback to manual log parsing if process_receipt didn't find it as expected
             # This part might be redundant if process_receipt works, but can be a backup
             for log in tx_receipt.logs:
                # Check if topics exist and are sufficient
                if len(log.topics) >= 4 and log.address == Web3.to_checksum_address(nft_contract_address):
                    event_signature_hash = w3_instance.keccak(text="Transfer(address,address,uint256)").hex()
                    if log.topics[0].hex() == event_signature_hash:
                        # Check 'from' address (topic 1) is address(0) for mint
                        # topics[1] is 'from', topics[2] is 'to', topics[3] is 'tokenId'
                        from_address_hex = log.topics[1].hex()
                        # Normalize zero address representation
                        if from_address_hex == '0x0000000000000000000000000000000000000000000000000000000000000000' or \
                           from_address_hex == '0x0000000000000000000000000000000000000000': # Some nodes might vary
                            minted_token_id = w3_instance.to_int(hexstr=log.topics[3].hex())
                            print(f"NFT Mint event found via manual log parsing. Token ID: {minted_token_id}")
                            break


        print(f"NFT minted. Tx Status: Success. Token ID (from event processing): {minted_token_id if minted_token_id is not None else 'Not reliably found'}")

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier, 'action': 'nft_mint',
            'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),
            'status': 'Success', 'contract_address': nft_contract_address, 'token_id_minted': minted_token_id,
            'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result, minted_token_id 
    except Exception as e:
        return {
            'run_identifier': run_identifier, 'action': 'nft_mint',
            'sender_address': sender_address_val, 'nonce': nonce_val,
            'status': 'Error', 'error_message': str(e)
        }, None

def execute_nft_transfer(w3_instance, sender_pk, nft_contract_address, 
                         transfer_to_address, token_id, gas_price_wei,
                         run_identifier="N/A"):
    """Transfers a minted NFT using the deployed MyNFT contract."""
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        sender_account = w3_instance.eth.account.from_key(sender_pk)
        sender_address_val = sender_account.address # This is the current owner of the NFT
        nonce_val = w3_instance.eth.get_transaction_count(sender_address_val)

        nft_contract = w3_instance.eth.contract(address=Web3.to_checksum_address(nft_contract_address), abi=MY_NFT_ABI)
        
        # Using safeTransferFrom(from, to, tokenId)
        transfer_tx_data = nft_contract.functions.safeTransferFrom(
            sender_address_val, # From current owner
            Web3.to_checksum_address(transfer_to_address),
            token_id
        ).build_transaction({
            'from': sender_address_val,
            'nonce': nonce_val,
            'gasPrice': gas_price_wei,
            'gas': 150000  # Estimate or set a reasonable gas limit for NFT transfer
        })

        signed_tx = w3_instance.eth.account.sign_transaction(transfer_tx_data, sender_pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Transferring NFT ID {token_id} to {transfer_to_address}... Tx Hash: {tx_hash.hex()}")
        start_time = time.time()
        tx_receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time

        if tx_receipt.status != 1: raise Exception(f"NFT (ID: {token_id}) transfer failed.")
        print(f"NFT ID {token_id} transferred successfully.")

        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price_wei)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = w3_instance.from_wei(fee_paid_wei, 'ether')

        result = {
            'run_identifier': run_identifier, 'action': 'nft_transfer',
            'sender_address': sender_address_val, 'nonce': nonce_val, 'tx_hash': tx_hash.hex(),
            'status': 'Success', 'contract_address': nft_contract_address, 'token_id_transferred': token_id,
            'block_number': tx_receipt.blockNumber, 'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(w3_instance.from_wei(gas_price_wei, 'gwei'), 4),
            'effective_gas_price_gwei': round(w3_instance.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth, 'confirmation_time_sec': round(confirmation_time, 6)
        }
        return result
    except Exception as e:
        return {
            'run_identifier': run_identifier, 'action': 'nft_transfer',
            'sender_address': sender_address_val, 'nonce': nonce_val, 'token_id_transferred': token_id,
            'status': 'Error', 'error_message': str(e)
        }
