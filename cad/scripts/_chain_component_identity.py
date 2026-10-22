"""Roller-chain component identity for assembly interference classification."""

# Exact native member identities; Name2 basenames are allocator-controlled and
# cannot prove that an occurrence is a chain link.
_CHAIN_LINK_IDENTITIES = {
    ("sh-vn-chain-link", "InnerLink"): "InnerLink",
    ("sh-vn-chain-link", "OuterLink"): "OuterLink",
}
