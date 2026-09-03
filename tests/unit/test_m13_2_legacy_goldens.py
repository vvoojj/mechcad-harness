from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    RectangularPocketOperation,
    ThroughHoleOperation,
    ThroughSlotOperation,
    acceptance_program,
    cad_program_hash,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
)
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    GeometrySourceReference,
)
from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
from mechcad_harness.candidates.promotion_models import CandidatePromotionPolicy
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalComponentProperty,
    CanonicalComponentPropertyAvailability,
    CanonicalComponentPropertyAuthority,
    CanonicalComponentSpecification,
    CanonicalConnectionMeaning,
    CanonicalGeometryFidelity,
    CanonicalGeometrySourceReference,
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalPairRequirement,
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalDesignChoiceOrigin,
    DesignState,
)
from mechcad_harness.models.component_property import ComponentPropertyAuthority, ComponentPropertyAvailability
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationAuthorityFact,
    GeometryDerivationAuthorityRole,
    GeometryDerivationStatus,
    GeometryDerivationTransform,
    GeometryDerivationUnitConversion,
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
)
from mechcad_harness.state import state_hash


# Goldens captured from the unmodified pre-M13-2 tree. These literals are
# compatibility locks and must not be regenerated after production changes.
GOLDEN_PLATE_JSON = '{"part_id":"M13GoldenPlate","operations":[{"operation_id":"base","operation_type":"base_plate","length_mm":80.0,"width_mm":60.0,"thickness_mm":8.0},{"operation_id":"hole1","operation_type":"through_hole","x_mm":10.0,"y_mm":10.0,"diameter_mm":6.0},{"operation_id":"hole2","operation_type":"through_hole","x_mm":70.0,"y_mm":50.0,"diameter_mm":6.0},{"operation_id":"pocket","operation_type":"rectangular_pocket","x_mm":25.0,"y_mm":20.0,"length_mm":30.0,"width_mm":20.0,"depth_mm":3.0},{"operation_id":"slot","operation_type":"through_slot","center_x_mm":40.0,"center_y_mm":30.0,"length_mm":20.0,"width_mm":8.0,"orientation":"x"}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"}'
GOLDEN_PLATE_HASH = "sha256:8dab3415e8fe1e977738253c4e53bc2c6416f7d14fcf4c24ebdf7410d724187d"
GOLDEN_CANDIDATE_SPECIFICATION_V1_JSON = '{"schema_version":"component-specification@1","component_type":"motor","manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1","properties":[],"geometry_source":{"artifact_id":"ART-1","artifact_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111","source_identity":"vendor:geometry:1","format":"step"},"interfaces":["output"],"compatibility_declarations":["mount"],"specification_hash":"sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"}'
GOLDEN_CANDIDATE_SPECIFICATION_V1_HASH = "sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"
GOLDEN_CANDIDATE_SPECIFICATION_V2_JSON = '{"schema_version":"component-specification@2","component_type":"motor","manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1","properties":[],"geometry_source":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"interfaces":["output-shaft"],"compatibility_declarations":["mount"],"supplied_reference_frames":[{"frame_id":"output-frame","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","origin":{"fact_id":"frame-origin","expected_shape":"vector3","expected_unit":"mm","transform_role":"point_mm","evidence":[{"evidence_id":"evidence:frame-origin","shape":"vector3","value":[0.0,0.0,0.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:3566946fe5af38200a22d929da3799db3e07b3e2f96b5c9c285fdb84c7e1c9d0"}],"accepted_evidence_id":"evidence:frame-origin","fact_hash":"sha256:ad0748ce589e2c2cc0cc7c96fe2444f59ca4250ec0385cfc65dc9c2961e5384a"},"orientation":{"fact_id":"frame-orientation","expected_shape":"quaternion","expected_unit":"1","transform_role":"orientation","evidence":[{"evidence_id":"evidence:frame-orientation","shape":"quaternion","value":[1.0,0.0,0.0,0.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:76d7e7ee73a70aff82f70f9d4875167b9e98637106caeeab4bca48a7fdd91483"}],"accepted_evidence_id":"evidence:frame-orientation","fact_hash":"sha256:75a6d2fa2476d099523857be8a5293241967296651df1922759b8cb0785942a0"},"frame_hash":"sha256:88d94661e06ecab75ec6fed150362379a1fad1150d5b5366cac543ed8620da6d"}],"supplied_interface_definitions":[{"kind":"direct","interface_id":"output-shaft","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"shaft":{"interface_id":"output-shaft","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"reference_frame_id":"output-frame","axis_point":{"fact_id":"axis-point","expected_shape":"vector3","expected_unit":"mm","transform_role":"point_mm","evidence":[{"evidence_id":"evidence:axis-point","shape":"vector3","value":[1.0,2.0,3.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:2fbe3a85c09cbe478cc2730518268d1c6c3d5b431abe31895a14a9e4fa86cfd2"}],"accepted_evidence_id":"evidence:axis-point","fact_hash":"sha256:2d00592551b16a9a66e723cbdb1ad97b2e8d666edf13a290de7f49f916c0e6d7"},"axis_direction":{"fact_id":"axis-direction","expected_shape":"vector3","expected_unit":"1","transform_role":"direction_unit","evidence":[{"evidence_id":"evidence:axis-direction","shape":"vector3","value":[0.0,0.0,1.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:027dc963883b078f5e0ab4426225b3725b2ca2c0c6f9636e13a88f4fad4aa3a5"}],"accepted_evidence_id":"evidence:axis-direction","fact_hash":"sha256:e204bc5fa2b4cfe3b0ad7dedb04cd1c41841742c0a8980ca80141cd623dfd905"},"nominal_shaft_diameter":{"fact_id":"shaft-diameter","expected_shape":"scalar","expected_unit":"mm","transform_role":"length_mm","evidence":[{"evidence_id":"evidence:shaft-diameter","shape":"scalar","value":8.0,"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:440fc981aa9a6f4f9674844eb0ab065bb982a0bc82aab78fba5ccb7dcdace20e"}],"accepted_evidence_id":"evidence:shaft-diameter","fact_hash":"sha256:68bdad474ba77e42f2b6ffef02c9362e84be3042e1a5d806632902bf57b45d57"},"usable_axial_engagement_length":{"fact_id":"engagement","expected_shape":"scalar","expected_unit":"mm","transform_role":"length_mm","evidence":[{"evidence_id":"evidence:engagement","shape":"scalar","value":20.0,"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:986ffc905035449982e9ce5e3d831e6063c38ef0f4de89cda5321414048443a3"}],"accepted_evidence_id":"evidence:engagement","fact_hash":"sha256:3a5476fd2c8aa8933389ac40a306d69a538cba48ea0093c9e8ae247ae087a01c"},"shoulder_reference_plane":null,"shaft_profile":null,"d_flat_profile":null,"thread_designation":null,"interface_hash":"sha256:9b82c33c80d9fa901221dba4195554faf22ffea9bfcfdcada5d6b4e3df0b1c70"},"mounting_face":null,"derivation":null,"interface_hash":"sha256:eaa1262a4332c77a7bcb8b6fdf70c84435637cb8498955b97a0604f414fb3ea9"}],"geometry_derivation_transforms":[{"transform_id":"accepted-transform","source_geometry":{"artifact_id":"ART-TRANSFORM-SOURCE","artifact_hash":"sha256:4444444444444444444444444444444444444444444444444444444444444444","source_identity":"source:transform","format":"step","coordinate_system_id":"source-transform-coordinates@1","geometry_identity_hash":"sha256:dbdea28a39ad811f2ba6d62785b29ea99676fc4a55f930107fc7e28b24e90cc1"},"derived_geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"source_geometry_reference_hash":"sha256:dbdea28a39ad811f2ba6d62785b29ea99676fc4a55f930107fc7e28b24e90cc1","derived_geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","translation_fact":{"authority_role":"translation_mm","expected_shape":"vector3","expected_unit":"mm","evidence":[{"evidence_id":"translation-source","shape":"vector3","value":[0.0,0.0,0.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:9a5910c60923dc4b5c4293274ed9f0c0137a9b79d47ba9928648c712b3ea29f2"}],"accepted_evidence_id":"translation-source","authority_fact_hash":"sha256:fdb0787bfe07c94c182c1e5d32b838c7f06963a722b884a01d62ef77ebdaa9e2"},"rotation_fact":{"authority_role":"rotation","expected_shape":"quaternion","expected_unit":"1","evidence":[{"evidence_id":"rotation-source","shape":"quaternion","value":[1.0,0.0,0.0,0.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:2cb61d27df6d349f353f778c56b603e358723be6c0a127e363fff9b549dcb1bb"}],"accepted_evidence_id":"rotation-source","authority_fact_hash":"sha256:0f5e10c9090ebf8bd5f0c04de5e0ae6bad8cab6e8ab1de6073a37cc3e17921fb"},"uniform_scale_fact":{"authority_role":"uniform_scale","expected_shape":"scalar","expected_unit":"1","evidence":[{"evidence_id":"scale-source","shape":"scalar","value":1.25,"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:ec8e41ac815b8507dc2a81873ff084c8b962723bc954574b1d1bad1d0a7a006f"}],"accepted_evidence_id":"scale-source","authority_fact_hash":"sha256:29498fe49dc8b0e7352a6198e7d03693cdc6c00fd56111ac7cbe5b03fee6bc2d"},"unit_conversion":{"source_unit":"source-model-unit","derived_unit":"derived-model-unit","declaration":"explicit-model-unit-normalization@1"},"status":"accepted","transform_hash":"sha256:a93f0f6df9fa3e8c48c4105512c1ab17b006bd0d9c9dd52164aa656c89c192f3"}],"specification_hash":"sha256:aa818b7796814352c47cb67a84023b0d83b25b499dbe904846f25714fd77d52b"}'
GOLDEN_CANDIDATE_SPECIFICATION_V2_HASH = "sha256:aa818b7796814352c47cb67a84023b0d83b25b499dbe904846f25714fd77d52b"
GOLDEN_CANONICAL_SPECIFICATION_V1_JSON = '{"schema_version":"canonical-component-specification@1","component_type":"motor","manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1","properties":[],"geometry_source":{"artifact_id":"ART-1","artifact_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111","source_identity":"vendor:geometry:1","format":"step","reference_hash":"sha256:a3ec5de09c59fa48a2a331916ab5d060db2d03b4ff5dbe5e3b02185a3bb26f3a"},"interfaces":["output"],"compatibility_declarations":["mount"],"specification_hash":"sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"}'
GOLDEN_CANONICAL_SPECIFICATION_V1_HASH = "sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"
GOLDEN_CANONICAL_SPECIFICATION_V2_JSON = '{"schema_version":"canonical-component-specification@2","component_type":"motor","manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1","properties":[],"geometry_source":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","coordinate_system_id":"step-model-coordinates@1"},"interfaces":["output-shaft"],"compatibility_declarations":["mount"],"supplied_reference_frames":[{"frame_id":"output-frame","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","origin":{"fact_id":"frame-origin","expected_shape":"vector3","expected_unit":"mm","transform_role":"point_mm","evidence":[{"evidence_id":"evidence:frame-origin","shape":"vector3","value":[0.0,0.0,0.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:3566946fe5af38200a22d929da3799db3e07b3e2f96b5c9c285fdb84c7e1c9d0"}],"accepted_evidence_id":"evidence:frame-origin","fact_hash":"sha256:ad0748ce589e2c2cc0cc7c96fe2444f59ca4250ec0385cfc65dc9c2961e5384a"},"orientation":{"fact_id":"frame-orientation","expected_shape":"quaternion","expected_unit":"1","transform_role":"orientation","evidence":[{"evidence_id":"evidence:frame-orientation","shape":"quaternion","value":[1.0,0.0,0.0,0.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:76d7e7ee73a70aff82f70f9d4875167b9e98637106caeeab4bca48a7fdd91483"}],"accepted_evidence_id":"evidence:frame-orientation","fact_hash":"sha256:75a6d2fa2476d099523857be8a5293241967296651df1922759b8cb0785942a0"},"frame_hash":"sha256:88d94661e06ecab75ec6fed150362379a1fad1150d5b5366cac543ed8620da6d"}],"supplied_interface_definitions":[{"kind":"direct","interface_id":"output-shaft","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"shaft":{"interface_id":"output-shaft","geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"reference_frame_id":"output-frame","axis_point":{"fact_id":"axis-point","expected_shape":"vector3","expected_unit":"mm","transform_role":"point_mm","evidence":[{"evidence_id":"evidence:axis-point","shape":"vector3","value":[1.0,2.0,3.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:2fbe3a85c09cbe478cc2730518268d1c6c3d5b431abe31895a14a9e4fa86cfd2"}],"accepted_evidence_id":"evidence:axis-point","fact_hash":"sha256:2d00592551b16a9a66e723cbdb1ad97b2e8d666edf13a290de7f49f916c0e6d7"},"axis_direction":{"fact_id":"axis-direction","expected_shape":"vector3","expected_unit":"1","transform_role":"direction_unit","evidence":[{"evidence_id":"evidence:axis-direction","shape":"vector3","value":[0.0,0.0,1.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:027dc963883b078f5e0ab4426225b3725b2ca2c0c6f9636e13a88f4fad4aa3a5"}],"accepted_evidence_id":"evidence:axis-direction","fact_hash":"sha256:e204bc5fa2b4cfe3b0ad7dedb04cd1c41841742c0a8980ca80141cd623dfd905"},"nominal_shaft_diameter":{"fact_id":"shaft-diameter","expected_shape":"scalar","expected_unit":"mm","transform_role":"length_mm","evidence":[{"evidence_id":"evidence:shaft-diameter","shape":"scalar","value":8.0,"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:440fc981aa9a6f4f9674844eb0ab065bb982a0bc82aab78fba5ccb7dcdace20e"}],"accepted_evidence_id":"evidence:shaft-diameter","fact_hash":"sha256:68bdad474ba77e42f2b6ffef02c9362e84be3042e1a5d806632902bf57b45d57"},"usable_axial_engagement_length":{"fact_id":"engagement","expected_shape":"scalar","expected_unit":"mm","transform_role":"length_mm","evidence":[{"evidence_id":"evidence:engagement","shape":"scalar","value":20.0,"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:interface","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:986ffc905035449982e9ce5e3d831e6063c38ef0f4de89cda5321414048443a3"}],"accepted_evidence_id":"evidence:engagement","fact_hash":"sha256:3a5476fd2c8aa8933389ac40a306d69a538cba48ea0093c9e8ae247ae087a01c"},"shoulder_reference_plane":null,"shaft_profile":null,"d_flat_profile":null,"thread_designation":null,"interface_hash":"sha256:9b82c33c80d9fa901221dba4195554faf22ffea9bfcfdcada5d6b4e3df0b1c70"},"mounting_face":null,"derivation":null,"interface_hash":"sha256:eaa1262a4332c77a7bcb8b6fdf70c84435637cb8498955b97a0604f414fb3ea9"}],"geometry_derivation_transforms":[{"transform_id":"accepted-transform","source_geometry":{"artifact_id":"ART-TRANSFORM-SOURCE","artifact_hash":"sha256:4444444444444444444444444444444444444444444444444444444444444444","source_identity":"source:transform","format":"step","coordinate_system_id":"source-transform-coordinates@1","geometry_identity_hash":"sha256:dbdea28a39ad811f2ba6d62785b29ea99676fc4a55f930107fc7e28b24e90cc1"},"derived_geometry":{"artifact_id":"ART-SPEC","artifact_hash":"sha256:3333333333333333333333333333333333333333333333333333333333333333","source_identity":"source:geometry","format":"step","coordinate_system_id":"step-model-coordinates@1","geometry_identity_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983"},"source_geometry_reference_hash":"sha256:dbdea28a39ad811f2ba6d62785b29ea99676fc4a55f930107fc7e28b24e90cc1","derived_geometry_reference_hash":"sha256:940af7977854f1aec3f5883eed59dcdd7c44083026dfe5a5ff7d49089c8d5983","translation_fact":{"authority_role":"translation_mm","expected_shape":"vector3","expected_unit":"mm","evidence":[{"evidence_id":"translation-source","shape":"vector3","value":[0.0,0.0,0.0],"canonical_unit":"mm","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:9a5910c60923dc4b5c4293274ed9f0c0137a9b79d47ba9928648c712b3ea29f2"}],"accepted_evidence_id":"translation-source","authority_fact_hash":"sha256:fdb0787bfe07c94c182c1e5d32b838c7f06963a722b884a01d62ef77ebdaa9e2"},"rotation_fact":{"authority_role":"rotation","expected_shape":"quaternion","expected_unit":"1","evidence":[{"evidence_id":"rotation-source","shape":"quaternion","value":[1.0,0.0,0.0,0.0],"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:2cb61d27df6d349f353f778c56b603e358723be6c0a127e363fff9b549dcb1bb"}],"accepted_evidence_id":"rotation-source","authority_fact_hash":"sha256:0f5e10c9090ebf8bd5f0c04de5e0ae6bad8cab6e8ab1de6073a37cc3e17921fb"},"uniform_scale_fact":{"authority_role":"uniform_scale","expected_shape":"scalar","expected_unit":"1","evidence":[{"evidence_id":"scale-source","shape":"scalar","value":1.25,"canonical_unit":"1","availability":"available","authority":"manufacturer_datasheet","source_identity":"source:transform","applicability_context":null,"conversion_provenance":null,"evidence_origin":"source_document","source_document_identity":null,"geometry_reference_hash":null,"basis_evidence_ids":[],"evidence_hash":"sha256:ec8e41ac815b8507dc2a81873ff084c8b962723bc954574b1d1bad1d0a7a006f"}],"accepted_evidence_id":"scale-source","authority_fact_hash":"sha256:29498fe49dc8b0e7352a6198e7d03693cdc6c00fd56111ac7cbe5b03fee6bc2d"},"unit_conversion":{"source_unit":"source-model-unit","derived_unit":"derived-model-unit","declaration":"explicit-model-unit-normalization@1"},"status":"accepted","transform_hash":"sha256:a93f0f6df9fa3e8c48c4105512c1ab17b006bd0d9c9dd52164aa656c89c192f3"}],"specification_hash":"sha256:ab0dde3102b9e4224529d9cbe89fe3bb7553d292d8c5a43d09263c831a26193b"}'
GOLDEN_CANONICAL_SPECIFICATION_V2_HASH = "sha256:ab0dde3102b9e4224529d9cbe89fe3bb7553d292d8c5a43d09263c831a26193b"
GOLDEN_REQUEST_JSON = '{"schema_version":"candidate-cad-realization-request@1","candidate_hash":"sha256:1d73aba67527735eb14a8996c23c6264a54d1de1bf610d940e51b274b8930daf","source_binding":{"project_id":"PRJ-M12-4","source_revision":1,"source_state_hash":"sha256:20dab345e06a93a87b6f943156ad2347b00f1f513c54e3824db4a0d70f822f8e","consumed_authority":[{"path":"/id","value_hash":"sha256:03867a11332684e6c077a6e75c27d0a6ba001bcda28085ee554c05cd58638794","authority":"canonical_requirement"}]},"source_binding_hash":"sha256:f2123d22ce8a49df88bc46a963822153866f64d0013dfdcee8ac027cd8fce134","representation_policy_version":"candidate-cad-policy@1","compiler_identity":"candidate-cad-compiler","compiler_version":"1","candidate_instance_ids":["candidate-a"],"mappings":[{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:1d73aba67527735eb14a8996c23c6264a54d1de1bf610d940e51b274b8930daf","physical_instance_id":"candidate-a","cad_instance_id":"cad-mount","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:b39fd5298611a48585988edc36d9aa3c5c4fd391a70174fa9aa50fac7ed27cb6","source_geometry_identity":null,"geometry_definition_identities":["candidate:/mount-size"],"placement":{"x_mm":12.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"candidate_design_variable","input_identities":["candidate:/mount"],"derivation":"mount-frame@1","transform":{"x_mm":12.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:a8639a7c6031f04801a38b5944bd164b93f3be07d59b3a57411068a0d78a77cf"},"mapping_hash":"sha256:a3555590f35f2fbe6c64c6c88385e5a9a44126b61f7cfb4eb2fc6075dfc3eb9c"}],"design_variable_identities":["candidate:/mount-size"],"component_interface_identities":["candidate:/mount-interface"],"request_hash":"sha256:5a94b68d9fc117900a93baa0cdf3121fac04a7744a9ae8b89c4666c39ded30f7"}'
GOLDEN_REQUEST_HASH = "sha256:5a94b68d9fc117900a93baa0cdf3121fac04a7744a9ae8b89c4666c39ded30f7"
GOLDEN_REALIZATION_HASH = "sha256:c3819743156337ed51de098ff14e91421f56468006a4e12fbe942f8dee348cc7"
GOLDEN_CANDIDATE_HASH = "sha256:1d73aba67527735eb14a8996c23c6264a54d1de1bf610d940e51b274b8930daf"
GOLDEN_ORIGIN_JSON = '{"authority":"candidate_design_variable","input_identities":["candidate:/mount"],"derivation":"mount-frame@1","transform":{"x_mm":12.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:a8639a7c6031f04801a38b5944bd164b93f3be07d59b3a57411068a0d78a77cf"}'
GOLDEN_ORIGIN_HASH = "sha256:a8639a7c6031f04801a38b5944bd164b93f3be07d59b3a57411068a0d78a77cf"
GOLDEN_CANONICAL_MECHANISM_JSON = '{"schema_version":"canonical-physical-mechanism@1","id":"PM-1","name":"rotary output","component_specifications":[{"schema_version":"canonical-component-specification@1","component_type":"shaft","manufacturer":null,"part_number":null,"source_identity":"drawing:shaft@1","properties":[{"schema_version":"canonical-component-property@1","key":"diameter","availability":"available","normalized_value":12.0,"normalized_range":null,"canonical_unit":"mm","source_identity":"drawing:shaft@1","authority":"user_declared","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:db40abe2ffd59806d4bb272c98ab96aa0110a31c099cf58090d61d735862cd15"},{"schema_version":"canonical-component-property@1","key":"material","availability":"missing","normalized_value":null,"normalized_range":null,"canonical_unit":null,"source_identity":"drawing:shaft@1","authority":"user_declared","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:68f6aef4986209e43433922e075cefac0b18aa0104acfa4b27d9656f9053a5fb"},{"schema_version":"canonical-component-property@1","key":"dynamic_load_rating","availability":"not_applicable","normalized_value":null,"normalized_range":null,"canonical_unit":null,"source_identity":"drawing:shaft@1","authority":"user_declared","applicability_context":"shaft is not a bearing","conversion_provenance":null,"property_hash":"sha256:a4d6d8e15bdca9fd8d1fb31dc955148044904c5df3813bf4499a98ac4ce3b282"}],"geometry_source":{"artifact_id":"ART-shaft","artifact_hash":"sha256:4444444444444444444444444444444444444444444444444444444444444444","source_identity":"step:shaft@1","format":"step","reference_hash":"sha256:1bdb12f02072ce2901a85607325ee4acbfdc14950fa7e5c6b4fc2a9a538b45f3"},"interfaces":["input","output"],"compatibility_declarations":[],"specification_hash":"sha256:52ee947e9ca39b825e1a44a8c9067c7657142dfbd86e5fb8239ea653fa3e77ed"},{"schema_version":"canonical-component-specification@1","component_type":"mount","manufacturer":null,"part_number":null,"source_identity":"drawing:mount@1","properties":[],"geometry_source":null,"interfaces":["output-frame"],"compatibility_declarations":[],"specification_hash":"sha256:1b86cc58a3a4f6945c3b70a069ed3a80b4162aa5ddfa23c6a2e8ed068bf3e340"}],"components":[{"instance_id":"shaft-1","specification_hash":"sha256:52ee947e9ca39b825e1a44a8c9067c7657142dfbd86e5fb8239ea653fa3e77ed","role":"shaft","interfaces":["input","output"],"placement_id":"placement-shaft-1","component_hash":"sha256:aaef1fbae7c9c76e1adf6fd9241348e7d1c73c7c6571d4cebf294dbaf830bdeb"},{"instance_id":"mount-1","specification_hash":"sha256:1b86cc58a3a4f6945c3b70a069ed3a80b4162aa5ddfa23c6a2e8ed068bf3e340","role":"mount_or_support","interfaces":["output-frame"],"placement_id":null,"component_hash":"sha256:ba3920e460b81cb79d030b1fad39b77fe61a205a818409775e326254d31ac2ed"}],"accepted_design_choices":[{"key":"use_policy_default","value":false,"origin":"explicit_policy_assumption","provenance":"policy:mounting@1","source_identities":[],"choice_hash":"sha256:cc68aab7f406bbc686382ca3d386999070359a840a23f8552b303eb7191983dd"}],"placements":[{"placement_id":"placement-shaft-1","instance_id":"shaft-1","origin":"accepted_interface","input_identities":["interface:output@1"],"relation":"coaxial-output-axis@1","x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0],"placement_hash":"sha256:d8a4c0c38599631c49e504bc90b8af82a356798bbef0afdc2b0f597799cc4d31"}],"connections":[{"connection_id":"shaft-to-mount","kind":"fixed_attachment","from_instance_id":"shaft-1","from_interface_id":"output","to_instance_id":"mount-1","to_interface_id":"output-frame","meanings":["cad_placement_mating_intent"],"connection_hash":"sha256:7f4386e2693c24351bb05a14452fa4a2acd864de6aeb60015f51662ea3d8d405"}],"joint_bindings":[{"joint_id":"joint-output","expected_parent_instance_id":"mount-1","expected_child_instance_id":"shaft-1","axis_origin_x_mm":0.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"axis_frame_reference":"mount-1:output-frame","semantic_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111","semantic_version":"m10-joint-semantics@1","binding_hash":"sha256:09f6ba915f3e523e0cec7d91cc065230ed103e5ba7379928056748ebaed0edaf"}],"m10_obligations":[{"joint_semantic_key":"joint-output","angle_interval_deg":[0.0,360.0],"required_clearance_mm":1.0,"physical_pair_requirements":[{"requirement_key":"shaft-to-mount","first_instance_id":"shaft-1","first_interface_id":"output","second_instance_id":"mount-1","second_interface_id":"output-frame","requires_home_exact_check":false,"requirement_hash":"sha256:a49726b1858d4b8cf1a6a83b7a1e93c4445fafa4f73a940568e027eeb310a4bd"}],"fidelity_requirements":[["shaft-1","trusted_source_geometry"]],"required_home_check_semantics":["check-home-clearance"],"bounded_limitations":["internal bearing motion is outside scope"],"obligation_hash":"sha256:a9f518aa6b47d6723f01edd56661792bd01f7ba2538c99a4d5e84e2d64444289"}],"promotion_provenance":["promotion-input:selection@1"],"mechanism_hash":"sha256:3c3a038ddc367e1e6a0dfb292d86b096d48f0543abb14499633b0b054b647cda"}'
GOLDEN_CANONICAL_MECHANISM_HASH = "sha256:3c3a038ddc367e1e6a0dfb292d86b096d48f0543abb14499633b0b054b647cda"
GOLDEN_FIDELITY_VALUES = ("trusted_source_geometry", "declared_bounded_collision_representation")










def _plate_program() -> CadPartProgram:
    return CadPartProgram(
        part_id="M13GoldenPlate",
        operations=(
            BasePlateOperation(operation_id="base", length_mm=80, width_mm=60, thickness_mm=8),
            ThroughHoleOperation(operation_id="hole1", x_mm=10, y_mm=10, diameter_mm=6),
            ThroughHoleOperation(operation_id="hole2", x_mm=70, y_mm=50, diameter_mm=6),
            RectangularPocketOperation(
                operation_id="pocket", x_mm=25, y_mm=20, length_mm=30, width_mm=20, depth_mm=3
            ),
            ThroughSlotOperation(
                operation_id="slot", center_x_mm=40, center_y_mm=30, length_mm=20, width_mm=8, orientation="x"
            ),
        ),
    )


def _geometry_reference(*, artifact_id: str, artifact_hash: str, source_identity: str, coordinate_system_id=None):
    return GeometrySourceReference(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        source_identity=source_identity,
        coordinate_system_id=coordinate_system_id,
    )


def _interface_fact(fact_id, role, value, *, source_identity="source:interface"):
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (SuppliedInterfaceEvidenceShape.VECTOR3, "mm"),
        SuppliedInterfaceTransformRole.LENGTH_MM: (SuppliedInterfaceEvidenceShape.SCALAR, "mm"),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (SuppliedInterfaceEvidenceShape.VECTOR3, "1"),
        SuppliedInterfaceTransformRole.ORIENTATION: (SuppliedInterfaceEvidenceShape.QUATERNION, "1"),
    }[role]
    evidence = SuppliedInterfaceEvidence(
        evidence_id=f"evidence:{fact_id}",
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity=source_identity,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    return SuppliedInterfaceFact(
        fact_id=fact_id,
        expected_shape=shape,
        expected_unit=unit,
        transform_role=role,
        evidence=(evidence,),
        accepted_evidence_id=evidence.evidence_id,
    )


def _derivation_fact(role, shape, unit, value, evidence_id):
    evidence = SuppliedInterfaceEvidence(
        evidence_id=evidence_id,
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="source:transform",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    return GeometryDerivationAuthorityFact(
        authority_role=role,
        expected_shape=shape,
        expected_unit=unit,
        evidence=(evidence,),
        accepted_evidence_id=evidence_id,
    )


def _v2_reference() -> GeometrySourceReference:
    return _geometry_reference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
        coordinate_system_id="step-model-coordinates@1",
    )


def _v2_frame(reference: GeometrySourceReference) -> SuppliedComponentReferenceFrame:
    return SuppliedComponentReferenceFrame(
        frame_id="output-frame",
        geometry_reference_hash=reference.reference_hash,
        origin=_interface_fact("frame-origin", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)),
        orientation=_interface_fact(
            "frame-orientation", SuppliedInterfaceTransformRole.ORIENTATION, (1.0, 0.0, 0.0, 0.0)
        ),
    )


def _v2_interface(reference: GeometrySourceReference) -> SuppliedComponentInterfaceDefinition:
    geometry = GeometryArtifactIdentity.from_candidate(reference)
    geometry_hash = reference.reference_hash
    shaft = RotationalShaftInterface(
        interface_id="output-shaft",
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        reference_frame_id="output-frame",
        axis_point=_interface_fact("axis-point", SuppliedInterfaceTransformRole.POINT_MM, (1.0, 2.0, 3.0)),
        axis_direction=_interface_fact(
            "axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)
        ),
        nominal_shaft_diameter=_interface_fact(
            "shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.0
        ),
        usable_axial_engagement_length=_interface_fact(
            "engagement", SuppliedInterfaceTransformRole.LENGTH_MM, 20.0
        ),
    )
    return SuppliedComponentInterfaceDefinition(
        interface_id=shaft.interface_id,
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        shaft=shaft,
    )


def _v2_transform(reference: GeometrySourceReference) -> GeometryDerivationTransform:
    source_reference = _geometry_reference(
        artifact_id="ART-TRANSFORM-SOURCE",
        artifact_hash="sha256:" + "4" * 64,
        source_identity="source:transform",
        coordinate_system_id="source-transform-coordinates@1",
    )
    source = GeometryArtifactIdentity.from_candidate(source_reference)
    derived = GeometryArtifactIdentity.from_candidate(reference)
    return GeometryDerivationTransform(
        transform_id="accepted-transform",
        source_geometry=source,
        derived_geometry=derived,
        source_geometry_reference_hash=source_reference.reference_hash,
        derived_geometry_reference_hash=reference.reference_hash,
        translation_fact=_derivation_fact(
            GeometryDerivationAuthorityRole.TRANSLATION_MM,
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "mm",
            (0.0, 0.0, 0.0),
            "translation-source",
        ),
        rotation_fact=_derivation_fact(
            GeometryDerivationAuthorityRole.ROTATION,
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "1",
            (1.0, 0.0, 0.0, 0.0),
            "rotation-source",
        ),
        uniform_scale_fact=_derivation_fact(
            GeometryDerivationAuthorityRole.UNIFORM_SCALE,
            SuppliedInterfaceEvidenceShape.SCALAR,
            "1",
            1.25,
            "scale-source",
        ),
        unit_conversion=GeometryDerivationUnitConversion(
            source_unit="source-model-unit",
            derived_unit="derived-model-unit",
            declaration="explicit-model-unit-normalization@1",
        ),
        status=GeometryDerivationStatus.ACCEPTED,
    )


def _candidate_specification_v1() -> ComponentSpecificationSnapshot:
    reference = _geometry_reference(
        artifact_id="ART-1",
        artifact_hash="sha256:" + "1" * 64,
        source_identity="vendor:geometry:1",
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@1",
        component_type="motor",
        manufacturer="Acme",
        part_number="M-1",
        source_identity="vendor:acme:M-1",
        geometry_source=reference,
        interfaces=("output",),
        compatibility_declarations=("mount",),
    )


def _candidate_specification_v2() -> ComponentSpecificationSnapshot:
    reference = _v2_reference()
    definition = _v2_interface(reference)
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        manufacturer="Acme",
        part_number="M-1",
        source_identity="vendor:acme:M-1",
        geometry_source=reference,
        interfaces=("output-shaft",),
        compatibility_declarations=("mount",),
        supplied_reference_frames=(_v2_frame(reference),),
        supplied_interface_definitions=(definition,),
        geometry_derivation_transforms=(_v2_transform(reference),),
    )


def _canonical_specification(specification: ComponentSpecificationSnapshot) -> CanonicalComponentSpecification:
    return CanonicalComponentSpecification(
        schema_version=f"canonical-{specification.schema_version}",
        component_type=specification.component_type,
        manufacturer=specification.manufacturer,
        part_number=specification.part_number,
        source_identity=specification.source_identity,
        geometry_source=(
            None
            if specification.geometry_source is None
            else CanonicalGeometrySourceReference.model_validate(
                specification.geometry_source.model_dump(mode="json")
            )
        ),
        properties=tuple(
            CanonicalComponentProperty.model_validate(item.model_dump(mode="json"))
            for item in specification.properties
        ),
        interfaces=specification.interfaces,
        compatibility_declarations=specification.compatibility_declarations,
        supplied_reference_frames=specification.supplied_reference_frames,
        supplied_interface_definitions=specification.supplied_interface_definitions,
        geometry_derivation_transforms=specification.geometry_derivation_transforms,
    )


def _candidate() -> MechanicalDesignCandidate:
    state = DesignState(
        id="DES-M12-4",
        revision=1,
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )
    source = CandidateSourceBinding(
        project_id="PRJ-M12-4",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    specification = ComponentSpecificationSnapshot(
        component_type="fixture",
        source_identity="local:fixture@1",
        interfaces=("mount",),
    )
    instance = PhysicalComponentInstance(
        instance_id="candidate-a",
        specification_hash=specification.specification_hash,
        role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
        interfaces=("mount",),
    )
    realization = PhysicalMechanismRealization(components=(instance,))
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    return MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=(specification,),
        realization=realization,
        generator_identity="test-generator",
        generator_version="1",
    )


def _origin() -> CandidatePlacementOrigin:
    return CandidatePlacementOrigin(
        authority="candidate_design_variable",
        input_identities=("candidate:/mount",),
        derivation="mount-frame@1",
        transform=CadRigidTransform(x_mm=12.0),
    )


def _mapping(candidate: MechanicalDesignCandidate) -> CandidateCadInstanceMapping:
    return CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="candidate-a",
        cad_instance_id="cad-mount",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=cad_program_hash(acceptance_program()),
        geometry_definition_identities=("candidate:/mount-size",),
        placement=CadRigidTransform(x_mm=12.0),
        placement_origin=_origin(),
    )


def _request(candidate: MechanicalDesignCandidate, mapping: CandidateCadInstanceMapping) -> CandidateCadRealizationRequest:
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("candidate-a",),
        mappings=(mapping,),
        design_variable_identities=("candidate:/mount-size",),
        component_interface_identities=("candidate:/mount-interface",),
    )


def _realization(candidate: MechanicalDesignCandidate, request: CandidateCadRealizationRequest) -> CandidateCadRealization:
    assembly = CadAssemblyProgram(
        assembly_id="candidate-assembly",
        parts=(acceptance_program(),),
        instances=(
            CadComponentInstance(
                instance_id="cad-mount",
                part_id="M7A2ABracket",
                placement=CadRigidTransform(x_mm=12.0),
            ),
        ),
    )
    return CandidateCadRealization(
        candidate_hash=candidate.candidate_hash,
        request_hash=request.request_hash,
        mappings=request.mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="transient-freecad@1",
    )


def _canonical_mechanism() -> CanonicalPhysicalMechanism:
    specification = CanonicalComponentSpecification(
        component_type="shaft",
        source_identity="drawing:shaft@1",
        properties=(
            CanonicalComponentProperty(
                key="diameter",
                availability=CanonicalComponentPropertyAvailability.AVAILABLE,
                normalized_value=12.0,
                canonical_unit="mm",
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
            ),
            CanonicalComponentProperty(
                key="material",
                availability=CanonicalComponentPropertyAvailability.MISSING,
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
            ),
            CanonicalComponentProperty(
                key="dynamic_load_rating",
                availability=CanonicalComponentPropertyAvailability.NOT_APPLICABLE,
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
                applicability_context="shaft is not a bearing",
            ),
        ),
        interfaces=("input", "output"),
        geometry_source=CanonicalGeometrySourceReference(
            artifact_id="ART-shaft",
            artifact_hash="sha256:" + "4" * 64,
            source_identity="step:shaft@1",
        ),
    )
    mount_specification = CanonicalComponentSpecification(
        component_type="mount",
        source_identity="drawing:mount@1",
        interfaces=("output-frame",),
    )
    return CanonicalPhysicalMechanism(
        id="PM-1",
        name="rotary output",
        component_specifications=(specification, mount_specification),
        components=(
            CanonicalPhysicalComponent(
                instance_id="shaft-1",
                specification_hash=specification.specification_hash,
                role="shaft",
                interfaces=("input", "output"),
                placement_id="placement-shaft-1",
            ),
            CanonicalPhysicalComponent(
                instance_id="mount-1",
                specification_hash=mount_specification.specification_hash,
                role="mount_or_support",
                interfaces=("output-frame",),
            ),
        ),
        accepted_design_choices=(
            CanonicalAcceptedDesignChoice(
                key="use_policy_default",
                value=False,
                origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
                provenance="policy:mounting@1",
            ),
        ),
        placements=(
            CanonicalPlacement(
                placement_id="placement-shaft-1",
                instance_id="shaft-1",
                origin=CanonicalPlacementOrigin.ACCEPTED_INTERFACE,
                input_identities=("interface:output@1",),
                relation="coaxial-output-axis@1",
            ),
        ),
        connections=(
            CanonicalMechanicalConnection(
                connection_id="shaft-to-mount",
                kind=CanonicalMechanicalConnectionKind.FIXED_ATTACHMENT,
                from_instance_id="shaft-1",
                from_interface_id="output",
                to_instance_id="mount-1",
                to_interface_id="output-frame",
                meanings=(CanonicalConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,),
            ),
        ),
        joint_bindings=(
            CanonicalJointPhysicalBinding(
                joint_id="joint-output",
                expected_parent_instance_id="mount-1",
                expected_child_instance_id="shaft-1",
                axis_origin_x_mm=0.0,
                axis_origin_y_mm=0.0,
                axis_origin_z_mm=0.0,
                axis_direction_x=0.0,
                axis_direction_y=0.0,
                axis_direction_z=1.0,
                axis_frame_reference="mount-1:output-frame",
                semantic_hash="sha256:" + "1" * 64,
                semantic_version="m10-joint-semantics@1",
            ),
        ),
        m10_obligations=(
            CanonicalM10VerificationObligation(
                joint_semantic_key="joint-output",
                angle_interval_deg=(0.0, 360.0),
                required_clearance_mm=1.0,
                physical_pair_requirements=(
                    CanonicalPhysicalPairRequirement(
                        requirement_key="shaft-to-mount",
                        first_instance_id="shaft-1",
                        first_interface_id="output",
                        second_instance_id="mount-1",
                        second_interface_id="output-frame",
                    ),
                ),
                fidelity_requirements=(
                    ("shaft-1", CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
                ),
                required_home_check_semantics=("check-home-clearance",),
                bounded_limitations=("internal bearing motion is outside scope",),
            ),
        ),
        promotion_provenance=("promotion-input:selection@1",),
    )


def _assert_literal_json(record, literal: str) -> None:
    assert type(record).model_validate_json(literal) == record
    assert record.model_dump(mode="json") == json.loads(literal)
    assert record.model_dump_json() == literal


def test_plate_program_json_and_hash_are_pre_m13_2_literals():
    program = _plate_program()
    _assert_literal_json(program, GOLDEN_PLATE_JSON)
    assert cad_program_hash(program) == GOLDEN_PLATE_HASH


def test_candidate_specification_json_and_hashes_are_pre_m13_2_literals():
    v1 = _candidate_specification_v1()
    _assert_literal_json(v1, GOLDEN_CANDIDATE_SPECIFICATION_V1_JSON)
    assert v1.specification_hash == GOLDEN_CANDIDATE_SPECIFICATION_V1_HASH

    v2 = _candidate_specification_v2()
    _assert_literal_json(v2, GOLDEN_CANDIDATE_SPECIFICATION_V2_JSON)
    assert v2.specification_hash == GOLDEN_CANDIDATE_SPECIFICATION_V2_HASH


def test_canonical_specification_json_and_hashes_are_pre_m13_2_literals():
    v1 = _canonical_specification(_candidate_specification_v1())
    _assert_literal_json(v1, GOLDEN_CANONICAL_SPECIFICATION_V1_JSON)
    assert v1.specification_hash == GOLDEN_CANONICAL_SPECIFICATION_V1_HASH

    v2 = _canonical_specification(_candidate_specification_v2())
    _assert_literal_json(v2, GOLDEN_CANONICAL_SPECIFICATION_V2_JSON)
    assert v2.specification_hash == GOLDEN_CANONICAL_SPECIFICATION_V2_HASH


def test_candidate_cad_request_json_and_hashes_are_pre_m13_2_literals():
    candidate = _candidate()
    request = _request(candidate, _mapping(candidate))
    _assert_literal_json(request, GOLDEN_REQUEST_JSON)
    assert request.request_hash == GOLDEN_REQUEST_HASH


def test_candidate_realization_and_candidate_hashes_are_pre_m13_2_literals():
    candidate = _candidate()
    request = _request(candidate, _mapping(candidate))
    realization = _realization(candidate, request)
    assert candidate.candidate_hash == GOLDEN_CANDIDATE_HASH
    assert realization.realization_hash == GOLDEN_REALIZATION_HASH


def test_candidate_placement_origin_json_and_hash_are_pre_m13_2_literals():
    origin = _origin()
    _assert_literal_json(origin, GOLDEN_ORIGIN_JSON)
    assert origin.origin_hash == GOLDEN_ORIGIN_HASH


def test_canonical_mechanism_json_and_hash_are_pre_m13_2_literals():
    mechanism = _canonical_mechanism()
    _assert_literal_json(mechanism, GOLDEN_CANONICAL_MECHANISM_JSON)
    assert mechanism.mechanism_hash == GOLDEN_CANONICAL_MECHANISM_HASH


def test_mapping_schema_selection_is_schema_based():
    compiler = object.__new__(CandidatePromotionCompiler)
    v1 = _candidate_specification_v1()
    v2 = _candidate_specification_v2()
    compiler._verify_policy(CandidatePromotionPolicy(), SimpleNamespace(component_specifications=(v1, v1)))
    compiler._verify_policy(
        CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        SimpleNamespace(component_specifications=(v1, v2)),
    )

    with pytest.raises(ValueError, match="mapping schema"):
        compiler._verify_policy(
            CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
            SimpleNamespace(component_specifications=(v1,)),
        )
    with pytest.raises(ValueError, match="mapping schema"):
        compiler._verify_policy(
            CandidatePromotionPolicy(),
            SimpleNamespace(component_specifications=(v2,)),
        )


def test_fidelity_values_are_stable():
    expected = [
        "trusted_source_geometry",
        "declared_bounded_collision_representation",
        "exact_generated_geometry",
    ]
    assert [member.value for member in CandidateGeometryFidelity] == expected
    assert [member.value for member in CanonicalGeometryFidelity] == expected
