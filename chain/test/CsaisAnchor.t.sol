// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {CsaisAnchor} from "../src/CsaisAnchor.sol";

/// Uji tanpa forge-std: kegagalan ditandai revert (require).
contract Outsider {
    function tryAnchor(CsaisAnchor c) external returns (bool ok) {
        (ok,) = address(c).call(abi.encodeCall(CsaisAnchor.anchorRoot, (9, bytes32(uint256(9)), bytes32(0), 0)));
    }
}

contract CsaisAnchorTest {
    CsaisAnchor c;

    function setUp() public {
        c = new CsaisAnchor();
    }

    function test_anchor_and_read() public {
        bytes32 root = keccak256("root-1");
        c.anchorRoot(1, root, bytes32(0), 0);
        (uint64 batchId, uint8 kind,, uint64 blockNumber,) = c.getAnchor(root);
        require(batchId == 1 && kind == 0 && blockNumber == block.number, "anchor data");
        require(c.latestRoot() == root && c.anchorCount() == 1, "latest");
    }

    function test_same_root_twice_reverts() public {
        bytes32 root = keccak256("root-2");
        c.anchorRoot(2, root, bytes32(0), 1);
        (bool ok,) = address(c).call(abi.encodeCall(CsaisAnchor.anchorRoot, (3, root, bytes32(0), 1)));
        require(!ok, "duplicate must revert");
    }

    function test_only_relayer() public {
        Outsider o = new Outsider();
        require(!o.tryAnchor(c), "outsider must be rejected");
        c.setRelayer(address(o), true);
        require(o.tryAnchor(c), "allowed relayer");
    }

    function test_empty_root_reverts() public {
        (bool ok,) = address(c).call(abi.encodeCall(CsaisAnchor.anchorRoot, (4, bytes32(0), bytes32(0), 0)));
        require(!ok, "empty root must revert");
    }
}
