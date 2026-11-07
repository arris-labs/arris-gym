"""The CadQuery-compatible subset over arris.build. Imports only arris."""


class UnsupportedApi(Exception):
    """A program called something outside the `cq` subset.

    The message names the call. The sandbox decides the status
    `unsupported_api` from this type alone, never from its text.
    """
