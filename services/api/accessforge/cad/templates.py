"""Fixed CadQuery generators for the reviewed MVP releases.

No function in this module reads user files, imports a user module, or evaluates
template text.  Every dimensional value is validated by the static registry
before it reaches these generators.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

from accessforge.cad.registry import TemplateRegistryError


def _cadquery() -> Any:
    """Load CadQuery after VTK's native symbols are initialised.

    CadQuery 2.8's pip OCP wheel expects the VTK module to be importable before
    its optional IVtk bridge is loaded.  This is backend-only and exercised by
    the compiler smoke test; the browser never sees either dependency.
    """

    importlib.import_module("vtk")
    return importlib.import_module("cadquery")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TemplateRegistryError(message)


def build_pull_tab_extender(parameters: Mapping[str, float]) -> Any:
    """Create a flat, non-load-bearing pull-tab extension with an attachment slot."""

    outer_width = parameters["pull_loop_outer_width"]
    outer_height = parameters["pull_loop_outer_height"]
    slot_width = parameters["attachment_slot_width"] + 2 * parameters["attachment_clearance"]
    slot_height = parameters["attachment_slot_height"] + 2 * parameters["attachment_clearance"]
    thickness = parameters["body_thickness"]
    edge_radius = parameters["edge_radius"]
    _require(
        outer_width >= slot_width + 2 * edge_radius,
        "The pull-tab width leaves insufficient material around the attachment slot.",
    )
    _require(
        outer_height >= slot_height + 4 * edge_radius,
        "The pull-tab height leaves insufficient material around the attachment slot.",
    )
    _require(
        edge_radius <= min(outer_width, outer_height) / 2,
        "The requested pull-tab edge radius is too large for its dimensions.",
    )
    cq = _cadquery()
    body = cq.Workplane("XY").box(outer_width, outer_height, thickness)
    # The attachment slot is deliberately a simple through-cut.  It is not a
    # locking feature and does not make a claim about a zipper's force path.
    body = (
        body.faces(">Z")
        .workplane()
        .center(0, -outer_height / 4)
        .rect(slot_width, slot_height)
        .cutThruAll()
    )
    if edge_radius > 0:
        body = body.edges("|Z").fillet(edge_radius)
    return body


def _build_split_sleeve(
    *,
    inner_diameter: float,
    outer_diameter: float,
    length: float,
    slit_width: float,
    edge_radius: float,
    context: str,
) -> Any:
    _require(
        outer_diameter > inner_diameter,
        f"The {context} outer diameter must exceed its inner diameter.",
    )
    wall = (outer_diameter - inner_diameter) / 2
    _require(
        wall >= 2.4,
        f"The {context} wall must be at least 2.4 mm in this provisional release.",
    )
    _require(slit_width < outer_diameter / 2, f"The {context} slit is too wide.")
    _require(
        edge_radius <= min(wall / 2, length / 4),
        f"The {context} edge radius is too large for its wall or length.",
    )
    cq = _cadquery()
    sleeve = (
        cq.Workplane("XY").circle(outer_diameter / 2).circle(inner_diameter / 2).extrude(length)
    )
    # This is an open C-sleeve, not a snap/locking mechanism.  The cut crosses
    # the positive X side and has a bounded width supplied by the fixed schema.
    cutter = (
        cq.Workplane("XY")
        .center(outer_diameter / 2 - slit_width / 2, 0)
        .rect(slit_width, outer_diameter + 2)
        .extrude(length + 2, both=True)
    )
    sleeve = sleeve.cut(cutter)
    if edge_radius > 0:
        sleeve = sleeve.edges("|Z").fillet(edge_radius)
    return sleeve


def build_cylindrical_grip_thickener(parameters: Mapping[str, float]) -> Any:
    """Create a bounded open sleeve for a cylindrical, non-safety-critical grip."""

    return _build_split_sleeve(
        inner_diameter=parameters["inner_diameter"],
        outer_diameter=parameters["outer_diameter"],
        length=parameters["grip_length"],
        slit_width=parameters["slit_width"],
        edge_radius=parameters["edge_radius"],
        context="cylindrical grip thickener",
    )


def build_handle_sleeve(parameters: Mapping[str, float]) -> Any:
    """Create a bounded open sleeve for an ordinary, non-safety-critical handle."""

    return _build_split_sleeve(
        # The manifest defines fit clearance as radial allowance, so the
        # generated opening adds it on both sides of the measured diameter.
        inner_diameter=parameters["handle_diameter"] + 2 * parameters["fit_clearance"],
        outer_diameter=parameters["outer_diameter"],
        length=parameters["sleeve_length"],
        slit_width=parameters["slit_width"],
        edge_radius=parameters["edge_radius"],
        context="handle sleeve",
    )


TemplateGenerator = Callable[[Mapping[str, float]], Any]


_GENERATORS: dict[str, TemplateGenerator] = {
    "pull_tab_extender": build_pull_tab_extender,
    "cylindrical_grip_thickener": build_cylindrical_grip_thickener,
    "handle_sleeve": build_handle_sleeve,
}


def build_template(template_id: str, parameters: Mapping[str, float]) -> Any:
    generator = _GENERATORS.get(template_id)
    if generator is None:
        raise TemplateRegistryError("The requested template is not executable.")
    return generator(parameters)
