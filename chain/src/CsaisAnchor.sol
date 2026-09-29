// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @title CsaisAnchor
/// @notice Menjangkarkan akar Merkle batch bukti CSAIS (bukti artikel dan
/// catatan resmi D4). Hanya hash yang disimpan di rantai; datanya tetap
/// off-chain. Kontrak ini permissioned: hanya relayer CSAIS yang boleh
/// menjangkarkan, dan lembaga (BSSN, OJK, Komdigi, Siber Polri) terdaftar
/// untuk atestasi bertanda tangan pada tahap berikutnya.
contract CsaisAnchor {
    struct Anchor {
        uint64 batchId;
        uint8 kind; // 0 = bukti artikel, 1 = catatan resmi D4
        bytes32 previousRoot;
        uint64 blockNumber;
        uint64 timestamp;
    }

    address public admin;
    mapping(address => bool) public relayers;
    mapping(bytes32 => address) public institutions; // kode lembaga -> alamat
    mapping(bytes32 => Anchor) private anchors; // akar -> jangkar
    bytes32 public latestRoot;
    uint256 public anchorCount;

    event RootAnchored(bytes32 indexed root, uint64 indexed batchId, uint8 kind, bytes32 previousRoot);
    event RelayerSet(address indexed relayer, bool allowed);
    event InstitutionSet(bytes32 indexed code, address account);

    error NotAdmin();
    error NotRelayer();
    error AlreadyAnchored(bytes32 root);
    error EmptyRoot();

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    constructor() {
        admin = msg.sender;
        relayers[msg.sender] = true;
        emit RelayerSet(msg.sender, true);
    }

    function setRelayer(address relayer, bool allowed) external onlyAdmin {
        relayers[relayer] = allowed;
        emit RelayerSet(relayer, allowed);
    }

    function setInstitution(bytes32 code, address account) external onlyAdmin {
        institutions[code] = account;
        emit InstitutionSet(code, account);
    }

    /// @notice Jangkarkan satu akar batch. Akar yang sama tidak bisa dijangkarkan dua kali.
    function anchorRoot(uint64 batchId, bytes32 root, bytes32 previousRoot, uint8 kind) external {
        if (!relayers[msg.sender]) revert NotRelayer();
        if (root == bytes32(0)) revert EmptyRoot();
        if (anchors[root].blockNumber != 0) revert AlreadyAnchored(root);
        anchors[root] = Anchor(batchId, kind, previousRoot, uint64(block.number), uint64(block.timestamp));
        latestRoot = root;
        anchorCount += 1;
        emit RootAnchored(root, batchId, kind, previousRoot);
    }

    /// @notice Data jangkar satu akar; blockNumber 0 berarti belum dijangkarkan.
    function getAnchor(bytes32 root)
        external
        view
        returns (uint64 batchId, uint8 kind, bytes32 previousRoot, uint64 blockNumber, uint64 timestamp)
    {
        Anchor memory a = anchors[root];
        return (a.batchId, a.kind, a.previousRoot, a.blockNumber, a.timestamp);
    }
}
