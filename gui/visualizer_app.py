"""
VectorDB 3D Visualization Desktop Application
Interactive visualization of vectors in 3D space with distance metric exploration
"""

import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QSpinBox, QGroupBox, QTextEdit, QSplitter, QLineEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView, QOpenGLWidget,
                             QDialog, QDialogButtonBox, QMessageBox, QListWidget)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont, QPainter, QColor
from OpenGL.GL import *
from OpenGL.GLU import *
import math

from core.vector_db import VectorDB, DistanceMetric
from core.formula_editor import FormulaParser, CustomFormulaLibrary


class OpenGLWidget(QOpenGLWidget):
    """OpenGL widget for 3D vector visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vectors = []  # List of (vector, color, label) tuples
        self.query_vector = None
        self.neighbors = []  # List of indices of nearest neighbors
        self.selected_vector_idx = None  # Index of selected vector
        
        # Camera parameters
        self.rotation_x = 30
        self.rotation_y = 45
        self.zoom = -15
        self.last_pos = None
        self.is_dragging = False
        
        # Display settings
        self.show_grid = True
        self.show_axes = True
        self.show_labels = True  # Show vector labels
        self.show_quadrants = True  # Show quadrant labels
        
        # Animation
        self.animate = False
        self.animation_angle = 0
        
        # Selection callback
        self.on_vector_selected = None
        
    def initializeGL(self):
        """Initialize OpenGL settings"""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        # Light settings
        glLightfv(GL_LIGHT0, GL_POSITION, [5, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        
        # Background color
        glClearColor(0.1, 0.1, 0.15, 1.0)
        
    def resizeGL(self, w, h):
        """Handle window resize"""
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / h if h != 0 else 1, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        
    def paintGL(self):
        """Render the scene"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Camera positioning
        glTranslatef(0, 0, self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        if self.animate:
            glRotatef(self.animation_angle, 0, 1, 0)
            self.animation_angle = (self.animation_angle + 1) % 360
        
        # Draw coordinate axes
        if self.show_axes:
            self.draw_axes()
        
        # Draw grid
        if self.show_grid:
            self.draw_grid()
        
        # Draw quadrant labels
        if self.show_quadrants:
            self.draw_quadrant_labels()
        
        # Draw vectors
        self.draw_vectors()
        
        # Draw connections for nearest neighbors
        if self.query_vector is not None and self.neighbors:
            self.draw_neighbor_connections()
    
    def draw_text_3d(self, x, y, z, text, color=(1, 1, 1)):
        """Draw 3D text at position using renderText"""
        glDisable(GL_LIGHTING)
        glColor3f(*color)
        
        # Save current matrix
        glPushMatrix()
        
        # Position text
        glTranslatef(x, y, z)
        
        # Billboard effect - face camera (simplified)
        glRotatef(-self.rotation_y, 0, 1, 0)
        glRotatef(-self.rotation_x, 1, 0, 0)
        
        # Scale text
        scale = abs(self.zoom) / 50.0
        glScalef(scale, scale, scale)
        
        # Render text using QPainter overlay
        # Text labels disabled
        
        glPopMatrix()
        glEnable(GL_LIGHTING)
    
    def draw_axes(self):
        """Draw X, Y, Z axes with labels"""
        glDisable(GL_LIGHTING)
        glLineWidth(2.0)
        
        # X axis (red)
        glColor3f(1, 0, 0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(5, 0, 0)
        glEnd()
        # Text labels disabled
        
        # Y axis (green)
        glColor3f(0, 1, 0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 5, 0)
        glEnd()
        # Text labels disabled
        
        # Z axis (blue)
        glColor3f(0, 0, 1)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 5)
        glEnd()
        # Text labels disabled
        
        glEnable(GL_LIGHTING)
        glLineWidth(1.0)
    
    def draw_quadrant_labels(self):
        """Draw quadrant labels in 3D space"""
        glDisable(GL_LIGHTING)
        
        # Define 8 octants (3D quadrants) with positions and labels
        octants = [
            (6, 6, 6, "(+,+,+)", (0.8, 1.0, 0.8)),    # Front-top-right
            (-6, 6, 6, "(-,+,+)", (1.0, 0.8, 0.8)),   # Front-top-left
            (6, -6, 6, "(+,-,+)", (0.8, 0.8, 1.0)),   # Front-bottom-right
            (-6, -6, 6, "(-,-,+)", (1.0, 1.0, 0.8)),  # Front-bottom-left
            (6, 6, -6, "(+,+,-)", (0.9, 0.9, 1.0)),   # Back-top-right
            (-6, 6, -6, "(-,+,-)", (1.0, 0.9, 0.9)),  # Back-top-left
            (6, -6, -6, "(+,-,-)", (0.9, 1.0, 0.9)),  # Back-bottom-right
            (-6, -6, -6, "(-,-,-)", (1.0, 1.0, 1.0)), # Back-bottom-left
        ]
        
        for x, y, z, label, color in octants:
            glColor3f(*color)
            # Text labels disabled
        
        glEnable(GL_LIGHTING)
    
    def draw_grid(self):
        """Draw reference grid"""
        glDisable(GL_LIGHTING)
        glColor3f(0.2, 0.2, 0.25)
        glLineWidth(0.5)
        
        size = 10
        step = 1
        
        glBegin(GL_LINES)
        for i in range(-size, size + 1, step):
            # XZ plane
            glVertex3f(i, 0, -size)
            glVertex3f(i, 0, size)
            glVertex3f(-size, 0, i)
            glVertex3f(size, 0, i)
        glEnd()
        
        glEnable(GL_LIGHTING)
        glLineWidth(1.0)
    
    def draw_vectors(self):
        """Draw all vectors as spheres with arrows and labels"""
        for i, (vector, color, label) in enumerate(self.vectors):
            if len(vector) < 3:
                continue
            
            x, y, z = vector[0], vector[1], vector[2] if len(vector) > 2 else 0
            
            # Determine color and size based on state
            if i == self.selected_vector_idx:
                # Selected vector - bright cyan/white
                glColor3f(0, 1, 1)
                size = 0.2
            elif i in self.neighbors:
                # Neighbor - yellow
                glColor3f(1, 1, 0)
                size = 0.15
            else:
                # Normal vector
                glColor3f(*color)
                size = 0.1
            
            # Draw sphere at vector position
            glPushMatrix()
            glTranslatef(x, y, z)
            
            # Draw sphere
            quad = gluNewQuadric()
            gluSphere(quad, size, 20, 20)
            gluDeleteQuadric(quad)
            
            # Draw selection ring for selected vector
            if i == self.selected_vector_idx:
                glDisable(GL_LIGHTING)
                glColor3f(1, 1, 1)
                glLineWidth(3.0)
                
                # Draw a ring around the selected sphere
                glBegin(GL_LINE_LOOP)
                for angle in range(0, 360, 10):
                    rad = angle * 3.14159 / 180
                    glVertex3f(0.25 * math.cos(rad), 0.25 * math.sin(rad), 0)
                glEnd()
                
                glLineWidth(1.0)
                glEnable(GL_LIGHTING)
            
            glPopMatrix()
            
            # Draw arrow from origin to point
            self.draw_arrow(0, 0, 0, x, y, z, color)
    
    def draw_arrow(self, x1, y1, z1, x2, y2, z2, color):
        """Draw an arrow from point 1 to point 2"""
        glDisable(GL_LIGHTING)
        glColor3f(*color)
        glLineWidth(1.5)
        
        glBegin(GL_LINES)
        glVertex3f(x1, y1, z1)
        glVertex3f(x2, y2, z2)
        glEnd()
        
        glEnable(GL_LIGHTING)
        glLineWidth(1.0)
    
    def draw_neighbor_connections(self):
        """Draw lines connecting query vector to its neighbors"""
        if self.query_vector is None or len(self.query_vector) < 3:
            return
        
        qx, qy, qz = self.query_vector[0], self.query_vector[1], self.query_vector[2]
        
        glDisable(GL_LIGHTING)
        glColor4f(1, 1, 0, 0.5)  # Semi-transparent yellow
        glLineWidth(2.0)
        
        glBegin(GL_LINES)
        for idx in self.neighbors:
            if idx < len(self.vectors):
                vector, _, _ = self.vectors[idx]
                if len(vector) >= 3:
                    vx, vy, vz = vector[0], vector[1], vector[2]
                    glVertex3f(qx, qy, qz)
                    glVertex3f(vx, vy, vz)
        glEnd()
        
        # Draw query point label
        glColor3f(1, 1, 1)
        # Text labels disabled")
        
        glEnable(GL_LIGHTING)
        glLineWidth(1.0)
    
    def set_vectors(self, vectors_data):
        """
        Set vectors to display
        vectors_data: List of (vector, color, label) tuples
        """
        self.vectors = vectors_data
        self.update()
    
    def set_query_result(self, query_vector, neighbor_indices):
        """Highlight query vector and its neighbors"""
        self.query_vector = query_vector
        self.neighbors = neighbor_indices
        self.update()
    
    def clear_query(self):
        """Clear query highlighting"""
        self.query_vector = None
        self.neighbors = []
        self.update()
    
    def toggle_labels(self):
        """Toggle vector labels on/off"""
        self.show_labels = not self.show_labels
        self.update()
    
    def toggle_quadrants(self):
        """Toggle quadrant labels on/off"""
        self.show_quadrants = not self.show_quadrants
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press for rotation or selection"""
        self.last_pos = event.pos()
        self.is_dragging = False
        
        # Check for vector selection on left click
        if event.button() == Qt.LeftButton:
            self.check_vector_click(event.x(), event.y())
    
    def check_vector_click(self, mouse_x, mouse_y):
        """Check if a vector was clicked using 2D screen projection"""
        try:
            self.makeCurrent()
            
            # Get matrices
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            # Convert mouse Y (Qt uses top-left origin, OpenGL uses bottom-left)
            mouse_y_gl = viewport[3] - mouse_y
            
            # Find closest vector by projecting to screen space
            min_distance = float('inf')
            closest_idx = None
            
            for i, (vector, color, label) in enumerate(self.vectors):
                if len(vector) >= 3:
                    # Project 3D vector position to 2D screen coordinates
                    try:
                        screen_x, screen_y, screen_z = gluProject(
                            vector[0], vector[1], vector[2],
                            modelview, projection, viewport
                        )
                        
                        # Check if point is in front of camera
                        if 0 < screen_z < 1:
                            # Calculate 2D distance from mouse to projected point
                            dx = screen_x - mouse_x
                            dy = screen_y - mouse_y_gl
                            distance_2d = math.sqrt(dx*dx + dy*dy)
                            
                            # Set click radius based on vector state
                            if i == self.selected_vector_idx:
                                click_radius = 30  # Larger for selected
                            elif i in self.neighbors:
                                click_radius = 25  # Medium for neighbors
                            else:
                                click_radius = 20  # Normal size
                            
                            # Check if within click radius and closer than previous
                            if distance_2d < click_radius and distance_2d < min_distance:
                                min_distance = distance_2d
                                closest_idx = i
                                
                    except Exception as e:
                        continue
            
            # Update selection
            if closest_idx is not None:
                self.selected_vector_idx = closest_idx
                vector = self.vectors[closest_idx][0]
                label = self.vectors[closest_idx][2]
                self.update()
                
                if self.on_vector_selected:
                    self.on_vector_selected(closest_idx, vector, label)
            else:
                # Clicked on empty space - deselect
                if self.selected_vector_idx is not None:
                    self.selected_vector_idx = None
                    self.update()
                    if self.on_vector_selected:
                        self.on_vector_selected(None, None, None)
                        
        except Exception as e:
            print(f"Click detection error: {e}")
    
    def mouseMoveEvent(self, event):
        """Handle mouse drag for rotation"""
        if self.last_pos is not None:
            dx = event.x() - self.last_pos.x()
            dy = event.y() - self.last_pos.y()
            
            # Only rotate if mouse moved significantly
            if abs(dx) > 2 or abs(dy) > 2:
                self.is_dragging = True
            
            if event.buttons() & Qt.LeftButton and self.is_dragging:
                self.rotation_y += dx * 0.5
                self.rotation_x += dy * 0.5
                self.update()
            
            self.last_pos = event.pos()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.is_dragging = False
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        delta = event.angleDelta().y()
        self.zoom += delta * 0.01
        self.zoom = max(-50, min(-2, self.zoom))
        self.update()


class FormulaEditorDialog(QDialog):
    """Dialog for creating custom distance formulas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser = FormulaParser()
        self.library = CustomFormulaLibrary()
        self.custom_formula = None
        self.formula_name = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        self.setWindowTitle('Custom Formula Editor')
        self.setGeometry(200, 200, 800, 700)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel('Create Your Own Distance Formula')
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            'Enter a mathematical formula using vectors v1 and v2.\n'
            'Example: sqrt(sum((v1 - v2) ** 2)) for Euclidean distance'
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Formula name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('Formula Name:'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('e.g., My Custom Distance')
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Formula input
        formula_label = QLabel('Formula:')
        formula_label.setFont(QFont('Arial', 10, QFont.Bold))
        layout.addWidget(formula_label)
        
        self.formula_input = QTextEdit()
        self.formula_input.setMaximumHeight(100)
        self.formula_input.setPlaceholderText('sqrt(sum((v1 - v2) ** 2))')
        layout.addWidget(self.formula_input)
        
        # Buttons row
        btn_layout = QHBoxLayout()
        
        self.validate_btn = QPushButton('✓ Validate Formula')
        self.validate_btn.clicked.connect(self.validate_formula)
        btn_layout.addWidget(self.validate_btn)
        
        self.test_btn = QPushButton('🧪 Test Formula')
        self.test_btn.clicked.connect(self.test_formula)
        btn_layout.addWidget(self.test_btn)
        
        self.help_btn = QPushButton('❓ Show Help')
        self.help_btn.clicked.connect(self.show_help)
        btn_layout.addWidget(self.help_btn)
        
        layout.addLayout(btn_layout)
        
        # Templates section
        templates_group = QGroupBox('Formula Templates (Double-click to use)')
        templates_layout = QVBoxLayout()
        
        self.templates_list = QListWidget()
        self.templates_list.itemDoubleClicked.connect(self.load_template)
        
        # Populate templates
        for name, info in self.library.list_all().items():
            self.templates_list.addItem(f"{info['name']}: {info['formula']}")
        
        templates_layout.addWidget(self.templates_list)
        templates_group.setLayout(templates_layout)
        layout.addWidget(templates_group)
        
        # Output area
        output_label = QLabel('Validation Output:')
        output_label.setFont(QFont('Arial', 10, QFont.Bold))
        layout.addWidget(output_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        layout.addWidget(self.output_text)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept_formula)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def validate_formula(self):
        """Validate the current formula"""
        formula = self.formula_input.toPlainText().strip()
        
        if not formula:
            self.output_text.setText("❌ Please enter a formula")
            return
        
        is_valid, message = self.parser.validate_formula(formula)
        
        if is_valid:
            self.output_text.setText(f"✅ {message}\n\nFormula is ready to use!")
            self.output_text.setStyleSheet("background-color: #e8f5e9;")
        else:
            self.output_text.setText(f"❌ {message}")
            self.output_text.setStyleSheet("background-color: #ffebee;")
    
    def test_formula(self):
        """Test the formula with sample vectors"""
        formula = self.formula_input.toPlainText().strip()
        
        if not formula:
            self.output_text.setText("❌ Please enter a formula first")
            return
        
        is_valid, message = self.parser.validate_formula(formula)
        
        if not is_valid:
            self.output_text.setText(f"❌ Invalid formula: {message}")
            return
        
        # Create function and test
        func = self.parser.create_distance_function(formula, "test")
        
        # Test vectors
        test_cases = [
            (np.array([1, 2, 3]), np.array([4, 5, 6])),
            (np.array([0, 0, 0]), np.array([1, 1, 1])),
            (np.array([1, 0, 0]), np.array([0, 1, 0])),
            (np.array([5, 5, 5]), np.array([5, 5, 5])),
        ]
        
        output = "✅ Formula is valid!\n\nTest Results:\n" + "="*50 + "\n"
        
        for i, (v1, v2) in enumerate(test_cases, 1):
            try:
                result = func(v1, v2)
                output += f"\nTest {i}:\n"
                output += f"  v1 = {v1}\n"
                output += f"  v2 = {v2}\n"
                output += f"  distance = {result:.6f}\n"
            except Exception as e:
                output += f"\nTest {i}: ERROR - {e}\n"
        
        self.output_text.setText(output)
        self.output_text.setStyleSheet("background-color: #e3f2fd;")
    
    def show_help(self):
        """Show help dialog"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle('Formula Syntax Help')
        help_dialog.setGeometry(250, 250, 700, 600)
        
        layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setText(self.library.get_help_text())
        help_text.setFont(QFont('Courier New', 9))
        layout.addWidget(help_text)
        
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(help_dialog.close)
        layout.addWidget(close_btn)
        
        help_dialog.setLayout(layout)
        help_dialog.exec_()
    
    def load_template(self, item):
        """Load a template formula"""
        text = item.text()
        # Extract formula from "Name: formula" format
        formula = text.split(': ', 1)[1]
        self.formula_input.setText(formula)
        self.output_text.setText("Template loaded! Click 'Validate Formula' to check it.")
    
    def accept_formula(self):
        """Accept and create the formula"""
        formula = self.formula_input.toPlainText().strip()
        name = self.name_input.text().strip()
        
        if not formula:
            QMessageBox.warning(self, 'Error', 'Please enter a formula')
            return
        
        if not name:
            name = "Custom Formula"
        
        is_valid, message = self.parser.validate_formula(formula)
        
        if not is_valid:
            QMessageBox.warning(self, 'Invalid Formula', message)
            return
        
        self.custom_formula = self.parser.create_distance_function(formula, name)
        self.formula_name = name
        
        QMessageBox.information(
            self, 
            'Success', 
            f'Formula "{name}" created successfully!\n\nIt will be added to your distance metrics.'
        )
        
        self.accept()


class VectorDBVisualizerApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.db = None
        self.custom_formulas = {}  # Store custom formulas
        self.current_custom_formula = None
        self.init_ui()
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_visualization)
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('VectorDB Laboratory - 3D Visualization')
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # Center panel - 3D Visualization
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        
        self.gl_widget = OpenGLWidget()
        self.gl_widget.on_vector_selected = self.on_vector_clicked
        center_layout.addWidget(self.gl_widget)
        
        # Selection info bar at bottom of 3D view
        self.selection_info = QLabel('💡 Click vector to see details')
        self.selection_info.setStyleSheet("""
            QLabel {
                background-color: #263238;
                color: #00E5FF;
                padding: 5px;
                border-radius: 3px;
                font-size: 9pt;
                font-weight: bold;
                max-height: 60px;
            }
        """)
        self.selection_info.setWordWrap(True)
        self.selection_info.setMaximumHeight(60)
        center_layout.addWidget(self.selection_info)
        
        splitter.addWidget(center_widget)
        
        # Right panel - Results
        right_panel = self.create_results_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([350, 700, 350])
        
        # Set splitter proportions: 25% controls, 50% 3D view, 25% results
        splitter.setSizes([350, 700, 350])
        splitter.setStretchFactor(0, 0)  # Controls don't stretch
        splitter.setStretchFactor(1, 3)  # 3D view stretches most
        splitter.setStretchFactor(2, 1)  # Results stretch a bit
        
        main_layout.addWidget(splitter)
        
        # Initialize with empty database
        self.create_new_db()
        
    def create_control_panel(self):
        """Create the left control panel"""
        panel = QWidget()
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(450)
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel('Vector Database Controls')
        title.setFont(QFont('Arial', 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Database configuration
        db_group = QGroupBox('Database Configuration')
        db_layout = QVBoxLayout()
        
        # Dimension selector
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel('Dimensions:'))
        self.dim_spin = QSpinBox()
        self.dim_spin.setRange(2, 10)
        self.dim_spin.setValue(3)
        dim_layout.addWidget(self.dim_spin)
        db_layout.addLayout(dim_layout)
        
        # Metric selector
        metric_layout = QHBoxLayout()
        metric_layout.addWidget(QLabel('Distance Metric:'))
        self.metric_combo = QComboBox()
        for metric in DistanceMetric:
            self.metric_combo.addItem(metric.value)
        metric_layout.addWidget(self.metric_combo)
        db_layout.addLayout(metric_layout)
        
        # Custom formula button
        self.custom_formula_btn = QPushButton('📝 Create Custom Formula')
        self.custom_formula_btn.clicked.connect(self.open_formula_editor)
        self.custom_formula_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        db_layout.addWidget(self.custom_formula_btn)
        
        # Show current custom formula
        self.current_formula_label = QLabel('No custom formula loaded')
        self.current_formula_label.setWordWrap(True)
        self.current_formula_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 5px;
                border-radius: 3px;
                font-size: 9pt;
            }
        """)
        db_layout.addWidget(self.current_formula_label)
        
        # Create DB button
        self.create_db_btn = QPushButton('Create New Database')
        self.create_db_btn.clicked.connect(self.create_new_db)
        db_layout.addWidget(self.create_db_btn)
        
        # Load Darija dataset button
        self.load_darija_btn = QPushButton('📚 Load Darija Words')
        self.load_darija_btn.clicked.connect(self.load_darija_dataset)
        self.load_darija_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF6B35;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #FF5722;
            }
        """)
        db_layout.addWidget(self.load_darija_btn)
        
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        # Data generation
        gen_group = QGroupBox('Generate Sample Data')
        gen_layout = QVBoxLayout()
        
        num_layout = QHBoxLayout()
        num_layout.addWidget(QLabel('Number of vectors:'))
        self.num_vectors_spin = QSpinBox()
        self.num_vectors_spin.setRange(1, 1000)
        self.num_vectors_spin.setValue(50)
        num_layout.addWidget(self.num_vectors_spin)
        gen_layout.addLayout(num_layout)
        
        self.generate_btn = QPushButton('Generate Random Vectors')
        self.generate_btn.clicked.connect(self.generate_random_vectors)
        gen_layout.addWidget(self.generate_btn)
        
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)
        
        # Query controls
        query_group = QGroupBox('Query Controls')
        query_layout = QVBoxLayout()
        
        # Text input for word search - COMPACT VERSION
        search_label = QLabel('Search Word:')
        search_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        query_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('e.g., baba, khobz')
        self.search_input.returnPressed.connect(self.query_by_name)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                font-size: 10pt;
                border: 2px solid #9C27B0;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 2px solid #7B1FA2;
            }
        """)
        query_layout.addWidget(self.search_input)
        
        self.search_btn = QPushButton('🔍 Search')
        self.search_btn.clicked.connect(self.query_by_name)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 6px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        query_layout.addWidget(self.search_btn)
        
        # Compact separator
        separator = QLabel('─' * 20)
        separator.setStyleSheet("color: #555; font-size: 8pt;")
        separator.setAlignment(Qt.AlignCenter)
        query_layout.addWidget(separator)
        
        # K neighbors
        k_layout = QHBoxLayout()
        k_label = QLabel('K:')
        k_label.setStyleSheet("font-size: 10pt;")
        k_layout.addWidget(k_label)
        self.k_spin = QSpinBox()
        self.k_spin.setRange(1, 20)
        self.k_spin.setValue(5)
        self.k_spin.setStyleSheet("font-size: 10pt;")
        k_layout.addWidget(self.k_spin)
        query_layout.addLayout(k_layout)
        
        self.query_btn = QPushButton('Query Random')
        self.query_btn.clicked.connect(self.query_random)
        self.query_btn.setStyleSheet("font-size: 10pt; padding: 6px;")
        query_layout.addWidget(self.query_btn)
        
        self.query_selected_btn = QPushButton('🎯 Query Selected')
        self.query_selected_btn.clicked.connect(self.query_selected)
        self.query_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        query_layout.addWidget(self.query_selected_btn)
        
        self.clear_query_btn = QPushButton('Clear Query')
        self.clear_query_btn.clicked.connect(self.clear_query)
        self.clear_query_btn.setStyleSheet("font-size: 10pt; padding: 6px;")
        query_layout.addWidget(self.clear_query_btn)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # View controls
        view_group = QGroupBox('View Controls')
        view_layout = QVBoxLayout()
        
        self.animate_btn = QPushButton('Animation')
        self.animate_btn.clicked.connect(self.toggle_animation)
        self.animate_btn.setStyleSheet("font-size: 9pt; padding: 4px;")
        view_layout.addWidget(self.animate_btn)
        
        self.labels_btn = QPushButton('Labels')
        self.labels_btn.clicked.connect(self.toggle_labels)
        self.labels_btn.setCheckable(True)
        self.labels_btn.setChecked(True)
        self.labels_btn.setStyleSheet("font-size: 9pt; padding: 4px;")
        view_layout.addWidget(self.labels_btn)
        
        self.quadrants_btn = QPushButton('Quadrants')
        self.quadrants_btn.clicked.connect(self.toggle_quadrants)
        self.quadrants_btn.setCheckable(True)
        self.quadrants_btn.setChecked(True)
        self.quadrants_btn.setStyleSheet("font-size: 9pt; padding: 4px;")
        view_layout.addWidget(self.quadrants_btn)
        
        self.clear_selection_btn = QPushButton('Clear Select')
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setStyleSheet("font-size: 9pt; padding: 4px;")
        view_layout.addWidget(self.clear_selection_btn)
        
        self.reset_view_btn = QPushButton('Reset Camera')
        self.reset_view_btn.clicked.connect(self.reset_camera)
        self.reset_view_btn.setStyleSheet("font-size: 9pt; padding: 4px;")
        view_layout.addWidget(self.reset_view_btn)
        
        view_group.setLayout(view_layout)
        layout.addWidget(view_group)
        
        # Statistics
        self.stats_label = QLabel('Database: Not initialized')
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        
        layout.addStretch()
        
        return panel
    
    def create_results_panel(self):
        """Create the right results panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel('Query Results')
        title.setFont(QFont('Arial', 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(['Rank', 'ID', 'Distance', 'Vector'])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.results_table)
        
        # Log area
        log_label = QLabel('Activity Log:')
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
        
        return panel
    
    def create_new_db(self):
        """Create a new vector database"""
        dimension = self.dim_spin.value()
        metric = DistanceMetric(self.metric_combo.currentText())
        
        self.db = VectorDB(dimension, metric)
        self.update_stats()
        self.log(f"Created new VectorDB with dimension={dimension}, metric={metric.value}")
    
    def load_darija_dataset(self):
        """Load Darija (Moroccan Arabic) word embeddings"""
        try:
            from datasets.darija_embeddings import DarijaWordEmbeddings
            
            self.log("Loading Darija word embeddings...")
            
            # Create embeddings
            darija = DarijaWordEmbeddings(dimension=128)
            darija.create_darija_dataset()
            
            # Export to 3D
            try:
                from sklearn.decomposition import PCA
                export_data = darija.export_for_vectordb(dimension_3d=3)
            except ImportError:
                QMessageBox.warning(
                    self,
                    "Missing Library",
                    "scikit-learn is required for dimensionality reduction.\n\n"
                    "Install it with:\npip install scikit-learn"
                )
                return
            
            # Create new database
            self.db = VectorDB(dimension=3, metric=DistanceMetric.COSINE)
            
            # Add all words with colored spheres by category
            for word, vector, metadata in export_data:
                self.db.add_vector(word, vector, metadata)
            
            # Update visualization
            self.update_visualization()
            self.update_stats()
            
            # Show success message
            QMessageBox.information(
                self,
                "Darija Dataset Loaded! 🎉",
                f"Successfully loaded {len(self.db)} Darija words!\n\n"
                f"Categories:\n"
                f"• العائلة (Family)\n"
                f"• الماكلة (Food)\n"
                f"• السلامات (Greetings)\n"
                f"• الأرقام (Numbers)\n"
                f"• الألوان (Colors)\n"
                f"• And more!\n\n"
                f"Colors represent categories.\n"
                f"Click vectors to see translations!"
            )
            
            self.log(f"✅ Loaded {len(self.db)} Darija words with semantic embeddings")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Dataset",
                f"Failed to load Darija dataset:\n{str(e)}\n\n"
                f"Make sure the datasets folder exists."
            )
            self.log(f"Error loading Darija: {e}")
    
    def generate_random_vectors(self):
        """Generate random vectors and add to database"""
        if self.db is None:
            self.log("Error: Database not initialized")
            return
        
        num_vectors = self.num_vectors_spin.value()
        dimension = self.db.dimension
        
        vectors_data = []
        for i in range(num_vectors):
            # Generate random vector in range [-5, 5]
            vector = np.random.uniform(-5, 5, dimension)
            vector_id = f"vec_{len(self.db) + i}"
            
            # Random color
            color = (np.random.random(), np.random.random(), np.random.random())
            
            self.db.add_vector(vector_id, vector, {'color': color})
            vectors_data.append((vector, color, vector_id))
        
        self.update_visualization()
        self.update_stats()
        self.log(f"Generated {num_vectors} random vectors")
    
    def query_random(self):
        """Query the database with a random point"""
        if self.db is None or len(self.db) == 0:
            self.log("Error: Database is empty")
            return
        
        # Generate random query vector
        query_vector = np.random.uniform(-5, 5, self.db.dimension)
        k = self.k_spin.value()
        
        # Perform query with custom formula if available
        if self.current_custom_formula:
            # Use custom formula
            self.log(f"Querying with custom formula...")
            
            # Manually calculate distances using custom formula
            all_vectors = self.db.get_all_vectors()
            distances = []
            for entry in all_vectors:
                try:
                    dist = self.current_custom_formula(query_vector, entry.vector)
                    distances.append((entry, dist))
                except Exception as e:
                    self.log(f"Error calculating distance for {entry.id}: {e}")
                    continue
            
            # Sort by distance
            distances.sort(key=lambda x: x[1])
            results = distances[:k]
        else:
            # Use standard metric
            results = self.db.query(query_vector, k=k)
        
        # Update visualization
        neighbor_indices = []
        all_vectors = self.db.get_all_vectors()
        for entry, dist in results:
            for i, v in enumerate(all_vectors):
                if v.id == entry.id:
                    neighbor_indices.append(i)
                    break
        
        self.gl_widget.set_query_result(query_vector, neighbor_indices)
        
        # Update results table
        self.results_table.setRowCount(len(results))
        for i, (entry, distance) in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.results_table.setItem(i, 1, QTableWidgetItem(entry.id))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{distance:.4f}"))
            vector_str = '[' + ', '.join([f"{x:.2f}" for x in entry.vector[:3]]) + '...]'
            self.results_table.setItem(i, 3, QTableWidgetItem(vector_str))
        
        metric_used = "Custom Formula" if self.current_custom_formula else self.db.metric.value
        self.log(f"Query executed: found {len(results)} neighbors using {metric_used}")
    
    def query_selected(self):
        """Query using the currently selected vector"""
        if self.db is None or len(self.db) == 0:
            self.log("Error: Database is empty")
            QMessageBox.warning(self, "No Database", "Please create or load a database first.")
            return
        
        if self.gl_widget.selected_vector_idx is None:
            self.log("Error: No vector selected")
            QMessageBox.information(
                self,
                "No Selection",
                "Please click on a vector first, then click this button to find similar vectors."
            )
            return
        
        # Get the selected vector
        all_vectors = self.db.get_all_vectors()
        if self.gl_widget.selected_vector_idx >= len(all_vectors):
            return
        
        selected_entry = all_vectors[self.gl_widget.selected_vector_idx]
        query_vector = selected_entry.vector
        k = self.k_spin.value() + 1  # +1 because the vector itself will be in results
        
        # Perform query
        if self.current_custom_formula:
            # Use custom formula
            distances = []
            for entry in all_vectors:
                try:
                    dist = self.current_custom_formula(query_vector, entry.vector)
                    distances.append((entry, dist))
                except Exception as e:
                    continue
            distances.sort(key=lambda x: x[1])
            results = distances[:k]
        else:
            results = self.db.query(query_vector, k=k)
        
        # Remove the query vector itself from results (distance = 0)
        results = [(e, d) for e, d in results if e.id != selected_entry.id][:k-1]
        
        # Update visualization
        neighbor_indices = []
        for entry, dist in results:
            for i, v in enumerate(all_vectors):
                if v.id == entry.id:
                    neighbor_indices.append(i)
                    break
        
        self.gl_widget.set_query_result(query_vector, neighbor_indices)
        
        # Update results table
        self.results_table.setRowCount(len(results))
        for i, (entry, distance) in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # Show translation if available
            display_name = entry.id
            if 'translation' in entry.metadata:
                display_name = f"{entry.id} ({entry.metadata['translation']})"
            
            self.results_table.setItem(i, 1, QTableWidgetItem(display_name))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{distance:.4f}"))
            vector_str = '[' + ', '.join([f"{x:.2f}" for x in entry.vector[:3]]) + '...]'
            self.results_table.setItem(i, 3, QTableWidgetItem(vector_str))
        
        # Log with translation
        query_name = selected_entry.id
        if 'translation' in selected_entry.metadata:
            query_name = f"{selected_entry.id} ({selected_entry.metadata['translation']})"
        
        self.log(f"Query: '{query_name}' - found {len(results)} similar vectors")
    
    def query_by_name(self):
        """Query by typing a word name"""
        if self.db is None or len(self.db) == 0:
            self.log("Error: Database is empty")
            QMessageBox.warning(self, "No Database", "Please load Darija words or create a database first.")
            return
        
        # Get search term
        search_term = self.search_input.text().strip().lower()
        
        if not search_term:
            QMessageBox.information(
                self,
                "Empty Search",
                "Please type a word name in the search box.\n\n"
                "Examples: baba, mama, khobz, salam, wahed"
            )
            return
        
        # Find the word (case-insensitive, partial match)
        all_vectors = self.db.get_all_vectors()
        found_entry = None
        found_idx = None
        
        # First try exact match
        for i, entry in enumerate(all_vectors):
            if entry.id.lower() == search_term:
                found_entry = entry
                found_idx = i
                break
        
        # If not found, try partial match
        if not found_entry:
            for i, entry in enumerate(all_vectors):
                if search_term in entry.id.lower():
                    found_entry = entry
                    found_idx = i
                    break
        
        # If still not found, try matching translation
        if not found_entry:
            for i, entry in enumerate(all_vectors):
                translation = entry.metadata.get('translation', '').lower()
                if search_term in translation:
                    found_entry = entry
                    found_idx = i
                    break
        
        if not found_entry:
            # Show available words
            available = [e.id for e in all_vectors[:20]]
            QMessageBox.warning(
                self,
                "Word Not Found",
                f"'{search_term}' not found in database.\n\n"
                f"Try one of these:\n" + ", ".join(available) + "..."
            )
            self.log(f"Word '{search_term}' not found")
            return
        
        # Select the vector visually
        self.gl_widget.selected_vector_idx = found_idx
        self.gl_widget.update()
        
        # Show selection info
        if self.gl_widget.on_vector_selected:
            self.gl_widget.on_vector_selected(found_idx, found_entry.vector, found_entry.id)
        
        # Perform query
        query_vector = found_entry.vector
        k = self.k_spin.value() + 1
        
        if self.current_custom_formula:
            distances = []
            for entry in all_vectors:
                try:
                    dist = self.current_custom_formula(query_vector, entry.vector)
                    distances.append((entry, dist))
                except Exception as e:
                    continue
            distances.sort(key=lambda x: x[1])
            results = distances[:k]
        else:
            results = self.db.query(query_vector, k=k)
        
        # Remove self from results
        results = [(e, d) for e, d in results if e.id != found_entry.id][:k-1]
        
        # Update visualization
        neighbor_indices = []
        for entry, dist in results:
            for i, v in enumerate(all_vectors):
                if v.id == entry.id:
                    neighbor_indices.append(i)
                    break
        
        self.gl_widget.set_query_result(query_vector, neighbor_indices)
        
        # Update results table
        self.results_table.setRowCount(len(results))
        for i, (entry, distance) in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # Show translation if available
            display_name = entry.id
            if 'translation' in entry.metadata:
                display_name = f"{entry.id} ({entry.metadata['translation']})"
            
            self.results_table.setItem(i, 1, QTableWidgetItem(display_name))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{distance:.4f}"))
            vector_str = '[' + ', '.join([f"{x:.2f}" for x in entry.vector[:3]]) + '...]'
            self.results_table.setItem(i, 3, QTableWidgetItem(vector_str))
        
        # Log
        query_name = found_entry.id
        if 'translation' in found_entry.metadata:
            query_name = f"{found_entry.id} ({found_entry.metadata['translation']})"
        
        self.log(f"🔍 Searched: '{search_term}' → Found: '{query_name}' with {len(results)} similar words")
    
    def clear_query(self):
        """Clear query highlighting"""
        self.gl_widget.clear_query()
        self.results_table.setRowCount(0)
        self.log("Query cleared")
    
    def update_visualization(self):
        """Update the 3D visualization with current database vectors"""
        if self.db is None:
            return
        
        vectors_data = []
        for entry in self.db.get_all_vectors():
            color = entry.metadata.get('color', (0.5, 0.5, 0.5))
            vectors_data.append((entry.vector, color, entry.id))
        
        self.gl_widget.set_vectors(vectors_data)
        
        if self.gl_widget.animate:
            self.gl_widget.update()
    
    def update_stats(self):
        """Update statistics display"""
        if self.db is None:
            return
        
        stats = self.db.get_stats()
        stats_text = f"""Database Statistics:
        
Dimension: {self.db.dimension}
Metric: {self.db.metric.value}
Total Vectors: {stats['total_vectors']}
Total Queries: {stats['total_queries']}
        """
        self.stats_label.setText(stats_text)
    
    def toggle_animation(self):
        """Toggle rotation animation"""
        self.gl_widget.animate = not self.gl_widget.animate
        if self.gl_widget.animate:
            self.timer.start(16)  # ~60 FPS
            self.log("Animation enabled")
        else:
            self.timer.stop()
            self.log("Animation disabled")
    
    def toggle_labels(self):
        """Toggle vector labels"""
        self.gl_widget.toggle_labels()
        status = "enabled" if self.gl_widget.show_labels else "disabled"
        self.log(f"Vector labels {status}")
    
    def toggle_quadrants(self):
        """Toggle quadrant labels"""
        self.gl_widget.toggle_quadrants()
        status = "enabled" if self.gl_widget.show_quadrants else "disabled"
        self.log(f"Quadrant labels {status}")
    
    def clear_selection(self):
        """Clear vector selection"""
        self.gl_widget.selected_vector_idx = None
        self.gl_widget.update()
        self.selection_info.setText('💡 Click vector to see details')
        self.selection_info.setStyleSheet("""
            QLabel {
                background-color: #263238;
                color: #00E5FF;
                padding: 5px;
                border-radius: 3px;
                font-size: 9pt;
                font-weight: bold;
                max-height: 60px;
            }
        """)
        self.log("Selection cleared")
    
    def reset_camera(self):
        """Reset camera to default position"""
        self.gl_widget.rotation_x = 30
        self.gl_widget.rotation_y = 45
        self.gl_widget.zoom = -15
        self.gl_widget.update()
        self.log("Camera reset")
    
    def open_formula_editor(self):
        """Open the custom formula editor dialog"""
        dialog = FormulaEditorDialog(self)
        
        if dialog.exec_() == QDialog.Accepted:
            if dialog.custom_formula and dialog.formula_name:
                # Store the custom formula
                self.custom_formulas[dialog.formula_name] = dialog.custom_formula
                self.current_custom_formula = dialog.custom_formula
                
                # Update label
                self.current_formula_label.setText(
                    f"✓ Custom: {dialog.formula_name}\n"
                    f"Click 'Query' to use this formula"
                )
                self.current_formula_label.setStyleSheet("""
                    QLabel {
                        background-color: #c8e6c9;
                        padding: 5px;
                        border-radius: 3px;
                        font-size: 9pt;
                        color: #2e7d32;
                        font-weight: bold;
                    }
                """)
                
                self.log(f"Custom formula '{dialog.formula_name}' created and loaded")
    
    def on_vector_clicked(self, idx, vector, label):
        """Handle vector selection"""
        if idx is None:
            # Deselected
            self.selection_info.setText('💡 Click vector to see details')
            self.selection_info.setStyleSheet("""
                QLabel {
                    background-color: #263238;
                    color: #00E5FF;
                    padding: 5px;
                    border-radius: 3px;
                    font-size: 9pt;
                    font-weight: bold;
                    max-height: 60px;
                }
            """)
            self.log("Vector deselected")
        else:
            # Selected
            entry = self.db.get_all_vectors()[idx] if self.db else None
            if entry:
                # Get metadata - show only important info
                translation = entry.metadata.get('translation', '')
                category = entry.metadata.get('category', '')
                
                # Compact format
                if translation:
                    info_text = f"🎯 {label} → {translation} | {category} | ({vector[0]:.1f}, {vector[1]:.1f}, {vector[2]:.1f})"
                else:
                    info_text = f"🎯 {label} | {category} | ({vector[0]:.1f}, {vector[1]:.1f}, {vector[2]:.1f})"
                
                self.selection_info.setText(info_text)
                self.selection_info.setStyleSheet("""
                    QLabel {
                        background-color: #1B5E20;
                        color: #00FF00;
                        padding: 5px;
                        border-radius: 3px;
                        font-size: 9pt;
                        font-weight: bold;
                        max-height: 60px;
                    }
                """)
                
                self.log(f"Selected: {label} → {translation}")
    
    def log(self, message):
        """Add message to activity log"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")


def main():
    app = QApplication(sys.argv)
    window = VectorDBVisualizerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()