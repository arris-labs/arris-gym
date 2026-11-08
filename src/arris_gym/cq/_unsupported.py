"""`UnsupportedApi`: a program reached outside the `cq` subset. Private."""


class UnsupportedApi(Exception):
    """A program called something outside the `cq` subset.

    The message names the call as the census writes it (`Workplane.sphere`,
    `cq.Sketch`). The sandbox decides the status `unsupported_api` from this
    type alone, never from its text.
    """
