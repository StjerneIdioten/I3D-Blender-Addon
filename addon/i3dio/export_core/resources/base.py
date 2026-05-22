from __future__ import annotations

from typing import Generic, TypeVar

E = TypeVar("E")
K = TypeVar("K")


class IdEntryTable(Generic[E, K]):
    _by_key: dict[K, int]
    _entries: dict[int, E]

    def get_id(self, key: K) -> int | None:
        return self._by_key.get(key)

    def register(self, *, key: K, entry_id: int, entry: E) -> None:
        self._by_key[key] = entry_id
        self._entries[entry_id] = entry

    def get_entry(self, entry_id: int) -> E:
        return self._entries[entry_id]

    def entries(self) -> list[E]:
        # stable output order by numeric id
        return [self._entries[k] for k in sorted(self._entries)]

    def __len__(self) -> int:
        return len(self._entries)
