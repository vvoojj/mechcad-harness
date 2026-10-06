"""Authority contract for Rotator V2 Epic 01 S1."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    PROJECT_ROOT / "projects" / "rotator_v2" / "epic_01" / "authority_manifest.json"
)
PROJECT_DOCUMENT_PATHS = (
    PROJECT_ROOT / "projects" / "rotator_v2" / "requirements" / "MECHANICAL_CONSTRAINTS.md",
    PROJECT_ROOT / "projects" / "rotator_v2" / "5840-31ZY_COMPONENT_DATA.md",
)
CONFIRMATION_CHECKLIST_PATH = PROJECT_ROOT / "projects" / "rotator_v2" / "CONFIRMATION_CHECKLIST.md"


def test_s1_authority_manifest_freezes_reconciled_candidate_01_authority() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["epic"] == "ROTATOR_V2_EPIC_01_PHYSICAL_MECHANISM_AND_CANDIDATE_EVALUATION"
    assert manifest["readiness"] == {
        "input": "PASS",
        "cad_m10": "PASS",
        "m11": "FAIL",
    }
    assert manifest["motor_geometry"] == {
        "active": "components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step",
        "raw_source": "motor_az(1).step",
        "raw_source_status": "SUPERSEDED_PROVENANCE_ONLY",
    }
    assert manifest["drive_architecture"] == {
        "timing_belt": "NOT_USED",
        "az": "EXTERNAL_SPUR_REDUCTION",
        "el": "EXTERNAL_SPUR_REDUCTION",
        "historical_el_direct_coupling": "SUPERSEDED",
    }
    assert manifest["candidate_traceability"] == [
        "initial frozen design",
        "FINAL-CRIT-01",
        "Candidate 01 physical-realizability revision",
    ]
    assert manifest["classification_rule"] == {
        "default": "DESIGN_VARIABLE/FIRST_CANDIDATE_SELECTION",
        "exception": "explicitly source-derived authority only",
    }
    assert manifest["holds"] == {
        "m11": "FAIL",
        "manufacturing_release": "HOLD",
        "selection_promotion": "HOLD",
        "m4_thread_depth": "DEFERRED_MANUFACTURING_HOLD_POINT",
        "motor_mass_and_load_limits": "UNRESOLVED_NONBLOCKING",
    }

    transmission = manifest["frozen_candidate_01"]["common_transmission"]
    assert transmission["classification"] == "DESIGN_VARIABLE/FIRST_CANDIDATE_SELECTION"
    assert transmission["pinion_teeth"] == 30
    assert transmission["driven_teeth"] == 36
    assert transmission["module_mm"] == 2.0
    assert transmission["pressure_angle_deg"] == 20
    assert transmission["face_width_mm"] == 12
    assert transmission["center_distance_mm"] == 66
    assert transmission["external_ratio"] == 1.2
    assert transmission["pinion_outside_diameter_mm"] == 64
    assert transmission["driven_outside_diameter_mm"] == 76
    assert transmission["pinion_engagement_mm"] == 12
    assert transmission["pinion_adapter_interface"] == {
        "bore_mm": 8.0,
        "shaft_form": "D_SHAFT",
        "engagement_mm": 12,
        "no_thread_or_key_claim": True,
    }
    assert transmission["maximum_usable_coupling_zone_mm"] == {
        "value": 13,
        "classification": "DECLARED_PROJECT_INTERFACE_REQUIREMENT",
    }

    geometry = manifest["frozen_candidate_01"]["geometry"]
    assert geometry["classification"] == "DESIGN_VARIABLE/FIRST_CANDIDATE_SELECTION"
    assert geometry["envelope_bounds"] == {
        "base_maximum_mm": [350, 350],
        "stated_body_bound_mm": [500, 500, 650],
    }
    assert geometry["az_shaft"] == {
        "outer_diameter_mm": 60,
        "clear_bore_mm": 40,
        "length_mm": 220,
        "axial_extent": "Z=30..250",
    }
    assert geometry["az_support_centers_mm"] == [60, 180]
    assert geometry["az_journals"] == {"outer_diameter_mm": 50, "length_mm": 20}
    assert geometry["az_support"] == {
        "bore_mm": 50,
        "outer_diameter_mm": 80,
        "radial_width_mm": 15,
        "axial_length_mm": 20,
    }
    assert geometry["az_hub"] == {
        "outer_diameter_mm": 70,
        "length_mm": 30,
        "bore_mm": 60,
        "axial_extent": "Z=205..235",
    }
    assert geometry["az_gear_faces"] == {"center_mm": 226, "axial_extent": "Z=220..232"}
    assert geometry["az_base"] == {"size_mm": [350, 350, 20]}
    assert geometry["az_carrier"] == {
        "outer_size_mm": [120, 120, 200],
        "axial_extent": "Z=20..220",
        "retained_posts_xy_extents": [
            ["-60..-40", "-60..-40"],
            ["-60..-40", "40..60"],
            ["40..60", "-60..-40"],
        ],
        "station_a": "X/Y=-60..60,Z=50..70 minus D50",
        "station_b_left_rail": "X=-60..-35,Y=-60..60,Z=170..190",
        "corridor_diameter_mm": 40,
        "support_b_overlap_mm3": 2616.094617,
    }
    assert geometry["az_deck"] == {"size_mm": [220, 220, 12], "axial_extent": "Z=250..262"}
    assert geometry["el_shaft"] == {
        "outer_diameter_mm": 50,
        "length_mm": 300,
        "axial_extent": "Y=-150..150",
    }
    assert geometry["el_support_centers_mm"] == [-100, 100]
    assert geometry["el_journals"] == {"outer_diameter_mm": 50, "length_mm": 20}
    assert geometry["el_support"] == {
        "bore_mm": 50,
        "outer_diameter_mm": 80,
        "radial_width_mm": 15,
        "axial_length_mm": 20,
    }
    assert geometry["el_hub"] == {
        "outer_diameter_mm": 70,
        "length_mm": 30,
        "bore_mm": 50,
        "axial_extent": "Y=120..150",
    }
    assert geometry["el_gear_faces"] == {"center_mm": 141, "axial_extent": "Y=135..147"}
    assert geometry["el_fork"] == {
        "negative_y_arm": "X=-70..70,Y=-110..-90,Z=220..520",
        "positive_y_arm": "X=-70..40,Y=90..110,Z=220..520",
        "support_b_overlap_mm3": 30630.528373,
    }
    assert geometry["az_axis_direction"] == "+Z"
    assert geometry["el_axis_direction"] == "+Y"
    assert geometry["motor_axis_offset_x_mm"] == 66
    assert geometry["el_axis_height_mm"] == 520
    assert geometry["az_keep_out"] == {
        "diameter_mm": 30,
        "axial_extent": "Z=30..130",
        "hard_minimum_mm": 24,
        "preferred_mm": 30,
        "axial_reserve_mm": 100,
    }
    assert geometry["structural_thicknesses_mm"] == {
        "az_plate": 12,
        "el_plate": 20,
    }
    assert geometry["az_motor_plate"] == {
        "size_mm": [100, 80, 3],
        "x_extent": "16..116",
        "y_extent": "-40..40",
        "z_extent": "216.995646..219.995646",
        "center_opening_diameter_mm": 20,
        "mount_hole_diameter_mm": 4.5,
        "topology": {
            "central_opening": "D20 through",
            "mount_holes": "four D4.5 at transformed accepted M4 centers",
            "structural_contact": "Y=-40,X=40..60,Z=216.995646..219.995646",
            "pinion_separation_mm": 0.004354,
        },
    }
    assert geometry["el_motor_plate"] == {
        "size_mm": [100, 80, 3],
        "x_extent": "16..116",
        "y_extent": "131.995646..134.995646",
        "z_extent": "480..560",
        "center_opening_diameter_mm": 20,
        "mount_hole_diameter_mm": 4.5,
        "topology": {
            "central_opening": "D20 through",
            "mount_holes": "four D4.5 at transformed accepted M4 centers",
            "bridge_plate_contact": "Y=131.995646,X=16..40,Z=480..560",
            "pinion_separation_mm": 0.004354,
        },
    }
    assert geometry["el_edge_bridge"] == {
        "solid_extent": "X=16..40,Y=110..131.995646,Z=480..560",
        "positive_y_arm_contact": "Y=110,X=16..40,Z=480..520",
        "plate_contact": "Y=131.995646,X=16..40,Z=480..560",
    }
    assert geometry["carrier"]["pads"] == [
        {"y_extent": "-180..-120", "x_extent": "-60..60", "z_extent": "510..530"},
        {"y_extent": "-85..-65", "x_extent": "-60..60", "z_extent": "510..530"},
        {"y_extent": "-30..30", "x_extent": "-60..60", "z_extent": "510..530"},
        {"y_extent": "65..85", "x_extent": "-60..40", "z_extent": "510..530"},
        {"y_extent": "120..180", "x_extent": "-60..29", "z_extent": "510..530"},
    ]
    assert geometry["carrier"]["fore_aft_adjustment_per_antenna_mount_mm"] == [-100, 100]
    assert geometry["carrier"]["rail"] == "X=-60..-50,Y=-180..180,Z=525..530"
    assert geometry["carrier"]["rail_and_pad_envelope"] == "X=-60..60,Y=-180..180,Z=510..530"
    assert geometry["carrier"]["complete_assembly_z_extent"] == "485..555"
    assert geometry["carrier"]["boss"] == {
        "center_mm": [0, 0, 520],
        "axis": "+Y",
        "outer_diameter_mm": 70,
        "bore_mm": 50,
        "length_mm": 30,
    }
    assert geometry["carrier"]["three_antenna_positions_mm"] == [[0, -150, 0], [0, 0, 0], [0, 150, 0]]
    assert geometry["carrier"]["two_antenna_positions_mm"] == [[0, -75, 0], [0, 75, 0]]
    assert geometry["interfaces"] == {
        "az_shaft_hub": {"nominal_bore_mm": 60, "axial_engagement_mm": 30},
        "el_shaft_hub": {"nominal_bore_mm": 50, "axial_engagement_mm": 30},
        "az_gear_mesh": {"pitch_diameters_mm": [60, 72], "face_overlap_mm": 12},
        "el_gear_mesh": {"pitch_diameters_mm": [60, 72], "face_overlap_mm": 12},
        "motor_mount": {"nominal_pitch_mm": [28, 40], "thread": "M4"},
    }

    placements = manifest["frozen_candidate_01"]["motor_target_transforms"]
    assert placements == {
        "source_output_frame": {
            "origin_mm": [0.093360, -5.137859, 30.043545],
            "axes": {"x": "+X", "y": "+Y", "z": "+Z"},
        },
        "motor_AZ": {
            "output_target_origin_mm": [66, 0, 220],
            "source_to_candidate_axes": {"x": "+X", "y": "+Y", "z": "+Z"},
            "mount_target_origin_mm": [66, 0, 216.995646],
        },
        "motor_EL": {
            "output_target_origin_mm": [66, 135, 520],
            "source_to_candidate_axes": {"x": "+X", "y": "-Z", "z": "+Y"},
            "mount_target_origin_mm": [66, 131.995646, 520],
        },
    }


def test_s1_project_legacy_gear_and_envelope_guidance_defers_to_epic_01_authority() -> None:
    for document_path in PROJECT_DOCUMENT_PATHS:
        document = document_path.read_text(encoding="utf-8")

        assert "Historical pre-freeze guidance" in document
        assert "superseded for frozen Candidate 01" in document
        assert "epic_01/authority_manifest.json" in document


def test_s1_confirmation_checklist_marks_launch_envelopes_superseded_for_candidate_01() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checklist = CONFIRMATION_CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "Historical preliminary envelope guidance (superseded for frozen Candidate 01)" in checklist
    assert "base maximum `380 x 340 mm`" in checklist
    assert "mechanism body maximum excluding antennas/mast `400 x 400 x 650 mm`" in checklist
    assert "`epic_01/authority_manifest.json`" in checklist
    envelope_bounds = manifest["frozen_candidate_01"]["geometry"]["envelope_bounds"]
    assert envelope_bounds == {
        "base_maximum_mm": [350, 350],
        "stated_body_bound_mm": [500, 500, 650],
    }
    assert "base `350 x 350 mm`" in checklist
    assert "body bound `500 x 500 x 650 mm`" in checklist
