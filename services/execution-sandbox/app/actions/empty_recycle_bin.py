# Deprecated alias: empty_recycle_bin -> empty_trash
from .empty_trash import EmptyTrashParams as EmptyRecycleBinParams
from .empty_trash import empty_trash as empty_recycle_bin

__all__ = ["EmptyRecycleBinParams", "empty_recycle_bin"]
