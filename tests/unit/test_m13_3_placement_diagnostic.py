from __future__ import annotations

from test_m13_3_promotion import _promotion_chain


def test_diagnostic(tmp_path):
    candidate, cad, bridge, _, _, request, _, _ = _promotion_chain(tmp_path)
    print("CANDIDATE REALIZATION", candidate.realization.model_dump(mode="json"))
    print("CAD MAPPINGS", [item.model_dump(mode="json") for item in cad.mappings])
    print("CAD REQUEST", getattr(cad, "request_hash", None))
    print("PLACEMENT DERIVATIONS", getattr(cad, "placement_derivations_hash", None))
    print("BRIDGE BODIES", bridge.model.model_dump(mode="json")["bodies"])
    print("REQUEST", request.model_dump(mode="json"))
