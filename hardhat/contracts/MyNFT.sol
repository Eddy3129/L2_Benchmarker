// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20; 

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyNFT is ERC721, Ownable {
    uint256 private _nextTokenId;

    constructor(string memory name, string memory symbol) ERC721(name, symbol) Ownable(msg.sender) {
    }

    function safeMint(address to) public onlyOwner {
        uint256 tokenId = _nextTokenId;
        _nextTokenId++; 
        _safeMint(to, tokenId);
    }

    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _increaseBalance(address account, uint128 amount)
        internal
        override(ERC721)
    {
        super._increaseBalance(account, amount);
    }
}