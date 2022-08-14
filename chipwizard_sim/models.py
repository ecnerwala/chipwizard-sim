from __future__ import annotations

from enum import Enum, unique
from dataclasses import dataclass
from typing import Optional


__all__ = [
    "Coords",
    "Direction",
    "CellComponent",
    "LayerCell",
    "Cell",
    "Solution",
    "Signal",
    "SignalType",
    "Level",
    "LayerCellState",
    "CellState",
    "State",
    "Metrics",
    "SimulationResult",
]


@dataclass(eq=True, order=True, frozen=True)
class Coords:
    x: int
    y: int

    def in_bounds(self) -> bool:
        return 0 <= self.x < 6 and 0 <= self.y < 5

    def __add__(self, o: Coords) -> Coords:
        return Coords(self.x + o.x, self.y + o.y)


@unique
class Direction(Enum):
    RIGHT = 1
    UP = 2
    LEFT = 4
    DOWN = 8

    def opposite(self) -> Direction:
        return {
            Direction.RIGHT: Direction.LEFT,
            Direction.UP: Direction.DOWN,
            Direction.LEFT: Direction.RIGHT,
            Direction.DOWN: Direction.UP,
        }[self]

    def delta(self) -> Coords:
        if self == Direction.RIGHT:
            return Coords(+1, 0)
        elif self == Direction.UP:
            return Coords(0, +1)
        elif self == Direction.LEFT:
            return Coords(-1, 0)
        elif self == Direction.DOWN:
            return Coords(0, -1)
        else:
            assert False


@unique
class CellComponent(Enum):
    METAL = 1
    NTYPE = 2
    PTYPE = 4
    CAPACITOR = 8
    VIA = 16
    N_ON_TOP = 32


@dataclass
class LayerCell:
    value: bool
    connections: set[Direction]

    def __bool__(self):
        return self.value

    def check(self):
        if not self.value:
            assert not self.connections


class Layer(Enum):
    METAL_LAYER = 0
    NTYPE_LAYER = 1
    PTYPE_LAYER = 2


@dataclass
class Cell:
    metal: LayerCell
    ntype: LayerCell
    ptype: LayerCell

    def layer(self, idx: Layer) -> LayerCell:
        return [self.metal, self.ntype, self.ptype][idx.value]

    capacitor: bool
    via: bool

    n_on_top: bool

    def is_transistor(self):
        return self.ntype and self.ptype

    def check(self):
        self.metal.check()
        self.ntype.check()
        self.ptype.check()

        if self.capacitor:
            # Capacitors can't overlap with silicon
            assert not self.ntype and not self.ptype

        if self.via:
            # Vias must go on raw ntype or ptype
            assert self.ntype or self.ptype
            assert not self.is_transistor()

        # Cannot have both ntype and ptype
        assert not (self.ntype.connections & self.ptype.connections)

        if self.is_transistor():
            base = self.ntype if self.n_on_top else self.ptype
            emi_col = self.ptype if self.n_on_top else self.ntype

            # Emitter/collector must have exactly 2 connections in opposite directions
            assert len(emi_col.connections) == 2 and sum(
                (d.delta() for d in emi_col.connections), Coords(0, 0)
            ) == Coords(0, 0)

            # Base must have at least one connection
            assert len(base.connections) >= 1


@dataclass
class Solution:
    cells: list[list[Cell]]
    selection: Optional[tuple[Coords, Coords]]
    save_string: Optional[str] = None

    def check(self):
        assert len(self.cells) == 6 and all(len(a) == 5 for a in self.cells)
        for x in range(6):
            for y in range(5):
                self.cells[x][y].check()
                for layer in Layer:
                    for d in self.cells[x][y].layer(layer).connections:
                        n_loc = Coords(x, y) + d.delta()
                        if n_loc.in_bounds():
                            assert (
                                d.opposite()
                                in self.cells[n_loc.x][n_loc.y].layer(layer).connections
                            )
                        else:
                            assert (
                                layer == Layer.METAL_LAYER
                                and n_loc.x in {-1, 6}
                                and n_loc.y in {0, 2, 4}
                            )


class SignalType(Enum):
    IN = 0
    OUT = 1


@dataclass
class Signal:
    values: list[int]
    type: SignalType
    loc: Coords


@dataclass
class Level:
    level_id: int
    level_name: str
    level_index: int  # for sorting

    signal_type: list[SignalType]
    signals: list[list[int]]


@dataclass
class LayerCellState:
    value: bool
    connections: set[Direction]
    powered: bool = False
    open: bool = True

    @classmethod
    def from_layer_cell(cls, layer_cell: LayerCell) -> LayerCellState:
        return cls(layer_cell.value, layer_cell.connections)


@dataclass
class CellState:
    metal: LayerCellState
    ntype: LayerCellState
    ptype: LayerCellState

    def layer(self, idx: Layer) -> LayerCellState:
        return [self.metal, self.ntype, self.ptype][idx.value]


    capacitor: bool
    via: bool

    n_on_top: bool

    def update_gates(self):
        if self.capacitor and self.metal:
            if not self.metal.powered:
                self.metal.open = False

        if self.ntype and self.ptype:
            if self.n_on_top:
                self.ptype.open = not self.ntype.powered
            else:
                self.ntype.open = self.ptype.powered

    @classmethod
    def from_cell(cls, cell: Cell) -> CellState:
        res = cls(
            metal=LayerCellState.from_layer_cell(cell.metal),
            ntype=LayerCellState.from_layer_cell(cell.ntype),
            ptype=LayerCellState.from_layer_cell(cell.ptype),
            capacitor=cell.capacitor,
            via=cell.via,
            n_on_top=cell.n_on_top
        )
        res.update_gates()
        return res


@dataclass
class State:
    cells: list[list[CellState]]

    def check_state(self):
        pass

    def visualize(self) -> str:
        return ""


@dataclass
class Metrics:
    # Counts of specific cell types
    # Note that num_ntype and num_ptype both count all transistors
    num_metal: int
    num_ntype: int
    num_ptype: int
    num_capacitors: int
    num_vias: int
    num_npn_transistors: int
    num_pnp_transistors: int

    # Aggregate statistics
    num_transistors: int
    num_silicon: int

    # Total of num_silicon + num_metal + num_vias
    total_volume: int

    silicon_width: int
    silicon_height: int
    silicon_size: int


@dataclass
class SimulationResult:
    level: Level
    solution: Solution

    states: list[State]

    metrics: Metrics
