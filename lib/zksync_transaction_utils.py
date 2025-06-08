# lib/zksync_transaction_utils.py
from zksync2.module.module_builder import ZkSyncBuilder
from zksync2.signer.eth_signer import PrivateKeyEthSigner
from zksync2.transaction.transaction_builders import TxFunctionCall
from zksync2.core.types import EthBlockParams
from eth_account import Account
from eth_typing import HexStr
import time
from web3 import Web3

# Assuming contract_loader.py is in the same 'lib' directory
from .contract_loader import load_contract_artifact

# --- Load Contract Artifacts ---
BASIC_POOL_ABI, BASIC_POOL_BYTECODE = load_contract_artifact("BasicPool.sol")

# NFT contract details
MY_NFT_ABI, MY_NFT_BYTECODE = None, None
try:
    MY_NFT_ABI, MY_NFT_BYTECODE = load_contract_artifact("MyNFT.sol")
except Exception as e:
    print(f"Warning: NFT details for MyNFT.sol not loaded via contract_loader. NFT tests might fail. Error: {e}")

# --- Helper function to extract ZKsync L1 fee data ---
def extract_zksync_l1_fee_data(zk_web3, tx_receipt):
    """Extract L1 fee components from ZKsync transaction receipt"""
    l1_fee_component_wei = tx_receipt.get('l1Fee')
    l1_gas_used_on_l1 = tx_receipt.get('l1GasUsed')
    l1_gas_price_on_l1 = tx_receipt.get('l1GasPrice')
    l1_fee_scalar = tx_receipt.get('l1FeeScalar')
    
    return {
        'l1_fee_wei': l1_fee_component_wei if l1_fee_component_wei is not None else None,
        'l1_fee_eth': zk_web3.from_wei(l1_fee_component_wei, 'ether') if l1_fee_component_wei is not None else None,
        'l1_gas_used': l1_gas_used_on_l1 if l1_gas_used_on_l1 is not None else None,
        'l1_gas_price_gwei': zk_web3.from_wei(l1_gas_price_on_l1, 'gwei') if l1_gas_price_on_l1 is not None else None,
        'l1_fee_scalar': l1_fee_scalar if l1_fee_scalar is not None else None
    }

# --- ZKsync P2P Transfer ---
def execute_zksync_p2p_transfer(zk_web3, sender_pk, recipient_address, amount_wei, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Get gas price
        gas_price = zk_web3.zksync.gas_price
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            to=Web3.to_checksum_address(recipient_address),
            value=amount_wei,
            data=HexStr("0x"),
            gas_limit=21000,
            gas_price=gas_price,
            max_priority_fee_per_gas=45250000,  # 0.1 gwei
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        
        # Create EIP712 transaction and sign
        tx_712 = tx_func_call.tx712(estimate_gas)
        signed_message = signer.sign_typed_data(tx_712.to_eip712_struct())
        msg = tx_712.encode(signed_message)
        
        print(f"ZKsync P2P Transfer: {sender_address_val} -> {recipient_address} | Amount: {zk_web3.from_wei(amount_wei, 'ether')} ETH")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync P2P transfer failed.")
            
        effective_gas_price = tx_receipt.get('effectiveGasPrice', gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'zksync_p2p_transfer',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'recipient_address': recipient_address,
            'amount_transferred_eth': zk_web3.from_wei(amount_wei, 'ether'),
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'zksync_p2p_transfer',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }

# --- ZKsync ERC20 Deployment ---
def deploy_zksync_simple_erc20(zk_web3, sender_pk, token_name, token_symbol, initial_supply, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        # Load ERC20 contract artifacts dynamically
        SIMPLE_ERC20_ABI, SIMPLE_ERC20_BYTECODE = load_contract_artifact("MyToken.sol")
        
        if not SIMPLE_ERC20_ABI or not SIMPLE_ERC20_BYTECODE:
            raise ValueError("ERC20 ABI or Bytecode not loaded/defined.")
            
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Create contract instance
        contract = zk_web3.zksync.contract(abi=SIMPLE_ERC20_ABI, bytecode=SIMPLE_ERC20_BYTECODE)
        
        # Build constructor transaction
        constructor_tx = contract.constructor(token_name, token_symbol, initial_supply)
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            data=constructor_tx.data_in_transaction,
            gas_limit=2000000,
            gas_price=zk_web3.zksync.gas_price,
            max_priority_fee_per_gas=45250000,
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        tx_func_call.tx["gas"] = estimate_gas
        
        # Sign and send transaction
        signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())
        msg = tx_func_call.encode(signed_message)
        
        print(f"Deploying ZKsync ERC20 ('{token_name}') contract...")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync ERC20 contract deployment failed.")
            
        contract_address = tx_receipt.contractAddress
        print(f"ZKsync ERC20 Contract '{token_name}' deployed successfully at: {contract_address}")
        
        effective_gas_price = tx_receipt.get('effectiveGasPrice', zk_web3.zksync.gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_erc20',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(zk_web3.zksync.gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_erc20',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }

# --- ZKsync ERC20 Mint ---
def execute_zksync_erc20_mint(zk_web3, sender_pk, erc20_contract_address, mint_to_address, mint_amount, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        # Load ERC20 ABI
        SIMPLE_ERC20_ABI, _ = load_contract_artifact("MyToken.sol")
        
        if not SIMPLE_ERC20_ABI:
            raise ValueError("ERC20 ABI not loaded/defined.")
            
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Create contract instance
        erc20_contract = zk_web3.zksync.contract(
            address=Web3.to_checksum_address(erc20_contract_address),
            abi=SIMPLE_ERC20_ABI
        )
        
        # Build mint transaction
        mint_tx = erc20_contract.functions.mint(
            Web3.to_checksum_address(mint_to_address),
            mint_amount
        )
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            to=Web3.to_checksum_address(erc20_contract_address),
            data=mint_tx.data_in_transaction,
            gas_limit=100000,
            gas_price=zk_web3.zksync.gas_price,
            max_priority_fee_per_gas=45250000,
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        tx_func_call.tx["gas"] = estimate_gas
        
        # Sign and send transaction
        signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())
        msg = tx_func_call.encode(signed_message)
        
        print(f"Minting {mint_amount} ZKsync tokens to {mint_to_address}...")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync ERC20 minting failed.")
            
        effective_gas_price = tx_receipt.get('effectiveGasPrice', zk_web3.zksync.gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'zksync_erc20_mint',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': erc20_contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(zk_web3.zksync.gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'zksync_erc20_mint',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }

# --- ZKsync ERC20 Approve ---
def execute_zksync_approve_erc20(zk_web3, sender_pk, erc20_contract_address, spender_address, approve_amount, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        # Load ERC20 ABI
        SIMPLE_ERC20_ABI, _ = load_contract_artifact("MyToken.sol")
        
        if not SIMPLE_ERC20_ABI:
            raise ValueError("ERC20 ABI not loaded/defined.")
            
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Create contract instance
        erc20_contract = zk_web3.zksync.contract(
            address=Web3.to_checksum_address(erc20_contract_address),
            abi=SIMPLE_ERC20_ABI
        )
        
        # Build approve transaction
        approve_tx = erc20_contract.functions.approve(
            Web3.to_checksum_address(spender_address),
            approve_amount
        )
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            to=Web3.to_checksum_address(erc20_contract_address),
            data=approve_tx.data_in_transaction,
            gas_limit=100000,
            gas_price=zk_web3.zksync.gas_price,
            max_priority_fee_per_gas=45250000,
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        tx_func_call.tx["gas"] = estimate_gas
        
        # Sign and send transaction
        signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())
        msg = tx_func_call.encode(signed_message)
        
        print(f"Approving {approve_amount} ZKsync tokens for spender {spender_address}...")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=180)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync ERC20 approval failed.")
            
        effective_gas_price = tx_receipt.get('effectiveGasPrice', zk_web3.zksync.gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'zksync_erc20_approve',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': erc20_contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(zk_web3.zksync.gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'zksync_erc20_approve',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }

# --- ZKsync AMM Pool Deployment ---
def deploy_zksync_amm_pool_contract(zk_web3, sender_pk, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        if not BASIC_POOL_ABI or not BASIC_POOL_BYTECODE:
            raise ValueError("BasicPool ABI or Bytecode not loaded/defined.")
            
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Create contract instance
        contract = zk_web3.zksync.contract(abi=BASIC_POOL_ABI, bytecode=BASIC_POOL_BYTECODE)
        
        # Build constructor transaction
        constructor_tx = contract.constructor()
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            data=constructor_tx.data_in_transaction,
            gas_limit=3000000,
            gas_price=zk_web3.zksync.gas_price,
            max_priority_fee_per_gas=45250000,
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        tx_func_call.tx["gas"] = estimate_gas
        
        # Sign and send transaction
        signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())
        msg = tx_func_call.encode(signed_message)
        
        print(f"Deploying ZKsync AMM Pool contract...")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync AMM Pool contract deployment failed.")
            
        contract_address = tx_receipt.contractAddress
        print(f"ZKsync AMM Pool Contract deployed successfully at: {contract_address}")
        
        effective_gas_price = tx_receipt.get('effectiveGasPrice', zk_web3.zksync.gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_amm_pool',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(zk_web3.zksync.gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_amm_pool',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }

# --- ZKsync NFT Deployment ---
def deploy_zksync_nft_contract(zk_web3, sender_pk, nft_name, nft_symbol, run_identifier="N/A"):
    sender_address_val = 'N/A'
    nonce_val = 'N/A'
    try:
        if not MY_NFT_ABI or not MY_NFT_BYTECODE:
            raise ValueError("NFT ABI or Bytecode not loaded/defined.")
            
        # Create signer
        account = Account.from_key(sender_pk)
        sender_address_val = account.address
        signer = PrivateKeyEthSigner(account, zk_web3.zksync.chain_id)
        
        # Get nonce
        nonce_val = zk_web3.zksync.get_transaction_count(
            Web3.to_checksum_address(sender_address_val), EthBlockParams.LATEST.value
        )
        
        # Create contract instance
        contract = zk_web3.zksync.contract(abi=MY_NFT_ABI, bytecode=MY_NFT_BYTECODE)
        
        # Build constructor transaction
        constructor_tx = contract.constructor(nft_name, nft_symbol)
        
        # Create transaction
        tx_func_call = TxFunctionCall(
            chain_id=zk_web3.zksync.chain_id,
            nonce=nonce_val,
            from_=sender_address_val,
            data=constructor_tx.data_in_transaction,
            gas_limit=2000000,
            gas_price=zk_web3.zksync.gas_price,
            max_priority_fee_per_gas=45250000,
        )
        
        # Estimate gas
        estimate_gas = zk_web3.zksync.eth_estimate_gas(tx_func_call.tx)
        tx_func_call.tx["gas"] = estimate_gas
        
        # Sign and send transaction
        signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())
        msg = tx_func_call.encode(signed_message)
        
        print(f"Deploying ZKsync NFT ('{nft_name}') contract...")
        start_time = time.time()
        tx_hash = zk_web3.zksync.send_raw_transaction(msg)
        tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        confirmation_time = end_time - start_time
        
        if tx_receipt.status != 1:
            raise Exception("ZKsync NFT contract deployment failed.")
            
        contract_address = tx_receipt.contractAddress
        print(f"ZKsync NFT Contract '{nft_name}' deployed successfully at: {contract_address}")
        
        effective_gas_price = tx_receipt.get('effectiveGasPrice', zk_web3.zksync.gas_price)
        fee_paid_wei = tx_receipt.gasUsed * effective_gas_price
        fee_paid_eth = zk_web3.from_wei(fee_paid_wei, 'ether')
        
        # Extract L1 fee data
        l1_fee_data = extract_zksync_l1_fee_data(zk_web3, tx_receipt)
        
        result = {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_nft',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'tx_hash': tx_hash.hex(),
            'status': 'Success',
            'contract_address': contract_address,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'configured_gas_price_gwei': round(zk_web3.from_wei(zk_web3.zksync.gas_price, 'gwei'), 4),
            'effective_gas_price_gwei': round(zk_web3.from_wei(effective_gas_price, 'gwei'), 4),
            'fee_paid_eth': fee_paid_eth,
            'confirmation_time_sec': round(confirmation_time, 6)
        }
        result.update(l1_fee_data)
        return result
        
    except Exception as e:
        return {
            'run_identifier': run_identifier,
            'action': 'deploy_zksync_nft',
            'sender_address': sender_address_val,
            'nonce': nonce_val,
            'status': 'Error',
            'error_message': str(e)
        }