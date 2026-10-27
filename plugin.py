# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon


class MyQgisVMPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.authenticated = False  # Chỉ hỏi mật khẩu 1 lần mỗi phiên QGIS (tắt QGIS là hỏi lại)
        self.menu_name = "&MyQgisVM"

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "MyQgisVM - Bộ công cụ xử lý GIS", self.iface.mainWindow())
        self.action.setToolTip("Mở bộ công cụ MyQgisVM")
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.menu_name, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        # Nếu cửa sổ tool đang mở thì đưa lên trước, không hỏi lại mật khẩu
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        from . import core
        # Đã bỏ bước yêu cầu mật khẩu; mở trực tiếp bộ công cụ.
        self.dialog = core.MyQgisVMDialog(self.iface.mainWindow())
        self.dialog.show()
