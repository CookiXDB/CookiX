#!/usr/bin/env python3
"""
CookiX — The Topological Memory Database (All-in-One)
"Stop measuring distances. Start understanding adjacency."

Run:  pip install numpy networkx scipy PyQt5 PyOpenGL
Then: python cookix_app.py
"""

import sys
import os
import math
import threading
import numpy as np
import networkx as nx
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QGroupBox, QTextEdit,
    QSplitter, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QOpenGLWidget, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QDialog, QDialogButtonBox, QMessageBox, QListWidget, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from OpenGL.GL import *
from OpenGL.GLU import *


# ═══════════════════════════════════════════════════════════
#  CORE: Distance Metrics & Vector DB
# ═══════════════════════════════════════════════════════════

class DistanceMetric(Enum):
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"
    MINKOWSKI = "minkowski"
    CANBERRA = "canberra"
    BRAYCURTIS = "braycurtis"
    CUSTOM_ADAPTIVE = "custom_adaptive"


@dataclass
class VectorEntry:
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    timestamp: datetime


class DistanceCalculator:
    @staticmethod
    def euclidean(v1, v2): return float(np.sqrt(np.sum((v1 - v2) ** 2)))
    @staticmethod
    def cosine(v1, v2):
        d = np.dot(v1, v2); n = np.linalg.norm(v1) * np.linalg.norm(v2)
        return 0.0 if n == 0 else float(1.0 - d / n)
    @staticmethod
    def manhattan(v1, v2): return float(np.sum(np.abs(v1 - v2)))
    @staticmethod
    def chebyshev(v1, v2): return float(np.max(np.abs(v1 - v2)))
    @staticmethod
    def minkowski(v1, v2, p=3): return float(np.power(np.sum(np.power(np.abs(v1 - v2), p)), 1/p))
    @staticmethod
    def canberra(v1, v2):
        n = np.abs(v1 - v2); d = np.abs(v1) + np.abs(v2); m = d != 0
        return float(np.sum(n[m] / d[m]))
    @staticmethod
    def braycurtis(v1, v2):
        n = np.sum(np.abs(v1 - v2)); d = np.sum(np.abs(v1 + v2))
        return 0.0 if d == 0 else float(n / d)
    @staticmethod
    def custom_adaptive(v1, v2):
        e = DistanceCalculator.euclidean(v1, v2)
        c = DistanceCalculator.cosine(v1, v2)
        m = DistanceCalculator.manhattan(v1, v2)
        m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
        r = min(m1, m2) / max(m1, m2) if max(m1, m2) > 0 else 1.0
        return float(0.4 * e + 0.3 * c + 0.2 * m + 0.1 * (1 - r))


class VectorDB:
    def __init__(self, dimension=3, metric=DistanceMetric.EUCLIDEAN):
        self.dimension = dimension
        self.metric = metric
        self.vectors: List[VectorEntry] = []
        self.index_map: Dict[str, int] = {}
        self.lock = threading.Lock()
        self.stats = {'total_vectors': 0, 'total_queries': 0}

    def add_vector(self, vid, vector, metadata=None):
        if len(vector) != self.dimension:
            raise ValueError(f"Dimension mismatch: {len(vector)} vs {self.dimension}")
        with self.lock:
            if vid in self.index_map: return False
            self.vectors.append(VectorEntry(vid, np.array(vector, dtype=np.float32), metadata or {}, datetime.now()))
            self.index_map[vid] = len(self.vectors) - 1
            self.stats['total_vectors'] += 1
            return True

    def _calc_dist(self, v1, v2, metric=None):
        metric = metric or self.metric
        funcs = {
            DistanceMetric.EUCLIDEAN: DistanceCalculator.euclidean,
            DistanceMetric.COSINE: DistanceCalculator.cosine,
            DistanceMetric.MANHATTAN: DistanceCalculator.manhattan,
            DistanceMetric.CHEBYSHEV: DistanceCalculator.chebyshev,
            DistanceMetric.MINKOWSKI: DistanceCalculator.minkowski,
            DistanceMetric.CANBERRA: DistanceCalculator.canberra,
            DistanceMetric.BRAYCURTIS: DistanceCalculator.braycurtis,
            DistanceMetric.CUSTOM_ADAPTIVE: DistanceCalculator.custom_adaptive,
        }
        return funcs[metric](v1, v2)

    def query(self, qv, k=5, metric=None):
        qv = np.array(qv, dtype=np.float32)
        with self.lock:
            dists = [(e, self._calc_dist(qv, e.vector, metric)) for e in self.vectors]
            dists.sort(key=lambda x: x[1])
            self.stats['total_queries'] += 1
            return dists[:k]

    def get_all_vectors(self): return self.vectors.copy()
    def get_stats(self): return self.stats.copy()
    def __len__(self): return len(self.vectors)


# ═══════════════════════════════════════════════════════════
#  CORE: Topological Engine (CookiX)
# ═══════════════════════════════════════════════════════════

class EdgeType(Enum):
    IS_A = "is_a"; PART_OF = "part_of"; HAS_PART = "has_part"
    CAUSES = "causes"; PREVENTS = "prevents"; ENABLES = "enables"
    REQUIRES = "requires"; CONTRADICTS = "contradicts"; IMPLIES = "implies"
    SIMILAR_TO = "similar_to"; DIFFERENT_FROM = "different_from"
    COMPATIBLE_WITH = "compatible_with"; REPLACES = "replaces"
    EXAMPLE_OF = "example_of"; USED_IN = "used_in"
    PRECEDES = "precedes"; FOLLOWS = "follows"


@dataclass
class EdgeDef:
    target_id: str; edge_type: EdgeType; weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False


@dataclass
class KnowledgeObject:
    id: str; content: str = ""
    edges: List[EdgeDef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStep:
    from_id: str; to_id: str; edge_type: EdgeType; weight: float
    def __repr__(self): return f"{self.from_id} --[{self.edge_type.value}]--> {self.to_id}"


@dataclass
class QueryResult:
    query: str; target_id: str; path: List[ReasoningStep]
    total_distance: float; confidence: float; explanation: str
    @property
    def path_string(self):
        if not self.path: return "(direct)"
        parts = [self.path[0].from_id]
        for s in self.path: parts += [f"--[{s.edge_type.value}]-->", s.to_id]
        return " ".join(parts)


class TopologicalEngine:
    def __init__(self, alpha=0.6, beta=0.4):
        self.objects: Dict[str, KnowledgeObject] = {}
        self.graph = nx.DiGraph()
        self.alpha = alpha; self.beta = beta

    def add_object(self, obj: KnowledgeObject):
        if obj.id in self.objects: return False
        self.objects[obj.id] = obj
        self.graph.add_node(obj.id, content=obj.content, metadata=obj.metadata)
        for e in obj.edges:
            self.graph.add_edge(obj.id, e.target_id, edge_type=e.edge_type.value, weight=e.weight, metadata=e.metadata)
            if e.bidirectional:
                self.graph.add_edge(e.target_id, obj.id, edge_type=e.edge_type.value, weight=e.weight, metadata=e.metadata)
        return True

    def query_direct(self, src, etype):
        obj = self.objects.get(src)
        if not obj: return []
        return [(e.target_id, e) for e in obj.edges if e.edge_type == etype]

    def query_path(self, src, tgt, max_hops=5):
        if src not in self.objects or tgt not in self.objects: return None
        visited = {src}; queue = [(src, [], 0.0)]
        while queue:
            cur, path, dist = queue.pop(0)
            if cur == tgt:
                return QueryResult(f"{src}->{tgt}", tgt, path, dist, 1.0/(1+dist), self._explain(path))
            if len(path) >= max_hops: continue
            obj = self.objects.get(cur)
            if not obj: continue
            for e in obj.edges:
                if e.target_id not in visited:
                    visited.add(e.target_id)
                    step = ReasoningStep(cur, e.target_id, e.edge_type, e.weight)
                    queue.append((e.target_id, path + [step], dist + e.weight))
        return None

    def query_neighborhood(self, src, max_hops=2, etypes=None):
        results = {}; visited = {src}; queue = [(src, [], 0.0)]
        while queue:
            cur, path, dist = queue.pop(0)
            if cur != src:
                results[cur] = QueryResult(f"N({src})", cur, path, dist, 1.0/(1+dist), self._explain(path))
            if len(path) >= max_hops: continue
            obj = self.objects.get(cur)
            if not obj: continue
            for e in obj.edges:
                if e.target_id not in visited and (etypes is None or e.edge_type in etypes):
                    visited.add(e.target_id)
                    queue.append((e.target_id, path + [ReasoningStep(cur, e.target_id, e.edge_type, e.weight)], dist + e.weight))
        return results

    def query_reasoning(self, src, intent, target_etype, max_hops=3):
        results = []
        direct = self.query_direct(src, target_etype)
        for tid, e in direct:
            step = ReasoningStep(src, tid, e.edge_type, e.weight)
            results.append(QueryResult(intent, tid, [step], e.weight, 1.0, f"Direct {target_etype.value} found."))
        if results: return sorted(results, key=lambda r: r.total_distance)
        expand_types = {EdgeType.SIMILAR_TO, EdgeType.IS_A, EdgeType.PART_OF}
        nbrs = self.query_neighborhood(src, max_hops, expand_types)
        for nid, nr in nbrs.items():
            for ftid, fe in self.query_direct(nid, target_etype):
                fp = nr.path + [ReasoningStep(nid, ftid, fe.edge_type, fe.weight)]
                td = nr.total_distance + fe.weight
                expl = f"No direct {target_etype.value}. Found via {len(fp)}-hop path."
                results.append(QueryResult(intent, ftid, fp, td, 1.0/(1+td), expl))
        return sorted(results, key=lambda r: r.total_distance)

    def geodesic(self, a, b):
        try: return float(nx.shortest_path_length(self.graph, a, b, weight='weight'))
        except: return float('inf')

    def get_stats(self):
        s = {'objects': len(self.objects), 'edges': self.graph.number_of_edges()}
        if self.graph.number_of_nodes() > 0:
            degs = [d for _, d in self.graph.degree()]
            s['avg_degree'] = f"{np.mean(degs):.1f}"
            s['density'] = f"{nx.density(self.graph):.3f}"
            et = {}
            for u, v, d in self.graph.edges(data=True):
                t = d.get('edge_type', '?'); et[t] = et.get(t, 0) + 1
            s['edge_types'] = et
        return s

    def _explain(self, path):
        if not path: return "Direct match."
        return " → ".join(f"'{s.from_id}' --[{s.edge_type.value}]--> '{s.to_id}'" for s in path)

    def __len__(self): return len(self.objects)


# ═══════════════════════════════════════════════════════════
#  DEMO SCENARIOS (prebuilt)
# ═══════════════════════════════════════════════════════════

def build_umbrella_scenario():
    engine = TopologicalEngine()
    engine.add_object(KnowledgeObject("rain", "Rain — precipitation", edges=[
        EdgeDef("storm", EdgeType.PART_OF), EdgeDef("water", EdgeType.IS_A),
        EdgeDef("rain_coat", EdgeType.CAUSES, 0.8, {"effect": "gets wet"}),
    ]))
    engine.add_object(KnowledgeObject("umbrella", "Umbrella — rain protection", edges=[
        EdgeDef("rain", EdgeType.PREVENTS, 0.5, {"mechanism": "canopy shield"}),
        EdgeDef("rain_coat", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("rain_coat", "Rain coat — waterproof outerwear", edges=[
        EdgeDef("rain", EdgeType.PREVENTS, 0.6, {"mechanism": "waterproof fabric"}),
        EdgeDef("umbrella", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("storm", "Storm — severe weather", edges=[
        EdgeDef("rain", EdgeType.HAS_PART),
        EdgeDef("umbrella", EdgeType.CONTRADICTS, metadata={"reason": "too windy"}),
    ]))
    engine.add_object(KnowledgeObject("water", "Water — H2O"))
    engine.add_object(KnowledgeObject("sunshine", "Sunshine", edges=[
        EdgeDef("rain", EdgeType.CONTRADICTS),
    ]))
    return engine


def build_pipe_scenario():
    engine = TopologicalEngine()
    engine.add_object(KnowledgeObject("pipe_120mm", "120mm steel pipe", edges=[
        EdgeDef("pipe_130mm", EdgeType.SIMILAR_TO, 0.3, {"tolerance": "10mm"}),
        EdgeDef("steel_pipe", EdgeType.IS_A),
        EdgeDef("adapter_ring", EdgeType.REQUIRES),
    ], metadata={"diameter": 120}))
    engine.add_object(KnowledgeObject("pipe_130mm", "130mm steel pipe", edges=[
        EdgeDef("pipe_120mm", EdgeType.SIMILAR_TO, 0.3),
        EdgeDef("fitting_B", EdgeType.COMPATIBLE_WITH, 0.2, {"spec": "ISO-4422"}),
        EdgeDef("steel_pipe", EdgeType.IS_A),
    ], metadata={"diameter": 130}))
    engine.add_object(KnowledgeObject("fitting_B", "Type B flanged fitting, 130mm", edges=[
        EdgeDef("pipe_130mm", EdgeType.COMPATIBLE_WITH, 0.2),
        EdgeDef("iso_4422", EdgeType.USED_IN),
    ], metadata={"nominal_size": 130}))
    engine.add_object(KnowledgeObject("steel_pipe", "Steel pipe category"))
    engine.add_object(KnowledgeObject("adapter_ring", "Adapter 120→130mm", edges=[
        EdgeDef("pipe_120mm", EdgeType.COMPATIBLE_WITH),
        EdgeDef("pipe_130mm", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("iso_4422", "ISO 4422 — Pipe standard"))
    return engine


# ═══════════════════════════════════════════════════════════
#  UI: OpenGL 3D Widget
# ═══════════════════════════════════════════════════════════

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vectors = []; self.query_vector = None; self.neighbors = []
        self.selected_idx = None; self.rotation_x = 30; self.rotation_y = 45
        self.zoom = -15; self.last_pos = None; self.is_dragging = False
        self.animate = False; self.anim_angle = 0
        self.on_selected = None

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING); glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glLightfv(GL_LIGHT0, GL_POSITION, [5, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        glClearColor(0.06, 0.06, 0.10, 1.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h); glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(45, w/h if h else 1, 0.1, 100.0); glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT); glLoadIdentity()
        glTranslatef(0, 0, self.zoom); glRotatef(self.rotation_x, 1, 0, 0); glRotatef(self.rotation_y, 0, 1, 0)
        if self.animate:
            glRotatef(self.anim_angle, 0, 1, 0); self.anim_angle = (self.anim_angle + 0.8) % 360
        self._axes(); self._grid(); self._vectors(); self._connections()

    def _axes(self):
        glDisable(GL_LIGHTING); glLineWidth(2.5)
        for c, e in [((0.9,0.2,0.2),(6,0,0)),((0.2,0.9,0.2),(0,6,0)),((0.2,0.2,0.9),(0,0,6))]:
            glColor3f(*c); glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(*e); glEnd()
        glEnable(GL_LIGHTING); glLineWidth(1)

    def _grid(self):
        glDisable(GL_LIGHTING); glColor3f(0.15,0.15,0.20); glLineWidth(0.5)
        glBegin(GL_LINES)
        for i in range(-10,11):
            glVertex3f(i,0,-10); glVertex3f(i,0,10); glVertex3f(-10,0,i); glVertex3f(10,0,i)
        glEnd(); glEnable(GL_LIGHTING); glLineWidth(1)

    def _vectors(self):
        for i, (v, c, lbl) in enumerate(self.vectors):
            if len(v) < 3: continue
            x, y, z = v[0], v[1], v[2]
            if i == self.selected_idx: glColor3f(0, 1, 1); sz = 0.22
            elif i in self.neighbors: glColor3f(1, 1, 0); sz = 0.16
            else: glColor3f(*c); sz = 0.10
            glPushMatrix(); glTranslatef(x, y, z)
            q = gluNewQuadric(); gluSphere(q, sz, 16, 16); gluDeleteQuadric(q)
            if i == self.selected_idx:
                glDisable(GL_LIGHTING); glColor3f(1,1,1); glLineWidth(2.5)
                glBegin(GL_LINE_LOOP)
                for a in range(0, 360, 10): r = a*math.pi/180; glVertex3f(0.28*math.cos(r), 0.28*math.sin(r), 0)
                glEnd(); glLineWidth(1); glEnable(GL_LIGHTING)
            glPopMatrix()
            glDisable(GL_LIGHTING); glColor3f(*c); glLineWidth(1.2)
            glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(x,y,z); glEnd()
            glEnable(GL_LIGHTING); glLineWidth(1)

    def _connections(self):
        if self.query_vector is None or not self.neighbors: return
        qx, qy, qz = self.query_vector[:3]
        glDisable(GL_LIGHTING); glColor3f(1, 0.9, 0); glLineWidth(2.5)
        glBegin(GL_LINES)
        for idx in self.neighbors:
            if idx < len(self.vectors):
                v = self.vectors[idx][0]
                if len(v) >= 3: glVertex3f(qx, qy, qz); glVertex3f(v[0], v[1], v[2])
        glEnd()
        # Draw query point
        glColor3f(1, 1, 1)
        glPushMatrix(); glTranslatef(qx, qy, qz)
        q = gluNewQuadric(); gluSphere(q, 0.18, 16, 16); gluDeleteQuadric(q)
        glPopMatrix()
        glEnable(GL_LIGHTING); glLineWidth(1)

    def set_vectors(self, data): self.vectors = data; self.update()
    def set_query(self, qv, nbrs): self.query_vector = qv; self.neighbors = nbrs; self.update()
    def clear_query(self): self.query_vector = None; self.neighbors = []; self.update()

    def mousePressEvent(self, e):
        self.last_pos = e.pos(); self.is_dragging = False
        if e.button() == Qt.LeftButton: self._click_test(e.x(), e.y())

    def _click_test(self, mx, my):
        try:
            self.makeCurrent(); vp = [0, 0, self.width(), self.height()]
            ay = self.rotation_y*np.pi/180; cy, sy = np.cos(ay), np.sin(ay)
            ry = np.array([[cy,0,sy,0],[0,1,0,0],[-sy,0,cy,0],[0,0,0,1]], dtype=np.float64)
            ax = self.rotation_x*np.pi/180; cx, sx = np.cos(ax), np.sin(ax)
            rx = np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]], dtype=np.float64)
            tr = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,self.zoom],[0,0,0,1]], dtype=np.float64)
            mv = tr @ rx @ ry; pr = glGetDoublev(GL_PROJECTION_MATRIX); wy = vp[3] - my
            np_ = gluUnProject(mx, wy, 0.0, mv, pr, vp); fp = gluUnProject(mx, wy, 1.0, mv, pr, vp)
            rd = np.array([fp[i]-np_[i] for i in range(3)]); rd = rd/np.linalg.norm(rd); ro = np.array(np_)
            best_d, best_i = float('inf'), None
            for i, (v, c, l) in enumerate(self.vectors):
                if len(v) >= 3:
                    vp_ = np.array(v[:3]); vo = vp_ - ro; pl = np.dot(vo, rd)
                    if pl > 0:
                        d = np.linalg.norm(vp_ - (ro + pl * rd))
                        if d < 0.5 and d < best_d: best_d = d; best_i = i
            if best_i is not None:
                self.selected_idx = best_i; self.update()
                if self.on_selected: self.on_selected(best_i, self.vectors[best_i][0], self.vectors[best_i][2])
            elif self.selected_idx is not None:
                self.selected_idx = None; self.update()
                if self.on_selected: self.on_selected(None, None, None)
        except: pass

    def mouseMoveEvent(self, e):
        if self.last_pos:
            dx, dy = e.x()-self.last_pos.x(), e.y()-self.last_pos.y()
            if abs(dx) > 2 or abs(dy) > 2: self.is_dragging = True
            if e.buttons() & Qt.LeftButton and self.is_dragging:
                self.rotation_y += dx*0.5; self.rotation_x += dy*0.5; self.update()
            self.last_pos = e.pos()

    def mouseReleaseEvent(self, e): self.is_dragging = False
    def wheelEvent(self, e):
        self.zoom += e.angleDelta().y() * 0.01; self.zoom = max(-50, min(-2, self.zoom)); self.update()


# ═══════════════════════════════════════════════════════════
#  UI: Main Application
# ═══════════════════════════════════════════════════════════

DARK_STYLE = """
QMainWindow, QWidget { background-color: #1a1a2e; color: #e0e0e0; }
QGroupBox { border: 1px solid #3a3a5e; border-radius: 6px; margin-top: 10px; padding-top: 15px; font-weight: bold; color: #a0c4ff; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
QPushButton { background-color: #2d2d4e; color: #e0e0e0; border: 1px solid #4a4a6e; border-radius: 4px; padding: 7px 14px; font-weight: bold; }
QPushButton:hover { background-color: #3a3a6e; border-color: #6a6aae; }
QPushButton:pressed { background-color: #4a4a7e; }
QComboBox, QSpinBox, QLineEdit { background-color: #2a2a4a; color: #e0e0e0; border: 1px solid #4a4a6e; border-radius: 3px; padding: 4px; }
QTextEdit { background-color: #12122a; color: #b0e0b0; border: 1px solid #3a3a5e; border-radius: 4px; font-family: Consolas, monospace; }
QTableWidget { background-color: #12122a; color: #e0e0e0; border: 1px solid #3a3a5e; gridline-color: #2a2a4e; }
QHeaderView::section { background-color: #2a2a4e; color: #a0c4ff; border: 1px solid #3a3a5e; padding: 4px; font-weight: bold; }
QTabWidget::pane { border: 1px solid #3a3a5e; }
QTabBar::tab { background-color: #2a2a4e; color: #a0a0c0; padding: 8px 16px; border: 1px solid #3a3a5e; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background-color: #3a3a6e; color: #ffffff; }
QTreeWidget { background-color: #12122a; color: #e0e0e0; border: 1px solid #3a3a5e; }
QSplitter::handle { background-color: #3a3a5e; }
QLabel { color: #c0c0e0; }
"""


class CookiXApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = None
        self.topo_engine = None
        self.timer = QTimer(); self.timer.timeout.connect(self._tick)
        self._init_ui()
        self._new_db()
        self._load_scenario("umbrella")

    def _init_ui(self):
        self.setWindowTitle("CookiX — The Topological Memory Database")
        self.setGeometry(80, 80, 1500, 920)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)

        # ─── LEFT: Controls ───
        left = QWidget(); ll = QVBoxLayout(left); ll.setSpacing(6)

        # Title
        t = QLabel("🍪 CookiX Lab"); t.setFont(QFont("Segoe UI", 15, QFont.Bold))
        t.setAlignment(Qt.AlignCenter); t.setStyleSheet("color:#ff9f43; padding:6px;"); ll.addWidget(t)

        # Vector DB controls
        g1 = QGroupBox("Vector DB"); g1l = QVBoxLayout()
        h = QHBoxLayout(); h.addWidget(QLabel("Dims:")); self.dim_spin = QSpinBox(); self.dim_spin.setRange(2,10); self.dim_spin.setValue(3); h.addWidget(self.dim_spin)
        h.addWidget(QLabel("Metric:")); self.metric_cb = QComboBox()
        for m in DistanceMetric: self.metric_cb.addItem(m.value)
        h.addWidget(self.metric_cb); g1l.addLayout(h)
        b = QPushButton("🔄 New DB"); b.clicked.connect(self._new_db); g1l.addWidget(b)

        h2 = QHBoxLayout(); h2.addWidget(QLabel("Vectors:")); self.n_spin = QSpinBox(); self.n_spin.setRange(1,500); self.n_spin.setValue(40); h2.addWidget(self.n_spin)
        b2 = QPushButton("➕ Generate"); b2.clicked.connect(self._generate); h2.addWidget(b2); g1l.addLayout(h2)

        h3 = QHBoxLayout(); h3.addWidget(QLabel("K:")); self.k_spin = QSpinBox(); self.k_spin.setRange(1,20); self.k_spin.setValue(5); h3.addWidget(self.k_spin)
        b3 = QPushButton("🔍 Query"); b3.clicked.connect(self._query_random); h3.addWidget(b3); g1l.addLayout(h3)

        b4 = QPushButton("✖ Clear Query"); b4.clicked.connect(self._clear_query); g1l.addWidget(b4)
        g1.setLayout(g1l); ll.addWidget(g1)

        # Topo Engine controls
        g2 = QGroupBox("Topological Engine"); g2l = QVBoxLayout()
        self.scenario_cb = QComboBox(); self.scenario_cb.addItems(["umbrella", "pipe"])
        h4 = QHBoxLayout(); h4.addWidget(QLabel("Scenario:")); h4.addWidget(self.scenario_cb)
        b5 = QPushButton("📂 Load"); b5.clicked.connect(lambda: self._load_scenario(self.scenario_cb.currentText())); h4.addWidget(b5)
        g2l.addLayout(h4)

        self.topo_query_src = QLineEdit(); self.topo_query_src.setPlaceholderText("Source ID (e.g. umbrella)")
        self.topo_query_tgt = QLineEdit(); self.topo_query_tgt.setPlaceholderText("Target ID (e.g. storm)")
        g2l.addWidget(QLabel("Path Query:")); g2l.addWidget(self.topo_query_src); g2l.addWidget(self.topo_query_tgt)
        b6 = QPushButton("🧠 Find Path"); b6.clicked.connect(self._topo_path_query); g2l.addWidget(b6)

        self.topo_reason_src = QLineEdit(); self.topo_reason_src.setPlaceholderText("Source ID (e.g. pipe_120mm)")
        self.topo_reason_etype = QComboBox()
        for et in EdgeType: self.topo_reason_etype.addItem(et.value)
        self.topo_reason_etype.setCurrentText("compatible_with")
        g2l.addWidget(QLabel("Reasoning Query:"))
        g2l.addWidget(self.topo_reason_src)
        h5 = QHBoxLayout(); h5.addWidget(QLabel("Edge:")); h5.addWidget(self.topo_reason_etype); g2l.addLayout(h5)
        b7 = QPushButton("⚡ Reason"); b7.clicked.connect(self._topo_reasoning); g2l.addWidget(b7)

        g2.setLayout(g2l); ll.addWidget(g2)

        # View controls
        g3 = QGroupBox("View"); g3l = QVBoxLayout()
        b8 = QPushButton("🔄 Toggle Animation"); b8.clicked.connect(self._toggle_anim); g3l.addWidget(b8)
        b9 = QPushButton("🎯 Reset Camera"); b9.clicked.connect(self._reset_cam); g3l.addWidget(b9)
        g3.setLayout(g3l); ll.addWidget(g3)

        self.stats_label = QLabel(""); self.stats_label.setWordWrap(True); self.stats_label.setStyleSheet("color:#80cbc4; font-size:10pt;")
        ll.addWidget(self.stats_label)
        ll.addStretch()
        splitter.addWidget(left)

        # ─── CENTER: 3D View ───
        center = QWidget(); cl = QVBoxLayout(center)
        self.gl = GLWidget(); self.gl.on_selected = self._on_vec_selected; cl.addWidget(self.gl)
        self.info_bar = QLabel("🖱  Drag to rotate  •  Scroll to zoom  •  Click vectors to inspect")
        self.info_bar.setStyleSheet("background:#0d1b2a; color:#00e5ff; padding:10px; border-radius:5px; font-weight:bold; font-size:10pt;")
        self.info_bar.setWordWrap(True); cl.addWidget(self.info_bar)
        splitter.addWidget(center)

        # ─── RIGHT: Results ───
        right = QWidget(); rl = QVBoxLayout(right)
        self.tabs = QTabWidget()

        # Tab 1: Vector results
        t1 = QWidget(); t1l = QVBoxLayout(t1)
        self.results_table = QTableWidget(); self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["#", "ID", "Distance", "Vector"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t1l.addWidget(self.results_table)
        self.tabs.addTab(t1, "📊 Vector Results")

        # Tab 2: Topo results
        t2 = QWidget(); t2l = QVBoxLayout(t2)
        self.topo_output = QTextEdit(); self.topo_output.setReadOnly(True)
        t2l.addWidget(self.topo_output)
        self.tabs.addTab(t2, "🧠 Topo Results")

        # Tab 3: Graph view
        t3 = QWidget(); t3l = QVBoxLayout(t3)
        self.graph_tree = QTreeWidget(); self.graph_tree.setHeaderLabels(["Node / Edge", "Type", "Details"])
        self.graph_tree.setColumnWidth(0, 150)
        t3l.addWidget(self.graph_tree)
        self.tabs.addTab(t3, "🌐 Graph View")

        rl.addWidget(self.tabs)

        # Log
        rl.addWidget(QLabel("Activity Log:"))
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True); self.log_text.setMaximumHeight(160)
        rl.addWidget(self.log_text)
        splitter.addWidget(right)

        splitter.setSizes([320, 700, 380])
        root.addWidget(splitter)

    # ─── Vector DB Actions ───

    def _new_db(self):
        self.db = VectorDB(self.dim_spin.value(), DistanceMetric(self.metric_cb.currentText()))
        self._update_viz(); self._update_stats()
        self._log(f"Created VectorDB: dim={self.db.dimension}, metric={self.db.metric.value}")

    def _generate(self):
        if not self.db: return
        n = self.n_spin.value()
        for i in range(n):
            v = np.random.uniform(-5, 5, self.db.dimension)
            c = tuple(np.random.random(3) * 0.6 + 0.3)
            self.db.add_vector(f"v{len(self.db)+i}", v, {'color': c})
        self._update_viz(); self._update_stats()
        self._log(f"Generated {n} vectors")

    def _query_random(self):
        if not self.db or len(self.db) == 0: return
        qv = np.random.uniform(-5, 5, self.db.dimension)
        results = self.db.query(qv, self.k_spin.value())
        all_v = self.db.get_all_vectors()
        nbr_idx = []
        for e, _ in results:
            for i, v in enumerate(all_v):
                if v.id == e.id: nbr_idx.append(i); break
        self.gl.set_query(qv, nbr_idx)
        self.results_table.setRowCount(len(results))
        for i, (e, d) in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.results_table.setItem(i, 1, QTableWidgetItem(e.id))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{d:.4f}"))
            self.results_table.setItem(i, 3, QTableWidgetItem(str(np.round(e.vector[:3], 2))))
        self.tabs.setCurrentIndex(0)
        self._log(f"Vector query: {len(results)} neighbors via {self.db.metric.value}")

    def _clear_query(self):
        self.gl.clear_query(); self.results_table.setRowCount(0); self._log("Query cleared")

    # ─── Topo Engine Actions ───

    def _load_scenario(self, name):
        if name == "umbrella":
            self.topo_engine = build_umbrella_scenario()
            self.topo_query_src.setText("umbrella"); self.topo_query_tgt.setText("storm")
            self.topo_reason_src.setText("umbrella"); self.topo_reason_etype.setCurrentText("compatible_with")
        else:
            self.topo_engine = build_pipe_scenario()
            self.topo_query_src.setText("pipe_120mm"); self.topo_query_tgt.setText("fitting_B")
            self.topo_reason_src.setText("pipe_120mm"); self.topo_reason_etype.setCurrentText("compatible_with")
        self._refresh_graph_tree()
        self._update_stats()
        self._log(f"Loaded '{name}' scenario: {len(self.topo_engine)} objects")

    def _topo_path_query(self):
        if not self.topo_engine: return
        src = self.topo_query_src.text().strip(); tgt = self.topo_query_tgt.text().strip()
        if not src or not tgt: return
        result = self.topo_engine.query_path(src, tgt, max_hops=5)
        out = f"🔍 PATH QUERY: {src} → {tgt}\n{'='*50}\n\n"
        if result:
            out += f"✅ Path found!\n\n"
            out += f"Path:       {result.path_string}\n"
            out += f"Distance:   {result.total_distance:.2f}\n"
            out += f"Confidence: {result.confidence:.2f}\n\n"
            out += f"Steps:\n"
            for i, s in enumerate(result.path, 1):
                out += f"  {i}. {s.from_id} --[{s.edge_type.value}]--> {s.to_id}  (weight={s.weight:.1f})\n"
        else:
            out += f"❌ No path found between '{src}' and '{tgt}'.\n"
        # Also show neighborhood
        out += f"\n{'='*50}\n📍 NEIGHBORHOOD of '{src}' (2 hops):\n\n"
        nbrs = self.topo_engine.query_neighborhood(src, max_hops=2)
        for nid, nr in sorted(nbrs.items(), key=lambda x: x[1].total_distance):
            out += f"  {nid:18s}  dist={nr.total_distance:.2f}  via {nr.path_string}\n"
        self.topo_output.setText(out)
        self.tabs.setCurrentIndex(1)
        self._log(f"Topo path query: {src} → {tgt}: {'found' if result else 'no path'}")

    def _topo_reasoning(self):
        if not self.topo_engine: return
        src = self.topo_reason_src.text().strip()
        etype_str = self.topo_reason_etype.currentText()
        if not src: return
        etype = EdgeType(etype_str)
        results = self.topo_engine.query_reasoning(src, f"{src} {etype_str}?", etype, max_hops=3)
        out = f"⚡ REASONING RETRIEVAL\n{'='*50}\n"
        out += f"Source: {src}\n"
        out += f"Looking for: {etype_str}\n\n"

        # Show direct check
        direct = self.topo_engine.query_direct(src, etype)
        out += f"Step 1 — Direct lookup [{etype_str}]: "
        if direct:
            out += f"FOUND {len(direct)} direct edges\n"
        else:
            out += "NULL (not found)\n"
        out += f"\nStep 2 — Reasoning via topological expansion:\n\n"

        if results:
            for i, r in enumerate(results, 1):
                out += f"  Result {i}:\n"
                out += f"    Target:     {r.target_id}\n"
                out += f"    Path:       {r.path_string}\n"
                out += f"    Distance:   {r.total_distance:.2f}\n"
                out += f"    Confidence: {r.confidence:.2f}\n"
                out += f"    {r.explanation}\n\n"
        else:
            out += "  No reasoning paths found.\n"

        # Distances
        out += f"\n{'='*50}\n📐 CookiX Distances from '{src}':\n\n"
        for oid in self.topo_engine.objects:
            if oid != src:
                d = self.topo_engine.geodesic(src, oid)
                out += f"  → {oid:18s}  geodesic={d:.2f}\n" if d != float('inf') else f"  → {oid:18s}  (unreachable)\n"

        self.topo_output.setText(out)
        self.tabs.setCurrentIndex(1)
        self._log(f"Reasoning: {src} [{etype_str}] → {len(results)} results")

    def _refresh_graph_tree(self):
        self.graph_tree.clear()
        if not self.topo_engine: return
        for oid, obj in self.topo_engine.objects.items():
            node_item = QTreeWidgetItem([oid, "node", obj.content[:60]])
            node_item.setForeground(0, QColor("#a0c4ff"))
            node_item.setForeground(1, QColor("#80cbc4"))
            for e in obj.edges:
                edge_item = QTreeWidgetItem([f"→ {e.target_id}", e.edge_type.value, f"w={e.weight:.1f}  {e.metadata}"])
                edge_item.setForeground(0, QColor("#ffab91"))
                edge_item.setForeground(1, QColor("#ce93d8"))
                node_item.addChild(edge_item)
            self.graph_tree.addTopLevelItem(node_item)
        self.graph_tree.expandAll()

    # ─── View ───

    def _toggle_anim(self):
        self.gl.animate = not self.gl.animate
        if self.gl.animate: self.timer.start(16)
        else: self.timer.stop()
        self._log(f"Animation {'on' if self.gl.animate else 'off'}")

    def _reset_cam(self):
        self.gl.rotation_x = 30; self.gl.rotation_y = 45; self.gl.zoom = -15; self.gl.update()

    def _tick(self):
        if self.gl.animate: self.gl.update()

    def _update_viz(self):
        if not self.db: return
        data = [(e.vector, e.metadata.get('color', (0.5, 0.5, 0.5)), e.id) for e in self.db.get_all_vectors()]
        self.gl.set_vectors(data)

    def _update_stats(self):
        parts = []
        if self.db:
            s = self.db.get_stats()
            parts.append(f"VectorDB: {s['total_vectors']} vectors, {self.db.metric.value}")
        if self.topo_engine:
            s = self.topo_engine.get_stats()
            parts.append(f"TopoEngine: {s['objects']} objects, {s['edges']} edges")
            if 'edge_types' in s:
                parts.append(f"Edge types: {', '.join(f'{k}({v})' for k,v in s['edge_types'].items())}")
        self.stats_label.setText("\n".join(parts))

    def _on_vec_selected(self, idx, vector, label):
        if idx is None:
            self.info_bar.setText("🖱  Drag to rotate  •  Scroll to zoom  •  Click vectors to inspect")
            self.info_bar.setStyleSheet("background:#0d1b2a; color:#00e5ff; padding:10px; border-radius:5px; font-weight:bold;")
        else:
            self.info_bar.setText(f"🎯 {label}  •  ({vector[0]:.3f}, {vector[1]:.3f}, {vector[2]:.3f})")
            self.info_bar.setStyleSheet("background:#1b3a1b; color:#00ff88; padding:10px; border-radius:5px; font-weight:bold;")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CookiXApp()
    window.show()
    sys.exit(app.exec_())