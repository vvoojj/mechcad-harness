from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
    MultiJointCollisionConfigurationResult,
    MultiJointCollisionSweepRequest,
    MultiJointCollisionSweepResult,
    MultiJointDiscreteCollisionSweepService,
)
from mechcad_harness.multi_joint_continuous_clearance import (
    ContinuousExactPairResult,
    ContinuousPairCertificate,
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousClearanceProofService,
    MultiJointContinuousCollisionWitness,
)
from mechcad_harness.multi_joint_continuous_path import (
    ARTICULATED_DESCENDANT_REACH_BOUND_VERSION,
    MULTI_JOINT_CONTINUOUS_PATH_PROOF_VERSION,
    MULTI_JOINT_PATH_INTERPOLATION_VERSION,
    MultiJointContinuousPathRequest,
    MultiJointPath,
    TrustedLocalGeometryExtent,
)
from mechcad_harness.multi_joint_kinematics import (
    MULTI_JOINT_FORWARD_KINEMATICS_VERSION,
    JointConfiguration,
    KinematicForwardKinematicsResult,
    KinematicModel,
    KinematicModelV2,
    MultiJointKinematicsService,
    RevoluteJointModel,
    RevoluteJointModelV2,
    kinematic_model_wire_payload,
    parse_kinematic_model,
    parse_revolute_joint_model,
    kinematic_model_hash,
)
from mechcad_harness.transient_assembly_analysis import (
    TransientAssemblyAnalysisService,
)
# Captured from the unmodified pre-M13-3P source. These literals are immutable
# compatibility locks and must not be regenerated after production changes.
GOLDEN_REVOLUTE_JOINT_JSON = '{"joint_id":"joint-1","joint_kind":"revolute","parent_instance_id":"base","child_instance_id":"link-1","axis_origin_x_mm":5.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.5773502691896258,"axis_direction_y":0.5773502691896258,"axis_direction_z":0.5773502691896258,"min_angle_deg":-45.0,"max_angle_deg":135.0}'
GOLDEN_KINEMATIC_MODEL_JSON = '{"model_id":"m13-3p-two-joint-model","joints":[{"joint_id":"joint-1","joint_kind":"revolute","parent_instance_id":"base","child_instance_id":"link-1","axis_origin_x_mm":0.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null},{"joint_id":"joint-2","joint_kind":"revolute","parent_instance_id":"link-1","child_instance_id":"link-2","axis_origin_x_mm":30.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null}],"evaluator_version":"multi-joint-forward-kinematics@1.0"}'
GOLDEN_KINEMATIC_MODEL_HASH = "sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d"
GOLDEN_ONE_JOINT_FK_JSON = '{"evaluator_version":"multi-joint-forward-kinematics@1.0","source_assembly_hash":"sha256:ba2d4efa7527efa4dc4969b4afdc2b3c1b322befb80e7ac768d849b0720f841f","model_hash":"sha256:62572862214fbb77e64375668348a359d4b75ba41b80fb6f2bdd1cffdae2a233","configuration_hash":"sha256:796d81c2891bd5490c4b83ef73569412e5410440af4fa931912b65796714d337","transformed_assembly_hash":"sha256:11da65923f22733e4ef2d033a72a5179ca2c28beb225e229f20367fecc5b3987","model_id":"m13-3p-one-joint-model","ordered_joint_states":[{"joint_id":"joint-1","joint_position_deg":30.0,"within_limits":true}],"instance_world_transforms":[{"instance_id":"base","is_articulated":false,"transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","is_articulated":true,"transform":{"x_mm":27.767090063073983,"y_mm":8.333333333333334,"z_mm":-6.100423396407311,"rotation_quaternion":[0.9659258262890683,0.14942924536134225,0.14942924536134225,0.14942924536134225]}}],"transformed_assembly":{"assembly_id":"m13-3p-one-joint","parts":[{"part_id":"link","operations":[{"operation_id":"base","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"}],"imported_components":[],"instances":[{"instance_id":"base","part_id":"link","placement":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","part_id":"link","placement":{"x_mm":27.767090063073983,"y_mm":8.333333333333334,"z_mm":-6.100423396407311,"rotation_quaternion":[0.9659258262890683,0.14942924536134225,0.14942924536134225,0.14942924536134225]}}]},"result_hash":"sha256:afcd9ead1e39667e71e15cd1c9a2b57dca59b2574037194dc21a0d01258f0d4f"}'
GOLDEN_ONE_JOINT_FK_RESULT_HASH = "sha256:afcd9ead1e39667e71e15cd1c9a2b57dca59b2574037194dc21a0d01258f0d4f"
GOLDEN_TWO_JOINT_FK_JSON = '{"evaluator_version":"multi-joint-forward-kinematics@1.0","source_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","model_hash":"sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d","configuration_hash":"sha256:660fca0dd36c8cfd8b8c17902b3bdfb298c806a229494cdcd86296478aac0096","transformed_assembly_hash":"sha256:ad00561617c1026d8bea0d6d8bd79cb8ac3c8b769658036535caacad7cf78ddc","model_id":"m13-3p-two-joint-model","ordered_joint_states":[{"joint_id":"joint-1","joint_position_deg":30.0,"within_limits":true},{"joint_id":"joint-2","joint_position_deg":15.0,"within_limits":true}],"instance_world_transforms":[{"instance_id":"base","is_articulated":false,"transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","is_articulated":true,"transform":{"x_mm":25.980762113533164,"y_mm":15.0,"z_mm":0.0,"rotation_quaternion":[0.9659258262890683,0.0,0.0,0.25881904510252074]}},{"instance_id":"link-2","is_articulated":true,"transform":{"x_mm":66.10365985079727,"y_mm":44.14213562373095,"z_mm":0.0,"rotation_quaternion":[0.9238795325112867,0.0,0.0,0.3826834323650897]}}],"transformed_assembly":{"assembly_id":"m13-3p-two-joint","parts":[{"part_id":"link","operations":[{"operation_id":"base","operation_type":"base_plate","length_mm":10.0,"width_mm":10.0,"thickness_mm":2.0}],"coordinate_system":"lower-left-bottom; +X length, +Y width, +Z thickness"}],"imported_components":[],"instances":[{"instance_id":"base","part_id":"link","placement":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","part_id":"link","placement":{"x_mm":25.980762113533164,"y_mm":15.0,"z_mm":0.0,"rotation_quaternion":[0.9659258262890683,0.0,0.0,0.25881904510252074]}},{"instance_id":"link-2","part_id":"link","placement":{"x_mm":66.10365985079727,"y_mm":44.14213562373095,"z_mm":0.0,"rotation_quaternion":[0.9238795325112867,0.0,0.0,0.3826834323650897]}}]},"result_hash":"sha256:120c5f27073bb57fee82b2b8f92893889a674e9d4b4c4ba7837c49702f130b89"}'
GOLDEN_TWO_JOINT_FK_RESULT_HASH = "sha256:120c5f27073bb57fee82b2b8f92893889a674e9d4b4c4ba7837c49702f130b89"
GOLDEN_COLLISION_SWEEP_REQUEST_JSON = '{"source_assembly_id":"m13-3p-two-joint","source_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","model":{"model_id":"m13-3p-two-joint-model","joints":[{"joint_id":"joint-1","joint_kind":"revolute","parent_instance_id":"base","child_instance_id":"link-1","axis_origin_x_mm":0.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null},{"joint_id":"joint-2","joint_kind":"revolute","parent_instance_id":"link-1","child_instance_id":"link-2","axis_origin_x_mm":30.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null}],"evaluator_version":"multi-joint-forward-kinematics@1.0"},"configurations":[{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":0.0,"joint-2":0.0}},{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":30.0,"joint-2":15.0}}],"moving_instance_ids":["link-1","link-2"],"stationary_instance_ids":["base"],"volume_tolerance_mm3":0.001,"distance_tolerance_mm":0.002,"evaluator_version":"multi-joint-exact-collision-sweep@1.0","model_hash":"sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d","request_hash":"sha256:ab0c8e6ee04760bfa225c34f80d3f2713e3619c02ddae6a1dba7c2e46feb41eb"}'
GOLDEN_COLLISION_SWEEP_REQUEST_HASH = "sha256:ab0c8e6ee04760bfa225c34f80d3f2713e3619c02ddae6a1dba7c2e46feb41eb"
GOLDEN_COLLISION_CONFIGURATION_RESULT_JSON = '{"configuration_index":1,"configuration_hash":"sha256:660fca0dd36c8cfd8b8c17902b3bdfb298c806a229494cdcd86296478aac0096","transformed_assembly_hash":"sha256:ad00561617c1026d8bea0d6d8bd79cb8ac3c8b769658036535caacad7cf78ddc","ordered_joint_states":[{"joint_id":"joint-1","joint_position_deg":30.0,"within_limits":true},{"joint_id":"joint-2","joint_position_deg":15.0,"within_limits":true}],"instance_world_transforms":[{"instance_id":"base","is_articulated":false,"transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","is_articulated":true,"transform":{"x_mm":25.980762113533164,"y_mm":15.0,"z_mm":0.0,"rotation_quaternion":[0.9659258262890683,0.0,0.0,0.25881904510252074]}},{"instance_id":"link-2","is_articulated":true,"transform":{"x_mm":66.10365985079727,"y_mm":44.14213562373095,"z_mm":0.0,"rotation_quaternion":[0.9238795325112867,0.0,0.0,0.3826834323650897]}}],"pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"}],"classification":"positive_clearance","any_interference":false,"any_touching":false,"all_positive_clearance":true,"minimum_exact_distance_mm":25.0}'
GOLDEN_COLLISION_CONFIGURATION_RESULT_DIGEST = "sha256:0d0278d697287603083a5cbb73c95283a5b75ee75ae62ffca407957e525a0de0"
GOLDEN_COLLISION_SWEEP_RESULT_JSON = '{"evaluator_version":"multi-joint-exact-collision-sweep@1.0","source_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","model_hash":"sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d","request_hash":"sha256:ab0c8e6ee04760bfa225c34f80d3f2713e3619c02ddae6a1dba7c2e46feb41eb","configuration_results":[{"configuration_index":0,"configuration_hash":"sha256:5e3e70d8bff9a5352777de2b16545e048313fa9f1e124c60a7e6d72c1c876e9e","transformed_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","ordered_joint_states":[{"joint_id":"joint-1","joint_position_deg":0.0,"within_limits":true},{"joint_id":"joint-2","joint_position_deg":0.0,"within_limits":true}],"instance_world_transforms":[{"instance_id":"base","is_articulated":false,"transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","is_articulated":true,"transform":{"x_mm":30.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-2","is_articulated":true,"transform":{"x_mm":80.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}}],"pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"}],"classification":"positive_clearance","any_interference":false,"any_touching":false,"all_positive_clearance":true,"minimum_exact_distance_mm":25.0},{"configuration_index":1,"configuration_hash":"sha256:660fca0dd36c8cfd8b8c17902b3bdfb298c806a229494cdcd86296478aac0096","transformed_assembly_hash":"sha256:ad00561617c1026d8bea0d6d8bd79cb8ac3c8b769658036535caacad7cf78ddc","ordered_joint_states":[{"joint_id":"joint-1","joint_position_deg":30.0,"within_limits":true},{"joint_id":"joint-2","joint_position_deg":15.0,"within_limits":true}],"instance_world_transforms":[{"instance_id":"base","is_articulated":false,"transform":{"x_mm":0.0,"y_mm":0.0,"z_mm":0.0,"rotation_quaternion":[1.0,0.0,0.0,0.0]}},{"instance_id":"link-1","is_articulated":true,"transform":{"x_mm":25.980762113533164,"y_mm":15.0,"z_mm":0.0,"rotation_quaternion":[0.9659258262890683,0.0,0.0,0.25881904510252074]}},{"instance_id":"link-2","is_articulated":true,"transform":{"x_mm":66.10365985079727,"y_mm":44.14213562373095,"z_mm":0.0,"rotation_quaternion":[0.9238795325112867,0.0,0.0,0.3826834323650897]}}],"pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":25.0,"classification":"positive_clearance"}],"classification":"positive_clearance","any_interference":false,"any_touching":false,"all_positive_clearance":true,"minimum_exact_distance_mm":25.0}],"any_interference":false,"any_touching":false,"all_positive_clearance":true,"collision_configuration_indices":[],"minimum_exact_distance_mm":25.0,"minimum_distance_configuration_index":0,"continuous_path_verified":false,"result_hash":"sha256:af9f86d14f4248fc870ead91c3763f67f97e2afa7e207348569994d43099aae2"}'
GOLDEN_COLLISION_SWEEP_RESULT_HASH = "sha256:af9f86d14f4248fc870ead91c3763f67f97e2afa7e207348569994d43099aae2"
GOLDEN_CONTINUOUS_PATH_REQUEST_JSON = '{"source_assembly_id":"m13-3p-two-joint","source_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","model":{"model_id":"m13-3p-two-joint-model","joints":[{"joint_id":"joint-1","joint_kind":"revolute","parent_instance_id":"base","child_instance_id":"link-1","axis_origin_x_mm":0.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null},{"joint_id":"joint-2","joint_kind":"revolute","parent_instance_id":"link-1","child_instance_id":"link-2","axis_origin_x_mm":30.0,"axis_origin_y_mm":0.0,"axis_origin_z_mm":0.0,"axis_direction_x":0.0,"axis_direction_y":0.0,"axis_direction_z":1.0,"min_angle_deg":null,"max_angle_deg":null}],"evaluator_version":"multi-joint-forward-kinematics@1.0"},"path":{"model_id":"m13-3p-two-joint-model","waypoints":[{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":0.0,"joint-2":0.0}},{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":10.0,"joint-2":20.0}}]},"moving_instance_ids":["link-1","link-2"],"stationary_instance_ids":["base"],"required_clearance_mm":0.0,"proof_guard_mm":0.003,"volume_tolerance_mm3":0.001,"distance_tolerance_mm":0.002,"max_depth":0,"minimum_path_interval":0.1,"max_exact_evaluations":4096,"model_hash":"sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d","request_hash":"sha256:a3c3dca74655b11cc05d8ac86e923354ca264d432bf4f9e3c58eb999c9050581"}'
GOLDEN_CONTINUOUS_PATH_REQUEST_HASH = "sha256:a3c3dca74655b11cc05d8ac86e923354ca264d432bf4f9e3c58eb999c9050581"
GOLDEN_CONTINUOUS_EXACT_PAIR_JSON = '{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"}'
GOLDEN_CONTINUOUS_EXACT_PAIR_DIGEST = "sha256:105d8ebdbe8d26bb89b4ae8b71d337d12148c31080b233e1bec8e41a6e6bcf0c"
GOLDEN_CONTINUOUS_PAIR_CERTIFICATE_JSON = '{"moving_instance_id":"link-1","stationary_instance_id":"base","exact_distance_mm":100.0,"motion_bound_A_mm":2.7916407924687427,"motion_bound_B_mm":0.0,"pair_motion_bound_mm":2.7916407924687427,"certified_lower_clearance_mm":97.20835920753126}'
GOLDEN_CONTINUOUS_PAIR_CERTIFICATE_DIGEST = "sha256:2a2fd990e43e0bdc43a2eda9e75be0ae30823ceb5f4430aae06d3779a6c3d877"
GOLDEN_CONTINUOUS_WITNESS_JSON = '{"location":{"waypoint_index":0,"segment_index":null,"t":null},"configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":0.0,"joint-2":0.0}},"configuration_hash":"sha256:5e3e70d8bff9a5352777de2b16545e048313fa9f1e124c60a7e6d72c1c876e9e","transformed_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":1.0,"exact_distance_mm":0.0,"classification":"interference"}'
GOLDEN_CONTINUOUS_WITNESS_DIGEST = "sha256:43550cdf2c194d59148b214fdc2a6b250239007aaae4398f9cfe880db33ebdc0"
GOLDEN_CONTINUOUS_RESULT_JSON = '{"request_hash":"sha256:a3c3dca74655b11cc05d8ac86e923354ca264d432bf4f9e3c58eb999c9050581","source_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","model_hash":"sha256:ef8d93b108f766d7a452fe01abd0b3825710e1219d169ea4b8d7343e57e48f0d","proof_algorithm_version":"conservative-multi-joint-path-clearance-proof@1.0","reach_bound_algorithm_version":"articulated-descendant-reach-bound@1.0","status":"verified_clear","segment_results":[{"segment_index":0,"certified_intervals":[{"segment_index":0,"t_start":0.0,"t_end":1.0,"t_reference":0.5,"reference_configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":5.0,"joint-2":10.0}},"reference_configuration_hash":"sha256:48fea83cf8f2379685afd0cb2ed29fadcae9c4f4adda9670c673f0ae9822d126","transformed_assembly_hash":"sha256:79605655ebc42bafdf459b50d4db358343e25e7786e18c4bc1b6c7a7a5d8b363","pair_certificates":[{"moving_instance_id":"link-1","stationary_instance_id":"base","exact_distance_mm":100.0,"motion_bound_A_mm":2.7916407924687427,"motion_bound_B_mm":0.0,"pair_motion_bound_mm":2.7916407924687427,"certified_lower_clearance_mm":97.20835920753126},{"moving_instance_id":"link-2","stationary_instance_id":"base","exact_distance_mm":100.0,"motion_bound_A_mm":10.988432211073613,"motion_bound_B_mm":0.0,"pair_motion_bound_mm":10.988432211073613,"certified_lower_clearance_mm":89.01156778892638}]}],"unresolved_intervals":[]}],"certified_leaf_certificates":[{"segment_index":0,"t_start":0.0,"t_end":1.0,"t_reference":0.5,"reference_configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":5.0,"joint-2":10.0}},"reference_configuration_hash":"sha256:48fea83cf8f2379685afd0cb2ed29fadcae9c4f4adda9670c673f0ae9822d126","transformed_assembly_hash":"sha256:79605655ebc42bafdf459b50d4db358343e25e7786e18c4bc1b6c7a7a5d8b363","pair_certificates":[{"moving_instance_id":"link-1","stationary_instance_id":"base","exact_distance_mm":100.0,"motion_bound_A_mm":2.7916407924687427,"motion_bound_B_mm":0.0,"pair_motion_bound_mm":2.7916407924687427,"certified_lower_clearance_mm":97.20835920753126},{"moving_instance_id":"link-2","stationary_instance_id":"base","exact_distance_mm":100.0,"motion_bound_A_mm":10.988432211073613,"motion_bound_B_mm":0.0,"pair_motion_bound_mm":10.988432211073613,"certified_lower_clearance_mm":89.01156778892638}]}],"unresolved_intervals":[],"collision_witness":null,"reach_bounds":{"algorithm_version":"articulated-descendant-reach-bound@1.0","extent_algorithm_version":"component-local-geometry-extent@1.0","records":[{"instance_id":"link-1","influencing_joint_id":"joint-1","component_identity":"m13-3p-fixture-part@1","local_geometry_radius_mm":2.0,"offset_lengths_mm":[30.0],"reach_bound_mm":32.000000001,"chain_instance_ids":["base","link-1"],"algorithm_version":"articulated-descendant-reach-bound@1.0"},{"instance_id":"link-2","influencing_joint_id":"joint-1","component_identity":"m13-3p-fixture-part@1","local_geometry_radius_mm":2.0,"offset_lengths_mm":[30.0,30.0,20.0],"reach_bound_mm":82.000000001,"chain_instance_ids":["base","link-1","link-2"],"algorithm_version":"articulated-descendant-reach-bound@1.0"},{"instance_id":"link-2","influencing_joint_id":"joint-2","component_identity":"m13-3p-fixture-part@1","local_geometry_radius_mm":2.0,"offset_lengths_mm":[20.0],"reach_bound_mm":22.000000001,"chain_instance_ids":["link-1","link-2"],"algorithm_version":"articulated-descendant-reach-bound@1.0"}]},"exact_evaluations":[{"evaluation_index":0,"location":{"waypoint_index":0,"segment_index":null,"t":null},"configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":0.0,"joint-2":0.0}},"configuration_hash":"sha256:5e3e70d8bff9a5352777de2b16545e048313fa9f1e124c60a7e6d72c1c876e9e","transformed_assembly_hash":"sha256:74c549c928c92a410af898dd19b519af489c7c6c701167ff24095cd106396b17","pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"}],"produced_requested_clearance_witness":false},{"evaluation_index":1,"location":{"waypoint_index":1,"segment_index":null,"t":null},"configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":10.0,"joint-2":20.0}},"configuration_hash":"sha256:6e940bf704baa64de518cb4084947db8132932f450a85847e51ebc40cbd003f8","transformed_assembly_hash":"sha256:09f8c3f00ae8286b402a75714ad11803af27a8da02384ff4db237e70e6026e93","pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"}],"produced_requested_clearance_witness":false},{"evaluation_index":2,"location":{"waypoint_index":null,"segment_index":0,"t":0.5},"configuration":{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":5.0,"joint-2":10.0}},"configuration_hash":"sha256:48fea83cf8f2379685afd0cb2ed29fadcae9c4f4adda9670c673f0ae9822d126","transformed_assembly_hash":"sha256:79605655ebc42bafdf459b50d4db358343e25e7786e18c4bc1b6c7a7a5d8b363","pair_results":[{"moving_instance_id":"link-1","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"},{"moving_instance_id":"link-2","stationary_instance_id":"base","interference_volume_mm3":0.0,"exact_distance_mm":100.0,"classification":"positive_clearance"}],"produced_requested_clearance_witness":false}],"exact_evaluations_count":3,"cache_hits":0,"continuous_path_verified":true,"minimum_certified_lower_clearance_mm":89.01156778892638,"result_hash":"sha256:f5649783bd6eab312108192d2ad65b22ff4c8650c9b6ff0745432080645b3c68"}'
GOLDEN_CONTINUOUS_RESULT_HASH = "sha256:f5649783bd6eab312108192d2ad65b22ff4c8650c9b6ff0745432080645b3c68"


_DUMMY_PART = CadPartProgram(
    part_id="link",
    operations=(
        BasePlateOperation(
            operation_id="base", length_mm=10, width_mm=10, thickness_mm=2
        ),
    ),
)


def _three_body_assembly(
    assembly_id="m10-2-fixture",
    link1_offset_mm=30.0,
    link2_offset_mm=50.0,
):
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-1",
                part_id="link",
                placement=CadRigidTransform(
                    x_mm=link1_offset_mm, y_mm=0, z_mm=0
                ),
            ),
            CadComponentInstance(
                instance_id="link-2",
                part_id="link",
                placement=CadRigidTransform(
                    x_mm=link1_offset_mm + link2_offset_mm, y_mm=0, z_mm=0
                ),
            ),
        ),
    )


def _two_body_assembly(assembly_id="m10-2-two-body"):
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-1",
                part_id="link",
                placement=CadRigidTransform(x_mm=30, y_mm=0, z_mm=0),
            ),
        ),
    )


def _three_body_model(
    model_id="model-3",
    j1_origin=(0, 0, 0),
    j1_direction=(0, 0, 1),
    j2_origin=(30, 0, 0),
    j2_direction=(0, 0, 1),
):
    return KinematicModel(
        model_id=model_id,
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_origin_x_mm=j1_origin[0],
                axis_origin_y_mm=j1_origin[1],
                axis_origin_z_mm=j1_origin[2],
                axis_direction_x=j1_direction[0],
                axis_direction_y=j1_direction[1],
                axis_direction_z=j1_direction[2],
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
                axis_origin_x_mm=j2_origin[0],
                axis_origin_y_mm=j2_origin[1],
                axis_origin_z_mm=j2_origin[2],
                axis_direction_x=j2_direction[0],
                axis_direction_y=j2_direction[1],
                axis_direction_z=j2_direction[2],
            ),
        ),
    )


def _literal_json(value) -> str:
    return json.dumps(value.model_dump(mode="json"), separators=(",", ":"))


def _record_digest(value) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _configuration(model_id: str, **positions: float) -> JointConfiguration:
    return JointConfiguration(model_id=model_id, positions=dict(positions))


def _constant_measure(*, volume: float, distance: float):
    def measure(request, transformed):
        return tuple(
            (moving, stationary, volume, distance)
            for moving, stationary in request.pairs
        )

    return measure


def _fixtures():
    one_assembly = _two_body_assembly(assembly_id="m13-3p-one-joint")
    one_model = KinematicModel(
        model_id="m13-3p-one-joint-model",
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_origin_x_mm=5,
                axis_direction_x=1,
                axis_direction_y=1,
                axis_direction_z=1,
                min_angle_deg=-45,
                max_angle_deg=135,
            ),
        ),
    )
    one_configuration = _configuration(one_model.model_id, **{"joint-1": 30})

    two_assembly = _three_body_assembly(assembly_id="m13-3p-two-joint")
    two_model = _three_body_model(model_id="m13-3p-two-joint-model")
    two_configuration = _configuration(
        two_model.model_id, **{"joint-1": 30, "joint-2": 15}
    )
    return (
        one_assembly,
        one_model,
        one_configuration,
        two_assembly,
        two_model,
        two_configuration,
    )


def _continuous_request(assembly, model) -> MultiJointContinuousPathRequest:
    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            _configuration(model.model_id, **{"joint-1": 0, "joint-2": 0}),
            _configuration(model.model_id, **{"joint-1": 10, "joint-2": 20}),
        ),
    )
    return MultiJointContinuousPathRequest(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        path=path,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
        required_clearance_mm=0.0,
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        proof_guard_mm=0.003,
        minimum_path_interval=0.1,
        max_depth=0,
    )


def _extents():
    return {
        instance_id: TrustedLocalGeometryExtent(
            instance_id=instance_id,
            component_identity="m13-3p-fixture-part@1",
            local_radius_mm=2.0,
        )
        for instance_id in ("base", "link-1", "link-2")
    }


def _assert_literal_json(record, literal: str) -> None:
    assert type(record).model_validate_json(literal) == record
    assert record.model_dump(mode="json") == json.loads(literal)
    assert record.model_dump_json() == literal


def test_kinematic_v1_literals_and_intrinsic_hashes_are_unchanged():
    (
        one_assembly,
        one_model,
        one_configuration,
        two_assembly,
        two_model,
        two_configuration,
    ) = _fixtures()
    joint = one_model.joints[0]
    one_fk = MultiJointKinematicsService().evaluate(
        one_assembly, one_model, one_configuration
    )
    two_fk = MultiJointKinematicsService().evaluate(
        two_assembly, two_model, two_configuration
    )

    _assert_literal_json(joint, GOLDEN_REVOLUTE_JOINT_JSON)
    _assert_literal_json(two_model, GOLDEN_KINEMATIC_MODEL_JSON)
    assert kinematic_model_hash(two_model) == GOLDEN_KINEMATIC_MODEL_HASH
    _assert_literal_json(one_fk, GOLDEN_ONE_JOINT_FK_JSON)
    assert one_fk.result_hash == GOLDEN_ONE_JOINT_FK_RESULT_HASH
    _assert_literal_json(two_fk, GOLDEN_TWO_JOINT_FK_JSON)
    assert two_fk.result_hash == GOLDEN_TWO_JOINT_FK_RESULT_HASH


def test_discrete_collision_v1_literals_hashes_and_record_digest_are_unchanged():
    _, _, _, assembly, model, _ = _fixtures()
    request = MultiJointCollisionSweepRequest(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=(
            _configuration(model.model_id, **{"joint-1": 0, "joint-2": 0}),
            _configuration(model.model_id, **{"joint-1": 30, "joint-2": 15}),
        ),
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
    )
    sweep = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(
            _constant_measure(volume=0.0, distance=25.0)
        )
    ).execute(request, assembly)
    configuration_result = sweep.configuration_results[1]

    _assert_literal_json(request, GOLDEN_COLLISION_SWEEP_REQUEST_JSON)
    assert request.request_hash == GOLDEN_COLLISION_SWEEP_REQUEST_HASH
    _assert_literal_json(
        configuration_result, GOLDEN_COLLISION_CONFIGURATION_RESULT_JSON
    )
    assert _record_digest(configuration_result) == GOLDEN_COLLISION_CONFIGURATION_RESULT_DIGEST
    _assert_literal_json(sweep, GOLDEN_COLLISION_SWEEP_RESULT_JSON)
    assert sweep.result_hash == GOLDEN_COLLISION_SWEEP_RESULT_HASH


def test_continuous_path_v1_literals_hashes_and_record_digests_are_unchanged(monkeypatch):
    _, _, _, assembly, model, _ = _fixtures()
    request = _continuous_request(assembly, model)
    extents = _extents()
    service = MultiJointContinuousClearanceProofService(
        exact_measure=_constant_measure(volume=0.0, distance=100.0),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    )
    result = service.execute(request, assembly)
    exact_pair = result.exact_evaluations[0].pair_results[0]
    certificate = result.certified_leaf_certificates[0].pair_certificates[0]

    def reject_model_copy(*args, **kwargs):
        raise AssertionError("witness generation must use the validated request")

    monkeypatch.setattr(MultiJointContinuousPathRequest, "model_copy", reject_model_copy)
    witness_result = MultiJointContinuousClearanceProofService(
        exact_measure=_constant_measure(volume=1.0, distance=0.0),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)
    witness = witness_result.collision_witness
    assert witness is not None

    _assert_literal_json(request, GOLDEN_CONTINUOUS_PATH_REQUEST_JSON)
    assert request.request_hash == GOLDEN_CONTINUOUS_PATH_REQUEST_HASH
    _assert_literal_json(exact_pair, GOLDEN_CONTINUOUS_EXACT_PAIR_JSON)
    assert _record_digest(exact_pair) == GOLDEN_CONTINUOUS_EXACT_PAIR_DIGEST
    _assert_literal_json(certificate, GOLDEN_CONTINUOUS_PAIR_CERTIFICATE_JSON)
    assert _record_digest(certificate) == GOLDEN_CONTINUOUS_PAIR_CERTIFICATE_DIGEST
    _assert_literal_json(witness, GOLDEN_CONTINUOUS_WITNESS_JSON)
    assert _record_digest(witness) == GOLDEN_CONTINUOUS_WITNESS_DIGEST
    _assert_literal_json(result, GOLDEN_CONTINUOUS_RESULT_JSON)
    assert result.result_hash == GOLDEN_CONTINUOUS_RESULT_HASH


def test_v1_identity_literals_are_unchanged():
    assert MULTI_JOINT_FORWARD_KINEMATICS_VERSION == "multi-joint-forward-kinematics@1.0"
    assert MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION == "multi-joint-exact-collision-sweep@1.0"
    assert MULTI_JOINT_PATH_INTERPOLATION_VERSION == "piecewise-linear-joint-command-path@1.0"
    assert ARTICULATED_DESCENDANT_REACH_BOUND_VERSION == "articulated-descendant-reach-bound@1.0"
    assert MULTI_JOINT_CONTINUOUS_PATH_PROOF_VERSION == "conservative-multi-joint-path-clearance-proof@1.0"


def test_all_golden_payloads_parse_through_current_v1_classes():
    assert isinstance(
        RevoluteJointModel.model_validate_json(GOLDEN_REVOLUTE_JOINT_JSON),
        RevoluteJointModel,
    )
    assert isinstance(
        KinematicModel.model_validate_json(GOLDEN_KINEMATIC_MODEL_JSON),
        KinematicModel,
    )
    assert isinstance(
        KinematicForwardKinematicsResult.model_validate_json(GOLDEN_ONE_JOINT_FK_JSON),
        KinematicForwardKinematicsResult,
    )
    assert isinstance(
        MultiJointCollisionSweepRequest.model_validate_json(
            GOLDEN_COLLISION_SWEEP_REQUEST_JSON
        ),
        MultiJointCollisionSweepRequest,
    )
    assert isinstance(
        MultiJointCollisionConfigurationResult.model_validate_json(
            GOLDEN_COLLISION_CONFIGURATION_RESULT_JSON
        ),
        MultiJointCollisionConfigurationResult,
    )
    assert isinstance(
        MultiJointCollisionSweepResult.model_validate_json(
            GOLDEN_COLLISION_SWEEP_RESULT_JSON
        ),
        MultiJointCollisionSweepResult,
    )
    assert isinstance(
        MultiJointContinuousPathRequest.model_validate_json(
            GOLDEN_CONTINUOUS_PATH_REQUEST_JSON
        ),
        MultiJointContinuousPathRequest,
    )
    assert isinstance(
        ContinuousExactPairResult.model_validate_json(GOLDEN_CONTINUOUS_EXACT_PAIR_JSON),
        ContinuousExactPairResult,
    )
    assert isinstance(
        ContinuousPairCertificate.model_validate_json(
            GOLDEN_CONTINUOUS_PAIR_CERTIFICATE_JSON
        ),
        ContinuousPairCertificate,
    )
    assert isinstance(
        MultiJointContinuousCollisionWitness.model_validate_json(
            GOLDEN_CONTINUOUS_WITNESS_JSON
        ),
        MultiJointContinuousCollisionWitness,
    )
    assert isinstance(
        MultiJointContinuousClearanceProofResult.model_validate_json(
            GOLDEN_CONTINUOUS_RESULT_JSON
        ),
        MultiJointContinuousClearanceProofResult,
    )


def test_absent_discriminators_parse_to_v1_classes():
    joint_payload = json.loads(GOLDEN_REVOLUTE_JOINT_JSON)
    model_payload = json.loads(GOLDEN_KINEMATIC_MODEL_JSON)

    assert isinstance(parse_revolute_joint_model(joint_payload), RevoluteJointModel)
    assert isinstance(parse_kinematic_model(model_payload), KinematicModel)


def test_v2_requires_its_explicit_discriminator():
    joint_payload = {
        "joint_id": "J1",
        "joint_kind": "revolute",
        "parent_body_id": "B1",
        "child_body_id": "B2",
    }
    model_payload = {
        "model_id": "M2",
        "bodies": [],
        "joints": [],
        "evaluator_version": "multi-joint-forward-kinematics@2.0",
        "transform_agreement_version": "rigid-transform-agreement@1.0",
    }

    with pytest.raises(ValueError):
        parse_revolute_joint_model(joint_payload)
    with pytest.raises(ValueError):
        parse_kinematic_model(model_payload)


def test_v1_rejects_v2_body_and_endpoint_fields():
    joint_payload = json.loads(GOLDEN_REVOLUTE_JOINT_JSON)
    joint_payload["schema_version"] = "revolute-joint-model@1"
    joint_payload["parent_body_id"] = "B1"
    model_payload = json.loads(GOLDEN_KINEMATIC_MODEL_JSON)
    model_payload["schema_version"] = "kinematic-model@1"
    model_payload["bodies"] = []

    with pytest.raises(ValueError):
        parse_revolute_joint_model(joint_payload)
    with pytest.raises(ValueError):
        parse_kinematic_model(model_payload)


def test_v2_rejects_v1_instance_endpoint_fields():
    joint_payload = {
        "schema_version": "revolute-joint-model@2",
        "joint_id": "J1",
        "joint_kind": "revolute",
        "parent_body_id": "B1",
        "child_body_id": "B2",
        "parent_instance_id": "I1",
    }

    with pytest.raises(ValueError):
        parse_revolute_joint_model(joint_payload)


def test_v2_wire_payload_has_explicit_semantic_fields_in_order():
    joint = RevoluteJointModelV2(
        joint_id="J1",
        joint_kind="revolute",
        parent_body_id="B1",
        child_body_id="B2",
        axis_origin_x_mm=5,
        axis_direction_x=1,
        axis_direction_y=1,
        axis_direction_z=1,
        min_angle_deg=-45,
        max_angle_deg=135,
    )

    payload = kinematic_model_wire_payload(
        KinematicModelV2(
            model_id="M2",
            bodies=(),
            joints=(joint,),
        )
    )["joints"][0]

    assert tuple(payload) == (
        "schema_version",
        "joint_id",
        "joint_kind",
        "parent_body_id",
        "child_body_id",
        "axis_origin_x_mm",
        "axis_origin_y_mm",
        "axis_origin_z_mm",
        "axis_direction_x",
        "axis_direction_y",
        "axis_direction_z",
        "min_angle_deg",
        "max_angle_deg",
    )
    assert payload["schema_version"] == "revolute-joint-model@2"
    assert payload["joint_id"] == "J1"
    assert payload["axis_direction_x"] == pytest.approx(1 / 3**0.5)
