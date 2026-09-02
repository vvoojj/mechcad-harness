from mechcad_harness.candidates.models import (
    ComponentPropertyAuthority as CandidateAuthority,
    ComponentPropertyAvailability as CandidateAvailability,
)
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalComponentPropertyAuthority,
    CanonicalComponentPropertyAvailability,
)


def test_legacy_authority_imports_are_the_shared_enum_classes_with_original_values():
    assert CandidateAvailability is ComponentPropertyAvailability
    assert CandidateAuthority is ComponentPropertyAuthority
    assert CanonicalComponentPropertyAvailability is ComponentPropertyAvailability
    assert CanonicalComponentPropertyAuthority is ComponentPropertyAuthority
    assert CandidateAuthority.MANUFACTURER_DATASHEET.value == "manufacturer_datasheet"
    assert CandidateAvailability.NOT_APPLICABLE.value == "not_applicable"
