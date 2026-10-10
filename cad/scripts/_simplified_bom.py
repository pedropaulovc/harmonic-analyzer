"""Pure BOM-number inheritance for simplified configurations.

Part derivation and assembly identity share this policy without coupling part
recipes to assembly component fingerprints or drawing recipes to part saves.
"""

from __future__ import annotations

_DOCUMENT_NAME = 1  # swBOMPartNumberSource_e.swBOMPartNumber_DocumentName
_CONFIGURATION_NAME = 2  # swBOMPartNumberSource_e.swBOMPartNumber_ConfigurationName
_PARENT_NAME = 4  # swBOMPartNumberSource_e.swBOMPartNumber_ParentName
USER_SPECIFIED = 8  # swBOMPartNumberSource_e.swBOMPartNumber_UserSpecified

# (BOMPartNoSource, AlternateName, UseAlternateNameInBOM, Description,
#  UseDescriptionInBOM) of one configuration.
type BomIdentity = tuple[int, str, bool, str, bool]


def child_bom_identity(
    parent: BomIdentity, parent_name: str, grandparent_name: str | None
) -> BomIdentity:
    """The BOM identity that makes ``<parent> Simplified`` print ``parent``'s number.

    "Link to Parent Configuration" (``ParentName``) prints the parent
    configuration's NAME, not its part number (SOLIDWORKS help, Component
    Options). So a parent numbered by its own name hands the child a link, but a
    parent that is itself linked prints ITS parent's name, which the child must
    pin as a user-specified number: a link would print the parent's name. The
    document name and a user-specified number carry over unchanged.
    """
    source, alternate, use_alternate, description, use_description = parent
    if source == _DOCUMENT_NAME:
        return (source, "", use_alternate, description, use_description)
    if source == _CONFIGURATION_NAME:
        return (_PARENT_NAME, "", use_alternate, description, use_description)
    if source == _PARENT_NAME:
        if grandparent_name is None:
            raise ValueError(
                f"{parent_name!r} links its part number to a parent configuration "
                "it does not have"
            )
        return (USER_SPECIFIED, grandparent_name, True, description, use_description)
    if source == USER_SPECIFIED:
        return (source, alternate, use_alternate, description, use_description)
    raise ValueError(f"{parent_name!r}: unknown BOM part-number source {source}")
