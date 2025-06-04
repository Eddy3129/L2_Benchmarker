# lib/contract_loader.py
import json
import os

HARDHAT_PROJECT_RELATIVE_PATH = "../hardhat"

def load_contract_artifact(contract_sol_filename):
    """
    Loads ABI and bytecode from a Hardhat JSON artifact file.
    contract_sol_filename should be like "TokenA.sol", "BasicPool.sol"
    """
    contract_name = contract_sol_filename.replace(".sol", "")
    
    # Determine the base path of this script (lib directory)
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the full path to the artifact file
    artifact_path = os.path.join(
        lib_dir,
        HARDHAT_PROJECT_RELATIVE_PATH,
        "artifacts",
        "contracts",
        contract_sol_filename,
        f"{contract_name}.json"
    )

    print(f"Attempting to load artifact from: {artifact_path}")

    try:
        with open(artifact_path, 'r') as f:
            artifact = json.load(f)
        
        abi = artifact.get('abi')
        bytecode_obj = artifact.get('bytecode') # Hardhat stores bytecode directly as a hex string

        if not abi:
            raise ValueError(f"ABI not found in artifact: {artifact_path}")
        if not bytecode_obj or not isinstance(bytecode_obj, str) or not bytecode_obj.startswith('0x'):
              raise ValueError(f"Bytecode not found or invalid in artifact: {artifact_path}. Bytecode found: {bytecode_obj}")
        return abi, bytecode_obj
    except FileNotFoundError:
        print(f"❌ Artifact file not found: {artifact_path}")
        print("Please ensure you have compiled your Hardhat project and the path is correct.")
        raise
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ Error parsing artifact {artifact_path}: {e}")
        raise
