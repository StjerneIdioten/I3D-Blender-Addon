from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from typing import Generic, TypeVar

KeyT = TypeVar("KeyT", bound=Hashable)
EntryT = TypeVar("EntryT")


@dataclass(slots=True)
class IdEntryTable(Generic[KeyT, EntryT]):
    """Base table for exported resources with stable numeric IDs."""

    _by_key: dict[KeyT, int] = field(default_factory=dict, init=False, repr=False)
    _entries: dict[int, EntryT] = field(default_factory=dict, init=False, repr=False)

    def get_id(self, key: KeyT) -> int | None:
        return self._by_key.get(key)

    def get_entry(self, entry_id: int) -> EntryT:
        return self._entries[entry_id]

    def get_existing(self, key: KeyT) -> EntryT | None:
        if (entry_id := self.get_id(key)) is None:
            return None
        return self._entries[entry_id]

    def register(self, *, key: KeyT, entry_id: int, entry: EntryT) -> None:
        """Register a new entry with the given key and ID. Raises if the key or ID is already registered."""
        if key in self._by_key:
            raise ValueError(f"{type(self).__name__}: key is already registered: {key!r}")
        if entry_id in self._entries:
            raise ValueError(f"{type(self).__name__}: entry ID is already registered: {entry_id}")

        self._by_key[key] = entry_id
        self._entries[entry_id] = entry

    def get_or_create(self, key: KeyT, factory: Callable[[], tuple[int, EntryT]]) -> tuple[int, EntryT, bool]:
        """Return an existing entry for key, or create and register a new one.
        Returns:
            A tuple of (entry_id, entry, created) where created is True if a new entry was created.
        """
        if (entry_id := self.get_id(key)) is not None:
            return entry_id, self._entries[entry_id], False

        entry_id, entry = factory()
        self.register(key=key, entry_id=entry_id, entry=entry)
        return entry_id, entry, True

    def iter_items(self) -> Iterator[tuple[int, EntryT]]:
        """Iterate ID/entry pairs in stable numeric ID order."""
        for entry_id in sorted(self._entries):
            yield entry_id, self._entries[entry_id]

    def iter_entries(self) -> Iterator[EntryT]:
        """Iterate entries in stable numeric ID order."""
        for _, entry in self.iter_items():
            yield entry

    def entries(self) -> list[EntryT]:
        """Return entries in stable numeric ID order."""
        return list(self.iter_entries())

    def __len__(self) -> int:
        return len(self._entries)
