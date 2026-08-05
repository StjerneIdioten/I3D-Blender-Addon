from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import logging

    from ..ctx import ExportContext
    from ..ir import SceneNode


PassFn = Callable[["ExportContext"], None]
NodePassFn = Callable[["ExportContext", "SceneNode"], None]


@dataclass(frozen=True, slots=True)
class ResolvePass:
    name: str
    run: PassFn


@dataclass(frozen=True, slots=True)
class ResolvePhase:
    name: str
    passes: tuple[ResolvePass, ...]


def resolve_all(ctx: ExportContext, phases: tuple[ResolvePhase, ...] | None = None) -> None:
    """Run all registered resolve phases."""
    if phases is None:
        phases = RESOLVE_PHASES

    logger = ctx.ctx_logger(prefix="resolve")
    logger.debug("Resolving %d scene nodes", len(ctx.ir.scene_nodes))

    for phase in phases:
        logger.debug("Resolve phase: %s", phase.name)

        for resolve_pass in phase.passes:
            label = f"{phase.name}.{resolve_pass.name}"
            with _timed(logger, label):
                try:
                    resolve_pass.run(ctx)
                except Exception:
                    logger.exception("Resolve pass failed: %s", label)
                    raise

    _log_summary(ctx, logger)


def ctx_pass(name: str, run: PassFn) -> ResolvePass:
    return ResolvePass(name, run)


def node_pass(name: str, run: NodePassFn, *, emitted_only: bool = False) -> ResolvePass:
    return ResolvePass(name, _per_node(run, emitted_only=emitted_only))


def phase(name: str, *passes: ResolvePass) -> ResolvePhase:
    return ResolvePhase(name, passes)


def _per_node(fn: NodePassFn, *, emitted_only: bool = False) -> PassFn:
    """Adapt a node pass into an export-context pass."""

    def run(ctx: ExportContext) -> None:
        for node in tuple(ctx.ir.iter_nodes(emitted_only=emitted_only)):
            fn(ctx, node)

    return run


def _validate_ir(ctx: ExportContext) -> None:
    ctx.ir.validate_basic()


RESOLVE_PHASES: tuple[ResolvePhase, ...] = (
    phase(
        "validate",
        ctx_pass("basic_ir", _validate_ir),
    ),
)


@contextmanager
def _timed(logger: logging.LoggerAdapter, label: str) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    finally:
        logger.debug("%s: %.2f ms", label, (perf_counter() - started_at) * 1000.0)


def _log_summary(ctx: ExportContext, logger: logging.LoggerAdapter) -> None:
    kinds = Counter(node.kind for node in ctx.ir.iter_nodes(emitted_only=True))
    logger.debug(
        "Resolve summary: emitted=%d/%d kinds=%s",
        sum(kinds.values()),
        len(ctx.ir.scene_nodes),
        {kind.name: count for kind, count in kinds.items()},
    )
