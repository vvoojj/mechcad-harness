from .models import BackendProvenance


def provenance_from_identity(identity, *, library_version: str | None = None) -> BackendProvenance:
    return BackendProvenance(
        backend_name=identity.name,
        backend_adapter_version=identity.adapter_version,
        library_name=identity.library_name,
        library_version=library_version or identity.library_version,
        library_source=identity.library_source,
        library_revision=identity.library_revision,
    )
