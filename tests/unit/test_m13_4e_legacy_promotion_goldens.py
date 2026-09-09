from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import StrictInt, StrictStr
from pydantic_core import PydanticUndefined

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import (
    CandidateCanonicalInstanceMapping,
    CandidateEvaluationPolicy,
    CandidatePromotionApplicationResult,
    CandidatePromotionCompilation,
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidateSelection,
    PrePromotionM10ScopeProjection,
    PromotionApplicationStatus,
    PromotionDecisionInputReference,
    PromotionManifestService,
    PromotionPhysicalPairRequirement,
    PromotionValueClassification,
)
from mechcad_harness.candidates.promotion_artifacts import (
    CandidatePromotionResultManifest,
    SelectedCandidateDecisionManifest,
)
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
    CanonicalPhysicalMechanism,
    DesignState,
)

from test_m12_candidate_evaluation import (
    _bound_m10_inputs,
    _evaluation_candidate,
    _evaluation_service,
    _m12_result,
)
from test_m12_promotion_apply import _compiled
from test_m12_promotion_compiler import _classifications


HASH = "sha256:" + "a" * 64
LEGACY_REQUEST_JSON = r'''{"schema_version":"candidate-promotion-request@1","project_id":"PRJ-M12","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","candidate":{"schema_version":"mechanical-design-candidate@1","source_binding":{"project_id":"PRJ-M12","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","consumed_authority":[{"path":"/id","value_hash":"sha256:02127c03d00d9598ff58eaee65151b742d7432c838784f7928856a45ef9fc51e","authority":"canonical_requirement"}]},"synthesis_request_hash":"sha256:6a2640d7e39e51fd0a98d15079456dc0765c203810fa8fac0663dfb9c41baa95","synthesis_policy_hash":"sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849","component_specifications":[{"schema_version":"component-specification@1","component_type":"motor","manufacturer":"Example Motion","part_number":"MTR-24-100","source_identity":"datasheet:example:MTR-24-100@1","properties":[{"schema_version":"component-property@1","key":"rated_voltage","availability":"available","normalized_value":24.0,"normalized_range":null,"canonical_unit":"V","source_identity":"datasheet:example:MTR-24-100@1","authority":"manufacturer_datasheet","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:38afd250a47fdb597bb468c98a821fc02af468889a1dbce6ec6338dbfa7cbf73"},{"schema_version":"component-property@1","key":"continuous_torque","availability":"missing","normalized_value":null,"normalized_range":null,"canonical_unit":null,"source_identity":"datasheet:example:MTR-24-100@1","authority":"manufacturer_datasheet","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:df17ff318a2b2fae8b061654b33239a52346c54bc03c8eca35d7c02dec90ecea"}],"geometry_source":null,"interfaces":["output-shaft","mount-face"],"compatibility_declarations":[],"specification_hash":"sha256:0b1620d3e2bb2a02fcaf19a9d827b282df7f26e2095a8db32dbb9b1bbce39f48"},{"schema_version":"component-specification@1","component_type":"shaft","manufacturer":null,"part_number":null,"source_identity":"custom:shaft@1","properties":[{"schema_version":"component-property@1","key":"diameter","availability":"available","normalized_value":12.0,"normalized_range":null,"canonical_unit":"mm","source_identity":"drawing:shaft@1","authority":"user_declared","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:31f8b346a479212ba79ec277ed154afd1b7d7e23e7eb83d281baef8043af170c"}],"geometry_source":null,"interfaces":["motor-side","hub-side","journal-a","journal-b"],"compatibility_declarations":[],"specification_hash":"sha256:e7f4e9547c8196c0a593af1723fc927bb9f92414b4bdd048b8ca23d5db8ea43a"},{"schema_version":"component-specification@1","component_type":"bearing","manufacturer":null,"part_number":null,"source_identity":"catalog:bearing@1","properties":[{"schema_version":"component-property@1","key":"dynamic_load_rating","availability":"not_applicable","normalized_value":null,"normalized_range":null,"canonical_unit":null,"source_identity":"catalog:bearing@1","authority":"distributor_listing","applicability_context":null,"conversion_provenance":null,"property_hash":"sha256:c12c3172aedb26cb7368ae6b80907510024051f32802ed79ef092268c5b30feb"}],"geometry_source":null,"interfaces":["bore","housing"],"compatibility_declarations":[],"specification_hash":"sha256:8bfc0217cbc728ab4af1181e780be519d021630561c22d3d9758a167bc28f247"},{"schema_version":"component-specification@1","component_type":"hub","manufacturer":null,"part_number":null,"source_identity":"custom:hub@1","properties":[],"geometry_source":null,"interfaces":["shaft","body"],"compatibility_declarations":[],"specification_hash":"sha256:4ccd604739123b0d67c6180d3fc4f8734ed00303c7d8cb90c4c164ec88e8ccb5"},{"schema_version":"component-specification@1","component_type":"mount","manufacturer":null,"part_number":null,"source_identity":"custom:mount@1","properties":[],"geometry_source":null,"interfaces":["motor","frame"],"compatibility_declarations":[],"specification_hash":"sha256:a2e714ec177a9b4d16cb983eead8247e2cce4a0ecb9f4cf27afa52a7d8e1e0b2"},{"schema_version":"component-specification@1","component_type":"driven-body","manufacturer":null,"part_number":null,"source_identity":"custom:body@1","properties":[],"geometry_source":null,"interfaces":["hub","payload"],"compatibility_declarations":[],"specification_hash":"sha256:906ae57c3d9e198c660a94a0afa6c90302837c9baac1eb514cc661b64b3552f6"}],"realization":{"schema_version":"physical-mechanism-realization@1","components":[{"instance_id":"motor","specification_hash":"sha256:0b1620d3e2bb2a02fcaf19a9d827b282df7f26e2095a8db32dbb9b1bbce39f48","role":"actuator","interfaces":["output-shaft","mount-face"]},{"instance_id":"driver","specification_hash":"sha256:0b1620d3e2bb2a02fcaf19a9d827b282df7f26e2095a8db32dbb9b1bbce39f48","role":"transmission","interfaces":["output-shaft","mount-face"]},{"instance_id":"shaft","specification_hash":"sha256:e7f4e9547c8196c0a593af1723fc927bb9f92414b4bdd048b8ca23d5db8ea43a","role":"shaft","interfaces":["motor-side","hub-side","journal-a","journal-b"]},{"instance_id":"bearing","specification_hash":"sha256:8bfc0217cbc728ab4af1181e780be519d021630561c22d3d9758a167bc28f247","role":"bearing","interfaces":["bore","housing"]},{"instance_id":"hub","specification_hash":"sha256:4ccd604739123b0d67c6180d3fc4f8734ed00303c7d8cb90c4c164ec88e8ccb5","role":"hub_or_coupling","interfaces":["shaft","body"]},{"instance_id":"mount","specification_hash":"sha256:a2e714ec177a9b4d16cb983eead8247e2cce4a0ecb9f4cf27afa52a7d8e1e0b2","role":"mount_or_support","interfaces":["motor","frame"]},{"instance_id":"body","specification_hash":"sha256:906ae57c3d9e198c660a94a0afa6c90302837c9baac1eb514cc661b64b3552f6","role":"driven_body","interfaces":["hub","payload"]}],"connections":[],"joint_bindings":[],"realization_hash":"sha256:63ee1c357bab9adbe4f57d280c2c029c3bede3c7098f40222175fdd4b1b6e7a4"},"design_variables":[],"unresolved_items":[],"generator_identity":"fixture-generator","generator_version":"1","parent_candidate_hash":null,"derivation_kind":null,"generation_ordinal":null,"candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57"},"synthesis_request":{"schema_version":"candidate-synthesis-request@1","source_binding":{"project_id":"PRJ-M12","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","consumed_authority":[{"path":"/id","value_hash":"sha256:02127c03d00d9598ff58eaee65151b742d7432c838784f7928856a45ef9fc51e","authority":"canonical_requirement"}]},"requested_joint_ids":[],"required_joint_ids":[],"out_of_scope_joint_ids":[],"requested_evaluation_categories":[],"request_hash":"sha256:6a2640d7e39e51fd0a98d15079456dc0765c203810fa8fac0663dfb9c41baa95"},"synthesis_policy":{"schema_version":"candidate-synthesis-policy@1","entries":[["allow-direct-drive","direct_drive","hard_admissibility"],["preferred-voltage","24 V","preference"]],"policy_hash":"sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849"},"m12_3_result":{"schema_version":"revolute-drive-admissibility@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","source_binding_hash":"sha256:364bdd17e0198e5a68fa5e289ba04fd47021d6163e9d88bd38076845ec62991a","synthesis_request_hash":"sha256:6a2640d7e39e51fd0a98d15079456dc0765c203810fa8fac0663dfb9c41baa95","synthesis_policy_hash":"sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849","requirements_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","design_variables":[],"consumed_property_bindings":[],"calculation_id":"m12-3.revolute-drive","calculation_version":"1","checks":[{"check_id":"required-drive","status":"satisfied","reason":null,"consumed_property_bindings":[],"consumed_requirement_paths":[],"calculation_id":"m12-3.revolute-drive","calculation_version":"1"}],"status":"admissible","result_hash":"sha256:9d00c53aa470715e048ee1e5b68f4fda04cf745fefc408899ac78f6681b56132"},"evaluation":{"schema_version":"candidate-evaluation@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","source_binding_hash":"sha256:364bdd17e0198e5a68fa5e289ba04fd47021d6163e9d88bd38076845ec62991a","synthesis_request_hash":"sha256:6a2640d7e39e51fd0a98d15079456dc0765c203810fa8fac0663dfb9c41baa95","synthesis_policy_hash":"sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849","policy":{"schema_version":"candidate-evaluation-policy@1","required_check_keys":["m12_3_admissibility","candidate_cad_realization","m10_continuous_clearance"],"policy_version":"candidate-evaluation@1","policy_hash":"sha256:4b807af3b07ede83f7de7c8a249de3a3550b12c27ae96da9856ad2ab39ebf3f8"},"policy_hash":"sha256:4b807af3b07ede83f7de7c8a249de3a3550b12c27ae96da9856ad2ab39ebf3f8","evaluation_scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","required_check_keys":["m12_3_admissibility","candidate_cad_realization","m10_continuous_clearance"],"m12_3_result":{"schema_version":"revolute-drive-admissibility@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","source_binding_hash":"sha256:364bdd17e0198e5a68fa5e289ba04fd47021d6163e9d88bd38076845ec62991a","synthesis_request_hash":"sha256:6a2640d7e39e51fd0a98d15079456dc0765c203810fa8fac0663dfb9c41baa95","synthesis_policy_hash":"sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849","requirements_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","design_variables":[],"consumed_property_bindings":[],"calculation_id":"m12-3.revolute-drive","calculation_version":"1","checks":[{"check_id":"required-drive","status":"satisfied","reason":null,"consumed_property_bindings":[],"consumed_requirement_paths":[],"calculation_id":"m12-3.revolute-drive","calculation_version":"1"}],"status":"admissible","result_hash":"sha256:9d00c53aa470715e048ee1e5b68f4fda04cf745fefc408899ac78f6681b56132"},"m12_3_result_hash":"sha256:9d00c53aa470715e048ee1e5b68f4fda04cf745fefc408899ac78f6681b56132","cad_stage_outcome":{"schema_version":"candidate-cad-stage-outcome@1","status":"success","realization":{"schema_version":"candidate-cad-realization@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","request_hash":"sha256:1b399b6af693ec8fdc21cd1a48ddaea3e6c471d4be18c787fef7fd5c1e1a0a11","mappings":[{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"motor","cad_instance_id":"cad-motor","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:9e290cb0499c01f49d9c1bf29f4794735b1a49be0fedfefeaf42d549b8553969","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:motor"],"placement":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:motor"],"derivation":"fixture-placement@1","transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:3bc8804879e5592b3e19abf8d1ba5bb7f652ba6b075ef699889287ae0f70ec74"},"mapping_hash":"sha256:44b1bfd77d5dbede434b4dd55baea2b5e58e3ea92198df56c7c7aba0c8939ac6"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"driver","cad_instance_id":"cad-driver","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:e8999308d72c83110721890097fa33d6024a49c556211db5f8a4b66c6abbd209","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:driver"],"placement":{"x_mm":20.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:driver"],"derivation":"fixture-placement@1","transform":{"x_mm":20.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:c3aaaa67e6c3a7f87878ddff488391ba953f6fee10bb52970cd6afd00c34e338"},"mapping_hash":"sha256:caed666bc92f436f653b33b6202275a6910d99e16b91e2498482dc083595951c"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"shaft","cad_instance_id":"cad-shaft","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:393d35ec55b81995f0da6f157c6134518640d5ce266b591246047b89e09eac5f","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:shaft"],"placement":{"x_mm":40.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:shaft"],"derivation":"fixture-placement@1","transform":{"x_mm":40.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:89ce11f70b6cc393c405c1a9bc9b71a7762783d48add67c92890f734e37c481c"},"mapping_hash":"sha256:779c67f6637f44004039a3c55b63b6ffef15ae707a9231e3333a57b587e581c4"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"bearing","cad_instance_id":"cad-bearing","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:e4e1d25b2a0a872b75ac99afc0ff731203845a9902d4c4bb66651f711d9f54f1","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:bearing"],"placement":{"x_mm":60.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:bearing"],"derivation":"fixture-placement@1","transform":{"x_mm":60.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:7b8f7aa4d0abb5ab12e06ba736112db0f955393eed2e6ac8b11e8eb09a2f5b98"},"mapping_hash":"sha256:5562e03010bbec4af67b56806786e30a1efc26f879ebb22952184fcc68e3059c"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"hub","cad_instance_id":"cad-hub","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:8686ea5542aaa9b306a6fe9c432c6197d9a6e6d9f57f194e335e50845fc9dff1","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:hub"],"placement":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:hub"],"derivation":"fixture-placement@1","transform":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:9c38693106cecb00b0ab78724aec1b999af0da12de17e7d8eeba92113ddfceeb"},"mapping_hash":"sha256:e0322d19e5bebfd1c96d6c57c7f95209113b5ff5bfe30ce1693f07b87e88a455"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"mount","cad_instance_id":"cad-mount","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:539a8528522a9d1d782ba5aa343cbff9002de3cad698cc02fc304153de235c61","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:mount"],"placement":{"x_mm":100.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:mount"],"derivation":"fixture-placement@1","transform":{"x_mm":100.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:6316fe60555911e5a1b7df5fbc4a3dfba2a1365a6d1384aa295c87bcf30313ef"},"mapping_hash":"sha256:a2b9f19fef111cf19fdba1f2a963e8fbd3fa4851f706466d46beba470d0ca486"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"body","cad_instance_id":"cad-body","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:a90ac6fdeece9efa7854a9253304a9dff861eca4217252b6623ac6b324f0927b","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:body"],"placement":{"x_mm":120.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:body"],"derivation":"fixture-placement@1","transform":{"x_mm":120.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:b7a9848c1e4482601e347ecac53ccda3caf6ef814079e0403d96591bb697146d"},"mapping_hash":"sha256:e4d493d07d012a9aaa1b2172b229f51d28551c32c7e85175d1bffece37709766"}],"assembly":{"assembly_id":"candidate-assembly","parts":[{"part_id":"part-motor","operations":[{"operation_id":"base-motor","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-driver","operations":[{"operation_id":"base-driver","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-shaft","operations":[{"operation_id":"base-shaft","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-bearing","operations":[{"operation_id":"base-bearing","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-hub","operations":[{"operation_id":"base-hub","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-mount","operations":[{"operation_id":"base-mount","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"},{"part_id":"part-body","operations":[{"operation_id":"base-body","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"}],"imported_components":[],"instances":[{"instance_id":"cad-motor","part_id":"part-motor","placement":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-driver","part_id":"part-driver","placement":{"x_mm":20.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-shaft","part_id":"part-shaft","placement":{"x_mm":40.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-bearing","part_id":"part-bearing","placement":{"x_mm":60.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-hub","part_id":"part-hub","placement":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-mount","part_id":"part-mount","placement":{"x_mm":100.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"cad-body","part_id":"part-body","placement":{"x_mm":120.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}}]},"assembly_hash":"sha256:77e7c68ffce02969a3e930e0de4eb122f345a667621d74e214ffa36488b4807e","representation_identities":["sha256:9e290cb0499c01f49d9c1bf29f4794735b1a49be0fedfefeaf42d549b8553969","sha256:e8999308d72c83110721890097fa33d6024a49c556211db5f8a4b66c6abbd209","sha256:393d35ec55b81995f0da6f157c6134518640d5ce266b591246047b89e09eac5f","sha256:e4e1d25b2a0a872b75ac99afc0ff731203845a9902d4c4bb66651f711d9f54f1","sha256:8686ea5542aaa9b306a6fe9c432c6197d9a6e6d9f57f194e335e50845fc9dff1","sha256:539a8528522a9d1d782ba5aa343cbff9002de3cad698cc02fc304153de235c61","sha256:a90ac6fdeece9efa7854a9253304a9dff861eca4217252b6623ac6b324f0927b"],"verified_source_content_identities":[],"compiler_identity":"fixture","compiler_version":"1","provider_identity":"fixture","realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157"},"realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157","reasons":[],"outcome_hash":"sha256:74da875c7f5dbe053050689e79f483532adcede9d2a832ba95178e517bc00098"},"cad_stage_outcome_hash":"sha256:74da875c7f5dbe053050689e79f483532adcede9d2a832ba95178e517bc00098","m10_stage_outcome":{"schema_version":"candidate-m10-stage-outcome@1","status":"success","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","cad_realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157","binding_hash":"sha256:16b399eb7cf9cf3e3d7ecbc3d9cdbe14770a3ed5b9076fb1ba091d00dc825a97","scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","evaluation_request_hash":"sha256:e2bf8f52648dec3123729f1a53d20cfd9d5176148a786b3ab14f7a7677e9c422","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","pair_proofs":[{"schema_version":"candidate-m10-pair-proof@1","pair":["cad-hub","cad-mount"],"moving_instance_id":"cad-hub","stationary_instance_id":"cad-mount","request":{"source_assembly_id":"candidate-assembly-m10-pair-bdd639d033bdbaf92650","source_assembly_hash":"sha256:fc693c50434c7595f2af6dc2a7606872b2c12ea06615101dc67a17106e1d325c","axis":{"origin_x_mm":120.0,"origin_y_mm":0.0,"origin_z_mm":0.0,"direction_x":0.0,"direction_y":0.0,"direction_z":1.0,"frame_id":"joint:output-joint"},"start_angle_deg":-45.0,"end_angle_deg":45.0,"moving_instance_ids":["cad-hub"],"stationary_instance_ids":["cad-mount"],"required_clearance_mm":1.0,"volume_tolerance_mm3":1e-9,"distance_tolerance_mm":1e-7,"proof_guard_mm":1e-6,"max_depth":16,"minimum_interval_deg":1e-6,"max_exact_evaluations":4096,"sweep_version":"rigid-body-collision-sweep@1.0","request_hash":"sha256:6a78cfbc626da819406d23850b5420a2da1746fd7190cf284e88c603917f5b1b"},"result":{"request_hash":"sha256:6a78cfbc626da819406d23850b5420a2da1746fd7190cf284e88c603917f5b1b","source_assembly_hash":"sha256:fc693c50434c7595f2af6dc2a7606872b2c12ea06615101dc67a17106e1d325c","proof_algorithm_version":"conservative-single-axis-clearance-proof@1.0","axis":{"origin_x_mm":120.0,"origin_y_mm":0.0,"origin_z_mm":0.0,"direction_x":0.0,"direction_y":0.0,"direction_z":1.0,"frame_id":"joint:output-joint"},"start_angle_deg":-45.0,"end_angle_deg":45.0,"moving_instance_ids":["cad-hub"],"stationary_instance_ids":["cad-mount"],"required_clearance_mm":1.0,"proof_guard_mm":1e-6,"status":"verified_clear","certified_leaf_certificates":[{"interval_start_deg":-45.0,"interval_end_deg":45.0,"reference_angle_deg":0.0,"pair_certificates":[{"moving_instance_id":"cad-hub","stationary_instance_id":"cad-mount","exact_distance_mm":10.0,"radial_bound_mm":1.0,"angular_motion_bound_mm":0.1,"certified_lower_clearance_mm":9.9}],"minimum_certified_lower_clearance_mm":9.9}],"unresolved_intervals":[],"collision_witness":null,"exact_evaluations_count":1,"maximum_depth_reached":0,"result_hash":"sha256:8aeaaa4bf5e5ec3530956a270b08c7158f001ce211018762a6823ccfa9e2a111"},"request_hash":"sha256:6a78cfbc626da819406d23850b5420a2da1746fd7190cf284e88c603917f5b1b","result_hash":"sha256:8aeaaa4bf5e5ec3530956a270b08c7158f001ce211018762a6823ccfa9e2a111","proof_hash":"sha256:49e6a14ae04f9759a5b9b9e2759a0594e4a7d04ed59b7b3948db63bff93fde4a"}],"home_exact_checks":[],"reasons":[],"outcome_hash":"sha256:b668cea975405d5ef45aa3f8fb963cd4062b322fb873b707fac5d819abfe4852"},"m10_stage_outcome_hash":"sha256:b668cea975405d5ef45aa3f8fb963cd4062b322fb873b707fac5d819abfe4852","cad_request":{"schema_version":"candidate-cad-realization-request@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","source_binding":{"project_id":"PRJ-M12","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","consumed_authority":[{"path":"/id","value_hash":"sha256:02127c03d00d9598ff58eaee65151b742d7432c838784f7928856a45ef9fc51e","authority":"canonical_requirement"}]},"source_binding_hash":"sha256:364bdd17e0198e5a68fa5e289ba04fd47021d6163e9d88bd38076845ec62991a","representation_policy_version":"candidate-evaluation-fixture@1","compiler_identity":"fixture","compiler_version":"1","candidate_instance_ids":["motor","driver","shaft","bearing","hub","mount","body"],"mappings":[{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"motor","cad_instance_id":"cad-motor","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:9e290cb0499c01f49d9c1bf29f4794735b1a49be0fedfefeaf42d549b8553969","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:motor"],"placement":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:motor"],"derivation":"fixture-placement@1","transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:3bc8804879e5592b3e19abf8d1ba5bb7f652ba6b075ef699889287ae0f70ec74"},"mapping_hash":"sha256:44b1bfd77d5dbede434b4dd55baea2b5e58e3ea92198df56c7c7aba0c8939ac6"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"driver","cad_instance_id":"cad-driver","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:e8999308d72c83110721890097fa33d6024a49c556211db5f8a4b66c6abbd209","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:driver"],"placement":{"x_mm":20.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:driver"],"derivation":"fixture-placement@1","transform":{"x_mm":20.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:c3aaaa67e6c3a7f87878ddff488391ba953f6fee10bb52970cd6afd00c34e338"},"mapping_hash":"sha256:caed666bc92f436f653b33b6202275a6910d99e16b91e2498482dc083595951c"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"shaft","cad_instance_id":"cad-shaft","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:393d35ec55b81995f0da6f157c6134518640d5ce266b591246047b89e09eac5f","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:shaft"],"placement":{"x_mm":40.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:shaft"],"derivation":"fixture-placement@1","transform":{"x_mm":40.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:89ce11f70b6cc393c405c1a9bc9b71a7762783d48add67c92890f734e37c481c"},"mapping_hash":"sha256:779c67f6637f44004039a3c55b63b6ffef15ae707a9231e3333a57b587e581c4"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"bearing","cad_instance_id":"cad-bearing","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:e4e1d25b2a0a872b75ac99afc0ff731203845a9902d4c4bb66651f711d9f54f1","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:bearing"],"placement":{"x_mm":60.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:bearing"],"derivation":"fixture-placement@1","transform":{"x_mm":60.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:7b8f7aa4d0abb5ab12e06ba736112db0f955393eed2e6ac8b11e8eb09a2f5b98"},"mapping_hash":"sha256:5562e03010bbec4af67b56806786e30a1efc26f879ebb22952184fcc68e3059c"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"hub","cad_instance_id":"cad-hub","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:8686ea5542aaa9b306a6fe9c432c6197d9a6e6d9f57f194e335e50845fc9dff1","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:hub"],"placement":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:hub"],"derivation":"fixture-placement@1","transform":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:9c38693106cecb00b0ab78724aec1b999af0da12de17e7d8eeba92113ddfceeb"},"mapping_hash":"sha256:e0322d19e5bebfd1c96d6c57c7f95209113b5ff5bfe30ce1693f07b87e88a455"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"mount","cad_instance_id":"cad-mount","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:539a8528522a9d1d782ba5aa343cbff9002de3cad698cc02fc304153de235c61","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:mount"],"placement":{"x_mm":100.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:mount"],"derivation":"fixture-placement@1","transform":{"x_mm":100.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:6316fe60555911e5a1b7df5fbc4a3dfba2a1365a6d1384aa295c87bcf30313ef"},"mapping_hash":"sha256:a2b9f19fef111cf19fdba1f2a963e8fbd3fa4851f706466d46beba470d0ca486"},{"schema_version":"candidate-cad-instance-mapping@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","physical_instance_id":"body","cad_instance_id":"cad-body","fidelity":"declared_bounded_collision_representation","representation_identity":"sha256:a90ac6fdeece9efa7854a9253304a9dff861eca4217252b6623ac6b324f0927b","source_geometry_identity":null,"geometry_definition_identities":["candidate:geometry:body"],"placement":{"x_mm":120.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"placement_origin":{"authority":"deterministic_derived_relation","input_identities":["candidate:placement:body"],"derivation":"fixture-placement@1","transform":{"x_mm":120.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]},"origin_hash":"sha256:b7a9848c1e4482601e347ecac53ccda3caf6ef814079e0403d96591bb697146d"},"mapping_hash":"sha256:e4d493d07d012a9aaa1b2172b229f51d28551c32c7e85175d1bffece37709766"}],"design_variable_identities":[],"component_interface_identities":[],"request_hash":"sha256:1b399b6af693ec8fdc21cd1a48ddaea3e6c471d4be18c787fef7fd5c1e1a0a11"},"m10_request":{"schema_version":"candidate-m10-evaluation-request@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","cad_realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157","binding_hash":"sha256:16b399eb7cf9cf3e3d7ecbc3d9cdbe14770a3ed5b9076fb1ba091d00dc825a97","scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","model_hash":"sha256:365fa7d110a6d4f9f5be983344b6ec80f0a40df185b3a8309ce57c53069509cf","mapping_hashes":["sha256:44b1bfd77d5dbede434b4dd55baea2b5e58e3ea92198df56c7c7aba0c8939ac6","sha256:5562e03010bbec4af67b56806786e30a1efc26f879ebb22952184fcc68e3059c","sha256:779c67f6637f44004039a3c55b63b6ffef15ae707a9231e3333a57b587e581c4","sha256:a2b9f19fef111cf19fdba1f2a963e8fbd3fa4851f706466d46beba470d0ca486","sha256:caed666bc92f436f653b33b6202275a6910d99e16b91e2498482dc083595951c","sha256:e0322d19e5bebfd1c96d6c57c7f95209113b5ff5bfe30ce1693f07b87e88a455","sha256:e4d493d07d012a9aaa1b2172b229f51d28551c32c7e85175d1bffece37709766"],"inventory":{"schema_version":"candidate-m10-collision-pair-inventory@1","cad_realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157","binding_hash":"sha256:16b399eb7cf9cf3e3d7ecbc3d9cdbe14770a3ed5b9076fb1ba091d00dc825a97","scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","expected_pair_universe":[["cad-bearing","cad-body"],["cad-bearing","cad-driver"],["cad-bearing","cad-hub"],["cad-bearing","cad-motor"],["cad-bearing","cad-mount"],["cad-bearing","cad-shaft"],["cad-body","cad-driver"],["cad-body","cad-hub"],["cad-body","cad-motor"],["cad-body","cad-mount"],["cad-body","cad-shaft"],["cad-driver","cad-hub"],["cad-driver","cad-motor"],["cad-driver","cad-mount"],["cad-driver","cad-shaft"],["cad-hub","cad-motor"],["cad-hub","cad-mount"],["cad-hub","cad-shaft"],["cad-motor","cad-mount"],["cad-motor","cad-shaft"],["cad-mount","cad-shaft"]],"classifications":[{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-body"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:c0292a106bff19e42c96ecb443924c271f289bd6769971c7a61a9002bc24f3f8"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-driver"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:bbb90609ea187349c4cce3761caf3a49c29067d0360c3a5af92e83260d8d977f"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-hub"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:8f96a0e11d325374ec38e45c99a698ad907b2eadc1958c7b8d6a7121c6c70ed2"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-motor"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:b5a3e74539af707c4611a6f221e931a7cacc6f5df019aaf42dfbe696a01a1545"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-mount"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:92401365fe1e3a156817262886be366dbbcf4ded4fcf99585d07369996b08b38"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-bearing","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:3f3f21d501c2796a127dd5c433351659bc446ec7b171a18ab06de4ab5f917297"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-body","cad-driver"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:8290e9712208954994b372060455200c7594dfa16fc8590bd337dc936ba012dd"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-body","cad-hub"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:04c38ddf75c98243482e60c17d27f7546c292d08c4656a74ddf9e45001012d96"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-body","cad-motor"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:5be59d9f967ec59f28677ac62d96aa196d5596d516edd4ea983ca7c7e3e78736"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-body","cad-mount"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:5e62ee2c386208bb7c2f3effbe252dbb3fa53407c8c80030c954fcfcfb35b5c6"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-body","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:075e16fac9bc3d08d76d32b09b483679b25b4cff3c979326837c89e265f24e2f"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-driver","cad-hub"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:adb8792029d147914e689a5df93176b2f8b776845d9159f3ac8c5a75a72ebb97"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-driver","cad-motor"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:1e012cd43cc02bbea22b29651f4343bb55a389b508ecfbc3c1de718b5dfddc3d"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-driver","cad-mount"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:7c1db7248197a42877efe358b760a43a9345ffb10679b428c2adc38c6367925d"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-driver","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:cc43991a13561a637e76cd5f236842903fb16b814a7efc40a5dd9b6881a36836"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-hub","cad-motor"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:ed1dda4408316f9627cdbe9bd80a7fe06bf74d21c852bbf1afd8077ec2d6fe94"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-hub","cad-mount"],"classification":"check_clearance","reason":null,"requires_home_exact_check":false,"classification_hash":"sha256:70df8d95300f2e2c6213cc9ae5eeff8b7b3f2d3f76d796eb821008df0ecc87a2"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-hub","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:937aafa67cea1735a75e2cc43b74721a9f7b113ee7a58fecea798a6a6a7a3a4a"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-motor","cad-mount"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:700a3b124f1f1062515df494e8810ff7b080d2966bfa619fd07f18f27fef176b"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-motor","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:30d31122181128a963adc341c0c00ca60dd6a03dca5d6fa9710db99edb21d0e1"},{"schema_version":"candidate-m10-collision-pair-classification@1","pair":["cad-mount","cad-shaft"],"classification":"other_explicit_out_of_scope","reason":"not required by the declared M10 engineering scope","requires_home_exact_check":false,"classification_hash":"sha256:3c82e21457186d5e20aa91aaa64881dc4cafff5da6b2d5ff32165c1f9a42ae7e"}],"checked_pairs":[["cad-hub","cad-mount"]],"excluded_pairs":[["cad-bearing","cad-body"],["cad-bearing","cad-driver"],["cad-bearing","cad-hub"],["cad-bearing","cad-motor"],["cad-bearing","cad-mount"],["cad-bearing","cad-shaft"],["cad-body","cad-driver"],["cad-body","cad-hub"],["cad-body","cad-motor"],["cad-body","cad-mount"],["cad-body","cad-shaft"],["cad-driver","cad-hub"],["cad-driver","cad-motor"],["cad-driver","cad-mount"],["cad-driver","cad-shaft"],["cad-hub","cad-motor"],["cad-hub","cad-shaft"],["cad-motor","cad-mount"],["cad-motor","cad-shaft"],["cad-mount","cad-shaft"]],"inventory_hash":"sha256:1b6a0ffe7c78fbe5b6fb4d3335003c5ebcdb1ae0df3f0416506fb393fd57bc7f"},"request_hash":"sha256:e2bf8f52648dec3123729f1a53d20cfd9d5176148a786b3ab14f7a7677e9c422"},"m10_scope":{"schema_version":"candidate-m10-evaluation-scope@1","output_joint_semantic_key":"primary-output-revolute","angle_interval_deg":[-45.0,45.0],"required_clearance_mm":1.0,"pair_scope_requirements":[{"schema_version":"candidate-m10-pair-scope-requirement@1","requirement_key":"hub-mount-clearance","first_constituent_key":"hub","second_constituent_key":"mount","required_classification":"check_clearance","requires_home_exact_check":false}],"fidelity_requirements":[["hub","declared_bounded_collision_representation"],["mount","declared_bounded_collision_representation"]],"required_home_check_semantics":["exact-home-nonintended-interference@1"],"proof_service_version":"m10-single-axis-continuous-proof@1","policy_assumptions":["unmodeled-internal-motion-is-not-continuously-certified"],"scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2"},"m10_binding":{"schema_version":"candidate-m10-binding@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","cad_realization_hash":"sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157","model":{"model_id":"m12-output-model","joints":[{"joint_id":"output-joint","joint_kind":"revolute","parent_instance_id":"cad-mount","child_instance_id":"cad-shaft","axis_origin_x_mm":20.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null}],"evaluator_version":"multi-joint-forward-kinematics@1.0"},"model_hash":"sha256:365fa7d110a6d4f9f5be983344b6ec80f0a40df185b3a8309ce57c53069509cf","output_joint_id":"output-joint","driver_gear_constituent_key":null,"output_axis":{"origin_x_mm":120.0,"origin_y_mm":0.0,"origin_z_mm":0.0,"direction_x":0.0,"direction_y":0.0,"direction_z":1.0,"frame_id":"joint:output-joint"},"constituent_dispositions":[{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"motor","cad_instance_id":"cad-motor","constituent_key":"motor","disposition":"fixed","output_transform_group":null,"disposition_hash":"sha256:f5a552b2130e7c32782fd9f86b558164159939d325aa60042b86a84549cfa659"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"driver","cad_instance_id":"cad-driver","constituent_key":"driver","disposition":"internal_motion_unmodeled","output_transform_group":null,"disposition_hash":"sha256:ca17c622851b3f214da869667cea4346bc9c474a8b837bdae3cdc4f4da1e866d"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"shaft","cad_instance_id":"cad-shaft","constituent_key":"shaft","disposition":"output_rigid","output_transform_group":"output-joint","disposition_hash":"sha256:af3f77c8a4db099514bae2bb34dfe984a73fc3d81feda3a86d4656a4211f4108"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"bearing","cad_instance_id":"cad-bearing","constituent_key":"bearing","disposition":"fixed","output_transform_group":null,"disposition_hash":"sha256:101fcfabbcd937dc3ab37b7bd17d5f1f4ddadecbd4ab7985ea014b0e3cf651a9"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"hub","cad_instance_id":"cad-hub","constituent_key":"hub","disposition":"output_rigid","output_transform_group":"output-joint","disposition_hash":"sha256:acd43d2342595f4d2503a32fb32a0f565fa93d9c715c6b77c115bf37aac4a901"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"mount","cad_instance_id":"cad-mount","constituent_key":"mount","disposition":"fixed","output_transform_group":null,"disposition_hash":"sha256:4224b765c6487db61f247001e6ef3b62193e7cf7c8ffe41a4a6a0388ec493404"},{"schema_version":"candidate-m10-constituent-disposition@1","physical_instance_id":"body","cad_instance_id":"cad-body","constituent_key":"body","disposition":"output_rigid","output_transform_group":"output-joint","disposition_hash":"sha256:f46a76d49788542f8c48aac5c5eb96b22d8d8b5eb4e1ebcb7496873794cfb1f1"}],"binding_hash":"sha256:16b399eb7cf9cf3e3d7ecbc3d9cdbe14770a3ed5b9076fb1ba091d00dc825a97"},"metrics":[{"schema_version":"candidate-metric@1","key":"verified_clearance_lower_bound_mm","value":9.9,"unit":"mm","source_result_hashes":["sha256:8aeaaa4bf5e5ec3530956a270b08c7158f001ce211018762a6823ccfa9e2a111"],"derivation":"minimum_certified_lower_clearance_mm","metric_hash":"sha256:edbad65208b26f18d2492337a94192eccff8e046615905571842fbd7ce3b33f9"}],"hard_witnesses":[],"unresolved_findings":[],"outcome":"feasible","evaluator_identity":"candidate-evaluation","evaluator_version":"1","evaluation_hash":"sha256:95d06e1c713bcd3e4a60c6643e7bc7d3b5912d577e1d5f5897bf70e7ce08acaa"},"selection":{"schema_version":"candidate-selection@1","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","evaluation_hash":"sha256:95d06e1c713bcd3e4a60c6643e7bc7d3b5912d577e1d5f5897bf70e7ce08acaa","source_binding_hash":"sha256:364bdd17e0198e5a68fa5e289ba04fd47021d6163e9d88bd38076845ec62991a","evaluation_scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","selector_identity":"fixture-selector","rationale":"fixture selection","comparison_used":false,"comparison_result_hash":null,"selection_hash":"sha256:5c8f5bda8a72a82ba130267f152dc97004747813a94546c36580ccc01b4b6e2c"},"comparison_used":false,"comparison":null,"comparison_request":null,"comparison_entries":null,"promotion_policy":{"schema_version":"candidate-promotion-policy@1","allowed_target_family":"canonical_physical_mechanism","mapping_schema_version":"candidate-canonical-mapping@1","compiler_version":"candidate-promotion@1","allowed_classifications":["accepted_physical_fact","accepted_design_choice","canonical_rederivation_input","provenance_only","do_not_promote"],"required_property_authorities":[],"publication_mode":"decision_and_result_manifests","policy_hash":"sha256:901fbe10d0c48cfa146961f6372e7c81ce27befbbe562e6611f23e20fa1fa9bc"},"canonical_target_mechanism_id":"PM-1","classifications":[{"source_identity":"candidate:property:datasheet:example:MTR-24-100@1:rated_voltage","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":24.0,"classification_hash":"sha256:4a0d37ae554f855c93393090db9917d29a59269f31e112c06f342dae04c9fa0e"},{"source_identity":"candidate:property:datasheet:example:MTR-24-100@1:continuous_torque","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:d365607d20cd25fb6915a5c60bac7ebe8489f1761244260b177b119f5365c024"},{"source_identity":"candidate:property:custom:shaft@1:diameter","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":12.0,"classification_hash":"sha256:3cc05679d69895aa58af97172296f1f9c96706053527833e4bf0162e03931aae"},{"source_identity":"candidate:property:catalog:bearing@1:dynamic_load_rating","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:796f330070e8913d684604cd43ff7dfb0b7ad134ddcb1548ebcdb84d71dc52f2"},{"source_identity":"candidate:physical-instance:motor","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:df42a2d2b32975f4f96387418fb4ad79cfb902c14dccb883143c0eaea4df83b6"},{"source_identity":"candidate:physical-instance:driver","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:d57e8e8caeefc53ec855ae88272e7177e08b5521795163b0c4829d6410dd44af"},{"source_identity":"candidate:physical-instance:shaft","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:3d4a7d99856a843ec326db492700d656115bfa0f9b1167f89a0130c7885858ec"},{"source_identity":"candidate:physical-instance:bearing","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:4983933bd551b3656512a992961f1063dd7e14947a9ac9ba6a75f48d67ea7994"},{"source_identity":"candidate:physical-instance:hub","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:7625812889648bc16d5ad21f7350d50300d5444f12aaed04f22f4a99f4147b37"},{"source_identity":"candidate:physical-instance:mount","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:0d91f4803b64b3b3f42c4b0fff78efc2ef0533ac0fcd7efa37abd5fa1baca24e"},{"source_identity":"candidate:physical-instance:body","source_provenance":"source_authority","classification":"accepted_physical_fact","source_value":null,"classification_hash":"sha256:e19eb00bfa05eb770ffd505f53023a7127b9774b77b8548b1b2daf1a42c0c2d6"}],"m11_target_intent":null,"request_hash":"sha256:6b812b65d021e1ba7dbff5616cb0c666135c6dca257d43b85bd29e9d85086783"}'''
LEGACY_READINESS_JSON = r'''{"schema_version":"candidate-promotion-readiness@1","project_id":"PRJ-M12","source_revision":1,"source_state_hash":"sha256:d517d8f02776145f88820525148f945ab127cb80c4c503caed5cf360b69510c7","source_binding_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111","request_hash":"sha256:6b812b65d021e1ba7dbff5616cb0c666135c6dca257d43b85bd29e9d85086783","candidate_hash":"sha256:80d877921a69d5fab88b4b2533933c1b9ea604a50b2b342d459426ba50300e57","m12_3_result_hash":"sha256:9d00c53aa470715e048ee1e5b68f4fda04cf745fefc408899ac78f6681b56132","evaluation_hash":"sha256:95d06e1c713bcd3e4a60c6643e7bc7d3b5912d577e1d5f5897bf70e7ce08acaa","selection_hash":"sha256:5c8f5bda8a72a82ba130267f152dc97004747813a94546c36580ccc01b4b6e2c","evaluation_scope_hash":"sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2","comparison_used":false,"comparison_result_hash":null,"promotion_policy_hash":"sha256:901fbe10d0c48cfa146961f6372e7c81ce27befbbe562e6611f23e20fa1fa9bc","canonical_target_mechanism_id":"PM-1","mapping":[{"candidate_instance_id":"shaft","canonical_instance_id":"component-1","canonical_path":"/physical_mechanisms/PM-1/components/component-1","classification":"accepted_physical_fact","source_identity":"candidate:physical-instance:shaft","source_provenance":"source_authority","source_value":null,"mapping_hash":"sha256:7a1d14cccdb237f552c73187301a2830f42a5111afcb58e8c45a9daec7c311c0"}],"classification_identities":["sha256:4a0d37ae554f855c93393090db9917d29a59269f31e112c06f342dae04c9fa0e","sha256:d365607d20cd25fb6915a5c60bac7ebe8489f1761244260b177b119f5365c024","sha256:3cc05679d69895aa58af97172296f1f9c96706053527833e4bf0162e03931aae","sha256:796f330070e8913d684604cd43ff7dfb0b7ad134ddcb1548ebcdb84d71dc52f2","sha256:df42a2d2b32975f4f96387418fb4ad79cfb902c14dccb883143c0eaea4df83b6","sha256:d57e8e8caeefc53ec855ae88272e7177e08b5521795163b0c4829d6410dd44af","sha256:3d4a7d99856a843ec326db492700d656115bfa0f9b1167f89a0130c7885858ec","sha256:4983933bd551b3656512a992961f1063dd7e14947a9ac9ba6a75f48d67ea7994","sha256:7625812889648bc16d5ad21f7350d50300d5444f12aaed04f22f4a99f4147b37","sha256:0d91f4803b64b3b3f42c4b0fff78efc2ef0533ac0fcd7efa37abd5fa1baca24e","sha256:e19eb00bfa05eb770ffd505f53023a7127b9774b77b8548b1b2daf1a42c0c2d6"],"trusted_geometry_artifact_ids":[],"readiness_hash":"sha256:cdbd46674c2388ef0c595c88ade1e8574586367d207a47d7d6096e4b2d31aa29"}'''


LEGACY_REFERENCE_JSON = (
    '{"schema_version":"promotion-decision-input-reference@1",'
    '"promotion_request_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"project_id":"PRJ-LEGACY","base_revision":3,'
    '"base_state_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"candidate_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"synthesis_request_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"synthesis_policy_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"m12_3_result_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"evaluation_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"selection_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"comparison_used":false,"comparison_result_hash":null,"comparison_request_hash":null,'
    '"promotion_policy_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"canonical_target_mechanism_id":"PM-LEGACY",'
    '"m11_target_intent":null,'
    '"mapping_identities":["sha256:195fb46a48217152d42e81c36cda7816df8701e74eccf6c4b3d08b8c2d87f4fd"],'
    '"classification_identities":["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],'
    '"reference_hash":"sha256:7eed2765ef2fe0bc78b7f2a3a63157f16db54b8b4486e435c76bba61fd0ec3de"}'
)
LEGACY_REFERENCE_HASH = (
    "sha256:7eed2765ef2fe0bc78b7f2a3a63157f16db54b8b4486e435c76bba61fd0ec3de"
)
LEGACY_DECISION_ID = "PROMOTION-DECISION-12c4913c320b60032291617e"
LEGACY_DECISION_HASH = (
    "sha256:12c4913c320b60032291617e64938d639d0971e3b9ae87f71cef49a9213d1411"
)
LEGACY_DECISION_BYTE_HASH = (
    "sha256:9e4854ed8e1fa82902af11007d035fbd2a924962212a8787d6482ba5a058c1ba"
)
LEGACY_DECISION_BYTES = (
    b'{"base_revision":3,"base_state_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"compilation_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"decision_hash":"sha256:12c4913c320b60032291617e64938d639d0971e3b9ae87f71cef49a9213d1411",'
    b'"input_reference":{"base_revision":3,"base_state_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"candidate_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"canonical_target_mechanism_id":"PM-LEGACY","classification_identities":["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],'
    b'"comparison_request_hash":null,"comparison_result_hash":null,"comparison_used":false,'
    b'"evaluation_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","m11_target_intent":null,'
    b'"m12_3_result_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"mapping_identities":["sha256:195fb46a48217152d42e81c36cda7816df8701e74eccf6c4b3d08b8c2d87f4fd"],'
    b'"project_id":"PRJ-LEGACY","promotion_policy_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"promotion_request_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"reference_hash":"sha256:7eed2765ef2fe0bc78b7f2a3a63157f16db54b8b4486e435c76bba61fd0ec3de",'
    b'"schema_version":"promotion-decision-input-reference@1","selection_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"synthesis_policy_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"synthesis_request_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
    b'"mapping":[{"candidate_instance_id":"fixture","canonical_instance_id":"PM-LEGACY:fixture",'
    b'"canonical_path":"/physical_mechanisms/PM-LEGACY/components/PM-LEGACY:fixture",'
    b'"classification":"accepted_physical_fact","mapping_hash":"sha256:195fb46a48217152d42e81c36cda7816df8701e74eccf6c4b3d08b8c2d87f4fd",'
    b'"source_identity":"candidate:physical-instance:fixture","source_provenance":"source_authority","source_value":null}],'
    b'"pre_promotion_scope_projection":{"angle_interval_deg":[0.0,1.0],"bounded_limitations":[],"fidelity_requirements":[],'
    b'"joint_semantic_key":"legacy-joint","path_semantics":"single_axis_interval","physical_pair_requirements":[{"first_instance_id":"first",'
    b'"first_interface_id":"out","requirement_hash":"sha256:976fcec42a25777d2b86daf9b66e68b7d598bf3d13fe142094ab98fd9c5d8eab",'
    b'"requirement_key":"pair","requires_home_exact_check":false,"second_instance_id":"second","second_interface_id":"frame"}],'
    b'"projection_hash":"sha256:9ca44f50f1257f624e403b8a0fd7e95d6ed23e04a9ac502a6683a22fa60745ca",'
    b'"required_clearance_mm":0.1,"required_home_check_semantics":[],"schema_version":"pre-promotion-m10-scope-projection@1"},'
    b'"projection":{"accepted_design_choices":[],"canonical_instance_ids":["PM-LEGACY:fixture"],"canonical_target_mechanism_id":"PM-LEGACY",'
    b'"component_specifications":[{"compatibility_declarations":[],"component_type":"fixture","geometry_source":null,"interfaces":["frame"],'
    b'"manufacturer":null,"part_number":null,"properties":[],"schema_version":"canonical-component-specification@1",'
    b'"source_identity":"legacy:fixture","specification_hash":"sha256:68c24e0166f64c6d8209d375a778fb615c65e4b422650ed8cc0336e4ab3b805b"}],'
    b'"components":[{"component_hash":"sha256:8820ae4715a894eeba58f66b5c4b01ea277906805920f2ee696e88f6ea3b04f7",'
    b'"instance_id":"PM-LEGACY:fixture","interfaces":["frame"],"placement_id":null,"role":"mount_or_support",'
    b'"specification_hash":"sha256:68c24e0166f64c6d8209d375a778fb615c65e4b422650ed8cc0336e4ab3b805b"}],'
    b'"connections":[],"joint_bindings":[],"m10_obligations":[],"mapping_identities":["PM-LEGACY:fixture"],"placements":[],'
    b'"projection_hash":"sha256:c10823fffe6c3c3f000f427c281838908e36ae3ba0f2f49575e3585a7b91226c",'
    b'"schema_version":"promotable-mechanism-projection@1"},"projection_hash":"sha256:c10823fffe6c3c3f000f427c281838908e36ae3ba0f2f49575e3585a7b91226c",'
    b'"promotion_policy_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"promotion_proposal_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"schema_version":"selected-candidate-decision-manifest@1"}\n'
)
LEGACY_RESULT_ID = "PROMOTION-RESULT-8605412573d867cc2c2d3ace"
LEGACY_RESULT_HASH = (
    "sha256:8605412573d867cc2c2d3ace12662f1cca48b6ed198fa08a4716fc04ddbcde10"
)
LEGACY_RESULT_BYTE_HASH = (
    "sha256:50da2fca79195e22438ed5b9620f7e54d257c3761267df7cb38ee6c9e04735b0"
)
LEGACY_RESULT_BYTES = (
    b'{"application_id":null,"changed_paths":["/physical_mechanisms/PM-LEGACY"],'
    b'"changeset_id":"legacy-changeset","decision_artifact_hash":"sha256:9e4854ed8e1fa82902af11007d035fbd2a924962212a8787d6482ba5a058c1ba",'
    b'"decision_artifact_id":"PROMOTION-DECISION-12c4913c320b60032291617e",'
    b'"mechanism_path":"/physical_mechanisms/PM-LEGACY",'
    b'"promotion_proposal_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"proposal_id":"legacy-proposal","result_hash":"sha256:8605412573d867cc2c2d3ace12662f1cca48b6ed198fa08a4716fc04ddbcde10",'
    b'"resulting_revision":4,"resulting_state_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"schema_version":"candidate-promotion-result-manifest@1"}\n'
)
LEGACY_STATUS_VALUES = (
    "pre_apply_failure",
    "changeengine_rejected",
    "promotion_applied_but_run_transition_failed",
    "promotion_applied_but_invalidation_persistence_failed",
    "promotion_applied_but_invalidation_verification_failed",
    "promotion_applied_but_result_provenance_failed",
    "promotion_applied",
)

LEGACY_REQUEST_HASH = (
    "sha256:6b812b65d021e1ba7dbff5616cb0c666135c6dca257d43b85bd29e9d85086783"
)
LEGACY_READINESS_HASH = (
    "sha256:cdbd46674c2388ef0c595c88ade1e8574586367d207a47d7d6096e4b2d31aa29"
)
LEGACY_APPLICATION_RESULT_JSON = (
    '{"schema_version":"candidate-promotion-application-result@1","request":null,'
    '"compilation":null,"decision_artifact_id":null,"result_artifact_id":null,'
    '"applied_revision":null,"applied_state_hash":null,"status":"pre_apply_failure",'
    '"error":null}'
)


def _legacy_fixture(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-LEGACY", run_id="RUN-LEGACY")
    specification = CanonicalComponentSpecification(
        component_type="fixture", source_identity="legacy:fixture", interfaces=("frame",)
    )
    mechanism = CanonicalPhysicalMechanism(
        id="PM-LEGACY",
        name="legacy fixture",
        component_specifications=(specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="PM-LEGACY:fixture",
                specification_hash=specification.specification_hash,
                role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=("frame",),
            ),
        ),
    )
    projection = CandidatePromotionCompiler._projection(mechanism)
    mapping = CandidateCanonicalInstanceMapping(
        candidate_instance_id="fixture",
        canonical_instance_id="PM-LEGACY:fixture",
        canonical_path="/physical_mechanisms/PM-LEGACY/components/PM-LEGACY:fixture",
        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        source_identity="candidate:physical-instance:fixture",
    )
    reference = PromotionDecisionInputReference(
        promotion_request_hash=HASH,
        project_id="PRJ-LEGACY",
        base_revision=3,
        base_state_hash=HASH,
        candidate_hash=HASH,
        synthesis_request_hash=HASH,
        synthesis_policy_hash=HASH,
        m12_3_result_hash=HASH,
        evaluation_hash=HASH,
        selection_hash=HASH,
        promotion_policy_hash=HASH,
        canonical_target_mechanism_id="PM-LEGACY",
        mapping_identities=(mapping.mapping_hash,),
        classification_identities=(HASH,),
    )
    scope = PrePromotionM10ScopeProjection(
        joint_semantic_key="legacy-joint",
        angle_interval_deg=(0.0, 1.0),
        required_clearance_mm=0.1,
        physical_pair_requirements=(
            PromotionPhysicalPairRequirement(
                requirement_key="pair",
                first_instance_id="first",
                first_interface_id="out",
                second_instance_id="second",
                second_interface_id="frame",
            ),
        ),
    )
    return store, reference, scope, projection, mapping


def _baseline_request_and_readiness():
    state = DesignState(
        id="DES-M12",
        revision=1,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    selection = CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    values = {
        "project_id": candidate.source_binding.project_id,
        "source_revision": candidate.source_binding.source_revision,
        "source_state_hash": candidate.source_binding.source_state_hash,
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "m12_3_result": _m12_result(candidate),
        "evaluation": evaluation,
        "selection": selection,
        "promotion_policy": CandidatePromotionPolicy(),
        "canonical_target_mechanism_id": "PM-1",
    }
    request = CandidatePromotionRequest(**values)
    request = CandidatePromotionRequest(**(values | {"classifications": _classifications(request)}))
    readiness, _, _ = _compiled(request)
    return request, readiness


def test_legacy_request_and_readiness_hashes_match_detached_baseline():
    request, readiness = _baseline_request_and_readiness()

    assert request.model_dump_json() == LEGACY_REQUEST_JSON
    assert request.request_hash == LEGACY_REQUEST_HASH
    assert readiness.model_dump_json() == LEGACY_READINESS_JSON
    assert readiness.readiness_hash == LEGACY_READINESS_HASH


def test_legacy_promotion_models_and_artifacts_are_immutable(tmp_path):
    store, reference, scope, projection, mapping = _legacy_fixture(tmp_path)
    service = PromotionManifestService()
    decision = service.publish_decision(
        store,
        input_reference=reference,
        pre_promotion_scope_projection=scope,
        promotion_policy_hash=HASH,
        base_revision=3,
        base_state_hash=HASH,
        compilation_hash=HASH,
        promotion_proposal_hash=HASH,
        projection_hash=projection.projection_hash,
        projection=projection,
        mapping=(mapping,),
    )
    result = service.publish_result(
        store,
        decision_artifact=decision,
        promotion_proposal_hash=HASH,
        proposal_id="legacy-proposal",
        changeset_id="legacy-changeset",
        changed_paths=("/physical_mechanisms/PM-LEGACY",),
        mechanism_path="/physical_mechanisms/PM-LEGACY",
        resulting_revision=4,
        resulting_state_hash=HASH,
    )

    assert reference.model_dump_json() == LEGACY_REFERENCE_JSON
    assert reference.reference_hash == LEGACY_REFERENCE_HASH
    assert isinstance(
        SelectedCandidateDecisionManifest.model_validate(
            service.resolve_decision(store, decision.artifact_id).model_dump(mode="json")
        ),
        SelectedCandidateDecisionManifest,
    )
    assert decision.artifact_id == LEGACY_DECISION_ID
    assert decision.input_hash == LEGACY_DECISION_HASH
    assert decision.sha256 == LEGACY_DECISION_BYTE_HASH
    assert decision.artifact_type is ArtifactType.JSON
    decision_bytes = (tmp_path / decision.relative_path).read_bytes()
    assert decision_bytes.endswith(b"\n")
    assert not decision_bytes.endswith(b"\n\n")
    assert decision_bytes == LEGACY_DECISION_BYTES
    assert f"sha256:{hashlib.sha256(decision_bytes).hexdigest()}" == LEGACY_DECISION_BYTE_HASH

    result_manifest = service.resolve_result(store, result.artifact_id)
    assert isinstance(
        CandidatePromotionResultManifest.model_validate(result_manifest.model_dump(mode="json")),
        CandidatePromotionResultManifest,
    )
    assert result.artifact_id == LEGACY_RESULT_ID
    assert result.input_hash == LEGACY_DECISION_BYTE_HASH
    assert result.sha256 == LEGACY_RESULT_BYTE_HASH
    result_bytes = (tmp_path / result.relative_path).read_bytes()
    assert result_bytes == LEGACY_RESULT_BYTES
    assert result_bytes.endswith(b"\n")
    assert not result_bytes.endswith(b"\n\n")
    assert result_manifest.result_hash == LEGACY_RESULT_HASH


def test_legacy_receipt_schema_and_status_values_are_immutable():
    fields = CandidatePromotionApplicationResult.model_fields
    assert tuple(fields) == (
        "schema_version",
        "request",
        "compilation",
        "decision_artifact_id",
        "result_artifact_id",
        "applied_revision",
        "applied_state_hash",
        "status",
        "error",
    )
    assert fields["schema_version"].annotation == Literal[
        "candidate-promotion-application-result@1"
    ]
    assert fields["schema_version"].default == "candidate-promotion-application-result@1"
    assert not fields["schema_version"].is_required()
    assert fields["request"].annotation == CandidatePromotionRequest | None
    assert fields["request"].default is None
    assert not fields["request"].is_required()
    assert fields["compilation"].annotation == CandidatePromotionCompilation | None
    assert fields["compilation"].default is None
    assert not fields["compilation"].is_required()
    for name, annotation in (
        ("decision_artifact_id", StrictStr | None),
        ("result_artifact_id", StrictStr | None),
        ("applied_revision", StrictInt | None),
        ("applied_state_hash", StrictStr | None),
        ("error", StrictStr | None),
    ):
        assert fields[name].annotation == annotation
        assert fields[name].default is None
        assert not fields[name].is_required()
    assert fields["status"].annotation is PromotionApplicationStatus
    assert fields["status"].default is PydanticUndefined
    assert fields["status"].is_required()
    assert CandidatePromotionApplicationResult(
        status=PromotionApplicationStatus.PRE_APPLY_FAILURE
    ).model_dump_json() == LEGACY_APPLICATION_RESULT_JSON
    assert tuple(status.value for status in PromotionApplicationStatus) == LEGACY_STATUS_VALUES
