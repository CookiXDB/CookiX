"""Controlled vocabulary of typed relations.

In NoVectDB a relation is not a distance — it is a *typed, directed* connection
with algebraic properties (symmetry, transitivity, an inverse). Those properties
are what let the query engine reason over paths instead of proximity.

The vocabulary is extensible: register custom relations with :func:`register`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RelationProperties:
    """Algebraic properties of a relation type.

    Attributes:
        symmetric: ``a r b`` implies ``b r a`` (e.g. ``similar_to``).
        transitive: ``a r b`` and ``b r c`` imply ``a r c`` (e.g. ``is_a``).
        inverse: name of the relation obtained by reversing direction, if any.
        description: human-readable meaning, surfaced in reasoning paths.
    """

    symmetric: bool = False
    transitive: bool = False
    inverse: str | None = None
    description: str = ""


# Built-in vocabulary. Inverses are declared once; register() wires both ways.
_BUILTINS: dict[str, RelationProperties] = {
    "is_a": RelationProperties(transitive=True, inverse="subsumes", description="type/subtype"),
    "subsumes": RelationProperties(transitive=True, inverse="is_a", description="supertype of"),
    "part_of": RelationProperties(transitive=True, inverse="has_part", description="component of"),
    "has_part": RelationProperties(transitive=True, inverse="part_of", description="contains part"),
    "causes": RelationProperties(inverse="caused_by", description="causal antecedent"),
    "caused_by": RelationProperties(inverse="causes", description="causal consequent"),
    "prevents": RelationProperties(inverse="prevented_by", description="blocks/negates"),
    "prevented_by": RelationProperties(inverse="prevents", description="blocked by"),
    "requires": RelationProperties(inverse="required_by", description="depends on"),
    "required_by": RelationProperties(inverse="requires", description="dependency of"),
    "contradicts": RelationProperties(symmetric=True, description="logically conflicts with"),
    "compatible_with": RelationProperties(symmetric=True, description="works together with"),
    "similar_to": RelationProperties(symmetric=True, description="resembles"),
    "related_to": RelationProperties(symmetric=True, description="generic association"),
    "example_of": RelationProperties(inverse="has_example", description="instance of"),
    "has_example": RelationProperties(inverse="example_of", description="has instance"),
    "conforms_to": RelationProperties(inverse="specified_by", description="meets standard"),
    "specified_by": RelationProperties(inverse="conforms_to", description="standard for"),
    "used_in": RelationProperties(inverse="uses", description="applied within"),
    "uses": RelationProperties(inverse="used_in", description="makes use of"),
}

_REGISTRY: dict[str, RelationProperties] = dict(_BUILTINS)


def register(name: str, properties: RelationProperties | None = None) -> None:
    """Add a custom relation type to the vocabulary.

    If ``properties.inverse`` names a relation that is not yet registered, a
    mirror entry is created automatically so traversal can walk edges backwards.
    """
    props = properties or RelationProperties()
    _REGISTRY[name] = props
    if props.inverse and props.inverse not in _REGISTRY:
        _REGISTRY[props.inverse] = RelationProperties(
            symmetric=props.symmetric,
            transitive=props.transitive,
            inverse=name,
            description=f"inverse of {name}",
        )


def is_registered(name: str) -> bool:
    return name in _REGISTRY


def properties(name: str) -> RelationProperties:
    """Return properties for ``name``, falling back to a neutral default."""
    return _REGISTRY.get(name, RelationProperties(description="unspecified relation"))


def inverse_of(name: str) -> str | None:
    props = _REGISTRY.get(name)
    if props is None:
        return None
    if props.symmetric:
        return name
    return props.inverse


def vocabulary() -> list[str]:
    """All currently registered relation names, sorted."""
    return sorted(_REGISTRY)
