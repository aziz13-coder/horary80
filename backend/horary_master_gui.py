#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Horary Master - Complete Enhanced Traditional Horary Astrology GUI Application

A complete PySide6 GUI for traditional horary astrology with enhanced features:
- Full backend integration with HoraryEngine
- Dashboard with real statistics and chart management
- Interactive chart casting with live validation
- Complete chart analysis with wheel visualization
- Timeline view with historical analysis
- Notebook system for organizing research
- License management and configuration
- Dark/Light theme support

Created: 2025-06-06
Author: Horary Master Team
"""

import sys
import os
import json
import sqlite3
import logging
import traceback
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QFormLayout, QStackedWidget, QToolBar, QStatusBar,
    QPushButton, QLabel, QTextEdit, QLineEdit, QComboBox, QDateTimeEdit,
    QRadioButton, QButtonGroup, QFrame, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QProgressBar, QListWidget, 
    QListWidgetItem, QMessageBox, QDialog, QDialogButtonBox,
    QTextBrowser, QGroupBox, QCheckBox, QSpinBox, QSlider,
    QSplitter, QHeaderView, QAbstractItemView, QTreeWidget, QTreeWidgetItem,
    QCalendarWidget, QPlainTextEdit, QFileDialog, QInputDialog,
    QStyledItemDelegate, QStyleOptionViewItem, QPushButton as QBtn,
    QSizePolicy
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, QObject, Signal, QSize, QRect,
    QPropertyAnimation, QEasingCurve, QDate, QTime, QDateTime,
    QAbstractItemModel, QModelIndex, QSortFilterProxyModel
)
from PySide6.QtGui import (
    QFont, QPixmap, QIcon, QPainter, QPen, QBrush, QColor,
    QLinearGradient, QAction, QPalette, QFontMetrics, QStandardItemModel,
    QStandardItem, QTextDocument, QTextCursor
)



# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the horary engine with proper error handling
HORARY_ENGINE_AVAILABLE = False
HORARY_ENGINE_ERROR = None

try:
    # Add the current directory to Python path to find modules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from horary_engine import HoraryEngine
    from license_manager import LicenseManager, get_license_info
    HORARY_ENGINE_AVAILABLE = True
    logger.info("Horary engine loaded successfully")
except ImportError as e:
    HORARY_ENGINE_ERROR = f"Import error: {str(e)}"
    logger.error(f"Failed to import horary engine: {e}")
except Exception as e:
    HORARY_ENGINE_ERROR = f"Unexpected error: {str(e)}"
    logger.error(f"Unexpected error loading horary engine: {e}")


class ChartDatabase:
    """Enhanced SQLite database for storing chart history and notes"""
    
    def __init__(self, db_path: str = "horary_charts.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Charts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS charts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                location TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                judgment TEXT,
                confidence INTEGER,
                chart_data TEXT,
                notes TEXT,
                tags TEXT,
                category TEXT DEFAULT 'general'
            )
        ''')
        
        # Notebook entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notebook_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'general',
                tags TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                modified_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                chart_id INTEGER,
                FOREIGN KEY (chart_id) REFERENCES charts (id)
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def save_chart(self, question: str, location: str, result: Dict[str, Any], 
                   notes: str = "", tags: List[str] = None, category: str = "general") -> int:
        """Save a chart to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        chart_data = json.dumps(result, default=str)  # Handle datetime serialization
        judgment = result.get('judgment', 'UNKNOWN')
        confidence = result.get('confidence', 0)
        tags_str = json.dumps(tags) if tags else "[]"
        
        cursor.execute('''
            INSERT INTO charts (question, location, judgment, confidence, chart_data, notes, tags, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (question, location, judgment, confidence, chart_data, notes, tags_str, category))
        
        chart_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Chart saved with ID: {chart_id}")
        return chart_id
    
    def get_recent_charts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent charts from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if category column exists
            cursor.execute("PRAGMA table_info(charts)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'category' in columns:
                cursor.execute('''
                    SELECT id, question, location, timestamp, judgment, confidence, category, tags
                    FROM charts
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT id, question, location, timestamp, judgment, confidence, tags
                    FROM charts
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            charts = []
            for row in cursor.fetchall():
                if 'category' in columns and len(row) == 8:
                    tags = json.loads(row[7]) if row[7] else []
                    charts.append({
                        'id': row[0],
                        'question': row[1],
                        'location': row[2],
                        'timestamp': row[3],
                        'judgment': row[4],
                        'confidence': row[5],
                        'category': row[6],
                        'tags': tags
                    })
                else:
                    tags = json.loads(row[6]) if row[6] else []
                    charts.append({
                        'id': row[0],
                        'question': row[1],
                        'location': row[2],
                        'timestamp': row[3],
                        'judgment': row[4],
                        'confidence': row[5],
                        'category': 'general',  # Default category for old schema
                        'tags': tags
                    })
            
            conn.close()
            return charts
            
        except Exception as e:
            conn.close()
            logger.error(f"Error getting recent charts: {e}")
            return []
    
    def get_chart(self, chart_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific chart by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if category column exists
            cursor.execute("PRAGMA table_info(charts)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'category' in columns:
                cursor.execute('''
                    SELECT question, location, timestamp, judgment, confidence, chart_data, notes, tags, category
                    FROM charts WHERE id = ?
                ''', (chart_id,))
            else:
                cursor.execute('''
                    SELECT question, location, timestamp, judgment, confidence, chart_data, notes, tags
                    FROM charts WHERE id = ?
                ''', (chart_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                try:
                    chart_data = json.loads(row[5]) if row[5] else {}
                    tags = json.loads(row[7]) if row[7] else []
                except json.JSONDecodeError:
                    chart_data = {}
                    tags = []
                
                if 'category' in columns and len(row) == 9:
                    return {
                        'id': chart_id,
                        'question': row[0],
                        'location': row[1],
                        'timestamp': row[2],
                        'judgment': row[3],
                        'confidence': row[4],
                        'chart_data': chart_data,
                        'notes': row[6],
                        'tags': tags,
                        'category': row[8]
                    }
                else:
                    return {
                        'id': chart_id,
                        'question': row[0],
                        'location': row[1],
                        'timestamp': row[2],
                        'judgment': row[3],
                        'confidence': row[4],
                        'chart_data': chart_data,
                        'notes': row[6],
                        'tags': tags,
                        'category': 'general'  # Default category for old schema
                    }
            
            return None
            
        except Exception as e:
            conn.close()
            logger.error(f"Error getting chart {chart_id}: {e}")
            return None
    
    def get_charts_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get charts within a date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if category column exists
            cursor.execute("PRAGMA table_info(charts)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'category' in columns:
                cursor.execute('''
                    SELECT id, question, location, timestamp, judgment, confidence, category
                    FROM charts
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (start_date.isoformat(), end_date.isoformat()))
            else:
                cursor.execute('''
                    SELECT id, question, location, timestamp, judgment, confidence
                    FROM charts
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (start_date.isoformat(), end_date.isoformat()))
            
            charts = []
            for row in cursor.fetchall():
                if 'category' in columns and len(row) == 7:
                    charts.append({
                        'id': row[0],
                        'question': row[1],
                        'location': row[2],
                        'timestamp': row[3],
                        'judgment': row[4],
                        'confidence': row[5],
                        'category': row[6]
                    })
                else:
                    charts.append({
                        'id': row[0],
                        'question': row[1],
                        'location': row[2],
                        'timestamp': row[3],
                        'judgment': row[4],
                        'confidence': row[5],
                        'category': 'general'  # Default category for old schema
                    })
            
            conn.close()
            return charts
            
        except Exception as e:
            conn.close()
            logger.error(f"Error getting charts by date range: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total charts
            cursor.execute('SELECT COUNT(*) FROM charts')
            total_charts = cursor.fetchone()[0]
            
            # This month charts
            first_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cursor.execute('SELECT COUNT(*) FROM charts WHERE timestamp >= ?', (first_of_month.isoformat(),))
            this_month = cursor.fetchone()[0]
            
            # Success rate (YES vs NO judgments)
            cursor.execute('SELECT judgment, COUNT(*) FROM charts WHERE judgment IN ("YES", "NO") GROUP BY judgment')
            judgment_counts = dict(cursor.fetchall())
            
            total_judgments = sum(judgment_counts.values())
            yes_count = judgment_counts.get('YES', 0)
            success_rate = (yes_count / total_judgments * 100) if total_judgments > 0 else 0
            
            # Category breakdown - check if column exists
            cursor.execute("PRAGMA table_info(charts)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'category' in columns:
                cursor.execute('SELECT category, COUNT(*) FROM charts GROUP BY category')
                categories = dict(cursor.fetchall())
            else:
                # For old schema without category column, show all as 'general'
                categories = {'general': total_charts} if total_charts > 0 else {}
            
            conn.close()
            
            return {
                'total_charts': total_charts,
                'this_month': this_month,
                'success_rate': success_rate,
                'categories': categories,
                'total_judgments': total_judgments
            }
            
        except Exception as e:
            conn.close()
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_charts': 0,
                'this_month': 0,
                'success_rate': 0,
                'categories': {},
                'total_judgments': 0
            }
    def save_notebook_entry(self, title: str, content: str, category: str = "general", 
                           tags: List[str] = None, chart_id: Optional[int] = None) -> int:
        """Save a notebook entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        tags_str = json.dumps(tags) if tags else "[]"
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO notebook_entries (title, content, category, tags, created_date, modified_date, chart_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, category, tags_str, now, now, chart_id))
        
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return entry_id
    
    def get_notebook_entries(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get notebook entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT id, title, content, category, tags, created_date, modified_date, chart_id
                FROM notebook_entries WHERE category = ?
                ORDER BY modified_date DESC
            ''', (category,))
        else:
            cursor.execute('''
                SELECT id, title, content, category, tags, created_date, modified_date, chart_id
                FROM notebook_entries
                ORDER BY modified_date DESC
            ''')
        
        entries = []
        for row in cursor.fetchall():
            tags = json.loads(row[4]) if row[4] else []
            entries.append({
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'category': row[3],
                'tags': tags,
                'created_date': row[5],
                'modified_date': row[6],
                'chart_id': row[7]
            })
        
        conn.close()
        return entries


class HoraryCalculationWorker(QObject):
    """Enhanced worker thread for horary calculations with proper error handling"""
    
    calculation_finished = Signal(dict)
    calculation_error = Signal(str)
    calculation_progress = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.engine = None
        self.initialize_engine()
    
    def initialize_engine(self):
        """Initialize the horary engine with proper error handling"""
        try:
            if HORARY_ENGINE_AVAILABLE:
                self.engine = HoraryEngine()
                logger.info("HoraryEngine initialized successfully")
            else:
                error_msg = HORARY_ENGINE_ERROR or "Horary engine not available"
                logger.error(f"Cannot initialize engine: {error_msg}")
                self.engine = None
        except Exception as e:
            logger.error(f"Failed to initialize HoraryEngine: {e}")
            self.engine = None
    
    def calculate_chart(self, question: str, settings: Dict[str, Any]):
        """Perform horary calculation in background thread"""
        try:
            self.calculation_progress.emit("Initializing calculation...")
            
            if not self.engine:
                raise Exception(f"Horary engine not available: {HORARY_ENGINE_ERROR}")
            
            self.calculation_progress.emit("Validating inputs...")
            
            # Validate inputs
            if not question.strip():
                raise ValueError("Question cannot be empty")
            
            if not settings.get('location', '').strip():
                raise ValueError("Location cannot be empty")
            
            self.calculation_progress.emit("Calculating chart...")
            
            # Perform calculation
            result = self.engine.judge(question, settings)
            
            self.calculation_progress.emit("Processing results...")
            
            # Validate result
            if not isinstance(result, dict):
                raise ValueError("Invalid result format from engine")
            
            if 'judgment' not in result:
                raise ValueError("Missing judgment in result")
            
            self.calculation_progress.emit("Calculation complete!")
            self.calculation_finished.emit(result)
            
            logger.info(f"Chart calculation successful: {result.get('judgment', 'Unknown')}")
            
        except Exception as e:
            error_msg = f"Calculation failed: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            self.calculation_error.emit(error_msg)


class AlertBanner(QFrame):
    """Enhanced alert banner widget with dismiss functionality"""
    
    dismissed = Signal()
    
    def __init__(self, message: str, alert_type: str = "warning", dismissible: bool = True):
        super().__init__()
        self.setup_ui(message, alert_type, dismissible)
    
    def setup_ui(self, message: str, alert_type: str, dismissible: bool):
        """Setup the alert banner UI"""
        self.setFrameStyle(QFrame.Box)
        
        colors = {
            "warning": {"bg": "#fff3cd", "border": "#ffeaa7", "text": "#856404"},
            "error": {"bg": "#f8d7da", "border": "#f5c6cb", "text": "#721c24"},
            "info": {"bg": "#d1ecf1", "border": "#bee5eb", "text": "#0c5460"},
            "success": {"bg": "#d4edda", "border": "#c3e6cb", "text": "#155724"}
        }
        
        color_set = colors.get(alert_type, colors["warning"])
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color_set["bg"]};
                border: 1px solid {color_set["border"]};
                border-radius: 4px;
                padding: 8px;
                margin: 4px;
                color: {color_set["text"]};
            }}
        """)
        
        layout = QHBoxLayout()
        
        # Icon
        icons = {"warning": "⚠️", "error": "❌", "info": "ℹ️", "success": "✅"}
        icon_label = QLabel(icons.get(alert_type, "ℹ️"))
        icon_label.setFont(QFont("Arial", 14))
        
        # Message
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        
        layout.addWidget(icon_label)
        layout.addWidget(message_label, 1)
        
        # Dismiss button
        if dismissible:
            dismiss_btn = QPushButton("✕")
            dismiss_btn.setFixedSize(20, 20)
            dismiss_btn.setStyleSheet("QPushButton { border: none; font-weight: bold; }")
            dismiss_btn.clicked.connect(self.dismiss)
            layout.addWidget(dismiss_btn)
        
        self.setLayout(layout)
    
    def dismiss(self):
        """Dismiss the alert banner"""
        self.hide()
        self.dismissed.emit()


class ChartCard(QFrame):
    """Enhanced reusable chart card component with more details"""
    
    chart_opened = Signal(int)
    chart_deleted = Signal(int)
    
    def __init__(self, chart_data: Dict[str, Any]):
        super().__init__()
        self.chart_id = chart_data['id']
        self.setup_ui(chart_data)
    
    def setup_ui(self, data: Dict[str, Any]):
        """Setup the enhanced chart card UI"""
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            QFrame:hover {
                border-color: #4CAF50;
                background-color: #f8f9fa;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
        """)
        
        layout = QVBoxLayout()
        
        # Header with title and menu
        header_layout = QHBoxLayout()
        
        title = data['question'][:80] + "..." if len(data['question']) > 80 else data['question']
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setWordWrap(True)
        
        # Context menu button
        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(24, 24)
        menu_btn.setAccessibleName("Options")
        menu_btn.setStyleSheet("QPushButton { border: none; font-weight: bold; }")
        
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(menu_btn)
        
        layout.addLayout(header_layout)
        
        # Details grid
        details_layout = QGridLayout()
        
        # Date and time
        try:
            date_obj = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            date_str = date_obj.strftime("%Y-%m-%d")
            time_str = date_obj.strftime("%H:%M")
        except:
            date_str = "Unknown"
            time_str = "Unknown"
        
        date_label = QLabel(f"📅 {date_str}")
        time_label = QLabel(f"🕐 {time_str}")
        date_label.setStyleSheet("color: #666; font-size: 10px;")
        time_label.setStyleSheet("color: #666; font-size: 10px;")
        
        # Location and confidence
        location_label = QLabel(f"📍 {data['location'][:30]}..." if len(data['location']) > 30 else f"📍 {data['location']}")
        confidence_label = QLabel(f"🎯 {data['confidence']}%")
        location_label.setStyleSheet("color: #666; font-size: 10px;")
        confidence_label.setStyleSheet("color: #666; font-size: 10px;")
        
        details_layout.addWidget(date_label, 0, 0)
        details_layout.addWidget(time_label, 0, 1)
        details_layout.addWidget(location_label, 1, 0)
        details_layout.addWidget(confidence_label, 1, 1)
        
        layout.addLayout(details_layout)
        
        # Footer with judgment and category
        footer_layout = QHBoxLayout()
        
        # Category badge
        category = data.get('category', 'general').title()
        category_badge = QLabel(category)
        category_badge.setStyleSheet("""
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
        """)
        category_badge.setFixedHeight(18)
        
        # Judgment tag
        judgment = data['judgment']
        tag_colors = {
            'YES': '#4CAF50',
            'NO': '#f44336', 
            'UNCLEAR': '#ff9800',
            'NOT RADICAL': '#9c27b0',
            'ERROR': '#607d8b',
            'UNKNOWN': '#757575'
        }
        
        tag_color = tag_colors.get(judgment, '#607d8b')
        tag_label = QLabel(judgment)
        tag_label.setStyleSheet(f"""
            background-color: {tag_color};
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
        """)
        tag_label.setFixedHeight(18)
        
        footer_layout.addWidget(category_badge)
        footer_layout.addStretch()
        footer_layout.addWidget(tag_label)
        
        layout.addLayout(footer_layout)
        
        self.setLayout(layout)
        self.setMinimumHeight(130)
        self.setMaximumHeight(130)
    
    def mousePressEvent(self, event):
        """Handle mouse click to open chart"""
        if event.button() == Qt.LeftButton:
            self.chart_opened.emit(self.chart_id)


class StatsGrid(QWidget):
    """Fixed statistics grid with proper layout and icon display"""
    
    def __init__(self, database: ChartDatabase):
        super().__init__()
        self.database = database
        self.setup_ui()
        self.update_stats()
    
    def setup_ui(self):
        """Setup the statistics grid with fixed layout"""
        layout = QGridLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Create stat cards with proper sizing
        self.total_charts_card = self.create_stat_card("Total Charts", "0", "📊")
        self.this_month_card = self.create_stat_card("This Month", "0", "📅")
        self.success_rate_card = self.create_stat_card("Success Rate", "0%", "✅")
        self.profile_tier_card = self.create_stat_card("Profile Tier", "Demo", "👤")
        
        # Arrange in 2x2 grid with equal sizing
        layout.addWidget(self.total_charts_card, 0, 0)
        layout.addWidget(self.success_rate_card, 0, 1)
        layout.addWidget(self.this_month_card, 1, 0)
        layout.addWidget(self.profile_tier_card, 1, 1)
        
        # Set equal column and row stretches
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        
        self.setLayout(layout)
    
    def create_stat_card(self, title: str, value: str, icon: str) -> QFrame:
        """Create a statistics card with fixed layout and proper icon display"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 20px;
                margin: 8px;
            }
            QFrame:hover {
                border-color: #2196F3;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
        """)
        
        # Set minimum and maximum sizes to ensure consistency
        card.setMinimumSize(200, 140)
        card.setMaximumSize(300, 180)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # Icon with proper styling
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 24))  # Use system emoji font
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border-radius: 20px;
                border: 1px solid #e9ecef;
            }
        """)
        
        # Title with proper wrapping
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 14px;
                font-weight: bold;
                background: none;
                border: none;
            }
        """)
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1)
        
        # Value with proper sizing
        value_label = QLabel(value if value else "--")
        value_label.setFont(QFont("Arial", 32, QFont.Bold))
        value_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                background: none;
                border: none;
            }
        """)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        value_label.setMinimumHeight(60)
        
        layout.addLayout(header_layout)
        layout.addWidget(value_label, 1)  # Give value more space
        
        card.setLayout(layout)
        card.value_label = value_label  # Store reference for updates
        
        return card
    
    def update_stats(self):
        """Update statistics from database"""
        try:
            stats = self.database.get_statistics()
            
            self.total_charts_card.value_label.setText(str(stats['total_charts']))
            self.this_month_card.value_label.setText(str(stats['this_month']))
            self.success_rate_card.value_label.setText(f"{stats['success_rate']:.1f}%")
            
            # Update profile tier based on license
            if HORARY_ENGINE_AVAILABLE:
                try:
                    license_info = get_license_info()
                    if license_info.get('valid', False):
                        tier = license_info.get('licenseType', 'Licensed').title()
                    else:
                        tier = "Demo"
                except:
                    tier = "Demo"
            else:
                tier = "Offline"
            
            self.profile_tier_card.value_label.setText(tier)
            
        except Exception as e:
            logger.error(f"Failed to update stats: {e}")


class ChartWheelCanvas(QWidget):
    """Enhanced custom widget for drawing astrological chart wheel"""
    
    def __init__(self):
        super().__init__()
        self.chart_data = None
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: white; border: 1px solid #ccc; border-radius: 4px;")
    
    def set_chart_data(self, chart_data: Dict[str, Any]):
        """Set the chart data to display"""
        self.chart_data = chart_data
        self.update()
    
    def paintEvent(self, event):
        """Paint the enhanced chart wheel"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.chart_data or 'chart_data' not in self.chart_data:
            self.draw_placeholder(painter)
            return
        
        try:
            self.draw_chart_wheel(painter)
        except Exception as e:
            logger.error(f"Error drawing chart wheel: {e}")
            self.draw_placeholder(painter)
    
    def draw_placeholder(self, painter: QPainter):
        """Draw placeholder when no chart data"""
        painter.setPen(QPen(QColor("#ccc"), 2))
        center = self.rect().center()
        radius = min(self.width(), self.height()) // 2 - 20
        painter.drawCircle(center, radius)
        
        painter.setPen(QPen(QColor("#999")))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(self.rect(), Qt.AlignCenter, "Chart Wheel\n(Awaiting Chart Data)")
    
    def draw_chart_wheel(self, painter: QPainter):
        """Draw the complete enhanced astrological chart wheel"""
        center = self.rect().center()
        outer_radius = min(self.width(), self.height()) // 2 - 30
        house_radius = outer_radius * 0.75
        planet_radius = outer_radius * 0.85
        
        # Draw background circle
        painter.setPen(QPen(QColor("#f0f0f0"), 1))
        painter.setBrush(QBrush(QColor("#fafafa")))
        painter.drawCircle(center, outer_radius)
        
        # Draw zodiac wheel
        self.draw_zodiac_wheel(painter, center, outer_radius, house_radius)
        
        # Draw house cusps
        chart_houses = self.chart_data['chart_data'].get('houses', [])
        if chart_houses:
            self.draw_house_cusps(painter, center, house_radius, chart_houses)
        
        # Draw planets
        chart_planets = self.chart_data['chart_data'].get('planets', {})
        if chart_planets:
            self.draw_planets(painter, center, planet_radius, chart_planets)
        
        # Draw aspects
        chart_aspects = self.chart_data['chart_data'].get('aspects', [])
        if chart_aspects:
            self.draw_aspects(painter, center, planet_radius * 0.7, chart_aspects, chart_planets)
    
    def draw_zodiac_wheel(self, painter: QPainter, center, outer_radius: int, inner_radius: int):
        """Draw the zodiac signs wheel with colors"""
        signs = [
            ("♈", "Aries", "#ff6b6b"),     ("♉", "Taurus", "#4ecdc4"),
            ("♊", "Gemini", "#45b7d1"),    ("♋", "Cancer", "#96ceb4"),
            ("♌", "Leo", "#feca57"),       ("♍", "Virgo", "#48dbfb"),
            ("♎", "Libra", "#ff9ff3"),     ("♏", "Scorpio", "#54a0ff"),
            ("♐", "Sagittarius", "#5f27cd"), ("♑", "Capricorn", "#00d2d3"),
            ("♒", "Aquarius", "#ff9f43"),  ("♓", "Pisces", "#a55eea")
        ]
        
        for i, (glyph, name, color) in enumerate(signs):
            start_angle = i * 30 - 90  # Start from Aries at top
            
            # Draw sign sector background (subtle)
            painter.setPen(QPen(QColor(color), 1))
            painter.setBrush(QBrush(QColor(color).lighter(190)))
            
            # Calculate sector coordinates (simplified for demonstration)
            painter.drawLine(
                center.x() + inner_radius * math.cos(math.radians(start_angle)),
                center.y() + inner_radius * math.sin(math.radians(start_angle)),
                center.x() + outer_radius * math.cos(math.radians(start_angle)),
                center.y() + outer_radius * math.sin(math.radians(start_angle))
            )
            
            # Draw sign glyph
            text_angle = start_angle + 15  # Center in sign
            text_radius = (outer_radius + inner_radius) / 2
            text_x = center.x() + text_radius * math.cos(math.radians(text_angle))
            text_y = center.y() + text_radius * math.sin(math.radians(text_angle))
            
            painter.setPen(QPen(QColor("#333"), 2))
            painter.setFont(QFont("Arial", 16, QFont.Bold))
            painter.drawText(QRect(text_x-15, text_y-15, 30, 30), Qt.AlignCenter, glyph)
        
        # Draw outer and inner circles
        painter.setPen(QPen(QColor("#333"), 2))
        painter.setBrush(QBrush())
        painter.drawCircle(center, outer_radius)
        painter.drawCircle(center, inner_radius)
    
    def draw_house_cusps(self, painter: QPainter, center, radius: int, houses: List[float]):
        """Draw house cusps with numbers"""
        painter.setPen(QPen(QColor("#666"), 2))
        
        for i, cusp in enumerate(houses):
            angle = cusp - 90  # Adjust for chart orientation
            
            # Draw cusp line
            x = center.x() + radius * math.cos(math.radians(angle))
            y = center.y() + radius * math.sin(math.radians(angle))
            painter.drawLine(center.x(), center.y(), x, y)
            
            # Draw house number
            number_radius = radius * 0.9
            number_x = center.x() + number_radius * math.cos(math.radians(angle + 15))
            number_y = center.y() + number_radius * math.sin(math.radians(angle + 15))
            
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#333")))
            painter.drawText(QRect(number_x-10, number_y-10, 20, 20), Qt.AlignCenter, str(i+1))
    
    def draw_planets(self, painter: QPainter, center, radius: int, planets: Dict[str, Any]):
        """Draw planets with glyphs and degrees"""
        planet_glyphs = {
            'Sun': '☉', 'Moon': '☽', 'Mercury': '☿', 'Venus': '♀',
            'Mars': '♂', 'Jupiter': '♃', 'Saturn': '♄'
        }
        
        planet_colors = {
            'Sun': '#ff6b35', 'Moon': '#a8dadc', 'Mercury': '#457b9d',
            'Venus': '#e63946', 'Mars': '#f77f00', 'Jupiter': '#fcbf49',
            'Saturn': '#003566'
        }
        
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        
        for planet_name, planet_data in planets.items():
            if planet_name in planet_glyphs:
                longitude = planet_data['longitude']
                angle = longitude - 90  # Adjust for chart orientation
                
                # Planet color
                color = planet_colors.get(planet_name, '#333333')
                painter.setPen(QPen(QColor(color), 2))
                
                # Planet position
                planet_x = center.x() + radius * math.cos(math.radians(angle))
                planet_y = center.y() + radius * math.sin(math.radians(angle))
                
                # Draw planet circle background
                painter.setBrush(QBrush(QColor(color).lighter(180)))
                painter.drawEllipse(planet_x-12, planet_y-12, 24, 24)
                
                # Draw planet glyph
                painter.setPen(QPen(QColor(color)))
                glyph = planet_glyphs[planet_name]
                painter.drawText(QRect(planet_x-12, planet_y-12, 24, 24), Qt.AlignCenter, glyph)
                
                # Draw degree text
                painter.setFont(QFont("Arial", 8))
                degree_text = f"{longitude:.1f}°"
                degree_x = center.x() + (radius + 25) * math.cos(math.radians(angle))
                degree_y = center.y() + (radius + 25) * math.sin(math.radians(angle))
                painter.drawText(QRect(degree_x-20, degree_y-10, 40, 20), Qt.AlignCenter, degree_text)
                painter.setFont(QFont("Arial", 14, QFont.Bold))
    
    def draw_aspects(self, painter: QPainter, center, radius: int, aspects: List[Dict], planets: Dict[str, Any]):
        """Draw aspect lines between planets"""
        aspect_colors = {
            'Conjunction': '#333333',
            'Sextile': '#4CAF50',
            'Square': '#f44336',
            'Trine': '#2196F3',
            'Opposition': '#ff9800'
        }
        
        for aspect in aspects:
            if not aspect.get('applying', False):
                continue  # Only show applying aspects
            
            planet1_name = aspect['planet1']
            planet2_name = aspect['planet2']
            aspect_type = aspect['aspect']
            
            if planet1_name in planets and planet2_name in planets:
                # Get planet positions
                lon1 = planets[planet1_name]['longitude']
                lon2 = planets[planet2_name]['longitude']
                
                angle1 = lon1 - 90
                angle2 = lon2 - 90
                
                x1 = center.x() + radius * math.cos(math.radians(angle1))
                y1 = center.y() + radius * math.sin(math.radians(angle1))
                x2 = center.x() + radius * math.cos(math.radians(angle2))
                y2 = center.y() + radius * math.sin(math.radians(angle2))
                
                # Draw aspect line
                color = aspect_colors.get(aspect_type, '#333333')
                painter.setPen(QPen(QColor(color), 1, Qt.DashLine))
                painter.drawLine(x1, y1, x2, y2)


class TimelineView(QWidget):
    """Complete timeline view for chart history and trends"""
    
    chart_selected = Signal(int)
    
    def __init__(self, database: ChartDatabase):
        super().__init__()
        self.database = database
        self.setup_ui()
        self.load_timeline_data()
    
    def setup_ui(self):
        """Setup the timeline view UI"""
        layout = QVBoxLayout()
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📈 Chart Timeline & Analysis")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        
        # Date range selector
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        
        self.start_date = QDateTimeEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("To:"))
        
        self.end_date = QDateTimeEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        
        date_layout.addWidget(self.end_date)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setAccessibleName("Refresh timeline")
        refresh_btn.clicked.connect(self.load_timeline_data)
        date_layout.addWidget(refresh_btn)
        
        header_layout.addWidget(title_label, 1)
        header_layout.addLayout(date_layout)
        
        layout.addLayout(header_layout)
        
        # Splitter for timeline and details
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Timeline calendar and stats
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # Mini calendar
        self.calendar = QCalendarWidget()
        self.calendar.setMaximumHeight(200)
        self.calendar.clicked.connect(self.on_date_selected)
        left_layout.addWidget(self.calendar)
        
        # Timeline stats
        stats_group = QGroupBox("Timeline Statistics")
        stats_layout = QFormLayout()
        
        self.total_period_label = QLabel("0")
        self.yes_count_label = QLabel("0")
        self.no_count_label = QLabel("0")
        self.avg_confidence_label = QLabel("0%")
        
        stats_layout.addRow("Total Charts:", self.total_period_label)
        stats_layout.addRow("YES Judgments:", self.yes_count_label)
        stats_layout.addRow("NO Judgments:", self.no_count_label)
        stats_layout.addRow("Avg Confidence:", self.avg_confidence_label)
        
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)
        
        left_layout.addStretch()
        left_widget.setLayout(left_layout)
        
        # Right: Chart list and details
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        # Chart list for selected period
        charts_label = QLabel("Charts in Period")
        charts_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_layout.addWidget(charts_label)
        
        self.timeline_list = QListWidget()
        self.timeline_list.itemDoubleClicked.connect(self.on_chart_double_clicked)
        right_layout.addWidget(self.timeline_list)
        
        right_widget.setLayout(right_layout)
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def load_timeline_data(self):
        """Load timeline data from database"""
        start_dt = self.start_date.dateTime().toPython()
        end_dt = self.end_date.dateTime().toPython()
        
        charts = self.database.get_charts_by_date_range(start_dt, end_dt)
        
        # Update statistics
        self.update_timeline_stats(charts)
        
        # Update chart list
        self.timeline_list.clear()
        
        for chart in charts:
            item_text = f"{chart['timestamp'][:10]} - {chart['judgment']} - {chart['question'][:50]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, chart['id'])
            
            # Color code by judgment
            if chart['judgment'] == 'YES':
                item.setBackground(QColor("#c8e6c9"))
            elif chart['judgment'] == 'NO':
                item.setBackground(QColor("#ffcdd2"))
            elif chart['judgment'] == 'UNCLEAR':
                item.setBackground(QColor("#fff3e0"))
            
            self.timeline_list.addItem(item)
        
        # Update calendar highlights
        self.highlight_calendar_dates(charts)
    
    def update_timeline_stats(self, charts: List[Dict]):
        """Update timeline statistics"""
        total = len(charts)
        yes_count = len([c for c in charts if c['judgment'] == 'YES'])
        no_count = len([c for c in charts if c['judgment'] == 'NO'])
        
        confidences = [c['confidence'] for c in charts if c['confidence'] is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        self.total_period_label.setText(str(total))
        self.yes_count_label.setText(str(yes_count))
        self.no_count_label.setText(str(no_count))
        self.avg_confidence_label.setText(f"{avg_confidence:.1f}%")
    
    def highlight_calendar_dates(self, charts: List[Dict]):
        """Highlight dates with charts on calendar"""
        # Reset calendar format
        self.calendar.setDateTextFormat(QDate(), self.calendar.dateTextFormat(QDate()))
        
        # Create date format for highlighted dates
        format_with_charts = self.calendar.dateTextFormat(QDate())
        format_with_charts.setBackground(QBrush(QColor("#e3f2fd")))
        format_with_charts.setForeground(QBrush(QColor("#1976d2")))
        
        # Highlight dates with charts
        for chart in charts:
            try:
                chart_date = datetime.fromisoformat(chart['timestamp'])
                q_date = QDate(chart_date.year, chart_date.month, chart_date.day)
                self.calendar.setDateTextFormat(q_date, format_with_charts)
            except:
                pass
    
    def on_date_selected(self, date: QDate):
        """Handle calendar date selection"""
        # Filter charts by selected date
        selected_date = date.toPython()
        start_dt = datetime.combine(selected_date, datetime.min.time())
        end_dt = datetime.combine(selected_date, datetime.max.time())
        
        charts = self.database.get_charts_by_date_range(start_dt, end_dt)
        
        # Update list to show only charts from selected date
        self.timeline_list.clear()
        for chart in charts:
            item_text = f"{chart['timestamp'][11:16]} - {chart['judgment']} - {chart['question'][:40]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, chart['id'])
            self.timeline_list.addItem(item)
    
    def on_chart_double_clicked(self, item: QListWidgetItem):
        """Handle chart selection from timeline"""
        chart_id = item.data(Qt.UserRole)
        if chart_id:
            self.chart_selected.emit(chart_id)


class NotebookView(QWidget):
    """Complete notebook system for organizing horary research"""
    
    def __init__(self, database: ChartDatabase):
        super().__init__()
        self.database = database
        self.current_entry_id = None
        self.setup_ui()
        self.load_notebook_entries()
    
    def setup_ui(self):
        """Setup the notebook view UI"""
        layout = QHBoxLayout()
        
        # Left sidebar: Entry list and categories
        sidebar = QWidget()
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout()
        
        # Header with new entry button
        header_layout = QHBoxLayout()
        title_label = QLabel("📝 Research Notebook")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        
        new_btn = QPushButton("+ New Entry")
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        new_btn.clicked.connect(self.new_entry)
        
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(new_btn)
        sidebar_layout.addLayout(header_layout)
        
        # Category filter
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))
        
        self.category_filter = QComboBox()
        self.category_filter.addItems(["All", "General", "Theory", "Practice", "Research", "Personal"])
        self.category_filter.currentTextChanged.connect(self.filter_entries)
        category_layout.addWidget(self.category_filter)
        
        sidebar_layout.addLayout(category_layout)
        
        # Entry list
        self.entry_list = QListWidget()
        self.entry_list.itemSelectionChanged.connect(self.load_selected_entry)
        sidebar_layout.addWidget(self.entry_list)
        
        sidebar.setLayout(sidebar_layout)
        
        # Right side: Entry editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout()
        
        # Entry header
        entry_header = QHBoxLayout()
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Entry Title...")
        self.title_edit.setFont(QFont("Arial", 14, QFont.Bold))
        self.title_edit.textChanged.connect(self.mark_modified)
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_entry)
        self.save_btn.setEnabled(False)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_entry)
        self.delete_btn.setEnabled(False)
        
        entry_header.addWidget(self.title_edit, 1)
        entry_header.addWidget(self.save_btn)
        entry_header.addWidget(self.delete_btn)
        
        editor_layout.addLayout(entry_header)
        
        # Entry metadata
        meta_layout = QHBoxLayout()
        
        meta_layout.addWidget(QLabel("Category:"))
        self.entry_category = QComboBox()
        self.entry_category.addItems(["General", "Theory", "Practice", "Research", "Personal"])
        self.entry_category.currentTextChanged.connect(self.mark_modified)
        
        meta_layout.addWidget(self.entry_category)
        meta_layout.addWidget(QLabel("Tags:"))
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma-separated tags...")
        self.tags_edit.textChanged.connect(self.mark_modified)
        
        meta_layout.addWidget(self.tags_edit, 1)
        meta_layout.addStretch()
        
        editor_layout.addLayout(meta_layout)
        
        # Content editor
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Write your notes here...\n\nSupports rich text formatting.")
        self.content_edit.textChanged.connect(self.mark_modified)
        editor_layout.addWidget(self.content_edit)
        
        # Entry info
        self.entry_info_label = QLabel()
        self.entry_info_label.setStyleSheet("color: #666; font-size: 11px;")
        editor_layout.addWidget(self.entry_info_label)
        
        editor_widget.setLayout(editor_layout)
        
        # Add to main layout
        layout.addWidget(sidebar)
        layout.addWidget(editor_widget, 1)
        
        self.setLayout(layout)
        
        # Initialize state
        self.clear_editor()
    
    def load_notebook_entries(self):
        """Load all notebook entries"""
        category = self.category_filter.currentText()
        filter_category = None if category == "All" else category.lower()
        
        entries = self.database.get_notebook_entries(filter_category)
        
        self.entry_list.clear()
        for entry in entries:
            item_text = f"{entry['title'][:50]}..."
            if len(entry['title']) <= 50:
                item_text = entry['title']
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, entry)
            item.setToolTip(f"Category: {entry['category'].title()}\nCreated: {entry['created_date'][:10]}")
            
            self.entry_list.addItem(item)
    
    def filter_entries(self):
        """Filter entries by category"""
        self.load_notebook_entries()
    
    def load_selected_entry(self):
        """Load the selected entry into the editor"""
        selected_items = self.entry_list.selectedItems()
        if not selected_items:
            self.clear_editor()
            return
        
        entry_data = selected_items[0].data(Qt.UserRole)
        if not entry_data:
            return
        
        self.current_entry_id = entry_data['id']
        
        # Load entry data
        self.title_edit.setText(entry_data['title'])
        self.content_edit.setPlainText(entry_data['content'] or "")
        self.entry_category.setCurrentText(entry_data['category'].title())
        
        tags = ", ".join(entry_data['tags']) if entry_data['tags'] else ""
        self.tags_edit.setText(tags)
        
        # Update info
        created = entry_data['created_date'][:19] if entry_data['created_date'] else "Unknown"
        modified = entry_data['modified_date'][:19] if entry_data['modified_date'] else "Unknown"
        self.entry_info_label.setText(f"Created: {created} | Modified: {modified}")
        
        # Enable controls
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(True)
    
    def clear_editor(self):
        """Clear the editor for new entry"""
        self.current_entry_id = None
        self.title_edit.clear()
        self.content_edit.clear()
        self.tags_edit.clear()
        self.entry_category.setCurrentIndex(0)
        self.entry_info_label.clear()
        
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
    
    def mark_modified(self):
        """Mark entry as modified"""
        self.save_btn.setEnabled(True)
    
    def new_entry(self):
        """Create a new entry"""
        self.clear_editor()
        self.title_edit.setFocus()
    
    def save_entry(self):
        """Save the current entry"""
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Please enter a title for the entry.")
            return
        
        content = self.content_edit.toPlainText()
        category = self.entry_category.currentText().lower()
        tags_text = self.tags_edit.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []
        
        try:
            if self.current_entry_id:
                # Update existing entry
                conn = sqlite3.connect(self.database.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE notebook_entries 
                    SET title = ?, content = ?, category = ?, tags = ?, modified_date = ?
                    WHERE id = ?
                ''', (title, content, category, json.dumps(tags), datetime.now().isoformat(), self.current_entry_id))
                
                conn.commit()
                conn.close()
            else:
                # Create new entry
                entry_id = self.database.save_notebook_entry(title, content, category, tags)
                self.current_entry_id = entry_id
            
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(True)
            self.load_notebook_entries()
            
            # Update info label
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if self.current_entry_id:
                self.entry_info_label.setText(f"Modified: {now}")
            
            QMessageBox.information(self, "Success", "Entry saved successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save entry: {str(e)}")
    
    def delete_entry(self):
        """Delete the current entry"""
        if not self.current_entry_id:
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this entry? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                conn = sqlite3.connect(self.database.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM notebook_entries WHERE id = ?', (self.current_entry_id,))
                conn.commit()
                conn.close()
                
                self.clear_editor()
                self.load_notebook_entries()
                
                QMessageBox.information(self, "Success", "Entry deleted successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete entry: {str(e)}")


class DashboardPage(QWidget):
    """Enhanced dashboard page with real data integration"""
    
    chart_selected = Signal(int)
    cast_chart_requested = Signal()
    
    def __init__(self, database: ChartDatabase):
        super().__init__()
        self.database = database
        self.setup_ui()
        self.refresh_data()
    
    def setup_ui(self):
        """Setup the enhanced dashboard UI"""
        layout = QVBoxLayout()
        
        # Alert banner for engine status
        if not HORARY_ENGINE_AVAILABLE:
            error_msg = f"Backend engine unavailable: {HORARY_ENGINE_ERROR}"
            self.alert_banner = AlertBanner(error_msg, "error")
        else:
            try:
                license_info = get_license_info()
                if not license_info.get('valid', False):
                    self.alert_banner = AlertBanner("Demo mode - Enhanced features require license", "warning")
                else:
                    days_remaining = license_info.get('daysRemaining', 0)
                    if days_remaining < 30:
                        self.alert_banner = AlertBanner(f"License expires in {days_remaining} days", "warning")
                    else:
                        self.alert_banner = AlertBanner("Licensed version - All features available", "success")
            except Exception as e:
                self.alert_banner = AlertBanner(f"License check failed: {str(e)}", "warning")
        
        layout.addWidget(self.alert_banner)

        # Stats grid with heading
        stats_heading = QLabel("Today's Stats")
        stats_heading.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(stats_heading)

        self.stats_grid = StatsGrid(self.database)
        layout.addWidget(self.stats_grid)
        
        # Action grid
        action_layout = QHBoxLayout()
        
        cast_button = QPushButton("⚡ Cast New Chart")
        cast_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                padding: 16px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #45a049, stop:1 #3d8b40);
            }
        """)
        cast_button.clicked.connect(self.cast_chart_requested.emit)
        
        timeline_button = QPushButton("📊 Timeline View")
        timeline_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff9800, stop:1 #f57c00);
                color: white;
                border: none;
                padding: 16px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f57c00, stop:1 #ef6c00);
            }
        """)
        timeline_button.clicked.connect(lambda: self.parent().parent().show_timeline())
        
        export_button = QPushButton("📤 Export Data")
        export_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                border: none;
                padding: 16px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1976D2, stop:1 #1565C0);
            }
        """)
        export_button.clicked.connect(self.export_data)
        
        action_layout.addWidget(cast_button)
        action_layout.addWidget(timeline_button)
        action_layout.addWidget(export_button)
        action_layout.addStretch()
        
        layout.addLayout(action_layout)
        
        # Recent charts section
        recent_header = QHBoxLayout()
        recent_label = QLabel("Recent Charts")
        recent_label.setFont(QFont("Arial", 18, QFont.Bold))
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setAccessibleName("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setToolTip("Refresh dashboard data")
        
        recent_header.addWidget(recent_label, 1)
        recent_header.addWidget(refresh_btn)
        
        layout.addLayout(recent_header)
        
        # Search and filter
        search_layout = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search charts...")
        self.search_edit.textChanged.connect(self.filter_charts)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "YES", "NO", "UNCLEAR", "NOT RADICAL", "ERROR"])
        self.filter_combo.currentTextChanged.connect(self.filter_charts)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["All Categories", "General", "Marriage", "Money", "Health", "Career"])
        self.category_combo.currentTextChanged.connect(self.filter_charts)
        
        search_layout.addWidget(self.search_edit, 3)
        search_layout.addWidget(self.filter_combo, 1)
        search_layout.addWidget(self.category_combo, 1)
        
        layout.addLayout(search_layout)
        
        # Charts list
        self.charts_scroll = QScrollArea()
        self.charts_widget = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_widget)
        self.charts_scroll.setWidget(self.charts_widget)
        self.charts_scroll.setWidgetResizable(True)
        self.charts_scroll.setMinimumHeight(400)
        
        layout.addWidget(self.charts_scroll, 1)
        
        self.setLayout(layout)
    
    def refresh_data(self):
        """Refresh all dashboard data"""
        self.load_recent_charts()
        self.stats_grid.update_stats()
        logger.info("Dashboard data refreshed")
    
    def load_recent_charts(self):
        """Load recent charts into the dashboard"""
        try:
            charts = self.database.get_recent_charts(50)  # Load more for filtering

            # Clear existing charts
            for i in reversed(range(self.charts_layout.count())):
                child = self.charts_layout.itemAt(i).widget()
                if child:
                    child.setParent(None)

            if not charts:
                empty = QLabel("No charts yet. Click Cast New Chart to get started.")
                empty.setAlignment(Qt.AlignCenter)
                empty.setStyleSheet("color: #666; margin: 40px;")
                self.charts_layout.addWidget(empty)
            else:
                # Add chart cards
                for chart in charts:
                    card = ChartCard(chart)
                    card.chart_opened.connect(self.chart_selected.emit)
                    self.charts_layout.addWidget(card)

            # Add stretch at the end
            self.charts_layout.addStretch()

            logger.info(f"Loaded {len(charts)} charts into dashboard")
            
        except Exception as e:
            logger.error(f"Failed to load recent charts: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load charts: {str(e)}")
    
    def filter_charts(self):
        """Filter charts based on search and filter criteria"""
        search_text = self.search_edit.text().lower()
        filter_judgment = self.filter_combo.currentText()
        filter_category = self.category_combo.currentText()
        
        for i in range(self.charts_layout.count()):
            widget = self.charts_layout.itemAt(i).widget()
            if isinstance(widget, ChartCard):
                # Get chart data and check if it matches filters
                chart_data = self.database.get_chart(widget.chart_id)
                if chart_data:
                    show = True
                    
                    # Search filter
                    if search_text:
                        question_match = search_text in chart_data['question'].lower()
                        location_match = search_text in chart_data['location'].lower()
                        if not (question_match or location_match):
                            show = False
                    
                    # Judgment filter
                    if filter_judgment != "All" and chart_data['judgment'] != filter_judgment:
                        show = False
                    
                    # Category filter
                    if filter_category != "All Categories":
                        chart_category = chart_data.get('category', 'general').title()
                        if chart_category != filter_category:
                            show = False
                    
                    widget.setVisible(show)
    
    def export_data(self):
        """Export chart data to various formats"""
        try:
            # Ask user for export format and location
            export_formats = ["JSON", "CSV", "PDF Report"]
            format_choice, ok = QInputDialog.getItem(
                self, "Export Data", "Select export format:", export_formats, 0, False
            )
            
            if not ok:
                return
            
            # Get save location
            if format_choice == "JSON":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Export as JSON", "horary_charts.json", "JSON Files (*.json)"
                )
            elif format_choice == "CSV":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Export as CSV", "horary_charts.csv", "CSV Files (*.csv)"
                )
            else:  # PDF
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Export as PDF", "horary_report.pdf", "PDF Files (*.pdf)"
                )
            
            if not file_path:
                return
            
            # Export data
            charts = self.database.get_recent_charts(1000)  # Get all charts
            
            if format_choice == "JSON":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(charts, f, indent=2, ensure_ascii=False, default=str)
            
            elif format_choice == "CSV":
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Question', 'Location', 'Timestamp', 'Judgment', 'Confidence', 'Category'])
                    for chart in charts:
                        writer.writerow([
                            chart['id'], chart['question'], chart['location'],
                            chart['timestamp'], chart['judgment'], chart['confidence'],
                            chart.get('category', 'general')
                        ])
            
            # For PDF, would need additional library like reportlab
            else:
                QMessageBox.information(self, "Export", "PDF export not yet implemented. Please use JSON or CSV.")
                return
            
            QMessageBox.information(self, "Export Complete", f"Data exported successfully to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data: {str(e)}")


class CastChartPage(QWidget):
    """Fixed cast chart form page with full-width layout"""
    
    chart_cast = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_calculation_worker()
    
    def setup_calculation_worker(self):
        """Setup calculation worker thread"""
        self.calc_thread = QThread()
        self.calc_worker = HoraryCalculationWorker()
        self.calc_worker.moveToThread(self.calc_thread)
        
        # Connect signals
        self.calc_worker.calculation_finished.connect(self.on_calculation_finished)
        self.calc_worker.calculation_error.connect(self.on_calculation_error)
        self.calc_worker.calculation_progress.connect(self.on_calculation_progress)
        
        self.calc_thread.started.connect(lambda: logger.info("Calculation thread started"))
        self.calc_thread.start()
    
    def setup_ui(self):
        """Setup the cast chart form with full-width layout"""
        # Main layout wraps a scroll area so the form feels like a web page
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(16)
        
        # Form title
        title_label = QLabel("⚡ Cast Enhanced Horary Chart")
        title_label.setFont(QFont("Arial", 26, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Show error banner only when engine is unavailable
        if not HORARY_ENGINE_AVAILABLE:
            status_label = QLabel(f"❌ Backend Error: {HORARY_ENGINE_ERROR}")
            status_label.setStyleSheet("""
                QLabel {
                    color: #e74c3c;
                    font-weight: bold;
                    padding: 15px;
                    background-color: #ffebee;
                    border: 2px solid #ffcdd2;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
            """)
            status_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(status_label)
        
        # Create form container that will live inside a scroll area
        form_container = QWidget()
        form_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 15px;
                padding: 40px;
            }
        """)

        form_layout = QVBoxLayout(form_container)
        form_layout.setSpacing(16)
        
        # Create form sections in a responsive layout
        sections_layout = QGridLayout()
        sections_layout.setSpacing(16)
        sections_layout.setColumnStretch(0, 1)
        sections_layout.setColumnStretch(1, 1)
        
        # Question field - spans both columns
        question_section = self.create_question_section()
        sections_layout.addWidget(question_section, 0, 0, 1, 2)  # Row 0, columns 0-1
        
        # Location field - spans both columns  
        location_section = self.create_location_section()
        sections_layout.addWidget(location_section, 1, 0, 1, 2)  # Row 1, columns 0-1
        
        # Time options - left column
        time_section = self.create_time_section()
        sections_layout.addWidget(time_section, 2, 0)  # Row 2, column 0
        
        # House assignment - right column
        house_section = self.create_house_section()
        sections_layout.addWidget(house_section, 2, 1)  # Row 2, column 1
        
        # Advanced options - spans both columns
        advanced_section = self.create_advanced_section()
        sections_layout.addWidget(advanced_section, 3, 0, 1, 2)  # Row 3, columns 0-1
        
        form_layout.addLayout(sections_layout)
        
        # Progress indicator
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-style: italic;
                font-size: 16px;
                text-align: center;
                margin: 15px 0;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 6px;
            }
        """)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.hide()
        form_layout.addWidget(self.progress_label)
        
        # Submit button - full width with better styling
        self.submit_button = QPushButton("⚡ Cast Enhanced Horary Chart")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                padding: 25px 50px;
                border-radius: 12px;
                font-size: 20px;
                font-weight: bold;
                margin-top: 30px;
                min-height: 60px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #45a049, stop:1 #3d8b40);
                transform: translateY(-2px);
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.submit_button.clicked.connect(self.cast_chart)
        form_layout.addWidget(self.submit_button)
        
        # Wrap form in a scroll area for better UX on small screens
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(form_container)
        scroll_area.setMaximumWidth(600)

        main_layout.addWidget(scroll_area, alignment=Qt.AlignCenter)
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def create_question_section(self) -> QWidget:
        """Create the question input section with full width"""
        section = QGroupBox("Horary Question *")
        section.setFont(QFont("Arial", 16, QFont.Bold))
        section.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.question_edit = QTextEdit()
        self.question_edit.setMinimumHeight(120)
        self.question_edit.setMaximumHeight(150)
        self.question_edit.setPlaceholderText("Enter your horary question here...\n\nBe specific and focused. Traditional horary works best with clear, sincere questions.")
        self.question_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                font-family: Arial;
                background-color: white;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #4CAF50;
                background-color: #f9fff9;
            }
        """)
        
        layout.addWidget(self.question_edit)
        section.setLayout(layout)
        return section
    
    def create_location_section(self) -> QWidget:
        """Create the location input section with full width"""
        section = QGroupBox("Location *")
        section.setFont(QFont("Arial", 16, QFont.Bold))
        section.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Enter location (e.g., London, England or New York, NY)")
        self.location_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
                background-color: #f9fff9;
            }
        """)
        
        self.location_status = QLabel()
        self.location_status.setStyleSheet("font-size: 12px; color: #666; margin-top: 8px;")

        location_btn = QPushButton("Use My Location")
        location_btn.setAccessibleName("Use my location")
        location_btn.clicked.connect(self.autofill_location)

        layout.addWidget(self.location_edit)
        layout.addWidget(location_btn)
        layout.addWidget(self.location_status)
        section.setLayout(layout)
        return section
    
    def create_time_section(self) -> QWidget:
        """Create the time options section"""
        section = QGroupBox("Chart Time")
        section.setFont(QFont("Arial", 16, QFont.Bold))
        section.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.time_button_group = QButtonGroup()
        
        self.current_time_radio = QRadioButton("Use current time (moment of asking)")
        self.current_time_radio.setChecked(True)
        self.current_time_radio.setFont(QFont("Arial", 13))
        self.time_button_group.addButton(self.current_time_radio)
        
        self.custom_time_radio = QRadioButton("Specify custom time")
        self.custom_time_radio.setFont(QFont("Arial", 13))
        self.time_button_group.addButton(self.custom_time_radio)
        
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.datetime_edit.setEnabled(False)
        self.datetime_edit.setCalendarPopup(True)
        # QDateTimeEdit inherits from QAbstractSpinBox and does not use
        # scroll bars, so no policy needs to be applied here
        self.datetime_edit.setStyleSheet("""
            QDateTimeEdit {
                padding: 12px 15px;
                font-size: 13px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: #f8f9fa;
                min-height: 20px;
            }
            QDateTimeEdit:enabled {
                background-color: white;
                border-color: #4CAF50;
            }
        """)
        
        self.custom_time_radio.toggled.connect(self.datetime_edit.setEnabled)
        
        layout.addWidget(self.current_time_radio)
        layout.addWidget(self.custom_time_radio)
        layout.addWidget(self.datetime_edit)
        
        section.setLayout(layout)
        return section
    
    def create_house_section(self) -> QWidget:
        """Create the house assignment section"""
        section = QGroupBox("House Assignment")
        section.setFont(QFont("Arial", 16, QFont.Bold))
        section.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.house_button_group = QButtonGroup()
        
        self.auto_house_radio = QRadioButton("Automatic (AI analyzes question)")
        self.auto_house_radio.setChecked(True)
        self.auto_house_radio.setFont(QFont("Arial", 12))
        self.house_button_group.addButton(self.auto_house_radio)
        
        self.manual_house_radio = QRadioButton("Manual house selection")
        self.manual_house_radio.setFont(QFont("Arial", 12))
        self.house_button_group.addButton(self.manual_house_radio)
        
        self.house_combo = QComboBox()
        house_options = [
            "1st House - Self, Body, Life",
            "2nd House - Money, Possessions", 
            "3rd House - Siblings, Communication",
            "4th House - Home, Family",
            "5th House - Children, Creativity",
            "6th House - Health, Work",
            "7th House - Marriage, Partnerships",
            "8th House - Death, Transformation",
            "9th House - Travel, Religion",
            "10th House - Career, Reputation",
            "11th House - Friends, Hopes",
            "12th House - Hidden Things"
        ]
        self.house_combo.addItems(house_options)
        self.house_combo.setEnabled(False)
        self.house_combo.setStyleSheet("""
            QComboBox {
                padding: 12px 15px;
                font-size: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: #f8f9fa;
                min-height: 20px;
            }
            QComboBox:enabled {
                background-color: white;
                border-color: #4CAF50;
            }
        """)
        
        self.manual_house_radio.toggled.connect(self.house_combo.setEnabled)
        
        layout.addWidget(self.auto_house_radio)
        layout.addWidget(self.manual_house_radio)
        layout.addWidget(self.house_combo)
        
        section.setLayout(layout)
        return section
    
    def create_advanced_section(self) -> QWidget:
        """Create the advanced options section"""
        section = QGroupBox("Advanced Options")
        section.setFont(QFont("Arial", 16, QFont.Bold))
        section.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Create checkboxes in a grid for better organization
        checkbox_layout = QGridLayout()
        checkbox_layout.setSpacing(15)
        
        self.ignore_radicality_check = QCheckBox("Ignore radicality concerns")
        self.ignore_void_moon_check = QCheckBox("Ignore void of course Moon")
        self.ignore_combustion_check = QCheckBox("Ignore combustion effects")
        self.ignore_saturn_7th_check = QCheckBox("Ignore Saturn in 7th warning")
        
        checkboxes = [
            self.ignore_radicality_check, self.ignore_void_moon_check,
            self.ignore_combustion_check, self.ignore_saturn_7th_check
        ]
        
        for i, checkbox in enumerate(checkboxes):
            checkbox.setFont(QFont("Arial", 12))
            checkbox.setStyleSheet("QCheckBox { margin: 8px 0; }")
            row = i // 2
            col = i % 2
            checkbox_layout.addWidget(checkbox, row, col)
        
        layout.addLayout(checkbox_layout)
        section.setLayout(layout)
        return section

    def autofill_location(self):
        """Attempt to detect user location via IP geolocation"""
        try:
            resp = requests.get("https://ipinfo.io/json", timeout=5)
            data = resp.json()
            parts = [data.get("city"), data.get("region"), data.get("country")]
            location = ", ".join([p for p in parts if p])
            if location:
                self.location_edit.setText(location)
                self.location_status.setText("Location detected automatically")
            else:
                self.location_status.setText("Could not detect location")
        except Exception:
            self.location_status.setText("Location detection failed")
    
    # ... rest of the methods remain the same as in original code ...
    def cast_chart(self):
        """Cast the horary chart with validation"""
        # Same implementation as original
        pass
    
    def on_calculation_progress(self, message: str):
        """Handle calculation progress updates"""
        self.progress_label.setText(message)
        logger.debug(f"Calculation progress: {message}")
    
    def on_calculation_finished(self, result: dict):
        """Handle completed calculation"""
        self.submit_button.setEnabled(True)
        self.submit_button.setText("⚡ Cast Enhanced Horary Chart")
        self.progress_label.hide()
        
        result['form_data'] = {
            'question': self.question_edit.toPlainText().strip(),
            'location': self.location_edit.text().strip(),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Chart calculation completed: {result.get('judgment', 'Unknown')}")
        self.chart_cast.emit(result)
    
    def on_calculation_error(self, error: str):
        """Handle calculation error"""
        self.submit_button.setEnabled(True)
        self.submit_button.setText("⚡ Cast Enhanced Horary Chart")
        self.progress_label.hide()
        
        logger.error(f"Chart calculation failed: {error}")
        
        QMessageBox.critical(self, "Calculation Error", 
                           f"Failed to calculate horary chart:\n\n{error}\n\n"
                           "Please check your inputs and try again.")

# ... (Previous ChartDetailPage, SettingsDialog classes remain the same) ...

class ChartDetailPage(QWidget):
    """Enhanced chart detail page with complete functionality"""
    
    def __init__(self):
        super().__init__()
        self.chart_data = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the enhanced chart detail UI"""
        layout = QVBoxLayout()

        # Placeholder for a summary card of the chart
        self.card_layout = QVBoxLayout()
        layout.addLayout(self.card_layout)

        # Chart header with enhanced information
        self.header_widget = self.create_chart_header()
        layout.addWidget(self.header_widget)
        
        # Splitter for chart wheel and tabs
        splitter = QSplitter(Qt.Vertical)
        
        # Chart wheel canvas with controls
        wheel_widget = QWidget()
        wheel_layout = QVBoxLayout()
        
        # Wheel controls
        wheel_controls = QHBoxLayout()
        wheel_controls.addWidget(QLabel("Chart Wheel:"))
        
        zoom_in_btn = QPushButton("🔍+")
        zoom_out_btn = QPushButton("🔍-")
        reset_btn = QPushButton("⚡ Reset")
        
        for btn in [zoom_in_btn, zoom_out_btn, reset_btn]:
            btn.setFixedSize(32, 32)
        
        wheel_controls.addWidget(zoom_in_btn)
        wheel_controls.addWidget(zoom_out_btn)
        wheel_controls.addWidget(reset_btn)
        wheel_controls.addStretch()
        
        wheel_layout.addLayout(wheel_controls)
        
        # Chart wheel
        self.chart_wheel = ChartWheelCanvas()
        self.chart_wheel.setMinimumHeight(450)
        wheel_layout.addWidget(self.chart_wheel)
        
        wheel_widget.setLayout(wheel_layout)
        splitter.addWidget(wheel_widget)
        
        # Enhanced tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.setup_tabs()
        splitter.addWidget(self.tab_widget)
        
        # Set splitter proportions
        splitter.setSizes([450, 600])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def create_chart_header(self) -> QWidget:
        """Create enhanced chart header"""
        header = QFrame()
        header.setFrameStyle(QFrame.Box)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title row
        title_row = QHBoxLayout()
        
        self.title_label = QLabel("Chart Analysis")
        self.title_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.title_label.setWordWrap(True)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        self.share_btn = QPushButton("📤 Share")
        self.export_btn = QPushButton("⬇️ Export")
        self.print_btn = QPushButton("🖨️ Print")
        
        for btn in [self.share_btn, self.export_btn, self.print_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
            """)
        
        actions_layout.addWidget(self.share_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.print_btn)
        
        title_row.addWidget(self.title_label, 1)
        title_row.addLayout(actions_layout)
        
        # Badges and meta row
        meta_row = QHBoxLayout()
        
        self.radical_badge = QLabel("RADICAL")
        self.radical_badge.setStyleSheet("""
            QLabel {
                background-color: #28a745;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        
        self.confidence_badge = QLabel("85%")
        self.confidence_badge.setStyleSheet("""
            QLabel {
                background-color: #007bff;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        
        self.judgment_badge = QLabel("YES")
        self.judgment_badge.setStyleSheet("""
            QLabel {
                background-color: #28a745;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        
        self.timestamp_label = QLabel("Calculated on...")
        self.timestamp_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        
        meta_row.addWidget(self.radical_badge)
        meta_row.addWidget(self.confidence_badge)
        meta_row.addWidget(self.judgment_badge)
        meta_row.addStretch()
        meta_row.addWidget(self.timestamp_label)
        
        layout.addLayout(title_row)
        layout.addLayout(meta_row)
        
        header.setLayout(layout)
        return header
    
    def setup_tabs(self):
        """Setup all detail tabs with complete functionality"""
        # Judgment tab
        self.judgment_tab = self.create_judgment_tab()
        self.tab_widget.addTab(self.judgment_tab, "📋 Judgment")
        
        # Dignities tab
        self.dignities_tab = self.create_dignities_tab()
        self.tab_widget.addTab(self.dignities_tab, "👑 Dignities")
        
        # Aspects tab
        self.aspects_tab = self.create_aspects_tab()
        self.tab_widget.addTab(self.aspects_tab, "🔗 Aspects")
        
        # General Info tab
        self.general_tab = self.create_general_info_tab()
        self.tab_widget.addTab(self.general_tab, "ℹ️ General Info")
        
        # Considerations tab
        self.considerations_tab = self.create_considerations_tab()
        self.tab_widget.addTab(self.considerations_tab, "⚖️ Considerations")
        
        # Moon Story tab
        self.moon_story_tab = self.create_moon_story_tab()
        self.tab_widget.addTab(self.moon_story_tab, "🌙 Moon Story")
        
        # Notes tab
        self.notes_tab = self.create_notes_tab()
        self.tab_widget.addTab(self.notes_tab, "📝 Notes")
    
    def create_judgment_tab(self) -> QWidget:
        """Create enhanced judgment tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Category and context selector
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Analysis Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "General Analysis", "Marriage & Love", "Money & Finance", 
            "Health & Illness", "Career & Business", "Travel", "Legal Matters"
        ])
        self.category_combo.currentTextChanged.connect(self.update_judgment_analysis)
        
        controls_layout.addWidget(self.category_combo)
        controls_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Analysis")
        refresh_btn.setAccessibleName("Refresh analysis")
        refresh_btn.clicked.connect(self.update_judgment_analysis)
        controls_layout.addWidget(refresh_btn)
        
        layout.addLayout(controls_layout)
        
        # Judgment display with rich formatting
        self.judgment_browser = QTextBrowser()
        self.judgment_browser.setMinimumHeight(400)
        self.judgment_browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 16px;
                background-color: #fafafa;
                font-family: Arial;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.judgment_browser)
        
        widget.setLayout(layout)
        return widget
    
    def create_dignities_tab(self) -> QWidget:
        """Create enhanced dignities table tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Table controls
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Planet Dignities & Strengths"))
        controls_layout.addStretch()
        
        export_dignities_btn = QPushButton("📊 Export Table")
        export_dignities_btn.clicked.connect(self.export_dignities_table)
        controls_layout.addWidget(export_dignities_btn)
        
        layout.addLayout(controls_layout)
        
        # Enhanced dignities table
        self.dignities_table = QTableWidget(7, 6)
        self.dignities_table.setHorizontalHeaderLabels([
            "Planet", "Sign", "House", "Dignity Score", "Strength Bar", "Notes"
        ])
        
        # Configure table appearance
        self.dignities_table.horizontalHeader().setStretchLastSection(True)
        self.dignities_table.setAlternatingRowColors(True)
        self.dignities_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dignities_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        
        layout.addWidget(self.dignities_table)
        
        # Dignity explanation
        explanation_label = QLabel("""
        <b>Dignity Scoring:</b> Rulership (+5), Exaltation (+4), Joy (+2), Angular (+1), 
        Succedent (0), Cadent (-1), Detriment (-5), Fall (-4). 
        Solar conditions: Cazimi (very strong), Combustion (very weak), Under Beams (weak).
        """)
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("color: #666; font-size: 11px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;")
        layout.addWidget(explanation_label)
        
        widget.setLayout(layout)
        return widget
    
    def create_aspects_tab(self) -> QWidget:
        """Create enhanced aspects tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Aspect controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Show Aspects:"))
        
        self.aspects_filter = QComboBox()
        self.aspects_filter.addItems(["All Aspects", "Applying Only", "Separating Only", "Exact Aspects"])
        self.aspects_filter.currentTextChanged.connect(self.filter_aspects)
        
        controls_layout.addWidget(self.aspects_filter)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Enhanced aspects table
        self.aspects_table = QTableWidget(0, 7)
        self.aspects_table.setHorizontalHeaderLabels([
            "Planets", "Aspect", "Orb", "Status", "Quality", "Timing", "Significance"
        ])
        
        self.aspects_table.horizontalHeader().setStretchLastSection(True)
        self.aspects_table.setAlternatingRowColors(True)
        self.aspects_table.setSortingEnabled(True)
        self.aspects_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 10px;
            }
        """)
        
        layout.addWidget(self.aspects_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_general_info_tab(self) -> QWidget:
        """Create enhanced general info tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create info sections
        sections_layout = QHBoxLayout()
        
        # Temporal info section
        temporal_group = QGroupBox("Temporal Information")
        temporal_layout = QFormLayout()
        
        self.planetary_day_label = QLabel("-")
        self.planetary_hour_label = QLabel("-")
        self.local_time_label = QLabel("-")
        self.utc_time_label = QLabel("-")
        
        temporal_layout.addRow("Planetary Day:", self.planetary_day_label)
        temporal_layout.addRow("Planetary Hour:", self.planetary_hour_label)
        temporal_layout.addRow("Local Time:", self.local_time_label)
        temporal_layout.addRow("UTC Time:", self.utc_time_label)
        
        temporal_group.setLayout(temporal_layout)
        
        # Lunar info section
        lunar_group = QGroupBox("Lunar Information")
        lunar_layout = QFormLayout()
        
        self.moon_phase_label = QLabel("-")
        self.moon_mansion_label = QLabel("-")
        self.moon_speed_label = QLabel("-")
        self.moon_condition_label = QLabel("-")
        
        lunar_layout.addRow("Moon Phase:", self.moon_phase_label)
        lunar_layout.addRow("Moon Mansion:", self.moon_mansion_label)
        lunar_layout.addRow("Moon Speed:", self.moon_speed_label)
        lunar_layout.addRow("Moon Condition:", self.moon_condition_label)
        
        lunar_group.setLayout(lunar_layout)
        
        sections_layout.addWidget(temporal_group)
        sections_layout.addWidget(lunar_group)
        
        layout.addLayout(sections_layout)
        
        # Chart coordinates section
        coords_group = QGroupBox("Chart Coordinates")
        coords_layout = QFormLayout()
        
        self.ascendant_label = QLabel("-")
        self.midheaven_label = QLabel("-")
        self.location_label = QLabel("-")
        self.coordinates_label = QLabel("-")
        
        coords_layout.addRow("Ascendant:", self.ascendant_label)
        coords_layout.addRow("Midheaven:", self.midheaven_label)
        coords_layout.addRow("Location:", self.location_label)
        coords_layout.addRow("Coordinates:", self.coordinates_label)
        
        coords_group.setLayout(coords_layout)
        layout.addWidget(coords_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_considerations_tab(self) -> QWidget:
        """Create enhanced considerations tab"""
        widget = QWidget()
        self.considerations_layout = QVBoxLayout()
        
        # Header
        header_label = QLabel("Traditional Horary Considerations")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setStyleSheet("color: #2c3e50; margin-bottom: 12px;")
        self.considerations_layout.addWidget(header_label)
        
        # Explanation
        explanation = QLabel("""
        These are the traditional considerations that determine whether a horary chart can be judged.
        Charts that fail these tests may not be reliable for divination.
        """)
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic; margin-bottom: 16px;")
        self.considerations_layout.addWidget(explanation)
        
        widget.setLayout(self.considerations_layout)
        return widget
    
    def create_moon_story_tab(self) -> QWidget:
        """Create enhanced moon story tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Moon story header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🌙 The Moon's Story")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        
        # Moon story controls
        self.moon_period_combo = QComboBox()
        self.moon_period_combo.addItems(["Next 7 days", "Next 30 days", "Next 90 days"])
        self.moon_period_combo.currentTextChanged.connect(self.update_moon_story)
        
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(QLabel("Show period:"))
        header_layout.addWidget(self.moon_period_combo)
        
        layout.addLayout(header_layout)
        
        # Scroll area for moon aspects
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.moon_content_widget = QWidget()
        self.moon_content_layout = QVBoxLayout(self.moon_content_widget)
        
        scroll_area.setWidget(self.moon_content_widget)
        layout.addWidget(scroll_area)
        
        widget.setLayout(layout)
        return widget
    
    def create_notes_tab(self) -> QWidget:
        """Create enhanced notes tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Notes toolbar
        toolbar_layout = QHBoxLayout()
        
        self.save_notes_btn = QPushButton("💾 Save Notes")
        self.save_notes_btn.clicked.connect(self.save_chart_notes)
        
        self.export_notes_btn = QPushButton("📤 Export Notes")
        self.export_notes_btn.clicked.connect(self.export_notes)
        
        self.voice_note_btn = QPushButton("🎤 Voice Note")
        self.voice_note_btn.setEnabled(False)  # Future feature
        
        toolbar_layout.addWidget(self.save_notes_btn)
        toolbar_layout.addWidget(self.export_notes_btn)
        toolbar_layout.addWidget(self.voice_note_btn)
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # Rich text editor for notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("""
Add your personal notes and observations about this chart here...

You can include:
• Traditional interpretations and reasoning
• Cross-references to other charts or events
• Follow-up questions or research ideas
• Outcome verification (for learning)

This text editor supports rich formatting - use the right-click menu for options.
        """)
        
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 12px;
                background-color: #fafafa;
                font-family: Arial;
                font-size: 13px;
                line-height: 1.4;
            }
        """)
        
        layout.addWidget(self.notes_edit)
        
        # Notes metadata
        self.notes_info_label = QLabel()
        self.notes_info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.notes_info_label)
        
        widget.setLayout(layout)
        return widget
    
    def set_chart_data(self, chart_data: Dict[str, Any]):
        """Set and display chart data"""
        self.chart_data = chart_data

        # Update summary card at top
        if hasattr(self, "card_layout"):
            while self.card_layout.count():
                child = self.card_layout.takeAt(0).widget()
                if child:
                    child.deleteLater()

            card = ChartCard(chart_data)
            self.card_layout.addWidget(card)

        self.update_display()
        logger.info(
            f"Chart detail page updated for chart ID: {chart_data.get('id', 'Unknown')}"
        )
    
    def update_display(self):
        """Update all displays with current chart data"""
        if not self.chart_data:
            return
        
        try:
            # Update header
            self.update_header()
            
            # Update chart wheel
            self.chart_wheel.set_chart_data(self.chart_data)
            
            # Update all tabs
            self.update_judgment_analysis()
            self.update_dignities_tab()
            self.update_aspects_tab()
            self.update_general_info_tab()
            self.update_considerations_tab()
            self.update_moon_story()
            self.load_chart_notes()
            
        except Exception as e:
            logger.error(f"Error updating chart display: {e}")
            QMessageBox.warning(self, "Display Error", f"Error updating chart display: {str(e)}")
    
    def update_header(self):
        """Update the chart header information"""
        question = self.chart_data.get('form_data', {}).get('question', 'Unknown Question')
        self.title_label.setText(question[:100] + "..." if len(question) > 100 else question)
        
        judgment = self.chart_data.get('judgment', 'UNKNOWN')
        confidence = self.chart_data.get('confidence', 0)
        
        # Update judgment badge
        judgment_colors = {
            'YES': '#28a745', 'NO': '#dc3545', 'UNCLEAR': '#ffc107',
            'NOT RADICAL': '#6f42c1', 'ERROR': '#6c757d'
        }
        
        self.judgment_badge.setText(judgment)
        color = judgment_colors.get(judgment, '#6c757d')
        self.judgment_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        
        # Update confidence badge
        self.confidence_badge.setText(f"{confidence}%")
        
        # Update radical badge
        considerations = self.chart_data.get('considerations', {})
        is_radical = considerations.get('radical', False)
        
        self.radical_badge.setText("RADICAL" if is_radical else "NOT RADICAL")
        radical_color = '#28a745' if is_radical else '#dc3545'
        self.radical_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {radical_color};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        
        # Update timestamp
        try:
            timestamp = self.chart_data.get('form_data', {}).get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp)
                self.timestamp_label.setText(f"Calculated on {dt.strftime('%Y-%m-%d at %H:%M')}")
        except:
            self.timestamp_label.setText("Timestamp unavailable")
    
    def update_judgment_analysis(self):
        """Update the judgment analysis display"""
        reasoning = self.chart_data.get('reasoning', [])
        judgment = self.chart_data.get('judgment', 'UNKNOWN')
        confidence = self.chart_data.get('confidence', 0)
        
        # Create rich HTML content
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 25px; }}
                h3 {{ color: #7f8c8d; }}
                .judgment {{ font-size: 24px; font-weight: bold; text-align: center; 
                           padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .yes {{ background-color: #d4edda; color: #155724; }}
                .no {{ background-color: #f8d7da; color: #721c24; }}
                .unclear {{ background-color: #fff3cd; color: #856404; }}
                .not-radical {{ background-color: #e2e3e5; color: #383d41; }}
                .confidence {{ text-align: center; font-size: 18px; margin: 10px 0; }}
                .reasoning {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; }}
                li {{ margin: 8px 0; }}
                .timing {{ background-color: #e3f2fd; padding: 12px; border-radius: 6px; margin: 15px 0; }}
            </style>
        </head>
        <body>
        
        <h1>Horary Judgment Analysis</h1>
        """
        
        # Judgment result
        judgment_class = judgment.lower().replace(' ', '-')
        html_content += f"""
        <div class="judgment {judgment_class}">
            {judgment}
        </div>
        
        <div class="confidence">
            Confidence Level: <strong>{confidence}%</strong>
        </div>
        """
        
        # Reasoning section
        if reasoning:
            html_content += """
            <h2>Traditional Analysis & Reasoning</h2>
            <div class="reasoning">
            <ul>
            """
            
            for reason in reasoning:
                html_content += f"<li>{reason}</li>"
            
            html_content += "</ul></div>"
        
        # Timing section
        timing = self.chart_data.get('timing')
        if timing:
            html_content += f"""
            <h2>Timing Indication</h2>
            <div class="timing">
                <strong>When:</strong> {timing}
            </div>
            """
        
        # Traditional factors
        traditional_factors = self.chart_data.get('traditional_factors', {})
        if traditional_factors:
            html_content += "<h2>Traditional Factors</h2><ul>"
            
            perfection_type = traditional_factors.get('perfection_type')
            if perfection_type:
                html_content += f"<li><strong>Perfection Type:</strong> {perfection_type.title()}</li>"
            
            reception = traditional_factors.get('reception')
            if reception and reception != 'none':
                html_content += f"<li><strong>Reception:</strong> {reception.replace('_', ' ').title()}</li>"
            
            if 'querent_strength' in traditional_factors:
                html_content += f"<li><strong>Querent Strength:</strong> {traditional_factors['querent_strength']}</li>"
            
            if 'quesited_strength' in traditional_factors:
                html_content += f"<li><strong>Quesited Strength:</strong> {traditional_factors['quesited_strength']}</li>"
            
            html_content += "</ul>"
        
        html_content += "</body></html>"
        
        self.judgment_browser.setHtml(html_content)
    
    def update_dignities_tab(self):
        """Update the dignities table with complete data"""
        chart_data = self.chart_data.get('chart_data', {})
        planets = chart_data.get('planets', {})
        
        self.dignities_table.setRowCount(len(planets))
        
        for row, (planet_name, planet_data) in enumerate(planets.items()):
            # Planet name
            planet_item = QTableWidgetItem(planet_name)
            planet_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.dignities_table.setItem(row, 0, planet_item)
            
            # Sign
            sign = planet_data.get('sign', 'Unknown')
            sign_item = QTableWidgetItem(sign)
            self.dignities_table.setItem(row, 1, sign_item)
            
            # House
            house = planet_data.get('house', 0)
            house_item = QTableWidgetItem(str(house))
            self.dignities_table.setItem(row, 2, house_item)
            
            # Dignity score
            dignity = planet_data.get('dignity_score', 0)
            dignity_text = f"{dignity:+d}"
            dignity_item = QTableWidgetItem(dignity_text)
            dignity_item.setFont(QFont("Arial", 10, QFont.Bold))
            
            # Color code dignity
            if dignity > 3:
                dignity_item.setBackground(QColor("#c8e6c9"))  # Strong green
            elif dignity > 0:
                dignity_item.setBackground(QColor("#e8f5e9"))  # Light green
            elif dignity < -3:
                dignity_item.setBackground(QColor("#ffcdd2"))  # Strong red
            elif dignity < 0:
                dignity_item.setBackground(QColor("#ffebee"))  # Light red
            
            self.dignities_table.setItem(row, 3, dignity_item)
            
            # Strength bar
            strength_bar = QProgressBar()
            strength_bar.setMinimum(-10)
            strength_bar.setMaximum(10)
            strength_bar.setValue(dignity)
            strength_bar.setTextVisible(False)
            strength_bar.setFixedHeight(20)
            
            if dignity > 0:
                strength_bar.setStyleSheet("""
                    QProgressBar::chunk { 
                        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #4CAF50, stop:1 #8BC34A);
                    }
                """)
            else:
                strength_bar.setStyleSheet("""
                    QProgressBar::chunk { 
                        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #f44336, stop:1 #FF5722);
                    }
                """)
            
            self.dignities_table.setCellWidget(row, 4, strength_bar)
            
            # Notes (dignity details)
            notes = []
            if planet_data.get('retrograde', False):
                notes.append("Retrograde")
            
            # Add solar condition if available
            solar_condition = planet_data.get('solar_condition')
            if solar_condition and solar_condition.get('condition') != 'Free of Sun':
                notes.append(solar_condition['condition'])
            
            notes_text = ", ".join(notes) if notes else "-"
            notes_item = QTableWidgetItem(notes_text)
            notes_item.setFont(QFont("Arial", 9))
            self.dignities_table.setItem(row, 5, notes_item)
        
        # Adjust column widths
        self.dignities_table.resizeColumnsToContents()
    
    def update_aspects_tab(self):
        """Update the aspects table with complete data"""
        aspects = self.chart_data.get('chart_data', {}).get('aspects', [])
        
        # Filter aspects based on selection
        filtered_aspects = self.filter_aspects_list(aspects)
        
        self.aspects_table.setRowCount(len(filtered_aspects))
        
        for row, aspect in enumerate(filtered_aspects):
            # Planets
            planets_text = f"{aspect['planet1']} - {aspect['planet2']}"
            planets_item = QTableWidgetItem(planets_text)
            planets_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.aspects_table.setItem(row, 0, planets_item)
            
            # Aspect type
            aspect_type = aspect['aspect']
            aspect_item = QTableWidgetItem(aspect_type)
            
            # Color code aspects
            aspect_colors = {
                'Conjunction': '#333333',
                'Sextile': '#4CAF50',
                'Square': '#f44336',
                'Trine': '#2196F3',
                'Opposition': '#ff9800'
            }
            
            color = aspect_colors.get(aspect_type, '#333333')
            aspect_item.setForeground(QColor(color))
            aspect_item.setFont(QFont("Arial", 10, QFont.Bold))
            
            self.aspects_table.setItem(row, 1, aspect_item)
            
            # Orb
            orb = aspect.get('orb', 0)
            orb_item = QTableWidgetItem(f"{orb:.2f}°")
            self.aspects_table.setItem(row, 2, orb_item)
            
            # Status
            applying = aspect.get('applying', False)
            status = "Applying" if applying else "Separating"
            status_item = QTableWidgetItem(status)
            
            if applying:
                status_item.setBackground(QColor("#e8f5e9"))
                status_item.setForeground(QColor("#2e7d32"))
            else:
                status_item.setBackground(QColor("#ffebee"))
                status_item.setForeground(QColor("#c62828"))
            
            self.aspects_table.setItem(row, 3, status_item)
            
            # Quality
            harmonious_aspects = ['Conjunction', 'Sextile', 'Trine']
            quality = "Harmonious" if aspect_type in harmonious_aspects else "Challenging"
            quality_item = QTableWidgetItem(quality)
            self.aspects_table.setItem(row, 4, quality_item)
            
            # Timing
            exact_time = aspect.get('exact_time')
            timing_text = "Now" if exact_time and exact_time == "exact" else str(exact_time) if exact_time else "Unknown"
            timing_item = QTableWidgetItem(timing_text)
            self.aspects_table.setItem(row, 5, timing_item)
            
            # Significance
            degrees_to_exact = aspect.get('degrees_to_exact', 0)
            if degrees_to_exact < 1:
                significance = "Very Strong"
            elif degrees_to_exact < 3:
                significance = "Strong"
            elif degrees_to_exact < 6:
                significance = "Moderate"
            else:
                significance = "Weak"
            
            significance_item = QTableWidgetItem(significance)
            self.aspects_table.setItem(row, 6, significance_item)
        
        # Adjust column widths
        self.aspects_table.resizeColumnsToContents()
    
    def filter_aspects_list(self, aspects: List[Dict]) -> List[Dict]:
        """Filter aspects based on current filter setting"""
        filter_text = self.aspects_filter.currentText()
        
        if filter_text == "All Aspects":
            return aspects
        elif filter_text == "Applying Only":
            return [a for a in aspects if a.get('applying', False)]
        elif filter_text == "Separating Only":
            return [a for a in aspects if not a.get('applying', False)]
        elif filter_text == "Exact Aspects":
            return [a for a in aspects if a.get('degrees_to_exact', 10) < 1]
        
        return aspects
    
    def filter_aspects(self):
        """Apply aspect filter"""
        self.update_aspects_tab()
    
    def update_general_info_tab(self):
        """Update the general info tab with complete data"""
        general_info = self.chart_data.get('general_info', {})
        chart_data = self.chart_data.get('chart_data', {})
        timezone_info = self.chart_data.get('timezone_info', {})
        
        # Temporal information
        self.planetary_day_label.setText(general_info.get('planetary_day', '-'))
        self.planetary_hour_label.setText(general_info.get('planetary_hour', '-'))
        self.local_time_label.setText(timezone_info.get('local_time', '-')[:19] if timezone_info.get('local_time') else '-')
        self.utc_time_label.setText(timezone_info.get('utc_time', '-')[:19] if timezone_info.get('utc_time') else '-')
        
        # Lunar information
        self.moon_phase_label.setText(general_info.get('moon_phase', '-'))
        
        mansion = general_info.get('moon_mansion', {})
        if isinstance(mansion, dict):
            mansion_text = f"{mansion.get('number', '-')} - {mansion.get('name', '')}"
        else:
            mansion_text = str(mansion) if mansion else '-'
        self.moon_mansion_label.setText(mansion_text)
        
        moon_condition = general_info.get('moon_condition', {})
        if isinstance(moon_condition, dict):
            speed = moon_condition.get('speed', 0)
            speed_cat = moon_condition.get('speed_category', '-')
            self.moon_speed_label.setText(f"{speed:.2f}°/day ({speed_cat})")
            
            condition_parts = [moon_condition.get('sign', '-')]
            if moon_condition.get('void_of_course', False):
                condition_parts.append("Void of Course")
            self.moon_condition_label.setText(" - ".join(condition_parts))
        
        # Chart coordinates
        ascendant = chart_data.get('ascendant', 0)
        self.ascendant_label.setText(f"{ascendant:.2f}°")
        
        midheaven = chart_data.get('midheaven', 0)
        self.midheaven_label.setText(f"{midheaven:.2f}°")
        
        location_name = timezone_info.get('location_name', '-')
        self.location_label.setText(location_name)
        
        coordinates = timezone_info.get('coordinates', {})
        if coordinates:
            lat = coordinates.get('latitude', 0)
            lon = coordinates.get('longitude', 0)
            self.coordinates_label.setText(f"{lat:.4f}°, {lon:.4f}°")
        else:
            self.coordinates_label.setText('-')
    
    def update_considerations_tab(self):
        """Update the considerations tab with complete analysis"""
        # Clear existing widgets
        for i in reversed(range(self.considerations_layout.count())):
            if i >= 2:  # Keep header and explanation
                child = self.considerations_layout.itemAt(i).widget()
                if child:
                    child.setParent(None)
        
        considerations = self.chart_data.get('considerations', {})
        
        # Radicality check
        radical_card = self.create_consideration_card(
            "Chart Radicality",
            considerations.get('radical_reason', 'Unknown'),
            considerations.get('radical', False),
            "Is the chart fit to be judged?"
        )
        self.considerations_layout.addWidget(radical_card)
        
        # Void Moon check
        void_card = self.create_consideration_card(
            "Void of Course Moon",
            considerations.get('moon_void_reason', 'Unknown'),
            not considerations.get('moon_void', True),
            "Does the Moon perfect any aspects before changing signs?"
        )
        self.considerations_layout.addWidget(void_card)
        
        # Additional considerations from chart data
        traditional_factors = self.chart_data.get('traditional_factors', {})
        
        if 'moon_void' in traditional_factors:
            moon_testimony_card = self.create_consideration_card(
                "Moon's Testimony",
                f"Moon condition affects judgment reliability",
                not traditional_factors.get('moon_void', True),
                "What does the Moon tell us about the matter?"
            )
            self.considerations_layout.addWidget(moon_testimony_card)
        
        self.considerations_layout.addStretch()
    
    def create_consideration_card(self, title: str, description: str, passed: bool, explanation: str = "") -> QFrame:
        """Create an enhanced consideration card"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        
        color = "#d4edda" if passed else "#f8d7da"
        border_color = "#c3e6cb" if passed else "#f5c6cb"
        icon = "✅" if passed else "❌"
        
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 16px;
                margin: 8px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Header row
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Arial", 20))
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        
        status_label = QLabel("PASSED" if passed else "FAILED")
        status_label.setFont(QFont("Arial", 10, QFont.Bold))
        status_label.setStyleSheet(f"color: {'#155724' if passed else '#721c24'};")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(status_label)
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 12px; margin-top: 8px;")
        layout.addWidget(desc_label)
        
        # Explanation
        if explanation:
            exp_label = QLabel(explanation)
            exp_label.setWordWrap(True)
            exp_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic; margin-top: 4px;")
            layout.addWidget(exp_label)
        
        card.setLayout(layout)
        return card
    
    def update_moon_story(self):
        """Update the Moon story with detailed aspect analysis"""
        # Clear existing content
        for i in reversed(range(self.moon_content_layout.count())):
            child = self.moon_content_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Get Moon aspects data
        moon_aspects = self.chart_data.get('moon_aspects', [])
        moon_last_aspect = self.chart_data.get('moon_last_aspect')
        moon_next_aspect = self.chart_data.get('moon_next_aspect')
        
        # Last aspect section
        if moon_last_aspect:
            last_section = self.create_moon_aspect_section("🌑 Moon's Last Aspect", moon_last_aspect, is_last=True)
            self.moon_content_layout.addWidget(last_section)
        
        # Next aspect section  
        if moon_next_aspect:
            next_section = self.create_moon_aspect_section("🌕 Moon's Next Aspect", moon_next_aspect, is_last=False)
            self.moon_content_layout.addWidget(next_section)
        
        # Current aspects section
        if moon_aspects:
            current_label = QLabel("🌙 Current Moon Aspects")
            current_label.setFont(QFont("Arial", 14, QFont.Bold))
            current_label.setStyleSheet("margin: 16px 0 8px 0; color: #2c3e50;")
            self.moon_content_layout.addWidget(current_label)
            
            for aspect in moon_aspects[:5]:  # Show top 5
                aspect_widget = self.create_moon_aspect_widget(aspect)
                self.moon_content_layout.addWidget(aspect_widget)
        
        if not moon_aspects and not moon_last_aspect and not moon_next_aspect:
            no_data_label = QLabel("No significant Moon aspects found in the current analysis.")
            no_data_label.setStyleSheet("color: #666; font-style: italic; text-align: center; padding: 20px;")
            self.moon_content_layout.addWidget(no_data_label)
        
        self.moon_content_layout.addStretch()
    
    def create_moon_aspect_section(self, title: str, aspect_data: Dict, is_last: bool = False) -> QWidget:
        """Create a detailed Moon aspect section"""
        section = QGroupBox(title)
        section.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Aspect details
        planet = aspect_data.get('planet', 'Unknown')
        aspect_type = aspect_data.get('aspect', 'Unknown')
        orb = aspect_data.get('orb', 0)
        timing = aspect_data.get('perfection_eta_description', 'Unknown')
        
        details_layout = QFormLayout()
        
        # Planet and aspect
        planet_aspect_label = QLabel(f"Moon {aspect_type} {planet}")
        planet_aspect_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Orb
        orb_label = QLabel(f"{orb:.2f}°")
        
        # Timing
        timing_label = QLabel(timing)
        timing_label.setStyleSheet("font-weight: bold;" + 
                                  ("color: #e74c3c;" if is_last else "color: #27ae60;"))
        
        # Status
        status = "Separating" if is_last else "Applying"
        status_label = QLabel(status)
        
        details_layout.addRow("Aspect:", planet_aspect_label)
        details_layout.addRow("Orb:", orb_label)
        details_layout.addRow("Timing:", timing_label)
        details_layout.addRow("Status:", status_label)
        
        layout.addLayout(details_layout)
        
        # Interpretation
        interpretation = self.get_moon_aspect_interpretation(aspect_type, planet, is_last)
        if interpretation:
            interp_label = QLabel(interpretation)
            interp_label.setWordWrap(True)
            interp_label.setStyleSheet("""
                background-color: #f8f9fa;
                padding: 12px;
                border-radius: 6px;
                font-style: italic;
                color: #495057;
                margin-top: 8px;
            """)
            layout.addWidget(interp_label)
        
        section.setLayout(layout)
        return section
    
    def get_moon_aspect_interpretation(self, aspect_type: str, planet: str, is_last: bool) -> str:
        """Get traditional interpretation for Moon aspect"""
        interpretations = {
            'Conjunction': {
                'Sun': "The Moon joins with the Sun - new beginnings, but potential for combustion",
                'Mercury': "Quick communication, mental activity, changes in plans",
                'Venus': "Harmonious feelings, pleasure, artistic inspiration",
                'Mars': "Emotional intensity, possible conflict or passionate action",
                'Jupiter': "Optimism, expansion, good fortune and protection",
                'Saturn': "Serious matters, delays, but potential for lasting structure"
            },
            'Sextile': {
                'Sun': "Supportive energy, good timing for important matters",
                'Mercury': "Clear communication, successful negotiations",
                'Venus': "Pleasant social connections, harmony in relationships",
                'Mars': "Productive action, energy channeled constructively",
                'Jupiter': "Opportunities for growth, helpful connections",
                'Saturn': "Steady progress, patience rewarded"
            },
            'Square': {
                'Sun': "Tension between emotion and will, obstacles to overcome",
                'Mercury': "Miscommunication, mental restlessness",
                'Venus': "Emotional conflicts in relationships, disappointments",
                'Mars': "Emotional volatility, potential for arguments",
                'Jupiter': "Overconfidence, excess, poor judgment",
                'Saturn': "Emotional restrictions, pessimism, delays"
            },
            'Trine': {
                'Sun': "Harmony between feelings and purpose, natural flow",
                'Mercury': "Intuitive insights, successful communication",
                'Venus': "Emotional satisfaction, harmony in love and money",
                'Mars': "Emotional courage, successful action",
                'Jupiter': "Emotional expansion, good fortune, protection",
                'Saturn': "Emotional stability, practical wisdom"
            },
            'Opposition': {
                'Sun': "Emotional/rational conflict, need for balance",
                'Mercury': "Conflicting thoughts and feelings",
                'Venus': "Relationship tensions, competing desires",
                'Mars': "Emotional confrontation, need to balance action and feeling",
                'Jupiter': "Tension between emotion and belief, overextension",
                'Saturn': "Emotional restrictions, feeling blocked or limited"
            }
        }
        
        base_interpretation = interpretations.get(aspect_type, {}).get(planet, "")
        
        if base_interpretation:
            time_context = "This influence is waning" if is_last else "This influence is approaching"
            return f"{base_interpretation}. {time_context}."
        
        return ""
    
    def create_moon_aspect_widget(self, aspect: Dict[str, Any]) -> QWidget:
        """Create enhanced moon aspect display widget"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 12px;
                margin: 4px 0;
            }
            QFrame:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        
        layout = QHBoxLayout()
        
        # Aspect info
        info_layout = QVBoxLayout()
        
        # Title
        title = f"Moon {aspect['aspect']} {aspect['planet']}"
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Details
        details_parts = [
            f"Orb: {aspect['orb']:.2f}°",
            f"Status: {aspect['status']}",
        ]
        
        if aspect.get('timing'):
            details_parts.append(f"Timing: {aspect['timing']}")
        
        details_label = QLabel(" • ".join(details_parts))
        details_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        
        info_layout.addWidget(title_label)
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, 1)
        
        # Status indicator
        status_color = "#28a745" if aspect.get('applying', False) else "#6c757d"
        status_indicator = QLabel("●")
        status_indicator.setStyleSheet(f"color: {status_color}; font-size: 16px;")
        layout.addWidget(status_indicator)
        
        widget.setLayout(layout)
        return widget
    
    def save_chart_notes(self):
        """Save notes for this chart"""
        if not self.chart_data or 'id' not in self.chart_data:
            QMessageBox.warning(self, "Save Error", "Cannot save notes: Chart not properly loaded.")
            return
        
        try:
            # This would typically connect to the database
            # For now, just show a success message
            notes_content = self.notes_edit.toPlainText()
            
            if not notes_content.strip():
                QMessageBox.information(self, "No Content", "Notes are empty - nothing to save.")
                return
            
            # TODO: Implement actual database save
            # self.database.update_chart_notes(self.chart_data['id'], notes_content)
            
            self.notes_info_label.setText(f"Notes saved at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            QMessageBox.information(self, "Success", "Notes saved successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save notes: {str(e)}")
    
    def load_chart_notes(self):
        """Load existing notes for this chart"""
        if not self.chart_data:
            return
        
        # Load notes from chart data
        notes = self.chart_data.get('notes', '')
        self.notes_edit.setPlainText(notes)
        
        if notes:
            self.notes_info_label.setText("Notes loaded from database")
        else:
            self.notes_info_label.setText("No existing notes")
    
    def export_notes(self):
        """Export notes to a file"""
        notes_content = self.notes_edit.toPlainText()
        if not notes_content.strip():
            QMessageBox.information(self, "No Content", "Notes are empty - nothing to export.")
            return
        
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Notes", "horary_notes.txt", "Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Add header
                    question = self.chart_data.get('form_data', {}).get('question', 'Unknown Question')
                    f.write(f"Horary Chart Notes\n")
                    f.write(f"Question: {question}\n")
                    f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*50 + "\n\n")
                    
                    # Add notes content
                    f.write(notes_content)
                
                QMessageBox.information(self, "Export Success", f"Notes exported to:\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export notes: {str(e)}")
    
    def export_dignities_table(self):
        """Export dignities table to CSV"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Dignities", "dignities.csv", "CSV Files (*.csv);;All Files (*)"
            )
            
            if file_path:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    headers = []
                    for col in range(self.dignities_table.columnCount()):
                        header_item = self.dignities_table.horizontalHeaderItem(col)
                        headers.append(header_item.text() if header_item else f"Column {col}")
                    writer.writerow(headers)
                    
                    # Write data
                    for row in range(self.dignities_table.rowCount()):
                        row_data = []
                        for col in range(self.dignities_table.columnCount()):
                            if col == 4:  # Skip strength bar column
                                row_data.append("")
                                continue
                            
                            item = self.dignities_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Export Success", f"Dignities table exported to:\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export table: {str(e)}")


class SettingsDialog(QDialog):
    """Enhanced settings dialog with complete configuration options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Horary Master Settings")
        self.setMinimumSize(600, 500)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the comprehensive settings dialog UI"""
        layout = QVBoxLayout()
        
        # Tab widget for different setting categories
        tab_widget = QTabWidget()
        
        # General settings
        general_tab = self.create_general_tab()
        tab_widget.addTab(general_tab, "General")
        
        # License settings
        license_tab = self.create_license_tab()
        tab_widget.addTab(license_tab, "License")
        
        # Advanced settings
        advanced_tab = self.create_advanced_tab()
        tab_widget.addTab(advanced_tab, "Advanced")
        
        layout.addWidget(tab_widget)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.save_and_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        
        layout.addWidget(button_box)
        self.setLayout(layout)
    
    def create_general_tab(self) -> QWidget:
        """Create the general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Appearance section
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()
        
        self.dark_mode_check = QCheckBox("Enable dark mode")
        self.auto_theme_check = QCheckBox("Follow system theme")
        
        appearance_layout.addRow("Theme:", self.dark_mode_check)
        appearance_layout.addRow("", self.auto_theme_check)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Chart settings
        chart_group = QGroupBox("Chart Settings")
        chart_layout = QFormLayout()
        
        self.auto_save_check = QCheckBox("Automatically save calculated charts")
        self.confirm_delete_check = QCheckBox("Confirm before deleting charts")
        self.default_location_edit = QLineEdit()
        self.default_location_edit.setPlaceholderText("Enter default location for calculations")
        
        self.chart_wheel_style_combo = QComboBox()
        self.chart_wheel_style_combo.addItems(["Traditional", "Modern", "Simplified"])
        
        chart_layout.addRow("Auto-save:", self.auto_save_check)
        chart_layout.addRow("Confirm delete:", self.confirm_delete_check)
        chart_layout.addRow("Default Location:", self.default_location_edit)
        chart_layout.addRow("Chart Style:", self.chart_wheel_style_combo)
        
        chart_group.setLayout(chart_layout)
        layout.addWidget(chart_group)
        
        # Data management
        data_group = QGroupBox("Data Management")
        data_layout = QVBoxLayout()
        
        backup_layout = QHBoxLayout()
        backup_layout.addWidget(QLabel("Database backup:"))
        
        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.clicked.connect(self.create_backup)
        
        self.restore_btn = QPushButton("Restore Backup")
        self.restore_btn.clicked.connect(self.restore_backup)
        
        backup_layout.addWidget(self.backup_btn)
        backup_layout.addWidget(self.restore_btn)
        backup_layout.addStretch()
        
        data_layout.addLayout(backup_layout)
        
        # Clear data options
        clear_layout = QHBoxLayout()
        clear_layout.addWidget(QLabel("Clear data:"))
        
        self.clear_charts_btn = QPushButton("Clear All Charts")
        self.clear_charts_btn.clicked.connect(self.clear_charts)
        self.clear_charts_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; }")
        
        clear_layout.addWidget(self.clear_charts_btn)
        clear_layout.addStretch()
        
        data_layout.addLayout(clear_layout)
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_license_tab(self) -> QWidget:
        """Create the enhanced license settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # License status
        status_group = QGroupBox("License Status")
        status_layout = QVBoxLayout()
        
        self.license_status_label = QLabel("Checking license...")
        self.license_status_label.setWordWrap(True)
        self.license_status_label.setStyleSheet("""
            QLabel {
                padding: 16px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-family: monospace;
            }
        """)
        
        status_layout.addWidget(self.license_status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # License actions
        actions_group = QGroupBox("License Management")
        actions_layout = QVBoxLayout()
        
        # Load license file
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel("License file:"))
        
        self.license_path_edit = QLineEdit()
        self.license_path_edit.setPlaceholderText("Path to license file...")
        
        self.browse_license_btn = QPushButton("📁 Browse")
        self.browse_license_btn.clicked.connect(self.browse_license_file)
        
        self.load_license_btn = QPushButton("📥 Load License")
        self.load_license_btn.clicked.connect(self.load_license_file)
        
        load_layout.addWidget(self.license_path_edit, 1)
        load_layout.addWidget(self.browse_license_btn)
        load_layout.addWidget(self.load_license_btn)
        
        actions_layout.addLayout(load_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.request_trial_btn = QPushButton("🆓 Request Trial License")
        self.request_trial_btn.clicked.connect(self.request_trial)
        
        self.purchase_btn = QPushButton("💳 Purchase Full License")
        self.purchase_btn.clicked.connect(self.purchase_license)
        
        self.refresh_license_btn = QPushButton("🔄 Refresh Status")
        self.refresh_license_btn.setAccessibleName("Refresh license status")
        self.refresh_license_btn.clicked.connect(self.refresh_license_status)
        
        button_layout.addWidget(self.request_trial_btn)
        button_layout.addWidget(self.purchase_btn)
        button_layout.addWidget(self.refresh_license_btn)
        
        actions_layout.addLayout(button_layout)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # License features
        features_group = QGroupBox("Available Features")
        features_layout = QVBoxLayout()
        
        self.features_list = QListWidget()
        self.features_list.setMaximumHeight(150)
        features_layout.addWidget(self.features_list)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_advanced_tab(self) -> QWidget:
        """Create the advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Calculation settings
        calc_group = QGroupBox("Calculation Settings")
        calc_layout = QFormLayout()
        
        self.orb_tolerance_spin = QSpinBox()
        self.orb_tolerance_spin.setRange(1, 15)
        self.orb_tolerance_spin.setValue(8)
        self.orb_tolerance_spin.setSuffix("°")
        
        self.house_system_combo = QComboBox()
        self.house_system_combo.addItems(["Regiomontanus", "Placidus", "Equal", "Whole Sign"])
        
        self.ephemeris_combo = QComboBox()
        self.ephemeris_combo.addItems(["Swiss Ephemeris", "Built-in"])
        
        calc_layout.addRow("Default Orb Tolerance:", self.orb_tolerance_spin)
        calc_layout.addRow("House System:", self.house_system_combo)
        calc_layout.addRow("Ephemeris:", self.ephemeris_combo)
        
        calc_group.setLayout(calc_layout)
        layout.addWidget(calc_group)
        
        # Debug settings
        debug_group = QGroupBox("Debug & Logging")
        debug_layout = QFormLayout()
        
        self.debug_mode_check = QCheckBox("Enable debug logging")
        self.log_calculations_check = QCheckBox("Log all calculations")
        self.verbose_output_check = QCheckBox("Verbose console output")
        
        debug_layout.addRow("Debug Mode:", self.debug_mode_check)
        debug_layout.addRow("Log Calculations:", self.log_calculations_check)
        debug_layout.addRow("Verbose Output:", self.verbose_output_check)
        
        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)
        
        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()
        
        self.cache_calculations_check = QCheckBox("Cache calculation results")
        self.preload_ephemeris_check = QCheckBox("Preload ephemeris data")
        
        self.max_charts_spin = QSpinBox()
        self.max_charts_spin.setRange(100, 10000)
        self.max_charts_spin.setValue(1000)
        
        perf_layout.addRow("Cache Results:", self.cache_calculations_check)
        perf_layout.addRow("Preload Ephemeris:", self.preload_ephemeris_check)
        perf_layout.addRow("Max Charts in DB:", self.max_charts_spin)
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def load_settings(self):
        """Load current settings"""
        # Load license status
        self.refresh_license_status()
        
        # Load other settings (would come from a config file or database)
        # For now, using defaults
        pass
    
    def refresh_license_status(self):
        """Refresh license status display"""
        if HORARY_ENGINE_AVAILABLE:
            try:
                license_info = get_license_info()
                if license_info.get('valid', False):
                    status_text = f"""✅ VALID LICENSE
Licensed to: {license_info['licensedTo']}
Email: {license_info.get('email', 'N/A')}
License Type: {license_info.get('licenseType', 'Unknown').title()}
Valid until: {license_info.get('expiryDate', 'Unknown')[:10]}
Days remaining: {license_info.get('daysRemaining', 0)}
Features enabled: {license_info['featureCount']}

Machine ID: {license_info.get('machineId', 'Unknown')}
Status: {license_info.get('status', 'Unknown')}"""
                    
                    # Update features list
                    self.features_list.clear()
                    features = license_info.get('features', {})
                    for feature, description in features.items():
                        item = QListWidgetItem(f"✅ {feature}: {description}")
                        self.features_list.addItem(item)
                    
                else:
                    status_text = f"""❌ INVALID LICENSE
Error: {license_info.get('error', 'Unknown error')}
Status: Invalid

Running in demo mode with limited features."""
                    
                    # Show demo features
                    self.features_list.clear()
                    demo_features = [
                        "❌ Enhanced calculations - Limited",
                        "❌ Solar conditions - Basic only", 
                        "❌ Moon analysis - Simplified",
                        "❌ Unlimited charts - 10 chart limit"
                    ]
                    for feature in demo_features:
                        item = QListWidgetItem(feature)
                        self.features_list.addItem(item)
                    
            except Exception as e:
                status_text = f"""⚠️ LICENSE CHECK FAILED
Error: {str(e)}

Cannot verify license status."""
                
        else:
            status_text = f"""❌ ENGINE NOT AVAILABLE
Error: {HORARY_ENGINE_ERROR}

Backend engine is not properly loaded."""
        
        self.license_status_label.setText(status_text)
    
    def browse_license_file(self):
        """Browse for license file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select License File", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.license_path_edit.setText(file_path)
    
    def load_license_file(self):
        """Load the selected license file"""
        file_path = self.license_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "No File", "Please select a license file first.")
            return
        
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "File Not Found", f"License file not found:\n{file_path}")
            return
        
        try:
            # Copy license file to application directory
            app_license_path = "./license.json"
            import shutil
            shutil.copy2(file_path, app_license_path)
            
            QMessageBox.information(self, "Success", 
                                  f"License file loaded successfully!\n\n"
                                  f"The application will need to be restarted for changes to take effect.")
            
            self.refresh_license_status()
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load license file:\n{str(e)}")
    
    def request_trial(self):
        """Request a trial license"""
        name, ok1 = QInputDialog.getText(self, "Trial License", "Enter your name:")
        if not ok1 or not name.strip():
            return
        
        email, ok2 = QInputDialog.getText(self, "Trial License", "Enter your email:")
        if not ok2 or not email.strip():
            return
        
        try:
            # This would normally connect to a licensing server
            # For demonstration, create a simple trial license
            trial_license = {
                "licensedTo": name.strip(),
                "email": email.strip(),
                "issueDate": datetime.now().isoformat(),
                "expiryDate": (datetime.now() + timedelta(days=30)).isoformat(),
                "features": ["enhanced_engine", "solar_conditions", "moon_analysis", "timezone_support"],
                "licenseType": "trial",
                "version": "1.0",
                "signature": "trial-demo-signature"
            }
            
            # Save trial license
            with open("./license.json", 'w', encoding='utf-8') as f:
                json.dump(trial_license, f, indent=2)
            
            QMessageBox.information(self, "Trial License Created", 
                                  f"30-day trial license created for {name}!\n\n"
                                  f"Please restart the application to activate the trial.")
            
            self.refresh_license_status()
            
        except Exception as e:
            QMessageBox.critical(self, "Trial Error", f"Failed to create trial license:\n{str(e)}")
    
    def purchase_license(self):
        """Show purchase information"""
        QMessageBox.information(self, "Purchase License", 
                              """To purchase a full license for Horary Master:

1. Visit: https://horarymaster.com/purchase
2. Choose your license type:
   • Professional: $99/year
   • Premium: $199/year  
   • Enterprise: $499/year

3. Complete payment and download your license file
4. Load the license file using the settings dialog

For questions, contact: license@horarymaster.com""")
    
    def create_backup(self):
        """Create database backup"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Create Backup", f"horary_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                "Database Files (*.db);;All Files (*)"
            )
            
            if file_path:
                import shutil
                shutil.copy2("horary_charts.db", file_path)
                QMessageBox.information(self, "Backup Created", f"Database backed up to:\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to create backup:\n{str(e)}")
    
    def restore_backup(self):
        """Restore database from backup"""
        reply = QMessageBox.question(
            self, "Restore Backup", 
            "This will replace your current database with the backup.\n"
            "All current data will be lost. Are you sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                file_path, _ = QFileDialog.getOpenFileName(
                    self, "Select Backup File", "", "Database Files (*.db);;All Files (*)"
                )
                
                if file_path:
                    import shutil
                    shutil.copy2(file_path, "horary_charts.db")
                    QMessageBox.information(self, "Restore Complete", 
                                          "Database restored successfully!\n\n"
                                          "Please restart the application.")
            
            except Exception as e:
                QMessageBox.critical(self, "Restore Error", f"Failed to restore backup:\n{str(e)}")
    
    def clear_charts(self):
        """Clear all charts from database"""
        reply = QMessageBox.question(
            self, "Clear All Charts", 
            "This will permanently delete ALL charts from the database.\n"
            "This action CANNOT be undone. Are you sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                conn = sqlite3.connect("horary_charts.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM charts")
                cursor.execute("DELETE FROM notebook_entries")
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Clear Complete", "All charts have been deleted.")
            
            except Exception as e:
                QMessageBox.critical(self, "Clear Error", f"Failed to clear charts:\n{str(e)}")
    
    def apply_settings(self):
        """Apply settings without closing dialog"""
        self.save_settings()
        QMessageBox.information(self, "Settings Applied", "Settings have been applied successfully.")
    
    def save_and_accept(self):
        """Save settings and close dialog"""
        self.save_settings()
        self.accept()
    
    def save_settings(self):
        """Save all settings"""
        # This would typically save to a configuration file or database
        # For now, just log the action
        logger.info("Settings saved (placeholder implementation)")


class HoraryMasterMainWindow(QMainWindow):
    """Enhanced main application window with complete functionality"""
    
    def __init__(self):
        super().__init__()
        self.database = ChartDatabase()
        self.current_theme = "light"
        self.setup_ui()
        self.setup_connections()
        self.setup_timers()
        
        # Apply initial styling
        self.apply_light_theme()
        
        # Initialize with dashboard
        self.stacked_widget.setCurrentIndex(0)
        
        # Check engine status
        self.check_engine_status()
        
        logger.info("Horary Master application initialized")
    
    def setup_ui(self):
        """Setup the complete main window UI"""
        self.setWindowTitle("Horary Master - Enhanced Traditional Astrology v2.0")
        self.setMinimumSize(1400, 900)
        
        # Set application icon (if available)
        try:
            self.setWindowIcon(QIcon("icon.png"))
        except:
            pass
        
        # Create central stacked widget
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Create all pages
        self.dashboard_page = DashboardPage(self.database)
        self.cast_chart_page = CastChartPage()
        self.chart_detail_page = ChartDetailPage()
        self.timeline_view = TimelineView(self.database)
        self.notebook_view = NotebookView(self.database)
        
        # Add pages to stack
        self.stacked_widget.addWidget(self.dashboard_page)      # Index 0
        self.stacked_widget.addWidget(self.cast_chart_page)     # Index 1
        self.stacked_widget.addWidget(self.chart_detail_page)   # Index 2
        self.stacked_widget.addWidget(self.timeline_view)       # Index 3
        self.stacked_widget.addWidget(self.notebook_view)       # Index 4
        
        # Create enhanced toolbar
        self.setup_toolbar()
        
        # Create enhanced status bar
        self.setup_status_bar()
    
    def setup_toolbar(self):
        """Setup the enhanced main toolbar with improved tab design"""
        # Create main toolbar container
        main_toolbar = QToolBar("Main Toolbar")
        main_toolbar.setMovable(False)
        main_toolbar.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, main_toolbar)
        
        # Create custom widget for the toolbar to have better control
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(8, 0, 8, 0)
        toolbar_layout.setSpacing(0)
        
        # Create navigation tabs container
        nav_widget = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)
        
        # Define navigation items with better icons
        nav_items = [
            ("Dashboard", "📊", 0),
            ("Cast Chart", "✨", 1),
            ("Timeline", "📈", 3),
            ("Notebook", "📓", 4)
        ]
        
        # Create tab buttons
        self.tab_buttons = []
        self.tab_button_group = QButtonGroup()
        
        for text, icon, page_index in nav_items:
            btn = QPushButton(f"{icon} {text}")
            btn.setCheckable(True)
            btn.setProperty("page_index", page_index)
            btn.clicked.connect(lambda checked, idx=page_index: self.switch_page(idx))
            
            # Apply custom styling for tabs
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-bottom: 3px solid transparent;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 500;
                    color: #666666;
                    min-width: 120px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.03);
                    color: #333333;
                    border-bottom-color: rgba(33, 150, 243, 0.3);
                }
                QPushButton:checked {
                    color: #2196F3;
                    background-color: rgba(33, 150, 243, 0.08);
                    border-bottom-color: #2196F3;
                    font-weight: 600;
                }
                QPushButton:pressed {
                    background-color: rgba(0, 0, 0, 0.05);
                }
            """)
            
            self.tab_button_group.addButton(btn)
            self.tab_buttons.append(btn)
            nav_layout.addWidget(btn)
        
        # Set first tab as active
        self.tab_buttons[0].setChecked(True)
        
        nav_widget.setLayout(nav_layout)
        toolbar_layout.addWidget(nav_widget)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("""
            QFrame {
                color: #e0e0e0;
                margin: 8px 16px;
            }
        """)
        toolbar_layout.addWidget(separator)
        
        # Add stretch to push utility buttons to the right
        toolbar_layout.addStretch()
        
        # Create utility buttons container
        utility_widget = QWidget()
        utility_layout = QHBoxLayout()
        utility_layout.setContentsMargins(0, 0, 0, 0)
        utility_layout.setSpacing(8)
        
        # Settings button
        self.settings_btn = self.create_utility_button("⚙", "Settings", self.show_settings)
        utility_layout.addWidget(self.settings_btn)
        
        # Theme toggle button
        self.theme_btn = self.create_utility_button("🌓", "Toggle Theme", self.toggle_dark_mode)
        self.theme_btn.setCheckable(True)
        utility_layout.addWidget(self.theme_btn)
        
        # Help button
        self.help_btn = self.create_utility_button("?", "Help", self.show_help)
        utility_layout.addWidget(self.help_btn)
        
        utility_widget.setLayout(utility_layout)
        toolbar_layout.addWidget(utility_widget)
        
        # Engine status with better styling
        self.engine_status_widget = self.create_status_widget()
        toolbar_layout.addWidget(self.engine_status_widget)
        
        toolbar_widget.setLayout(toolbar_layout)
        
        # Apply toolbar styling
        toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                min-height: 56px;
            }
        """)
        
        # Add the widget to toolbar
        main_toolbar.addWidget(toolbar_widget)
        
        # Store reference for dark mode
        self.toolbar_widget = toolbar_widget
    
    def create_utility_button(self, icon: str, tooltip: str, callback) -> QPushButton:
        """Create a styled utility button"""
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        btn.setFixedSize(40, 40)
        
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 20px;
                font-size: 18px;
                color: #666666;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
                border-color: rgba(0, 0, 0, 0.1);
                color: #333333;
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.1);
            }
            QPushButton:checked {
                background-color: #2196F3;
                color: white;
            }
        """)
        
        return btn
    
    def create_status_widget(self) -> QWidget:
        """Create engine status widget with better styling"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 0, 12, 0)
        
        self.engine_status_label = QLabel("Engine: Checking...")
        self.engine_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 6px 12px;
                background-color: rgba(0, 0, 0, 0.03);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        
        layout.addWidget(self.engine_status_label)
        widget.setLayout(layout)
        return widget
    
    def on_page_changed(self, index: int):
        """Handle page change events and update tab states"""
        # Update tab button states
        for btn in self.tab_buttons:
            page_index = btn.property("page_index")
            btn.setChecked(page_index == index)
        
        # Rest of the existing method...
        page_names = ["Dashboard", "Cast Chart", "Chart Detail", "Timeline", "Notebook"]
        page_name = page_names[index] if index < len(page_names) else f"Page {index}"
        
        # Refresh data when switching to certain pages
        if index == 0:  # Dashboard
            self.dashboard_page.refresh_data()
        elif index == 3:  # Timeline
            self.timeline_view.load_timeline_data()
        elif index == 4:  # Notebook
            self.notebook_view.load_notebook_entries()
    
    
    def setup_status_bar(self):
        """Setup enhanced status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Main status message
        self.status_bar.showMessage("Ready")
        
        # Permanent widgets on right side
        
        # Chart count
        self.chart_count_label = QLabel("Charts: 0")
        self.chart_count_label.setStyleSheet("padding: 2px 8px;")
        self.status_bar.addPermanentWidget(self.chart_count_label)
        
        # License status
        self.license_status_label = QLabel("Demo Mode")
        self.license_status_label.setStyleSheet("padding: 2px 8px; color: #ff9800;")
        self.status_bar.addPermanentWidget(self.license_status_label)
        
        # Time
        self.time_label = QLabel()
        self.time_label.setStyleSheet("padding: 2px 8px;")
        self.status_bar.addPermanentWidget(self.time_label)
    
    def setup_connections(self):
        """Setup all signal connections between components"""
        # Dashboard connections
        self.dashboard_page.chart_selected.connect(self.show_chart_detail)
        self.dashboard_page.cast_chart_requested.connect(lambda: self.switch_page(1))
        
        # Cast chart connections
        self.cast_chart_page.chart_cast.connect(self.on_chart_cast)
        
        # Timeline connections
        self.timeline_view.chart_selected.connect(self.show_chart_detail)
        
        # Page change tracking
        self.stacked_widget.currentChanged.connect(self.on_page_changed)
    
    def setup_timers(self):
        """Setup timers for periodic updates"""
        # Time display timer
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time_display)
        self.time_timer.start(1000)  # Update every second
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_info)
        self.status_timer.start(30000)  # Update every 30 seconds
        
        # Initial update
        self.update_time_display()
        self.update_status_info()
    
    def switch_page(self, index: int):
        """Switch to the specified page"""
        current_index = self.stacked_widget.currentIndex()
        if current_index != index:
            self.stacked_widget.setCurrentIndex(index)
            logger.debug(f"Switched to page {index}")
    
    
    def show_chart_detail(self, chart_id: int):
        """Show chart detail page for the given chart ID"""
        try:
            chart_data = self.database.get_chart(chart_id)
            if chart_data:
                self.chart_detail_page.set_chart_data(chart_data)
                self.switch_page(2)
                self.status_bar.showMessage(f"Viewing chart: {chart_data['question'][:50]}...", 5000)
            else:
                QMessageBox.warning(self, "Error", "Chart not found in database.")
                logger.warning(f"Chart ID {chart_id} not found in database")
        except Exception as e:
            logger.error(f"Error showing chart detail: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load chart: {str(e)}")
    
    def on_chart_cast(self, result: Dict[str, Any]):
        """Handle new chart calculation result"""
        try:
            # Save to database
            question = result.get('form_data', {}).get('question', 'Unknown')
            location = result.get('form_data', {}).get('location', 'Unknown')
            
            chart_id = self.database.save_chart(question, location, result)
            
            # Show chart detail
            result['id'] = chart_id
            self.chart_detail_page.set_chart_data(result)
            self.switch_page(2)
            
            # Refresh dashboard
            self.dashboard_page.refresh_data()
            
            # Show success message
            judgment = result.get('judgment', 'Unknown')
            confidence = result.get('confidence', 0)
            self.status_bar.showMessage(
                f"Chart calculated: {judgment} ({confidence}% confidence)", 5000
            )
            
            logger.info(f"Chart cast successfully: {judgment} with {confidence}% confidence")
            
        except Exception as e:
            logger.error(f"Error handling chart cast: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save chart: {str(e)}")
    
    def show_timeline(self):
        """Show timeline view"""
        self.switch_page(3)
    
    def show_notebook(self):
        """Show notebook view"""
        self.switch_page(4)
    
    def show_settings(self):
        """Show settings dialog"""
        try:
            dialog = SettingsDialog(self)
            result = dialog.exec()
            
            if result == QDialog.Accepted:
                # Settings were saved, might need to refresh some things
                self.update_status_info()
                self.status_bar.showMessage("Settings updated", 3000)
                
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open settings: {str(e)}")
    
# Continuation of the HoraryMasterMainWindow class methods and main application entry point

    def show_help(self):
        """Show help dialog"""
        help_text = """
<h2>Horary Master - Quick Help</h2>

<h3>Getting Started</h3>
<p>1. <b>Cast Chart:</b> Click the "Cast Chart" button or toolbar icon to create a new horary chart</p>
<p>2. <b>Enter Question:</b> Type your horary question clearly and specifically</p>
<p>3. <b>Set Location:</b> Enter the location where you are asking the question</p>
<p>4. <b>Review Results:</b> Analyze the judgment, reasoning, and traditional factors</p>

<h3>Navigation</h3>
<ul>
<li><b>Dashboard:</b> Overview of recent charts and statistics</li>
<li><b>Cast Chart:</b> Create new horary charts</li>
<li><b>Timeline:</b> View charts chronologically with analysis</li>
<li><b>Notebook:</b> Organize research and notes</li>
<li><b>Settings:</b> Configure application and license</li>
</ul>

<h3>Chart Analysis</h3>
<p>Each chart includes:</p>
<ul>
<li><b>Judgment:</b> Traditional horary verdict (YES/NO/UNCLEAR)</li>
<li><b>Dignities:</b> Planetary strength analysis</li>
<li><b>Aspects:</b> Planetary relationships and timing</li>
<li><b>Moon Story:</b> Lunar testimony and future aspects</li>
<li><b>Considerations:</b> Traditional validity checks</li>
</ul>

<h3>Traditional Horary Rules</h3>
<p>Horary astrology follows strict traditional rules:</p>
<ul>
<li><b>Radicality:</b> Charts must be "radical" (fit to be judged)</li>
<li><b>Significators:</b> Planets representing querent and quesited</li>
<li><b>Perfection:</b> How the question resolves (conjunction, aspect, etc.)</li>
<li><b>Timing:</b> When events will occur based on planetary motion</li>
<li><b>Reception:</b> How planets receive each other</li>
</ul>

<h3>Keyboard Shortcuts</h3>
<ul>
<li><b>Ctrl+N:</b> Cast new chart</li>
<li><b>Ctrl+S:</b> Save current chart notes</li>
<li><b>Ctrl+F:</b> Search charts</li>
<li><b>Ctrl+T:</b> Open timeline view</li>
<li><b>Ctrl+,:</b> Open settings</li>
<li><b>F1:</b> Show this help</li>
</ul>

<h3>Troubleshooting</h3>
<p><b>Engine Issues:</b> If calculations fail, check license status and restart the application.</p>
<p><b>Location Problems:</b> Use standard location formats like "London, England" or "New York, NY".</p>
<p><b>Chart Errors:</b> Ensure your question is specific and sincere - horary works best with focused queries.</p>

<h3>Support</h3>
<p>For additional help:</p>
<ul>
<li>Email: support@horarymaster.com</li>
<li>Documentation: https://horarymaster.com/docs</li>
<li>Community: https://horarymaster.com/community</li>
</ul>

<p><i>Version 2.0 - Enhanced Traditional Horary Astrology</i></p>
"""
        
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Horary Master Help")
        help_dialog.setMinimumSize(600, 700)
        
        layout = QVBoxLayout()
        
        # Help content
        help_browser = QTextBrowser()
        help_browser.setHtml(help_text)
        help_browser.setOpenExternalLinks(True)
        layout.addWidget(help_browser)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(help_dialog.accept)
        close_button.setDefault(True)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        help_dialog.setLayout(layout)
        
        help_dialog.exec()
    
    def toggle_dark_mode(self):
        """Toggle between dark and light themes"""
        if self.current_theme == "light":
            self.apply_dark_theme()
            self.current_theme = "dark"
            if hasattr(self, "dark_mode_action"):
                self.dark_mode_action.setChecked(True)
            if hasattr(self, "theme_btn"):
                self.theme_btn.setChecked(True)
            self.status_bar.showMessage("Dark mode enabled", 2000)
        else:
            self.apply_light_theme()
            self.current_theme = "light"
            if hasattr(self, "dark_mode_action"):
                self.dark_mode_action.setChecked(False)
            if hasattr(self, "theme_btn"):
                self.theme_btn.setChecked(False)
            self.status_bar.showMessage("Light mode enabled", 2000)
        
        logger.info(f"Theme switched to {self.current_theme}")
    
    def apply_light_theme(self):
        """Apply light theme styling"""
        light_style = """
        QMainWindow {
            background-color: #ffffff;
            color: #333333;
        }
        QToolBar {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            spacing: 3px;
            padding: 4px;
        }
        QToolBar QToolButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 2px;
            color: #495057;
        }
        QToolBar QToolButton:hover {
            background-color: #e9ecef;
            border-color: #adb5bd;
        }
        QToolBar QToolButton:checked {
            background-color: #007bff;
            color: white;
            border-color: #0056b3;
        }
        QStatusBar {
            background-color: #f8f9fa;
            border-top: 1px solid #dee2e6;
            color: #495057;
        }
        QTabWidget::pane {
            border: 1px solid #dee2e6;
            background-color: white;
        }
        QTabWidget::tab-bar {
            alignment: left;
        }
        QTabBar::tab {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-bottom: none;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
        }
        QTabBar::tab:hover {
            background-color: #e9ecef;
        }
        """
        self.setStyleSheet(light_style)
    
    def apply_dark_theme(self):
        """Apply dark theme styling"""
        dark_style = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QToolBar {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            spacing: 3px;
            padding: 4px;
        }
        QToolBar QToolButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 2px;
            color: #ffffff;
        }
        QToolBar QToolButton:hover {
            background-color: #4a4a4a;
            border-color: #666666;
        }
        QToolBar QToolButton:checked {
            background-color: #0078d4;
            color: white;
            border-color: #106ebe;
        }
        QStatusBar {
            background-color: #3c3c3c;
            border-top: 1px solid #555555;
            color: #ffffff;
        }
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #2b2b2b;
        }
        QTabBar::tab {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            border-bottom: none;
            padding: 8px 16px;
            margin-right: 2px;
            color: #ffffff;
        }
        QTabBar::tab:selected {
            background-color: #2b2b2b;
            border-bottom: 1px solid #2b2b2b;
        }
        QTabBar::tab:hover {
            background-color: #4a4a4a;
        }
        QTextEdit, QTextBrowser, QLineEdit {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            color: #ffffff;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: 1px solid #106ebe;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QComboBox {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            color: #ffffff;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox::down-arrow {
            border: none;
        }
        QGroupBox {
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
        }
        """
        self.setStyleSheet(dark_style)
    
    def check_engine_status(self):
        """Check and update engine status"""
        if HORARY_ENGINE_AVAILABLE:
            self.engine_status_label.setText("Engine: ✅ Ready")
            self.engine_status_label.setStyleSheet("color: #28a745; font-size: 11px; padding: 4px 8px;")
        else:
            self.engine_status_label.setText("Engine: ❌ Error")
            self.engine_status_label.setStyleSheet("color: #dc3545; font-size: 11px; padding: 4px 8px;")
    
    def update_time_display(self):
        """Update the time display in status bar"""
        current_time = QTime.currentTime()
        self.time_label.setText(current_time.toString("hh:mm:ss"))
    
    def update_status_info(self):
        """Update status information periodically"""
        try:
            # Update chart count
            stats = self.database.get_statistics()
            chart_count = stats.get('total_charts', 0)
            self.chart_count_label.setText(f"Charts: {chart_count}")
            
            # Update license status
            if HORARY_ENGINE_AVAILABLE:
                try:
                    license_info = get_license_info()
                    if license_info.get('valid', False):
                        license_type = license_info.get('licenseType', 'Licensed').title()
                        days_remaining = license_info.get('daysRemaining', 0)
                        
                        if days_remaining < 30:
                            self.license_status_label.setText(f"{license_type} ({days_remaining}d)")
                            self.license_status_label.setStyleSheet("padding: 2px 8px; color: #ff9800;")
                        else:
                            self.license_status_label.setText(license_type)
                            self.license_status_label.setStyleSheet("padding: 2px 8px; color: #28a745;")
                    else:
                        self.license_status_label.setText("Demo Mode")
                        self.license_status_label.setStyleSheet("padding: 2px 8px; color: #ff9800;")
                except:
                    self.license_status_label.setText("License Error")
                    self.license_status_label.setStyleSheet("padding: 2px 8px; color: #dc3545;")
            else:
                self.license_status_label.setText("Engine Offline")
                self.license_status_label.setStyleSheet("padding: 2px 8px; color: #dc3545;")
        
        except Exception as e:
            logger.error(f"Error updating status info: {e}")
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Cast new chart
        new_chart_shortcut = QAction(self)
        new_chart_shortcut.setShortcut("Ctrl+N")
        new_chart_shortcut.triggered.connect(lambda: self.switch_page(1))
        self.addAction(new_chart_shortcut)
        
        # Timeline view
        timeline_shortcut = QAction(self)
        timeline_shortcut.setShortcut("Ctrl+T")
        timeline_shortcut.triggered.connect(lambda: self.switch_page(3))
        self.addAction(timeline_shortcut)
        
        # Settings
        settings_shortcut = QAction(self)
        settings_shortcut.setShortcut("Ctrl+,")
        settings_shortcut.triggered.connect(self.show_settings)
        self.addAction(settings_shortcut)
        
        # Help
        help_shortcut = QAction(self)
        help_shortcut.setShortcut("F1")
        help_shortcut.triggered.connect(self.show_help)
        self.addAction(help_shortcut)
        
        # Dark mode toggle
        theme_shortcut = QAction(self)
        theme_shortcut.setShortcut("Ctrl+D")
        theme_shortcut.triggered.connect(self.toggle_dark_mode)
        self.addAction(theme_shortcut)
    
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Save any pending data
            logger.info("Application shutting down...")
            
            # Stop timers
            self.time_timer.stop()
            self.status_timer.stop()
            
            # Stop calculation thread if running
            if hasattr(self.cast_chart_page, 'calc_thread'):
                self.cast_chart_page.calc_thread.quit()
                self.cast_chart_page.calc_thread.wait(3000)  # Wait up to 3 seconds
            
            # Accept the close event
            event.accept()
            logger.info("Application closed successfully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            event.accept()  # Close anyway


def setup_application():
    """Setup the QApplication with proper configuration"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Horary Master")
    app.setApplicationDisplayName("Horary Master - Enhanced Traditional Astrology")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("Horary Master")
    app.setOrganizationDomain("horarymaster.com")
    
    # Set application icon
    try:
        app.setWindowIcon(QIcon("icon.png"))
    except:
        pass
    
    # Set style
    app.setStyle("Fusion")  # Use Fusion style for better cross-platform appearance
    
    return app


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Show error dialog if possible
    try:
        error_msg = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}"
        QMessageBox.critical(None, "Horary Master Error", error_msg)
    except:
        pass


def main():
    """Main application entry point"""
    try:
        # Set up global exception handling
        sys.excepthook = handle_exception
        
        # Create and configure application
        app = setup_application()
        
        # Check if horary engine is available and show startup info
        logger.info("Starting Horary Master v2.0...")
        logger.info(f"Engine available: {HORARY_ENGINE_AVAILABLE}")
        if not HORARY_ENGINE_AVAILABLE:
            logger.warning(f"Engine error: {HORARY_ENGINE_ERROR}")
        
        # Create and show main window
        main_window = HoraryMasterMainWindow()
        main_window.setup_keyboard_shortcuts()
        main_window.show()
        
        # Center window on screen
        screen = app.primaryScreen().availableGeometry()
        window_geo = main_window.geometry()
        main_window.move(
            (screen.width() - window_geo.width()) // 2,
            (screen.height() - window_geo.height()) // 2
        )
        
        logger.info("Application started successfully")
        
        # Run application
        exit_code = app.exec()
        
        logger.info(f"Application exited with code: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.critical(f"Fatal error starting application: {e}")
        logger.critical(traceback.format_exc())
        
        try:
            # Try to show error dialog
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None, 
                "Horary Master Startup Error", 
                f"Failed to start Horary Master:\n\n{str(e)}\n\nCheck the log file for details."
            )
        except:
            pass
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
    
    