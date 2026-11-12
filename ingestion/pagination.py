"""Bounded list-page configuration; no source access or business semantics."""


def page_size(value, maximum):
    if type(value) is int:
        size = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        size = int(value)
    else:
        raise ValueError('page size must be an integer')
    if not 1 <= size <= maximum:
        raise ValueError(f'page size must be 1..{maximum}')
    return size
