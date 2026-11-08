"""`UnsupportedApi`: a program reached outside the `cq` subset. Private."""


class UnsupportedApi(Exception):
    """A program called something outside the `cq` subset.

    The message names the call as the census writes it (`Workplane.sphere`,
    `cq.Sketch`). The sandbox decides the status `unsupported_api` from this
    type alone, never from its text.
    """


def is_python_name(name: str) -> bool:
    """Whether `name` belongs to Python or to arris-gym, never to CadQuery's API.

    A name with a leading underscore (a dunder protocol lookup such as
    `__deepcopy__`, or one of this package's private modules) answers
    `AttributeError` as Python expects, never `UnsupportedApi`.
    """
    return name.startswith("_")
