from __future__ import annotations

from cookix import relations


def test_builtin_relations_registered():
    assert relations.is_registered("prevents")
    assert relations.is_registered("compatible_with")
    assert "contradicts" in relations.vocabulary()


def test_inverse_relations():
    assert relations.inverse_of("causes") == "caused_by"
    assert relations.inverse_of("caused_by") == "causes"
    # symmetric relations are their own inverse
    assert relations.inverse_of("similar_to") == "similar_to"


def test_relation_properties():
    assert relations.properties("is_a").transitive is True
    assert relations.properties("similar_to").symmetric is True


def test_register_custom_relation_creates_inverse():
    relations.register(
        "calibrated_against",
        relations.RelationProperties(inverse="calibration_reference_for"),
    )
    assert relations.is_registered("calibrated_against")
    assert relations.is_registered("calibration_reference_for")
    assert relations.inverse_of("calibrated_against") == "calibration_reference_for"
