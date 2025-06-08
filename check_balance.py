from web3 import Web3

# Connect to both L1 and L2
l1_w3 = Web3(Web3.HTTPProvider("http://localhost:8545"))  # L1 reth node
l2_w3 = Web3(Web3.HTTPProvider("http://localhost:9545"))  # L2 zkSync node

# Your address
address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

# Check balances
l1_balance = l1_w3.from_wei(l1_w3.eth.get_balance(address), 'ether')
l2_balance = l2_w3.from_wei(l2_w3.eth.get_balance(address), 'ether')

print(f"L1 Balance: {l1_balance} ETH")
print(f"L2 Balance: {l2_balance} ETH")