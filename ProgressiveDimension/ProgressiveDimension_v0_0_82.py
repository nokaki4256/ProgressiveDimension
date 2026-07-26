# -*- coding: utf-8 -*-
"""
ProgressiveDimension.py

Progressive Dimension for FreeCAD TechDraw
Version: 0.0.82
"""

import math
from dataclasses import dataclass, field
from enum import Enum, auto

import FreeCAD as App
import FreeCADGui as Gui
import TechDraw

VERSION = "0.0.82"

DEBUG = True

class DimensionMode(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()

class LogLevel(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()

def log(msg, level=LogLevel.INFO):
    if not DEBUG and level == LogLevel.INFO:
        return
    prefix={LogLevel.INFO:"INFO",LogLevel.WARNING:"WARN",LogLevel.ERROR:"ERROR"}[level]
    App.Console.PrintMessage(f"[{prefix}] {msg}\n")

@dataclass
class GeometryItem:
    name:str=""
    point2d:object=None
    distance:float=0.0
    order:int=0

@dataclass
class LayoutItem:
    text_x:float=0.0
    text_y:float=0.0
    bend_point:object=None
    visible:bool=True

class ProgressiveDimensionEngine:
    def __init__(self):
        self.mode=None
        self.view=None
        self.geometry=[]
        self.layout=[]

    def reset(self):
        self.geometry.clear()
        self.layout.clear()

    def execute(self):
        raise NotImplementedError

log(f"Progressive Dimension {VERSION} loaded.")


# ============================================================
# v0.0.3
# Selection Engine (Skeleton)
# ============================================================

class SelectionEngine:
    """Collect and validate TechDraw selections."""

    def __init__(self):
        self.view = None
        self.items = []

    def clear(self):
        self.items.clear()

    def find_active_view(self):
        for obj in App.ActiveDocument.Objects:
            if getattr(obj, "TypeId", "") == "TechDraw::DrawViewPart":
                self.view = obj
                return obj
        return None

    def validate(self):
        if self.view is None:
            raise RuntimeError("No TechDraw::DrawViewPart found.")

        return True


class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def __init__(self):
        super().__init__()
        self.selection = SelectionEngine()

    def initialize(self):
        self.selection.find_active_view()
        self.selection.validate()
        self.view = self.selection.view



# ============================================================
# v0.0.4
# Selection API
# ============================================================

    def collect_selection(self):
        """Collect current GUI selections."""
        self.clear()
        selection = Gui.Selection.getSelectionEx()
        self.items.extend(selection)
        return self.items

    def first_view(self):
        for item in self.items:
            obj = getattr(item, "Object", None)
            if obj and getattr(obj, "TypeId", "") == "TechDraw::DrawViewPart":
                self.view = obj
                return obj
        return self.find_active_view()


class GeometryEngine:

    def __init__(self, view):
        self.view = view

    def vertex_from_selection(self, subname):
        return self.view.getVertexBySelection(subname)

    def edge_from_selection(self, subname):
        return self.view.getEdgeBySelection(subname)


# ============================================================
# v0.0.5
# Geometry Collection
# ============================================================

class GeometryCollector:

    def __init__(self, view):
        self.view=view

    def collect_vertices(self, subnames):
        items=[]
        for idx,name in enumerate(subnames):
            try:
                pt=self.view.getVertexBySelection(name)
            except Exception:
                continue
            g=GeometryItem(
                name=name,
                point2d=pt,
                distance=0.0,
                order=idx
            )
            items.append(g)
        return items

    @staticmethod
    def sort_horizontal(items):
        return sorted(items,key=lambda i:i.point2d.x)

    @staticmethod
    def sort_vertical(items):
        return sorted(items,key=lambda i:i.point2d.y)


# ============================================================
# v0.0.6
# Distance Calculation
# ============================================================

class DistanceCalculator:

    def __init__(self, mode):
        self.mode = mode

    def calculate(self, items):
        if not items:
            return []

        if self.mode == DimensionMode.HORIZONTAL:
            base = items[0].point2d.x
            for index, item in enumerate(items):
                item.distance = item.point2d.x - base
                item.order = index
        else:
            base = items[0].point2d.y
            for index, item in enumerate(items):
                item.distance = item.point2d.y - base
                item.order = index

        return items


# ============================================================
# v0.0.7
# Layout Engine (Initial)
# ============================================================

TEXT_OFFSET = 15.0
TEXT_INTERVAL = 6.0
TEXT_MARGIN = 2.0


class LayoutEngine:

    def __init__(self, mode):
        self.mode = mode

    def build(self, geometry_items):
        layouts = []

        for item in geometry_items:
            layout = LayoutItem()

            if self.mode == DimensionMode.HORIZONTAL:
                layout.text_x = item.point2d.x
                layout.text_y = TEXT_OFFSET
            else:
                layout.text_x = TEXT_OFFSET
                layout.text_y = item.point2d.y

            layout.visible = True
            layouts.append(layout)

        return layouts


# ============================================================
# v0.0.8
# Layout Collision (Initial)
# ============================================================

class LayoutCollisionResolver:

    def __init__(self, interval=TEXT_INTERVAL):
        self.interval = interval

    def resolve_horizontal(self, layouts):
        last_x = None
        for layout in layouts:
            if last_x is not None and abs(layout.text_x - last_x) < self.interval:
                layout.text_x = last_x + self.interval
            last_x = layout.text_x
        return layouts

    def resolve_vertical(self, layouts):
        last_y = None
        for layout in layouts:
            if last_y is not None and abs(layout.text_y - last_y) < self.interval:
                layout.text_y = last_y + self.interval
            last_y = layout.text_y
        return layouts


# ============================================================
# v0.0.9
# Leader Layout (Initial)
# ============================================================

LEADER_GAP = 1.0
LEADER_OVERSHOOT = 3.0

class LeaderLayoutEngine:

    def build(self, geometry_items, layout_items, mode):
        for geo, layout in zip(geometry_items, layout_items):
            if mode == DimensionMode.HORIZONTAL:
                layout.bend_point = (
                    geo.point2d.x,
                    layout.text_y - LEADER_GAP
                )
            else:
                layout.bend_point = (
                    layout.text_x - LEADER_GAP,
                    geo.point2d.y
                )
        return layout_items


# ============================================================
# v0.0.10
# Dimension Generator (Initial)
# ============================================================

class DimensionGenerator:

    def __init__(self, view):
        self.view = view
        self.dimensions = []

    def create(self, geometry_items, mode):
        self.dimensions.clear()

        dim_type = "DistanceX" if mode == DimensionMode.HORIZONTAL else "DistanceY"

        if len(geometry_items) < 2:
            return self.dimensions

        base = geometry_items[0].point2d

        for item in geometry_items[1:]:
            try:
                dim = TechDraw.makeDistanceDim(
                    self.view,
                    dim_type,
                    base,
                    item.point2d
                )
                self.dimensions.append(dim)
            except Exception as exc:
                log(f"Dimension creation failed: {exc}", LogLevel.WARNING)

        return self.dimensions


# ============================================================
# v0.0.11
# Dimension Layout Apply
# ============================================================

class DimensionLayoutApplier:

    def apply(self, dimensions, layouts):
        for dim, layout in zip(dimensions, layouts):
            try:
                dim.X = layout.text_x
                dim.Y = layout.text_y
            except Exception as exc:
                log(f"Layout apply failed: {exc}", LogLevel.WARNING)

        if dimensions:
            try:
                dimensions[0].Document.recompute()
            except Exception:
                pass


# ============================================================
# v0.0.12
# Leader Generator (Initial)
# ============================================================

class LeaderGenerator:

    def __init__(self, view):
        self.view = view
        self.leaders = []

    def create(self, layouts):
        self.leaders.clear()

        for layout in layouts:
            if layout.bend_point is None:
                continue

            try:
                leader = TechDraw.makeLeader(
                    self.view,
                    layout.bend_point
                )
                self.leaders.append(leader)
            except Exception as exc:
                log(f"Leader creation failed: {exc}", LogLevel.WARNING)

        return self.leaders


# ============================================================
# v0.0.13
# Layout Optimizer (Initial)
# ============================================================

class LayoutOptimizer:

    def optimize(self, geometry_items, layout_items, mode):
        for geo, layout in zip(geometry_items, layout_items):
            if mode == DimensionMode.HORIZONTAL:
                if layout.text_y < TEXT_MARGIN:
                    layout.text_y = TEXT_MARGIN
                if layout.bend_point is not None:
                    layout.bend_point = (
                        geo.point2d.x,
                        layout.text_y - LEADER_GAP
                    )
            else:
                if layout.text_x < TEXT_MARGIN:
                    layout.text_x = TEXT_MARGIN
                if layout.bend_point is not None:
                    layout.bend_point = (
                        layout.text_x - LEADER_GAP,
                        geo.point2d.y
                    )
        return layout_items


# ============================================================
# v0.0.14
# Integrated Layout Manager (Initial)
# ============================================================

class IntegratedLayoutManager:

    def process(self, geometry_items, mode):
        layout_engine = LayoutEngine(mode)
        layouts = layout_engine.build(geometry_items)

        resolver = LayoutCollisionResolver()
        if mode == DimensionMode.HORIZONTAL:
            layouts = resolver.resolve_horizontal(layouts)
        else:
            layouts = resolver.resolve_vertical(layouts)

        optimizer = LayoutOptimizer()
        layouts = optimizer.optimize(
            geometry_items,
            layouts,
            mode
        )

        leader_layout = LeaderLayoutEngine()
        layouts = leader_layout.build(
            geometry_items,
            layouts,
            mode
        )

        return layouts


# ============================================================
# v0.0.15
# Progressive Dimension Pipeline (Initial)
# ============================================================

class ProgressiveDimensionPipeline:

    def __init__(self, view, mode):
        self.view = view
        self.mode = mode

    def run(self, geometry_items):
        geometry_items = DistanceCalculator(self.mode).calculate(geometry_items)

        layouts = IntegratedLayoutManager().process(
            geometry_items,
            self.mode
        )

        dimensions = DimensionGenerator(self.view).create(
            geometry_items,
            self.mode
        )

        DimensionLayoutApplier().apply(dimensions, layouts)
        LeaderGenerator(self.view).create(layouts)

        return dimensions


# ============================================================
# v0.0.16
# Progressive Dimension Engine Execute (Initial)
# ============================================================

class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def execute(self):
        self.initialize()

        log("Collecting geometry...")

        collector = GeometryCollector(self.view)

        # TODO: replace with actual selection-derived subnames
        geometry_items = collector.collect_vertices([])

        pipeline = ProgressiveDimensionPipeline(
            self.view,
            self.mode or DimensionMode.HORIZONTAL
        )

        return pipeline.run(geometry_items)


# ============================================================
# v0.0.17
# Selection -> Geometry Bridge (Initial)
# ============================================================

class SelectionGeometryBridge:

    def collect_geometry(self, selection_engine, view):
        geometry = []

        selection = selection_engine.collect_selection()

        collector = GeometryCollector(view)

        for item in selection:
            subnames = getattr(item, "SubElementNames", [])
            geometry.extend(collector.collect_vertices(subnames))

        return geometry


class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def execute(self):
        self.initialize()

        bridge = SelectionGeometryBridge()

        geometry_items = bridge.collect_geometry(
            self.selection,
            self.view
        )

        pipeline = ProgressiveDimensionPipeline(
            self.view,
            self.mode or DimensionMode.HORIZONTAL
        )

        return pipeline.run(geometry_items)


# ============================================================
# v0.0.18
# Edge / Center Geometry (Initial)
# ============================================================

class GeometryResolver:

    def __init__(self, view):
        self.view = view

    def resolve_vertex(self, subname):
        return self.view.getVertexBySelection(subname)

    def resolve_edge(self, subname):
        return self.view.getEdgeBySelection(subname)

    def resolve_center(self, subname):
        edge = self.resolve_edge(subname)
        try:
            return edge.Curve.Center
        except Exception:
            return None


# ============================================================
# v0.0.19
# Selection Mode Resolver (Initial)
# ============================================================

class SelectionPointMode(Enum):
    AUTO = auto()
    START = auto()
    MID = auto()
    END = auto()
    CENTER = auto()


class SelectionPointResolver:

    def __init__(self, geometry_resolver):
        self.geometry = geometry_resolver

    def resolve(self, subname, mode=SelectionPointMode.AUTO):
        if mode == SelectionPointMode.CENTER:
            return self.geometry.resolve_center(subname)

        if mode == SelectionPointMode.AUTO:
            pt = self.geometry.resolve_center(subname)
            if pt is not None:
                return pt
            return self.geometry.resolve_vertex(subname)

        # Placeholder implementation.
        # START / MID / END will use edge parameter evaluation
        # in a future revision.
        return self.geometry.resolve_vertex(subname)


# ============================================================
# v0.0.20
# GUI Mode Integration (Initial)
# ============================================================

class UserSelectionSettings:

    def __init__(self):
        self.base_mode = SelectionPointMode.START
        self.target_mode = SelectionPointMode.AUTO

    def set_base_mode(self, mode):
        self.base_mode = mode

    def set_target_mode(self, mode):
        self.target_mode = mode


class SelectionGeometryBridge(SelectionGeometryBridge):

    def __init__(self):
        self.settings = UserSelectionSettings()

    def resolve_point(self, resolver, subname, is_base=False):
        mode = self.settings.base_mode if is_base else self.settings.target_mode
        return SelectionPointResolver(resolver).resolve(subname, mode)


# ============================================================
# v0.0.21
# Edge Point Evaluation (Initial)
# ============================================================

class EdgePointEvaluator:

    def start_point(self, edge):
        try:
            return edge.Vertexes[0].Point
        except Exception:
            return None

    def end_point(self, edge):
        try:
            return edge.Vertexes[-1].Point
        except Exception:
            return None

    def mid_point(self, edge):
        try:
            return edge.valueAt(edge.ParameterRange[0] +
                                (edge.ParameterRange[1]-edge.ParameterRange[0])/2.0)
        except Exception:
            return None


# ============================================================
# v0.0.22
# SelectionPointResolver Edge Support
# ============================================================

class SelectionPointResolver(SelectionPointResolver):

    def resolve(self, subname, mode=SelectionPointMode.AUTO):

        edge = None
        try:
            edge = self.geometry.resolve_edge(subname)
        except Exception:
            edge = None

        evaluator = EdgePointEvaluator()

        if edge is not None:
            if mode == SelectionPointMode.START:
                return evaluator.start_point(edge)

            if mode == SelectionPointMode.END:
                return evaluator.end_point(edge)

            if mode == SelectionPointMode.MID:
                return evaluator.mid_point(edge)

        return super().resolve(subname, mode)


# ============================================================
# v0.0.23
# Geometry Bridge Point Resolution
# ============================================================

class SelectionGeometryBridge(SelectionGeometryBridge):

    def collect_geometry(self, selection_engine, view):
        geometry = []

        selection = selection_engine.collect_selection()
        resolver = GeometryResolver(view)

        for sel_index, item in enumerate(selection):
            subnames = getattr(item, "SubElementNames", [])

            for sub_index, subname in enumerate(subnames):
                point = self.resolve_point(
                    resolver,
                    subname,
                    is_base=(sel_index == 0 and sub_index == 0)
                )

                if point is None:
                    continue

                geometry.append(
                    GeometryItem(
                        name=subname,
                        point2d=point,
                        order=len(geometry)
                    )
                )

        return geometry


# ============================================================
# v0.0.24
# Base Point Distance Strategy
# ============================================================

class BasePointStrategy:

    def __init__(self, mode):
        self.mode = mode

    def prepare(self, geometry_items):
        if not geometry_items:
            return []

        if self.mode == DimensionMode.HORIZONTAL:
            geometry_items.sort(key=lambda g: g.point2d.x)
        else:
            geometry_items.sort(key=lambda g: g.point2d.y)

        base = geometry_items[0]

        for index, item in enumerate(geometry_items):
            item.order = index
            if self.mode == DimensionMode.HORIZONTAL:
                item.distance = item.point2d.x - base.point2d.x
            else:
                item.distance = item.point2d.y - base.point2d.y

        return geometry_items


# ============================================================
# v0.0.25
# Pipeline Base Strategy Integration
# ============================================================

class ProgressiveDimensionPipeline(ProgressiveDimensionPipeline):

    def run(self, geometry_items):

        geometry_items = BasePointStrategy(
            self.mode
        ).prepare(geometry_items)

        layouts = IntegratedLayoutManager().process(
            geometry_items,
            self.mode
        )

        dimensions = DimensionGenerator(
            self.view
        ).create(
            geometry_items,
            self.mode
        )

        DimensionLayoutApplier().apply(
            dimensions,
            layouts
        )

        LeaderGenerator(
            self.view
        ).create(layouts)

        return dimensions


# ============================================================
# v0.0.26
# User Defined Base Point
# ============================================================

class BasePointStrategy(BasePointStrategy):

    def prepare(self, geometry_items, base_index=0):
        if not geometry_items:
            return []

        if base_index < 0 or base_index >= len(geometry_items):
            base_index = 0

        base = geometry_items.pop(base_index)
        geometry_items.insert(0, base)

        for index, item in enumerate(geometry_items):
            item.order = index
            if self.mode == DimensionMode.HORIZONTAL:
                item.distance = item.point2d.x - base.point2d.x
            else:
                item.distance = item.point2d.y - base.point2d.y

        return geometry_items


class ProgressiveDimensionPipeline(ProgressiveDimensionPipeline):

    def run(self, geometry_items, base_index=0):

        geometry_items = BasePointStrategy(
            self.mode
        ).prepare(
            geometry_items,
            base_index
        )

        layouts = IntegratedLayoutManager().process(
            geometry_items,
            self.mode
        )

        dimensions = DimensionGenerator(
            self.view
        ).create(
            geometry_items,
            self.mode
        )

        DimensionLayoutApplier().apply(dimensions, layouts)
        LeaderGenerator(self.view).create(layouts)

        return dimensions


# ============================================================
# v0.0.27
# Base Index Integration
# ============================================================

class SelectionGeometryBridge(SelectionGeometryBridge):

    def __init__(self):
        super().__init__()
        self.base_index = 0

    def get_base_index(self):
        return self.base_index


class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def execute(self):
        self.initialize()

        bridge = SelectionGeometryBridge()

        geometry_items = bridge.collect_geometry(
            self.selection,
            self.view
        )

        pipeline = ProgressiveDimensionPipeline(
            self.view,
            self.mode or DimensionMode.HORIZONTAL
        )

        return pipeline.run(
            geometry_items,
            base_index=bridge.get_base_index()
        )


# ============================================================
# v0.0.28
# Base Index Detection
# ============================================================

class SelectionGeometryBridge(SelectionGeometryBridge):

    def collect_geometry(self, selection_engine, view):
        geometry = []
        self.base_index = 0

        selection = selection_engine.collect_selection()
        resolver = GeometryResolver(view)

        for sel_index, item in enumerate(selection):
            subnames = getattr(item, "SubElementNames", [])

            for subname in subnames:
                point = self.resolve_point(
                    resolver,
                    subname,
                    is_base=(len(geometry) == 0)
                )

                if point is None:
                    continue

                if len(geometry) == 0:
                    self.base_index = 0

                geometry.append(
                    GeometryItem(
                        name=subname,
                        point2d=point,
                        order=len(geometry)
                    )
                )

        return geometry


# ============================================================
# v0.0.29
# User Base Point Override
# ============================================================

class UserSelectionSettings(UserSelectionSettings):

    def __init__(self):
        super().__init__()
        self.use_manual_base = False
        self.manual_base_index = 0

    def set_manual_base(self, index):
        self.use_manual_base = True
        self.manual_base_index = max(0, index)


class SelectionGeometryBridge(SelectionGeometryBridge):

    def get_base_index(self):
        if (
            self.settings.use_manual_base and
            self.settings.manual_base_index < len(getattr(self, "_geometry_cache", []))
        ):
            return self.settings.manual_base_index
        return self.base_index

    def collect_geometry(self, selection_engine, view):
        geometry = super().collect_geometry(selection_engine, view)
        self._geometry_cache = geometry
        return geometry


# ============================================================
# v0.0.30
# Engine Settings Integration
# ============================================================

class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def __init__(self):
        super().__init__()
        self.settings = UserSelectionSettings()

    def execute(self):
        self.initialize()

        bridge = SelectionGeometryBridge()
        bridge.settings = self.settings

        geometry_items = bridge.collect_geometry(
            self.selection,
            self.view
        )

        pipeline = ProgressiveDimensionPipeline(
            self.view,
            self.mode or DimensionMode.HORIZONTAL
        )

        return pipeline.run(
            geometry_items,
            base_index=bridge.get_base_index()
        )


# ============================================================
# v0.0.31
# Task Panel Skeleton
# ============================================================

class ProgressiveDimensionTaskPanel:

    def __init__(self, settings):
        self.settings = settings

    def set_dimension_mode(self, mode):
        self.dimension_mode = mode

    def set_base_mode(self, mode):
        self.settings.set_base_mode(mode)

    def set_target_mode(self, mode):
        self.settings.set_target_mode(mode)

    def set_manual_base(self, index):
        self.settings.set_manual_base(index)

    def apply(self, engine):
        engine.settings = self.settings
        if hasattr(self, "dimension_mode"):
            engine.mode = self.dimension_mode


# ============================================================
# v0.0.32
# Task Panel State Synchronization
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def load_from_settings(self):
        self.dimension_mode = getattr(
            self,
            "dimension_mode",
            DimensionMode.HORIZONTAL
        )
        self.base_mode = self.settings.base_mode
        self.target_mode = self.settings.target_mode
        self.manual_base = self.settings.manual_base_index
        self.use_manual_base = self.settings.use_manual_base

    def save_to_settings(self):
        self.settings.set_base_mode(self.base_mode)
        self.settings.set_target_mode(self.target_mode)

        if self.use_manual_base:
            self.settings.set_manual_base(self.manual_base)


# ============================================================
# v0.0.33
# TaskPanel Dialog Callbacks
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def accept(self):
        self.save_to_settings()
        return True

    def reject(self):
        return False

    def apply_changes(self, engine):
        self.save_to_settings()
        self.apply(engine)
        return engine.execute()


# ============================================================
# v0.0.34
# FreeCAD TaskPanel Interface
# ============================================================

try:
    from PySide import QtGui
except Exception:
    QtGui = None


class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def getStandardButtons(self):
        if QtGui is None:
            return 0

        return (
            int(QtGui.QDialogButtonBox.Ok) |
            int(QtGui.QDialogButtonBox.Cancel) |
            int(QtGui.QDialogButtonBox.Apply)
        )

    def open(self):
        try:
            Gui.Control.showDialog(self)
        except Exception as exc:
            log(f"Unable to open TaskPanel: {exc}", LogLevel.WARNING)

    def close(self):
        try:
            Gui.Control.closeDialog()
        except Exception as exc:
            log(f"Unable to close TaskPanel: {exc}", LogLevel.WARNING)


# ============================================================
# v0.0.35
# Initial Qt Widget Construction
# ============================================================

try:
    from PySide import QtGui, QtCore
except Exception:
    QtGui = None
    QtCore = None


class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def build_ui(self):
        if QtGui is None:
            self.form = None
            return None

        widget = QtGui.QWidget()
        layout = QtGui.QFormLayout(widget)

        self.mode_combo = QtGui.QComboBox()
        self.mode_combo.addItems(["Horizontal", "Vertical"])

        self.base_combo = QtGui.QComboBox()
        self.base_combo.addItems(["Start", "Mid", "End", "Center", "Auto"])

        self.target_combo = QtGui.QComboBox()
        self.target_combo.addItems(["Auto", "Start", "Mid", "End", "Center"])

        self.manual_base_check = QtGui.QCheckBox("Use manual base")
        self.manual_base_spin = QtGui.QSpinBox()
        self.manual_base_spin.setMinimum(0)

        layout.addRow("Dimension", self.mode_combo)
        layout.addRow("Base", self.base_combo)
        layout.addRow("Target", self.target_combo)
        layout.addRow(self.manual_base_check)
        layout.addRow("Base Index", self.manual_base_spin)

        self.form = widget
        return widget


# ============================================================
# v0.0.36
# Qt Signal Connection (Initial)
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def connect_signals(self):
        if QtGui is None or not hasattr(self, "mode_combo"):
            return

        self.mode_combo.currentIndexChanged.connect(
            lambda i: self.set_dimension_mode(
                DimensionMode.HORIZONTAL if i == 0 else DimensionMode.VERTICAL
            )
        )

        self.manual_base_check.toggled.connect(
            lambda checked: setattr(self, "use_manual_base", checked)
        )

        self.manual_base_spin.valueChanged.connect(
            lambda value: setattr(self, "manual_base", value)
        )

    def initialize_ui(self):
        self.build_ui()
        self.load_from_settings()
        self.connect_signals()
        return getattr(self, "form", None)


# ============================================================
# v0.0.37
# ComboBox <-> SelectionPointMode Mapping
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    _BASE_MODES = [
        SelectionPointMode.START,
        SelectionPointMode.MID,
        SelectionPointMode.END,
        SelectionPointMode.CENTER,
        SelectionPointMode.AUTO,
    ]

    _TARGET_MODES = [
        SelectionPointMode.AUTO,
        SelectionPointMode.START,
        SelectionPointMode.MID,
        SelectionPointMode.END,
        SelectionPointMode.CENTER,
    ]

    def connect_signals(self):
        super().connect_signals()

        if QtGui is None:
            return

        self.base_combo.currentIndexChanged.connect(
            lambda i: self.settings.set_base_mode(self._BASE_MODES[i])
        )

        self.target_combo.currentIndexChanged.connect(
            lambda i: self.settings.set_target_mode(self._TARGET_MODES[i])
        )

    def load_from_settings(self):
        super().load_from_settings()

        if QtGui is None or not hasattr(self, "base_combo"):
            return

        self.base_combo.setCurrentIndex(
            self._BASE_MODES.index(self.settings.base_mode)
        )
        self.target_combo.setCurrentIndex(
            self._TARGET_MODES.index(self.settings.target_mode)
        )


# ============================================================
# v0.0.38
# Widget <-> Settings Synchronization
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def load_from_settings(self):
        super().load_from_settings()

        if QtGui is None or not hasattr(self, "manual_base_check"):
            return

        self.manual_base_check.setChecked(
            self.settings.use_manual_base
        )
        self.manual_base_spin.setValue(
            self.settings.manual_base_index
        )

    def save_to_settings(self):
        super().save_to_settings()

        if QtGui is None or not hasattr(self, "manual_base_check"):
            return

        self.settings.use_manual_base = (
            self.manual_base_check.isChecked()
        )

        if self.settings.use_manual_base:
            self.settings.set_manual_base(
                self.manual_base_spin.value()
            )


# ============================================================
# v0.0.39
# FreeCAD Command Registration
# ============================================================

def show_progressive_dimension_dialog():
    settings = UserSelectionSettings()
    panel = ProgressiveDimensionTaskPanel(settings)
    panel.initialize_ui()
    panel.open()
    return panel


class ProgressiveDimensionCommand:

    def GetResources(self):
        return {
            "MenuText": "Progressive Dimension",
            "ToolTip": "Create progressive dimensions for TechDraw",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        show_progressive_dimension_dialog()


try:
    Gui.addCommand(
        "ProgressiveDimension",
        ProgressiveDimensionCommand()
    )
except Exception:
    pass


# ============================================================
# v0.0.40
# Execute / Validation Integration
# ============================================================

class ProgressiveDimensionTaskPanel(ProgressiveDimensionTaskPanel):

    def accept(self):
        self.save_to_settings()

        engine = ProgressiveDimensionEngine()
        self.apply(engine)

        try:
            App.ActiveDocument.openTransaction(
                "Progressive Dimension"
            )
            engine.execute()
            App.ActiveDocument.commitTransaction()
            self.close()
            return True

        except Exception as exc:
            try:
                App.ActiveDocument.abortTransaction()
            except Exception:
                pass

            log(f"Execution failed: {exc}", LogLevel.ERROR)
            return False


class ProgressiveDimensionCommand(ProgressiveDimensionCommand):

    def Activated(self):
        if App.ActiveDocument is None:
            log("No active document.", LogLevel.ERROR)
            return

        if not Gui.Selection.getSelectionEx():
            log("Please select TechDraw geometry first.", LogLevel.WARNING)
            return

        show_progressive_dimension_dialog()


# ============================================================
# v0.0.41
# Geometry Validation
# ============================================================

class GeometryValidator:

    def validate(self, geometry_items):
        if len(geometry_items) < 2:
            raise RuntimeError(
                "At least two valid geometry points are required."
            )

        names = set()
        filtered = []

        for item in geometry_items:
            key = (
                item.name,
                round(item.point2d.x, 6),
                round(item.point2d.y, 6)
            )

            if key in names:
                continue

            names.add(key)
            filtered.append(item)

        return filtered


class ProgressiveDimensionPipeline(ProgressiveDimensionPipeline):

    def run(self, geometry_items, base_index=0):

        geometry_items = GeometryValidator().validate(
            geometry_items
        )

        return super().run(
            geometry_items,
            base_index
        )


# ============================================================
# v0.0.42
# Geometry Type Resolver
# ============================================================

class GeometryType(Enum):
    UNKNOWN = auto()
    VERTEX = auto()
    EDGE = auto()
    CIRCLE = auto()
    LINE = auto()


class GeometryResolver(GeometryResolver):

    def geometry_type(self, subname):
        try:
            edge = self.resolve_edge(subname)
        except Exception:
            edge = None

        if edge is None:
            try:
                self.resolve_vertex(subname)
                return GeometryType.VERTEX
            except Exception:
                return GeometryType.UNKNOWN

        curve = getattr(edge, "Curve", None)
        cname = type(curve).__name__ if curve else ""

        if "Circle" in cname:
            return GeometryType.CIRCLE
        if "Line" in cname:
            return GeometryType.LINE
        return GeometryType.EDGE


class SelectionPointResolver(SelectionPointResolver):

    def resolve(self, subname, mode=SelectionPointMode.AUTO):

        if mode == SelectionPointMode.AUTO:
            gtype = self.geometry.geometry_type(subname)

            if gtype == GeometryType.CIRCLE:
                center = self.geometry.resolve_center(subname)
                if center is not None:
                    return center

            if gtype == GeometryType.VERTEX:
                return self.geometry.resolve_vertex(subname)

        return super().resolve(subname, mode)


# ============================================================
# v0.0.43
# Arc Detection / Orientation
# ============================================================

class GeometryType(Enum):
    UNKNOWN = auto()
    VERTEX = auto()
    EDGE = auto()
    CIRCLE = auto()
    LINE = auto()
    ARC = auto()


class GeometryResolver(GeometryResolver):

    def geometry_type(self, subname):
        gtype = super().geometry_type(subname)
        if gtype != GeometryType.EDGE:
            return gtype

        try:
            edge = self.resolve_edge(subname)
            curve = getattr(edge, "Curve", None)
            cname = type(curve).__name__ if curve else ""

            if "Arc" in cname:
                return GeometryType.ARC
        except Exception:
            pass

        return gtype

    def edge_orientation(self, subname):
        try:
            edge = self.resolve_edge(subname)
            p1 = edge.Vertexes[0].Point
            p2 = edge.Vertexes[-1].Point
            dx = abs(p2.x - p1.x)
            dy = abs(p2.y - p1.y)

            if dx > dy * 10:
                return "Horizontal"
            if dy > dx * 10:
                return "Vertical"
            return "Angled"
        except Exception:
            return "Unknown"


class SelectionPointResolver(SelectionPointResolver):

    def resolve(self, subname, mode=SelectionPointMode.AUTO):
        if mode == SelectionPointMode.AUTO:
            gtype = self.geometry.geometry_type(subname)

            if gtype in (GeometryType.CIRCLE, GeometryType.ARC):
                center = self.geometry.resolve_center(subname)
                if center is not None:
                    return center

        return super().resolve(subname, mode)


# ============================================================
# v0.0.44
# AUTO Edge Decision
# ============================================================

class SelectionPointResolver(SelectionPointResolver):

    def resolve(self, subname, mode=SelectionPointMode.AUTO):

        if mode == SelectionPointMode.AUTO:
            gtype = self.geometry.geometry_type(subname)

            if gtype in (GeometryType.CIRCLE, GeometryType.ARC):
                center = self.geometry.resolve_center(subname)
                if center is not None:
                    return center

            if gtype in (GeometryType.LINE, GeometryType.EDGE):
                edge = self.geometry.resolve_edge(subname)
                orient = self.geometry.edge_orientation(subname)
                evalr = EdgePointEvaluator()

                if orient == "Horizontal":
                    return evalr.start_point(edge)

                if orient == "Vertical":
                    return evalr.start_point(edge)

                mid = evalr.mid_point(edge)
                if mid is not None:
                    return mid

        return super().resolve(subname, mode)


# ============================================================
# v0.0.45
# Direction Aware AUTO Selection
# ============================================================

class SelectionPointResolver(SelectionPointResolver):

    def resolve_for_dimension(self, subname, dim_mode,
                              mode=SelectionPointMode.AUTO):

        if mode != SelectionPointMode.AUTO:
            return self.resolve(subname, mode)

        gtype = self.geometry.geometry_type(subname)

        if gtype in (GeometryType.CIRCLE, GeometryType.ARC):
            center = self.geometry.resolve_center(subname)
            if center is not None:
                return center

        if gtype not in (GeometryType.LINE, GeometryType.EDGE):
            return self.resolve(subname, mode)

        edge = self.geometry.resolve_edge(subname)
        ev = EdgePointEvaluator()

        p1 = ev.start_point(edge)
        p2 = ev.end_point(edge)

        if p1 is None or p2 is None:
            return self.resolve(subname, mode)

        if dim_mode == DimensionMode.HORIZONTAL:
            return p1 if p1.x <= p2.x else p2

        if dim_mode == DimensionMode.VERTICAL:
            return p1 if p1.y <= p2.y else p2

        return ev.mid_point(edge)


# ============================================================
# v0.0.46
# Direction-aware Bridge Integration
# ============================================================

class SelectionGeometryBridge(SelectionGeometryBridge):

    def collect_geometry(self, selection_engine, view, dim_mode=DimensionMode.HORIZONTAL):
        geometry = []
        self.base_index = 0

        selection = selection_engine.collect_selection()
        resolver = GeometryResolver(view)
        point_resolver = SelectionPointResolver(resolver)

        for item in selection:
            for subname in getattr(item, "SubElementNames", []):
                point = point_resolver.resolve_for_dimension(
                    subname,
                    dim_mode,
                    self.settings.base_mode if len(geometry) == 0 else self.settings.target_mode
                )

                if point is None:
                    continue

                geometry.append(
                    GeometryItem(
                        name=subname,
                        point2d=point,
                        order=len(geometry)
                    )
                )

        self._geometry_cache = geometry
        return geometry


class ProgressiveDimensionEngine(ProgressiveDimensionEngine):

    def execute(self):
        self.initialize()

        bridge = SelectionGeometryBridge()
        bridge.settings = self.settings

        mode = self.mode or DimensionMode.HORIZONTAL

        geometry_items = bridge.collect_geometry(
            self.selection,
            self.view,
            mode
        )

        pipeline = ProgressiveDimensionPipeline(self.view, mode)

        return pipeline.run(
            geometry_items,
            base_index=bridge.get_base_index()
        )


# ============================================================
# v0.0.47
# Automatic Dimension Side Selection
# ============================================================

@dataclass
class ViewBounds:
    xmin: float
    xmax: float
    ymin: float
    ymax: float


class LayoutDirectionResolver:

    OFFSET = 15.0

    def detect_bounds(self, geometry_items):
        xs = [g.point2d.x for g in geometry_items]
        ys = [g.point2d.y for g in geometry_items]
        return ViewBounds(min(xs), max(xs), min(ys), max(ys))

    def resolve(self, geometry_items, mode):
        b = self.detect_bounds(geometry_items)

        if mode == DimensionMode.HORIZONTAL:
            return ("Top", b.ymax + self.OFFSET)

        return ("Right", b.xmax + self.OFFSET)


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        side, offset = LayoutDirectionResolver().resolve(
            geometry_items,
            mode
        )

        for layout in layouts:
            if mode == DimensionMode.HORIZONTAL:
                layout.text_y = offset
            else:
                layout.text_x = offset

        return layouts


# ============================================================
# v0.0.48
# Smart Layout Side Selection
# ============================================================

class LayoutDirectionResolver(LayoutDirectionResolver):

    def resolve(self, geometry_items, mode):
        b = self.detect_bounds(geometry_items)

        left_space = abs(b.xmin)
        right_space = abs(420.0 - b.xmax)
        bottom_space = abs(b.ymin)
        top_space = abs(297.0 - b.ymax)

        if mode == DimensionMode.HORIZONTAL:
            if top_space >= bottom_space:
                return ("Top", b.ymax + self.OFFSET)
            return ("Bottom", b.ymin - self.OFFSET)

        if right_space >= left_space:
            return ("Right", b.xmax + self.OFFSET)
        return ("Left", b.xmin - self.OFFSET)


# ============================================================
# v0.0.49
# Layout Collision Expansion
# ============================================================

class LayoutCollisionResolver(LayoutCollisionResolver):

    EXTRA_MARGIN = 8.0

    def resolve_horizontal(self, layouts):
        layouts = super().resolve_horizontal(layouts)

        for i in range(1, len(layouts)):
            if abs(layouts[i].text_x - layouts[i-1].text_x) < self.EXTRA_MARGIN:
                layouts[i].text_x = layouts[i-1].text_x + self.EXTRA_MARGIN

        return layouts

    def resolve_vertical(self, layouts):
        layouts = super().resolve_vertical(layouts)

        for i in range(1, len(layouts)):
            if abs(layouts[i].text_y - layouts[i-1].text_y) < self.EXTRA_MARGIN:
                layouts[i].text_y = layouts[i-1].text_y + self.EXTRA_MARGIN

        return layouts


class LayoutOptimizer(LayoutOptimizer):

    def optimize(self, geometry_items, layout_items, mode):
        layout_items = super().optimize(geometry_items, layout_items, mode)

        for layout in layout_items:
            if mode == DimensionMode.HORIZONTAL:
                layout.text_y += 2.0
            else:
                layout.text_x += 2.0

        return layout_items


# ============================================================
# v0.0.50
# Existing Dimension Awareness
# ============================================================

class ExistingDimensionInspector:

    def collect(self, document):
        dims = []
        for obj in getattr(document, "Objects", []):
            if getattr(obj, "TypeId", "") == "TechDraw::DrawViewDimension":
                dims.append(obj)
        return dims


class LayoutOptimizer(LayoutOptimizer):

    SAFE_GAP = 10.0

    def optimize(self, geometry_items, layout_items, mode):
        layout_items = super().optimize(geometry_items, layout_items, mode)

        existing = ExistingDimensionInspector().collect(App.ActiveDocument)

        for dim in existing:
            for layout in layout_items:
                try:
                    if mode == DimensionMode.HORIZONTAL:
                        if abs(layout.text_y - dim.Y) < self.SAFE_GAP:
                            layout.text_y = dim.Y + self.SAFE_GAP
                    else:
                        if abs(layout.text_x - dim.X) < self.SAFE_GAP:
                            layout.text_x = dim.X + self.SAFE_GAP
                except Exception:
                    pass

        return layout_items


# ============================================================
# v0.0.51
# Progressive Offset Planner
# ============================================================

class OffsetPlanner:

    BASE_OFFSET = 15.0
    STEP = 8.0

    def assign(self, layouts, mode):
        for index, layout in enumerate(layouts):
            offset = self.BASE_OFFSET + index * self.STEP

            if mode == DimensionMode.HORIZONTAL:
                layout.text_y = max(layout.text_y, offset)
            else:
                layout.text_x = max(layout.text_x, offset)

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = OffsetPlanner().assign(layouts, mode)
        return layouts


# ============================================================
# v0.0.52
# Adaptive Offset Planner
# ============================================================

class OffsetPlanner(OffsetPlanner):

    DISTANCE_STEP = 0.15
    MAX_EXTRA = 20.0

    def assign(self, layouts, mode, geometry_items=None):
        layouts = super().assign(layouts, mode)

        if geometry_items is None:
            return layouts

        for geo, layout in zip(geometry_items, layouts):
            extra = min(abs(getattr(geo, "distance", 0.0)) * self.DISTANCE_STEP,
                        self.MAX_EXTRA)

            if mode == DimensionMode.HORIZONTAL:
                layout.text_y += extra
            else:
                layout.text_x += extra

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = OffsetPlanner().assign(layouts, mode, geometry_items)
        return layouts


# ============================================================
# v0.0.53
# Leader Alignment Planner
# ============================================================

class LeaderAlignmentPlanner:

    def align(self, layouts, mode):
        if not layouts:
            return layouts

        if mode == DimensionMode.HORIZONTAL:
            target = max(l.text_y for l in layouts)
            for l in layouts:
                l.text_y = target
                if l.bend_point is not None:
                    l.bend_point = (l.bend_point[0], target - LEADER_GAP)
        else:
            target = max(l.text_x for l in layouts)
            for l in layouts:
                l.text_x = target
                if l.bend_point is not None:
                    l.bend_point = (target - LEADER_GAP, l.bend_point[1])

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LeaderAlignmentPlanner().align(layouts, mode)
        return layouts


# ============================================================
# v0.0.54
# Leader Crossing Reduction
# ============================================================

class LeaderCrossingResolver:

    MIN_SPACING = 5.0

    def optimize(self, layouts, mode):
        if len(layouts) < 2:
            return layouts

        if mode == DimensionMode.HORIZONTAL:
            layouts.sort(key=lambda l: l.text_x)
            for i in range(1, len(layouts)):
                if layouts[i].text_x - layouts[i-1].text_x < self.MIN_SPACING:
                    layouts[i].text_x = layouts[i-1].text_x + self.MIN_SPACING
        else:
            layouts.sort(key=lambda l: l.text_y)
            for i in range(1, len(layouts)):
                if layouts[i].text_y - layouts[i-1].text_y < self.MIN_SPACING:
                    layouts[i].text_y = layouts[i-1].text_y + self.MIN_SPACING

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LeaderCrossingResolver().optimize(layouts, mode)
        return layouts


# ============================================================
# v0.0.55
# Layout Quality Evaluator
# ============================================================

class LayoutQualityEvaluator:

    def score(self, layouts, mode):
        score = 100.0

        for i in range(1, len(layouts)):
            if mode == DimensionMode.HORIZONTAL:
                gap = layouts[i].text_x - layouts[i-1].text_x
            else:
                gap = layouts[i].text_y - layouts[i-1].text_y

            if gap < 5.0:
                score -= (5.0 - gap) * 5.0

        return max(score, 0.0)


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        quality = LayoutQualityEvaluator().score(layouts, mode)
        log(f"Layout quality score: {quality:.1f}")

        return layouts


# ============================================================
# v0.0.56
# Candidate Layout Optimizer
# ============================================================

class CandidateLayoutOptimizer:

    OFFSET_CANDIDATES = (-10.0, -5.0, 0.0, 5.0, 10.0)

    def optimize(self, layouts, mode):
        if not layouts:
            return layouts

        evaluator = LayoutQualityEvaluator()
        best_layouts = layouts
        best_score = evaluator.score(layouts, mode)

        for delta in self.OFFSET_CANDIDATES:
            trial = []
            for l in layouts:
                item = LayoutItem(
                    text_x=l.text_x,
                    text_y=l.text_y,
                    bend_point=l.bend_point,
                    visible=l.visible
                )
                if mode == DimensionMode.HORIZONTAL:
                    item.text_y += delta
                else:
                    item.text_x += delta
                trial.append(item)

            score = evaluator.score(trial, mode)
            if score > best_score:
                best_layouts = trial
                best_score = score

        log(f"Best layout score: {best_score:.1f}")
        return best_layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = CandidateLayoutOptimizer().optimize(layouts, mode)
        return layouts


# ============================================================
# v0.0.57
# Leader Crossing Evaluation
# ============================================================

class LeaderCrossingEvaluator:

    PENALTY = 15.0

    def score(self, layouts, mode):
        penalty = 0.0

        for i in range(len(layouts)):
            for j in range(i + 1, len(layouts)):
                a = layouts[i]
                b = layouts[j]

                if mode == DimensionMode.HORIZONTAL:
                    if abs(a.text_x - b.text_x) < 2.0:
                        penalty += self.PENALTY
                else:
                    if abs(a.text_y - b.text_y) < 2.0:
                        penalty += self.PENALTY

        return penalty


class LayoutQualityEvaluator(LayoutQualityEvaluator):

    def score(self, layouts, mode):
        score = super().score(layouts, mode)
        score -= LeaderCrossingEvaluator().score(layouts, mode)
        return max(score, 0.0)


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        log(
            f"Crossing penalty: "
            f"{LeaderCrossingEvaluator().score(layouts, mode):.1f}"
        )
        return layouts


# ============================================================
# v0.0.58
# Model Overlap Evaluator
# ============================================================

class ModelOverlapEvaluator:

    PENALTY = 20.0
    CLEARANCE = 3.0

    def score(self, geometry_items, layouts, mode):
        penalty = 0.0

        for geo, layout in zip(geometry_items, layouts):
            if mode == DimensionMode.HORIZONTAL:
                if abs(layout.text_x - geo.point2d.x) < self.CLEARANCE:
                    penalty += self.PENALTY
            else:
                if abs(layout.text_y - geo.point2d.y) < self.CLEARANCE:
                    penalty += self.PENALTY

        return penalty


class CandidateLayoutOptimizer(CandidateLayoutOptimizer):

    def optimize(self, layouts, mode, geometry_items=None):
        best = super().optimize(layouts, mode)

        if geometry_items is not None:
            p = ModelOverlapEvaluator().score(geometry_items, best, mode)
            log(f"Model overlap penalty: {p:.1f}")

        return best


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = CandidateLayoutOptimizer().optimize(
            layouts,
            mode,
            geometry_items
        )
        return layouts


# ============================================================
# v0.0.59
# Automatic Overlap Recovery
# ============================================================

class LayoutRecoveryEngine:

    RECOVERY_STEP = 5.0
    MAX_ITERATIONS = 5

    def recover(self, geometry_items, layouts, mode):
        evaluator = ModelOverlapEvaluator()

        for _ in range(self.MAX_ITERATIONS):
            penalty = evaluator.score(geometry_items, layouts, mode)
            if penalty <= 0:
                break

            for layout in layouts:
                if mode == DimensionMode.HORIZONTAL:
                    layout.text_y += self.RECOVERY_STEP
                else:
                    layout.text_x += self.RECOVERY_STEP

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LayoutRecoveryEngine().recover(
            geometry_items,
            layouts,
            mode
        )
        return layouts


# ============================================================
# v0.0.60
# Leader Length Optimizer
# ============================================================

class LeaderLengthOptimizer:

    TARGET_LENGTH = 25.0

    def optimize(self, geometry_items, layouts, mode):
        for geo, layout in zip(geometry_items, layouts):
            if mode == DimensionMode.HORIZONTAL:
                layout.text_y = max(layout.text_y,
                                    geo.point2d.y + self.TARGET_LENGTH)
            else:
                layout.text_x = max(layout.text_x,
                                    geo.point2d.x + self.TARGET_LENGTH)

            if layout.bend_point is not None:
                if mode == DimensionMode.HORIZONTAL:
                    layout.bend_point = (geo.point2d.x,
                                         layout.text_y - LEADER_GAP)
                else:
                    layout.bend_point = (layout.text_x - LEADER_GAP,
                                         geo.point2d.y)
        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LeaderLengthOptimizer().optimize(
            geometry_items,
            layouts,
            mode
        )
        return layouts


# ============================================================
# v0.0.61
# Bounding Box Collision Evaluator
# ============================================================

TEXT_BOX_WIDTH = 18.0
TEXT_BOX_HEIGHT = 6.0

class TextBoundingBoxEvaluator:

    def collision_count(self, layouts):
        collisions = 0
        for i in range(len(layouts)):
            for j in range(i + 1, len(layouts)):
                a = layouts[i]
                b = layouts[j]
                if (abs(a.text_x - b.text_x) < TEXT_BOX_WIDTH and
                        abs(a.text_y - b.text_y) < TEXT_BOX_HEIGHT):
                    collisions += 1
        return collisions


class LayoutQualityEvaluator(LayoutQualityEvaluator):

    def score(self, layouts, mode):
        score = super().score(layouts, mode)
        score -= TextBoundingBoxEvaluator().collision_count(layouts) * 10.0
        return max(score, 0.0)


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        log(f"Text collisions: {TextBoundingBoxEvaluator().collision_count(layouts)}")
        return layouts


# ============================================================
# v0.0.62
# Local Collision Recovery
# ============================================================

class LocalCollisionRecovery:

    SHIFT_STEP = 4.0
    MAX_PASSES = 5

    def optimize(self, layouts, mode):
        detector = TextBoundingBoxEvaluator()

        for _ in range(self.MAX_PASSES):
            changed = False
            for i in range(len(layouts)):
                for j in range(i+1, len(layouts)):
                    a,b = layouts[i], layouts[j]
                    if (abs(a.text_x-b.text_x) < TEXT_BOX_WIDTH and
                        abs(a.text_y-b.text_y) < TEXT_BOX_HEIGHT):
                        if mode == DimensionMode.HORIZONTAL:
                            b.text_x += self.SHIFT_STEP
                        else:
                            b.text_y += self.SHIFT_STEP
                        changed = True
            if not changed or detector.collision_count(layouts)==0:
                break
        return layouts

class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LocalCollisionRecovery().optimize(layouts, mode)
        log(f"Remaining text collisions: {TextBoundingBoxEvaluator().collision_count(layouts)}")
        return layouts


# ============================================================
# v0.0.63
# Leader Segment Crossing Detection
# ============================================================

class LeaderSegmentEvaluator:

    PENALTY = 25.0

    @staticmethod
    def _ccw(a,b,c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])

    def intersects(self,p1,p2,p3,p4):
        return (self._ccw(p1,p3,p4) != self._ccw(p2,p3,p4) and
                self._ccw(p1,p2,p3) != self._ccw(p1,p2,p4))

    def crossing_count(self, geometry_items, layouts):
        count = 0
        segs = []
        for g,l in zip(geometry_items, layouts):
            if l.bend_point is None:
                continue
            segs.append(((g.point2d.x,g.point2d.y),
                         (l.bend_point[0], l.bend_point[1])))
        for i in range(len(segs)):
            for j in range(i+1, len(segs)):
                if self.intersects(*segs[i], *segs[j]):
                    count += 1
        return count


class LayoutQualityEvaluator(LayoutQualityEvaluator):

    def score(self, layouts, mode, geometry_items=None):
        score = super().score(layouts, mode)
        if geometry_items is not None:
            score -= LeaderSegmentEvaluator().crossing_count(
                geometry_items, layouts) * LeaderSegmentEvaluator.PENALTY
        return max(score, 0.0)


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        c = LeaderSegmentEvaluator().crossing_count(
            geometry_items, layouts)
        log(f"Leader segment crossings: {c}")
        return layouts


# ============================================================
# v0.0.64
# Leader Auto Reroute
# ============================================================

class LeaderAutoRouter:

    REROUTE_STEP = 6.0
    MAX_PASSES = 5

    def optimize(self, geometry_items, layouts, mode):
        evaluator = LeaderSegmentEvaluator()

        for _ in range(self.MAX_PASSES):
            if evaluator.crossing_count(geometry_items, layouts) == 0:
                break

            for geo, layout in zip(geometry_items, layouts):
                if layout.bend_point is None:
                    continue
                if mode == DimensionMode.HORIZONTAL:
                    layout.text_y += self.REROUTE_STEP
                    layout.bend_point = (geo.point2d.x,
                                         layout.text_y - LEADER_GAP)
                else:
                    layout.text_x += self.REROUTE_STEP
                    layout.bend_point = (layout.text_x - LEADER_GAP,
                                         geo.point2d.y)
        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)
        layouts = LeaderAutoRouter().optimize(
            geometry_items, layouts, mode
        )
        log(f"Leader crossings after reroute: "
            f"{LeaderSegmentEvaluator().crossing_count(geometry_items, layouts)}")
        return layouts


# ============================================================
# v0.0.65
# Geometry Descriptor Foundation
# ============================================================

from typing import Optional
from dataclasses import dataclass

@dataclass
class GeometryDescriptor:
    """Normalized geometry information used by the solver."""

    name: str = ""
    geometry_type: GeometryType = GeometryType.UNKNOWN
    point2d: object = None

    start_point: object = None
    mid_point: object = None
    end_point: object = None
    center_point: object = None

    orientation: str = "Unknown"

    radius: Optional[float] = None

    distance: float = 0.0
    order: int = 0


class GeometryFactory:

    def __init__(self, resolver):
        self.resolver = resolver
        self.edge_eval = EdgePointEvaluator()

    def create(self, subname, dim_mode):
        desc = GeometryDescriptor()
        desc.name = subname
        desc.geometry_type = self.resolver.geometry_type(subname)

        if desc.geometry_type in (GeometryType.LINE,
                                  GeometryType.EDGE,
                                  GeometryType.ARC):
            edge = self.resolver.resolve_edge(subname)
            desc.start_point = self.edge_eval.start_point(edge)
            desc.mid_point = self.edge_eval.mid_point(edge)
            desc.end_point = self.edge_eval.end_point(edge)
            desc.orientation = self.resolver.edge_orientation(subname)

        if desc.geometry_type in (GeometryType.CIRCLE,
                                  GeometryType.ARC):
            desc.center_point = self.resolver.resolve_center(subname)
            desc.point2d = desc.center_point
        else:
            spr = SelectionPointResolver(self.resolver)
            desc.point2d = spr.resolve_for_dimension(subname, dim_mode)

        return desc


class GeometryCache:

    def __init__(self):
        self._cache = {}

    def get(self, key):
        return self._cache.get(key)

    def put(self, key, value):
        self._cache[key] = value

    def clear(self):
        self._cache.clear()


class SelectionGeometryBridge(SelectionGeometryBridge):

    def collect_descriptors(self, selection_engine, view, dim_mode):
        cache = GeometryCache()
        resolver = GeometryResolver(view)
        factory = GeometryFactory(resolver)

        descriptors = []

        for item in selection_engine.collect_selection():
            for subname in getattr(item, "SubElementNames", []):
                d = cache.get(subname)
                if d is None:
                    d = factory.create(subname, dim_mode)
                    cache.put(subname, d)
                descriptors.append(d)

        return descriptors

    def collect_geometry(self, selection_engine, view,
                         dim_mode=DimensionMode.HORIZONTAL):

        geometry = []
        for desc in self.collect_descriptors(
                selection_engine, view, dim_mode):
            if desc.point2d is None:
                continue

            geometry.append(
                GeometryItem(
                    name=desc.name,
                    point2d=desc.point2d,
                    distance=desc.distance,
                    order=desc.order
                )
            )

        self._geometry_cache = geometry
        return geometry


# ============================================================
# v0.0.66
# Geometry Descriptor Expansion
# ============================================================

@dataclass
class BoundingBox2D:
    xmin: float = 0.0
    xmax: float = 0.0
    ymin: float = 0.0
    ymax: float = 0.0


class CurveType(Enum):
    UNKNOWN = auto()
    LINE = auto()
    ARC = auto()
    CIRCLE = auto()


@dataclass
class GeometryDescriptor(GeometryDescriptor):
    curve_type: CurveType = CurveType.UNKNOWN
    bounding_box: object = None
    source_object: object = None
    sub_element: str = ""
    diameter: Optional[float] = None
    is_closed: bool = False


class GeometryFactory(GeometryFactory):

    def create(self, subname, dim_mode):
        desc = super().create(subname, dim_mode)
        desc.sub_element = subname
        desc.source_object = getattr(self.resolver, "view", None)

        edge = None
        try:
            edge = self.resolver.resolve_edge(subname)
        except Exception:
            edge = None

        if edge:
            pts = [v.Point for v in getattr(edge, "Vertexes", [])]
            if pts:
                desc.bounding_box = BoundingBox2D(
                    xmin=min(p.x for p in pts),
                    xmax=max(p.x for p in pts),
                    ymin=min(p.y for p in pts),
                    ymax=max(p.y for p in pts),
                )

            curve = getattr(edge, "Curve", None)
            cname = type(curve).__name__ if curve else ""
            if "Circle" in cname:
                desc.curve_type = CurveType.CIRCLE
                r = getattr(curve, "Radius", None)
                desc.radius = r
                desc.diameter = None if r is None else r * 2.0
                desc.is_closed = True
            elif "Arc" in cname:
                desc.curve_type = CurveType.ARC
            elif "Line" in cname:
                desc.curve_type = CurveType.LINE

        return desc


# ============================================================
# v0.0.67
# Selection Descriptor Foundation
# ============================================================

from dataclasses import dataclass

@dataclass
class SelectionDescriptor:
    object_name: str = ""
    sub_element: str = ""
    source_object: object = None
    view: object = None


class SelectionResolver:

    def __init__(self, selection_engine):
        self.selection_engine = selection_engine

    def collect(self):
        descriptors = []

        for item in self.selection_engine.collect_selection():
            obj = getattr(item, "Object", None)
            for sub in getattr(item, "SubElementNames", []):
                descriptors.append(
                    SelectionDescriptor(
                        object_name=getattr(obj, "Name", ""),
                        sub_element=sub,
                        source_object=obj,
                        view=self.selection_engine.view,
                    )
                )

        return descriptors


class SelectionGeometryBridge(SelectionGeometryBridge):

    def collect_descriptors(self, selection_engine, view,
                            dim_mode=DimensionMode.HORIZONTAL):

        resolver = GeometryResolver(view)
        factory = GeometryFactory(resolver)
        cache = GeometryCache()

        descriptors = []

        for sel in SelectionResolver(selection_engine).collect():
            geo = cache.get(sel.sub_element)
            if geo is None:
                geo = factory.create(sel.sub_element, dim_mode)
                geo.source_object = sel.source_object
                geo.sub_element = sel.sub_element
                cache.put(sel.sub_element, geo)
            descriptors.append(geo)

        return descriptors


# ============================================================
# v0.0.68
# Constraint Foundation
# ============================================================

from dataclasses import dataclass
from enum import Enum, auto

class ConstraintType(Enum):
    ALIGN = auto()
    CLEARANCE = auto()
    LEADER = auto()
    BOUNDARY = auto()

@dataclass
class LayoutConstraint:
    constraint_type: ConstraintType
    target: str
    value: float
    priority: int = 100

class ConstraintBuilder:

    TEXT_CLEARANCE = 8.0
    MODEL_CLEARANCE = 5.0

    def build(self, descriptors, mode):
        constraints = []

        for desc in descriptors:
            constraints.append(
                LayoutConstraint(
                    ConstraintType.CLEARANCE,
                    desc.name,
                    self.TEXT_CLEARANCE,
                    100,
                )
            )

            if getattr(desc, "bounding_box", None) is not None:
                constraints.append(
                    LayoutConstraint(
                        ConstraintType.BOUNDARY,
                        desc.name,
                        self.MODEL_CLEARANCE,
                        80,
                    )
                )

        return constraints


class SelectionGeometryBridge(SelectionGeometryBridge):

    def build_constraints(self, selection_engine, view,
                          dim_mode=DimensionMode.HORIZONTAL):

        descriptors = self.collect_descriptors(
            selection_engine,
            view,
            dim_mode,
        )

        return ConstraintBuilder().build(descriptors, dim_mode)


# ============================================================
# v0.0.69
# Layout Solver Foundation
# ============================================================

from dataclasses import dataclass

@dataclass
class CandidateLayout:
    layouts: list
    score: float = 0.0


class ConstraintEvaluator:

    def evaluate(self, candidate, constraints):
        score = 100.0

        for c in constraints:
            if c.constraint_type == ConstraintType.CLEARANCE:
                score -= max(0.0, 10.0 - c.value)
            elif c.constraint_type == ConstraintType.BOUNDARY:
                score -= max(0.0, 8.0 - c.value) * 0.5

        candidate.score = max(score, 0.0)
        return candidate.score


class LayoutSolver:

    def __init__(self):
        self.evaluator = ConstraintEvaluator()

    def solve(self, layouts, constraints):
        candidate = CandidateLayout(list(layouts))
        self.evaluator.evaluate(candidate, constraints)
        return candidate.layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        bridge = SelectionGeometryBridge()
        constraints = []
        try:
            constraints = bridge.build_constraints(
                ProgressiveDimensionEngine().selection,
                ProgressiveDimensionEngine().view,
                mode
            )
        except Exception:
            pass

        layouts = LayoutSolver().solve(layouts, constraints)
        return layouts


# ============================================================
# v0.0.70
# Candidate Generator Foundation
# ============================================================

from dataclasses import dataclass

@dataclass
class LayoutScore:
    quality: float = 0.0
    constraint: float = 0.0

    @property
    def total(self):
        return self.quality + self.constraint


class CandidateGenerator:

    OFFSETS = (-10.0, -5.0, 0.0, 5.0, 10.0)

    def generate(self, layouts, mode):
        candidates = []
        for delta in self.OFFSETS:
            trial = []
            for item in layouts:
                clone = LayoutItem(
                    text_x=item.text_x,
                    text_y=item.text_y,
                    bend_point=item.bend_point,
                    visible=item.visible
                )
                if mode == DimensionMode.HORIZONTAL:
                    clone.text_y += delta
                else:
                    clone.text_x += delta
                trial.append(clone)
            candidates.append(CandidateLayout(trial))
        return candidates


class LayoutSolver(LayoutSolver):

    def solve(self, layouts, constraints, mode=None):
        if mode is None:
            return super().solve(layouts, constraints)

        generator = CandidateGenerator()
        quality = LayoutQualityEvaluator()

        best_layouts = layouts
        best_total = float("-inf")

        for candidate in generator.generate(layouts, mode):
            q = quality.score(candidate.layouts, mode)
            c = self.evaluator.evaluate(candidate, constraints)
            total = LayoutScore(q, c).total
            if total > best_total:
                best_total = total
                best_layouts = candidate.layouts

        return best_layouts


# ============================================================
# v0.0.71
# Advanced Layout Scoring
# ============================================================

from dataclasses import dataclass

@dataclass
class LayoutScore:
    quality: float = 0.0
    constraint: float = 0.0
    collisions: int = 0
    leader_crossings: int = 0
    boundary_penalty: float = 0.0

    @property
    def total(self):
        return (
            self.quality
            + self.constraint
            - self.collisions * 10.0
            - self.leader_crossings * 20.0
            - self.boundary_penalty
        )


class ConstraintEvaluator(ConstraintEvaluator):

    def evaluate(self, candidate, constraints):
        score = 100.0
        boundary = 0.0

        for c in constraints:
            if c.constraint_type == ConstraintType.CLEARANCE:
                score -= max(0.0, 8.0 - c.value)
            elif c.constraint_type == ConstraintType.BOUNDARY:
                boundary += max(0.0, 5.0 - c.value)

        candidate.score = max(score - boundary, 0.0)
        return candidate.score


class CandidateGenerator(CandidateGenerator):

    SIDE_OFFSETS = (
        ("Top", 10.0),
        ("Bottom", -10.0),
        ("Left", -10.0),
        ("Right", 10.0),
    )

    def generate(self, layouts, mode):
        candidates = super().generate(layouts, mode)

        for side, delta in self.SIDE_OFFSETS:
            trial = []
            for item in layouts:
                clone = LayoutItem(
                    text_x=item.text_x,
                    text_y=item.text_y,
                    bend_point=item.bend_point,
                    visible=item.visible,
                )
                if mode == DimensionMode.HORIZONTAL:
                    clone.text_y += delta
                else:
                    clone.text_x += delta
                trial.append(clone)
            candidates.append(CandidateLayout(trial))

        return candidates


# ============================================================
# v0.0.72
# Candidate Ranking
# ============================================================

from dataclasses import dataclass, field

@dataclass(order=True)
class RankedCandidate:
    total_score: float
    candidate_id: int = field(compare=False)
    layouts: list = field(compare=False, default_factory=list)
    score: object = field(compare=False, default=None)
    reason: str = field(compare=False, default="")


class CandidateRanking:

    def rank(self, ranked_candidates):
        return sorted(
            ranked_candidates,
            key=lambda c: c.total_score,
            reverse=True
        )


class LayoutSolver(LayoutSolver):

    def solve_with_ranking(self, layouts, constraints, mode):
        generator = CandidateGenerator()
        quality = LayoutQualityEvaluator()

        ranked = []

        for idx, candidate in enumerate(generator.generate(layouts, mode)):
            q = quality.score(candidate.layouts, mode)
            c = self.evaluator.evaluate(candidate, constraints)
            score = LayoutScore(
                quality=q,
                constraint=c
            )
            ranked.append(
                RankedCandidate(
                    total_score=score.total,
                    candidate_id=idx,
                    layouts=candidate.layouts,
                    score=score,
                    reason="Highest total score"
                )
            )

        ranked = CandidateRanking().rank(ranked)

        if ranked:
            log(f"Best candidate #{ranked[0].candidate_id} score={ranked[0].total_score:.2f}")

        return ranked


# ============================================================
# v0.0.73
# Solver Result Tracking
# ============================================================

from dataclasses import dataclass, field

@dataclass
class RejectedCandidate:
    candidate_id: int
    score: float
    reasons: list = field(default_factory=list)


@dataclass
class SolverResult:
    selected: object = None
    ranked: list = field(default_factory=list)
    rejected: list = field(default_factory=list)


class LayoutSolver(LayoutSolver):

    def solve_with_result(self, layouts, constraints, mode):
        ranked = self.solve_with_ranking(layouts, constraints, mode)

        result = SolverResult()

        if ranked:
            result.selected = ranked[0]
            result.ranked = ranked

            for item in ranked[1:]:
                result.rejected.append(
                    RejectedCandidate(
                        candidate_id=item.candidate_id,
                        score=item.total_score,
                        reasons=[
                            "Lower total score than selected candidate"
                        ]
                    )
                )

        return result


class IntegratedLayoutManager(IntegratedLayoutManager):

    def solve_layout(self, layouts, constraints, mode):
        solver = LayoutSolver()
        result = solver.solve_with_result(layouts, constraints, mode)

        if result.selected is not None:
            log(
                f"Selected candidate #{result.selected.candidate_id} "
                f"score={result.selected.total_score:.2f}"
            )

        return result


# ============================================================
# v0.0.74
# Detailed Score Aggregation
# ============================================================

from dataclasses import dataclass, field

@dataclass
class ScoreBreakdown:
    quality: float = 0.0
    constraint: float = 0.0
    collision_penalty: float = 0.0
    boundary_penalty: float = 0.0
    leader_penalty: float = 0.0
    notes: list = field(default_factory=list)

    @property
    def total(self):
        return (
            self.quality
            + self.constraint
            - self.collision_penalty
            - self.boundary_penalty
            - self.leader_penalty
        )


class LayoutSolver(LayoutSolver):

    def evaluate_candidate(self, candidate, constraints, mode):
        quality = LayoutQualityEvaluator().score(candidate.layouts, mode)
        constraint = self.evaluator.evaluate(candidate, constraints)

        breakdown = ScoreBreakdown(
            quality=quality,
            constraint=constraint
        )

        candidate.score = breakdown
        return breakdown


class SolverResult(SolverResult):

    def best_score(self):
        if self.selected is None:
            return None
        return getattr(self.selected, "score", None)


# ============================================================
# v0.0.75
# Refactoring Foundation
# ============================================================

from dataclasses import dataclass

@dataclass
class SolverContext:
    geometry: list
    constraints: list
    mode: object
    result: object = None


class SolverPipeline:

    def __init__(self):
        self._solver = LayoutSolver()

    def execute(self, geometry, constraints, mode):
        context = SolverContext(
            geometry=geometry,
            constraints=constraints,
            mode=mode,
        )
        context.result = self._solver.solve_with_result(
            geometry,
            constraints,
            mode,
        )
        return context


class IntegratedLayoutManager(IntegratedLayoutManager):

    def run_solver_pipeline(self, geometry, constraints, mode):
        """Unified entry point for future solver-based layout."""
        pipeline = SolverPipeline()
        return pipeline.execute(
            geometry,
            constraints,
            mode,
        )


def build_solver_context(geometry, constraints, mode):
    """Factory helper used by future modules."""
    return SolverContext(
        geometry=geometry,
        constraints=constraints,
        mode=mode,
    )

# ============================================================
# v0.0.76
# Solver Pipeline Integration
# ============================================================

class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        bridge = SelectionGeometryBridge()
        constraints = []

        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode,
            )
        except Exception as exc:
            log(f"Constraint build skipped: {exc}", LogLevel.WARNING)

        pipeline = SolverPipeline()
        result = pipeline.execute(
            layouts,
            constraints,
            mode,
        )

        if getattr(result, "result", None) and result.result.selected:
            return result.result.selected.layouts

        return layouts


# ============================================================
# v0.0.77
# Solver Pipeline Integration Step 2
# ============================================================

class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        constraints = []
        try:
            bridge = SelectionGeometryBridge()
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode
            )
        except Exception as exc:
            log(f"Constraint build fallback: {exc}", LogLevel.WARNING)

        solver = LayoutSolver()

        try:
            result = solver.solve_with_result(
                layouts,
                constraints,
                mode
            )
            if result.selected is not None:
                return result.selected.layouts
        except Exception as exc:
            log(f"Solver fallback: {exc}", LogLevel.WARNING)

        return solver.solve(layouts, constraints, mode)


# ============================================================
# v0.0.78
# Candidate Evaluation Integration
# ============================================================

class LayoutSolver(LayoutSolver):

    def solve_best(self, geometry_items, layouts, constraints, mode):
        """Select the best layout candidate using the current scoring model."""
        ranked = self.solve_with_ranking(layouts, constraints, mode)

        if not ranked:
            return layouts

        best = ranked[0]

        try:
            score = getattr(best, "total_score", 0.0)
            log(f"Selected candidate score: {score:.2f}")
        except Exception:
            pass

        return best.layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        constraints = []
        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            bridge = SelectionGeometryBridge()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode,
            )
        except Exception as exc:
            log(f"Constraint fallback: {exc}", LogLevel.WARNING)

        try:
            layouts = LayoutSolver().solve_best(
                geometry_items,
                layouts,
                constraints,
                mode,
            )
        except Exception as exc:
            log(f"Candidate evaluation skipped: {exc}", LogLevel.WARNING)

        return layouts


# ============================================================
# v0.0.79
# Candidate Selection Refinement
# ============================================================

class LayoutSolver(LayoutSolver):

    def solve_best(self, geometry_items, layouts, constraints, mode):
        result = self.solve_with_result(layouts, constraints, mode)

        if result.selected is None:
            return layouts

        best = result.selected.layouts

        try:
            best = LocalCollisionRecovery().optimize(best, mode)
        except Exception:
            pass

        try:
            best = LeaderAutoRouter().optimize(
                geometry_items,
                best,
                mode
            )
        except Exception:
            pass

        return best


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        constraints = []
        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            bridge = SelectionGeometryBridge()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode
            )
        except Exception:
            pass

        return LayoutSolver().solve_best(
            geometry_items,
            layouts,
            constraints,
            mode
        )


# ============================================================
# v0.0.80
# Candidate Stability Pass
# ============================================================

class LayoutSolver(LayoutSolver):

    def solve_best(self, geometry_items, layouts, constraints, mode):
        result = self.solve_with_result(layouts, constraints, mode)

        if result.selected is None:
            return layouts

        best = result.selected.layouts

        try:
            best = LocalCollisionRecovery().optimize(best, mode)
        except Exception:
            pass

        try:
            best = LeaderAutoRouter().optimize(
                geometry_items,
                best,
                mode
            )
        except Exception:
            pass

        try:
            quality = LayoutQualityEvaluator().score(best, mode)
            crossings = LeaderSegmentEvaluator().crossing_count(
                geometry_items,
                best
            )
            collisions = TextBoundingBoxEvaluator().collision_count(best)
            log(
                f"Final layout: quality={quality:.1f}, "
                f"collisions={collisions}, crossings={crossings}"
            )
        except Exception:
            pass

        return best


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        constraints = []
        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            bridge = SelectionGeometryBridge()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode
            )
        except Exception:
            pass

        return LayoutSolver().solve_best(
            geometry_items,
            layouts,
            constraints,
            mode
        )


# ============================================================
# v0.0.81
# Solver Stability Metrics
# ============================================================

class SolverStatistics:

    def __init__(self):
        self.candidates = 0
        self.selected_score = 0.0
        self.collisions = 0
        self.crossings = 0

    def report(self):
        log(
            f"SolverStats: candidates={self.candidates}, "
            f"score={self.selected_score:.2f}, "
            f"collisions={self.collisions}, "
            f"crossings={self.crossings}"
        )


class LayoutSolver(LayoutSolver):

    def solve_with_statistics(self, geometry_items, layouts, constraints, mode):
        result = self.solve_with_result(layouts, constraints, mode)

        stats = SolverStatistics()
        stats.candidates = len(getattr(result, "ranked", []))

        if result.selected is not None:
            stats.selected_score = getattr(result.selected, "total_score", 0.0)
            stats.collisions = TextBoundingBoxEvaluator().collision_count(
                result.selected.layouts
            )
            stats.crossings = LeaderSegmentEvaluator().crossing_count(
                geometry_items,
                result.selected.layouts
            )
            stats.report()
            return result.selected.layouts

        return layouts


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        constraints = []
        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()
            bridge = SelectionGeometryBridge()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode
            )
        except Exception:
            pass

        return LayoutSolver().solve_with_statistics(
            geometry_items,
            layouts,
            constraints,
            mode
        )


# ============================================================
# v0.0.82
# Enum Compatibility Fix + Solver Diagnostics
# ============================================================

class SolverDiagnostics:

    def validate(self, result):
        if result is None:
            return False
        if getattr(result, "selected", None) is None:
            log("Solver produced no selected candidate.", LogLevel.WARNING)
            return False
        return True


class IntegratedLayoutManager(IntegratedLayoutManager):

    def process(self, geometry_items, mode):
        layouts = super().process(geometry_items, mode)

        try:
            engine = ProgressiveDimensionEngine()
            engine.initialize()

            bridge = SelectionGeometryBridge()
            constraints = bridge.build_constraints(
                engine.selection,
                engine.view,
                mode,
            )

            solver = LayoutSolver()
            result = solver.solve_with_result(
                layouts,
                constraints,
                mode,
            )

            if SolverDiagnostics().validate(result):
                return result.selected.layouts

        except Exception as exc:
            log(f"Solver fallback: {exc}", LogLevel.WARNING)

        return layouts
