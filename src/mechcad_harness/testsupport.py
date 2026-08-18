from .materials import MaterialDataAuthority, MaterialPropertyName, MaterialPropertyStatus


def material_output(*, modulus=True, density=True):
    from .materials import MaterialPropertyValue

    return {
        "canonical_name": "Alu_G7075_T6",
        "category": "metal",
        "family": "aluminum",
        "authority": "typical_reference",
        "density": {"property": "density", "unit": "kg/m^3", "status": "available" if density else "missing", "min_value": 2810 if density else None, "max_value": 2810 if density else None, "representative_value": 2810 if density else None, "authority": "typical_reference", "source": "test", "value_semantics": "representative" if density else None},
        "properties": {"elastic_modulus": {"property": "elastic_modulus", "unit": "GPa", "status": "available" if modulus else "missing", "min_value": 68 if modulus else None, "max_value": 72 if modulus else None, "authority": "typical_reference", "source": "test"}},
        "backend_provenance": {"backend_name": "bd-materials", "backend_adapter_version": "0.1.0", "library_name": "bd_materials", "library_version": "0.2.4", "library_source": "pypi"},
    }


def geometry_output():
    return {"section_type": "rectangle", "area_mm2": 5000, "centroid_x_mm": 25, "centroid_y_mm": 50, "ixx_centroid_mm4": 4166666.666666667, "iyy_centroid_mm4": 1041666.666666667, "ixy_centroid_mm4": 0, "perimeter_mm": 300, "radius_of_gyration_x_mm": 28.8675, "radius_of_gyration_y_mm": 14.4338, "mesh_metadata": {"mesh_size_mm2": 5}, "backend_provenance": {"backend_name": "section-properties", "backend_adapter_version": "0.1.0", "library_name": "sectionproperties", "library_version": "3.10.2", "library_source": "pypi"}}
