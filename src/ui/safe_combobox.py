"""
SafeComboBox — Custom QComboBox that prevents dropdown from covering title bar.

This widget ensures the dropdown popup always appears below the combo box,
never extending upward to cover the application title bar.
"""

from PyQt6.QtWidgets import QComboBox, QListView, QStyledItemDelegate
from PyQt6.QtCore import Qt, QPoint, QEvent, QTimer


class SafeComboBox(QComboBox):
    """QComboBox that ensures dropdown doesn't cover the title bar."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create custom list view
        list_view = QListView()
        self.setView(list_view)
        
        # Limit maximum visible items
        self.setMaxVisibleItems(8)
        
        # Set size adjust policy
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    
    def showPopup(self):
        """Override to position popup below the combo box, never above."""
        # First, call parent to create and show the popup
        super().showPopup()
        
        # Use a timer to reposition after Qt's default positioning
        QTimer.singleShot(0, self._repositionPopup)
    
    def _repositionPopup(self):
        """Reposition the popup to be below the combo box."""
        popup = self.view().window()
        if not popup:
            return
        
        # Get combo box global position
        combo_global = self.mapToGlobal(QPoint(0, 0))
        
        # Calculate new position (below combo box)
        new_x = combo_global.x()
        new_y = combo_global.y() + self.height()
        
        # Get current popup size
        popup_width = max(self.width(), popup.width())
        popup_height = popup.height()
        
        # Limit height
        max_height = 250
        if popup_height > max_height:
            popup_height = max_height
        
        # Set new geometry
        popup.setGeometry(new_x, new_y, popup_width, popup_height)
        
        # Ensure it stays in position
        popup.move(new_x, new_y)

