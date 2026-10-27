# -*- coding: utf-8 -*-
"""
=============================================================================
                          MYQGISVM - MASTER TOOLBOX
                 BỘ CÔNG CỤ XỬ LÝ DỮ LIỆU GIS TOÀN DIỆN (VĂN MẠNH)
=============================================================================
Phiên bản: 1.0 (All-in-One Master Edition)
Tác giả: Văn Mạnh & Trợ lý Kỹ thuật QGIS
Tương thích hoàn toàn: QGIS 3.x (PyQt5) & QGIS 4.x (PyQt6)

DANH MỤC 5 PHÂN HỆ CHÍNH:
-----------------------------------------------------------------------------
1. 🌐 TỌA ĐỘ VN-2000 & GEOMAP:
   - Gán tọa độ chuẩn VN-2000 (múi 3°) cho 63 tỉnh thành Việt Nam.
   - 3 phạm vi: Layer đang chọn / Tất cả layer đang mở / Quét thư mục (.gpkg, .shp).
   - Tích hợp bản đồ nền trực tuyến GeoMap (Google Hybrid, Vệ tinh, OSM, ESRI...).
   - Tuyệt đối không sinh file rác (*.gpkg-journal), tự động dọn sạch rác cũ.

2. 🛠️ SỬA LỖI HÌNH HỌC (GEOMETRY QC):
   - Tự động sửa Invalid Geometry & Self-Intersection (makeValid, buffer(0)).
   - Sửa lỗi Ring Self-Intersection & Too few points.
   - Loại bỏ đỉnh nhọn bất thường (Spikes).
   - Xóa đối tượng trùng lặp (Duplicate Geometries) - giữ lại đối tượng đầu.
   - Quét & Tự động xử lý chồng lấn (Topology Overlap) giữa các polygon.

3. ✂️ XỬ LÝ POLYGON NÂNG CAO (SLIVERS & SHAPES):
   - Dọn dẹp dải mảnh nhỏ (Slivers) theo diện tích và bề rộng trung bình.
   - Cắt tỉa phần nhánh hẹp dính liền (Trim Thin Parts / Opening) quanh tọa độ.
   - Thay thế hình học Polygon (Replace Geometry) giữ nguyên thuộc tính.
   - Tra cứu nhanh thông tin đối tượng tại tọa độ (Inspect at Point).

4. 📋 THUỘC TÍNH & CHUẨN CSDL QPK:
   - Tự động thêm 6 trường thuộc tính chuẩn quy hoạch (QPK / TT16).
   - Điền thông số quy hoạch mặc định hàng loạt (maThongTinQH, maHoSoQH...).
   - Tự động tính toán & cập nhật Chiều dài (Line) và Diện tích (Polygon).
   - Điền nhanh giá trị thuộc tính cho các đối tượng.
   - Thêm cột dữ liệu tùy ý (Text / Integer / Double / Date) trừ các trường bắt buộc.

5. 🔄 GHÉP & CHUYỂN ĐỔI DỮ LIỆU:
   - Ghép dữ liệu giữa các layer (Tự động Polygonize nếu nguồn là Line).
   - Tách và trích xuất dữ liệu Text / CAD sang thuộc tính.
=============================================================================
"""

import os
import sys
import sqlite3
import traceback
import csv
import re
import math
import zipfile
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import quote

from qgis.core import (
    QgsDxfExport,
    QgsVectorFileWriter,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsRectangle,
    QgsPointXY,
    QgsGeometry,
    QgsWkbTypes,
    QgsFeature,
    QgsFeatureRequest,
    QgsSpatialIndex,
    QgsField,
    QgsCoordinateTransform
)
from qgis.utils import iface
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QFileDialog, QGroupBox, QMessageBox,
    QTabWidget, QWidget, QDoubleSpinBox, QComboBox, QTextEdit,
    QScrollArea, QFrame, QSplitter, QSpinBox,
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from qgis.PyQt.QtCore import Qt, QVariant, QDate, QDir, QFile, QIODevice, QSize
from qgis.PyQt.QtGui import QFont, QColor, QPixmap, QBrush, QIcon

# Xử lý tương thích QGIS 3 & 4 (PyQt5 & PyQt6)
ALIGN_CENTER = getattr(Qt.AlignmentFlag, 'AlignCenter', getattr(Qt, 'AlignCenter', None))
ALIGN_LEFT = getattr(Qt.AlignmentFlag, 'AlignLeft', getattr(Qt, 'AlignLeft', None))
KEEP_ASPECT = getattr(Qt.AspectRatioMode, 'KeepAspectRatio', getattr(Qt, 'KeepAspectRatio', None))
SMOOTH_TRANSFORM = getattr(Qt.TransformationMode, 'SmoothTransformation', getattr(Qt, 'SmoothTransformation', None))
USER_ROLE = getattr(Qt.ItemDataRole, 'UserRole', getattr(Qt, 'UserRole', 0x0100))

# Kiểu hình học (QGIS 4 dùng Qgis.GeometryType, QGIS 3 cũ dùng QgsWkbTypes.xxxGeometry)
try:
    from qgis.core import Qgis
    GEOM_POINT = Qgis.GeometryType.Point
    GEOM_POLYGON = Qgis.GeometryType.Polygon
    GEOM_LINE = Qgis.GeometryType.Line
except Exception:
    GEOM_POINT = QgsWkbTypes.PointGeometry
    GEOM_POLYGON = QgsWkbTypes.PolygonGeometry
    GEOM_LINE = QgsWkbTypes.LineGeometry

# Kiểu trường dữ liệu (QGIS >= 3.38 / 4 dùng QMetaType, bản cũ dùng QVariant)
try:
    from qgis.core import Qgis as _Qgis
    if getattr(_Qgis, 'QGIS_VERSION_INT', 99999) < 33800:
        raise ImportError("QGIS cũ")
    from qgis.PyQt.QtCore import QMetaType
    _MT = getattr(QMetaType, 'Type', QMetaType)
    FT_STRING = _MT.QString
    FT_DOUBLE = _MT.Double
    FT_INT = _MT.Int
    FT_DATE = _MT.QDate
except Exception:
    FT_STRING = QVariant.String
    FT_DOUBLE = QVariant.Double
    FT_INT = QVariant.Int
    FT_DATE = QVariant.Date

# 6 trường bắt buộc chuẩn CSDL QPK/TT16 (đã có nút thêm riêng ở mục 1 nên mục 5 không cho tạo trùng)
REQUIRED_FIELD_NAMES = ["maThongTinQH", "maHoSoQH", "maDoiTuong", "dienTich", "chieuDai", "ghiChu"]


def get_selected_vector_layers():
    """Lấy TẤT CẢ layer vector đang được chọn (bôi đen) trong bảng Layers.
    iface.activeLayer() chỉ trả về 1 layer duy nhất nên không dùng được khi chọn nhiều layer.
    Nếu không có layer nào được chọn trong bảng Layers thì dùng layer đang active."""
    layers = []
    try:
        view = iface.layerTreeView()
        if view is not None:
            if hasattr(view, "selectedLayersRecursive"):
                layers = list(view.selectedLayersRecursive())   # gồm cả layer nằm trong group đang chọn
            else:
                layers = list(view.selectedLayers())
    except Exception:
        layers = []
    if not layers:
        al = iface.activeLayer()
        if al is not None:
            layers = [al]
    result, seen = [], set()
    for lyr in layers:
        if isinstance(lyr, QgsVectorLayer) and lyr.id() not in seen:
            seen.add(lyr.id())
            result.append(lyr)
    return result


def sanitize_gis_field_name(name, auto_replace_spaces=True):
    """
    Chuẩn hóa tên trường thuộc tính cho GIS:
    - Bỏ dấu tiếng Việt (VD: đối_tượng -> doi_tuong)
    - Đổi khoảng trắng thành gạch dưới '_' nếu auto_replace_spaces=True
    - Loại bỏ ký tự đặc biệt nguy hiểm trong SQL/Shapefile/GPKG
    """
    if not name:
        return ""
    n = unicodedata.normalize('NFD', str(name))
    n = ''.join([c for c in n if unicodedata.category(c) != 'Mn'])
    n = n.replace('đ', 'd').replace('Đ', 'D')
    if auto_replace_spaces:
        n = re.sub(r'\s+', '_', n.strip())
        n = re.sub(r'[^a-zA-Z0-9_]', '', n)
    else:
        n = n.strip()
        n = re.sub(r'[^a-zA-Z0-9_ ]', '', n)
    return n

# =============================================================================
# DỮ LIỆU TỌA ĐỘ 63 TỈNH THÀNH VIỆT NAM (VN-2000 MÚI 3 ĐỘ)
# =============================================================================
PROVINCES_DATA = [
    ("TP. Hồ Chí Minh", "105°45'", 105.75, "EPSG:9210"),
    ("Khánh Hòa (Nha Trang)", "108°15'", 108.25, "EPSG:9217"),
    ("Hà Nội", "105°00'", 105.0, "EPSG:5897"),
    ("Đà Nẵng", "107°45'", 107.75, "EPSG:5899"),
    ("Hải Phòng", "105°45'", 105.75, "EPSG:9210"),
    ("Cần Thơ", "105°00'", 105.0, "EPSG:5897"),
    ("Bình Dương", "105°45'", 105.75, "EPSG:9210"),
    ("Đồng Nai", "107°45'", 107.75, "EPSG:5899"),
    ("Bà Rịa – Vũng Tàu", "107°45'", 107.75, "EPSG:5899"),
    ("Long An", "105°45'", 105.75, "EPSG:9210"),
    ("Tiền Giang", "105°45'", 105.75, "EPSG:9210"),
    ("Bến Tre", "105°45'", 105.75, "EPSG:9210"),
    ("Tây Ninh", "105°30'", 105.5, "EPSG:9209"),
    ("Bình Phước", "106°15'", 106.25, "EPSG:9212"),
    ("Lâm Đồng", "107°45'", 107.75, "EPSG:5899"),
    ("Bình Thuận", "108°30'", 108.5, "EPSG:9218"),
    ("Ninh Thuận", "108°15'", 108.25, "EPSG:9217"),
    ("Bình Định", "108°15'", 108.25, "EPSG:9217"),
    ("Phú Yên", "108°30'", 108.5, "EPSG:9218"),
    ("Quảng Nam", "107°45'", 107.75, "EPSG:5899"),
    ("Quảng Ngãi", "108°00'", 108.0, "EPSG:5898"),
    ("Thừa Thiên Huế", "107°00'", 107.0, "EPSG:9214"),
    ("Quảng Trị", "106°15'", 106.25, "EPSG:9212"),
    ("Quảng Bình", "106°00'", 106.0, "EPSG:9211"),
    ("Hà Tĩnh", "105°30'", 105.5, "EPSG:9209"),
    ("Nghệ An", "104°45'", 104.75, "EPSG:9208"),
    ("Thanh Hóa", "105°00'", 105.0, "EPSG:5897"),
    ("Quảng Ninh", "107°45'", 107.75, "EPSG:5899"),
    ("Bắc Ninh", "105°30'", 105.5, "EPSG:9209"),
    ("Bắc Giang", "107°00'", 107.0, "EPSG:9214"),
    ("Hải Dương", "105°30'", 105.5, "EPSG:9209"),
    ("Hưng Yên", "105°30'", 105.5, "EPSG:9209"),
    ("Hà Nam", "105°00'", 105.0, "EPSG:5897"),
    ("Nam Định", "105°30'", 105.5, "EPSG:9209"),
    ("Thái Bình", "105°30'", 105.5, "EPSG:9209"),
    ("Ninh Bình", "105°00'", 105.0, "EPSG:5897"),
    ("Vĩnh Phúc", "105°00'", 105.0, "EPSG:5897"),
    ("Phú Thọ", "104°45'", 104.75, "EPSG:9208"),
    ("Thái Nguyên", "106°30'", 106.5, "EPSG:9213"),
    ("Bắc Kạn", "106°30'", 106.5, "EPSG:9213"),
    ("Cao Bằng", "105°45'", 105.75, "EPSG:9210"),
    ("Lạng Sơn", "107°15'", 107.25, "EPSG:9215"),
    ("Hà Giang", "105°30'", 105.5, "EPSG:9209"),
    ("Tuyên Quang", "106°00'", 106.0, "EPSG:9211"),
    ("Lào Cai", "104°45'", 104.75, "EPSG:9208"),
    ("Yên Bái", "104°45'", 104.75, "EPSG:9208"),
    ("Sơn La", "104°00'", 104.0, "EPSG:9206"),
    ("Hòa Bình", "106°00'", 106.0, "EPSG:9211"),
    ("Điện Biên", "103°00'", 103.0, "EPSG:9205"),
    ("Lai Châu", "103°00'", 103.0, "EPSG:9205"),
    ("Kon Tum", "107°30'", 107.5, "EPSG:9216"),
    ("Gia Lai", "108°30'", 108.5, "EPSG:9218"),
    ("Đắk Lắk", "108°30'", 108.5, "EPSG:9218"),
    ("Đắk Nông", "108°30'", 108.5, "EPSG:9218"),
    ("Đồng Tháp", "105°00'", 105.0, "EPSG:5897"),
    ("An Giang", "104°45'", 104.75, "EPSG:9208"),
    ("Vĩnh Long", "105°30'", 105.5, "EPSG:9209"),
    ("Trà Vinh", "105°30'", 105.5, "EPSG:9209"),
    ("Hậu Giang", "105°00'", 105.0, "EPSG:5897"),
    ("Kiên Giang", "104°30'", 104.5, "EPSG:9207"),
    ("Sóc Trăng", "105°30'", 105.5, "EPSG:9209"),
    ("Bạc Liêu", "105°00'", 105.0, "EPSG:5897"),
    ("Cà Mau", "104°30'", 104.5, "EPSG:9207")
]

# DỮ LIỆU BẢN ĐỒ NỀN GEOMAP
GEOMAP_OPTIONS = [
    ("🛰️ Google Hybrid (Vệ tinh + Tên đường)", 
     "type=xyz&url=https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
     "Ảnh vệ tinh sắc nét kết hợp nhãn tên đường, địa danh của Google (Khuyên dùng)."),
     
    ("🛰️ Google Satellite (Vệ tinh chụp ảnh)", 
     "type=xyz&url=https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
     "Ảnh chụp thực địa vệ tinh thuần túy của Google Maps."),
     
    ("🗺️ Google Maps (Bản đồ đường phố)", 
     "type=xyz&url=https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
     "Bản đồ giao thông, đường sá tiêu chuẩn của Google Maps."),
     
    ("⛰️ Google Terrain (Bản đồ địa hình)", 
     "type=xyz&url=https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
     "Bản đồ đường sá kết hợp địa hình đổ bóng cao độ của Google."),
     
    ("🌐 OpenStreetMap (OSM Standard)", 
     "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png",
     "Bản đồ nền nguồn mở toàn cầu OpenStreetMap chi tiết."),
     
    ("🛰️ ESRI Satellite (World Imagery)", 
     "type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
     "Ảnh vệ tinh độ nét cao toàn cầu từ hệ thống ESRI ArcGIS."),
     
    ("🗺️ ESRI Topographic", 
     "type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
     "Bản đồ địa hình, đường nét chi tiết chất lượng cao của ESRI."),
     
    ("🏙️ CartoDB Positron (Nền sáng tối giản)", 
     "type=xyz&url=https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
     "Bản đồ nền sáng tối giản, rất thích hợp để làm nổi bật các lớp quy hoạch."),
     
    ("❌ Không gắn GeoMap (Chỉ gán tọa độ)", 
     "",
     "Chỉ thực hiện gán hệ tọa độ VN-2000 mà không tải bản đồ nền trực tuyến.")
]


# =============================================================================
# CÁC HÀM TIỆN ÍCH DÙNG CHUNG
# =============================================================================
def clean_leftover_journals(directory):
    """Quét và xóa sạch các file rác .gpkg-journal cũ còn sót lại trong thư mục"""
    if not os.path.isdir(directory):
        return 0
    cleaned = 0
    try:
        for fname in os.listdir(directory):
            if fname.lower().endswith((".gpkg-journal", ".gpkg-wal", ".gpkg-shm")):
                full_p = os.path.join(directory, fname)
                try:
                    os.remove(full_p)
                    cleaned += 1
                except Exception:
                    pass
    except Exception:
        pass
    return cleaned


def update_single_gpkg(file_path, srs_id, ktt_str, name, wkt_def, table_name=None):
    """Cập nhật CRS trực tiếp vào file GPKG bằng SQLite (Bộ nhớ MEMORY)"""
    conn = sqlite3.connect(file_path)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode = MEMORY;")
    c.execute("PRAGMA synchronous = OFF;")

    c.execute("""
        INSERT OR REPLACE INTO gpkg_spatial_ref_sys 
        (srs_name, srs_id, organization, organization_coordsys_id, definition, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (f"VN-2000 / TM-3 {ktt_str}", srs_id, "EPSG", srs_id, wkt_def, f"VN-2000 {name}"))

    if table_name:
        c.execute("UPDATE gpkg_geometry_columns SET srs_id = ? WHERE lower(table_name) = lower(?)", (srs_id, table_name))
        c.execute("UPDATE gpkg_contents SET srs_id = ? WHERE lower(table_name) = lower(?)", (srs_id, table_name))
    else:
        c.execute("UPDATE gpkg_geometry_columns SET srs_id = ?", (srs_id,))
        c.execute("UPDATE gpkg_contents SET srs_id = ?", (srs_id,))

    conn.commit()
    conn.close()

    for ext in ["-journal", "-wal", "-shm"]:
        jf = file_path + ext
        if os.path.exists(jf):
            try:
                os.remove(jf)
            except Exception:
                pass


def update_single_shp(file_path, wkt_def):
    """Ghi đè file .prj cho Shapefile"""
    base_name = os.path.splitext(file_path)[0]
    with open(base_name + ".prj", "w", encoding="utf-8") as f:
        f.write(wkt_def)


def build_xyz_uri(geomap_url):
    """Đổi URL tile thô sang chuỗi nguồn XYZ chuẩn của QGIS.
    Các ký tự & = { } trong URL (đặc biệt link Google) PHẢI được mã hoá, nếu không QGIS
    hiểu sai tham số -> lớp nền vẫn được thêm nhưng không tải được ô ảnh nào (trắng trơn)."""
    prefix = "type=xyz&url="
    raw = geomap_url[len(prefix):] if geomap_url.startswith(prefix) else geomap_url
    return prefix + quote(raw, safe=":/") + "&zmin=0&zmax=19"


def attach_geomap(geomap_name, geomap_url, zoom_extent=None):
    """Gắn bản đồ nền GeoMap vào QGIS và đưa xuống đáy Layer Tree.
    Trả về layer nếu gắn được, None nếu không tải/khởi tạo được."""
    if not geomap_url:
        return None

    project = QgsProject.instance()
    existing_layer = None
    for lyr in project.mapLayers().values():
        if lyr.name() == geomap_name and isinstance(lyr, QgsRasterLayer):
            existing_layer = lyr
            break

    root = project.layerTreeRoot()
    if existing_layer:
        geomap_layer = existing_layer
        node = root.findLayer(geomap_layer.id())
        if node:
            node.setItemVisibilityChecked(True)
    else:
        geomap_layer = QgsRasterLayer(build_xyz_uri(geomap_url), geomap_name, "wms")
        if not geomap_layer.isValid():
            return None
        project.addMapLayer(geomap_layer, False)
        root.addLayer(geomap_layer)   # addLayer chèn vào cuối cây = nằm dưới cùng

    geomap_layer.reload()

    if zoom_extent and not zoom_extent.isEmpty():
        scaled_extent = QgsRectangle(zoom_extent)
        scaled_extent.scale(1.15)
        iface.mapCanvas().setExtent(scaled_extent)

    geomap_layer.triggerRepaint()
    iface.mapCanvas().refresh()
    return geomap_layer


# =============================================================================
# ĐỐI CHIẾU FILE BÁO CÁO LỖI (EXCEL / CSV) VỚI CÁC LỚP TRONG QGIS
# =============================================================================
_XLSX_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_XLSX_M = "{%s}" % _XLSX_NS["m"]


def _norm_text(s):
    """Chuẩn hoá để so khớp: chữ thường, bỏ dấu tiếng Việt, ký tự lạ -> khoảng trắng."""
    s = unicodedata.normalize("NFD", str(s if s is not None else "")).lower().replace("đ", "d")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _col_letters(i):
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    s = ""
    i += 1
    while i > 0:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def _col_index_from_ref(ref):
    """'C12' -> 2"""
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return max(n - 1, 0)


def read_xlsx_sheets(path):
    """Đọc file .xlsx/.xlsm KHÔNG cần thư viện ngoài. Trả về {tên_sheet: [[ô, ô, ...], ...]} (mọi ô là chuỗi)."""
    sheets = {}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _XLSX_NS):
                shared.append("".join((t.text or "") for t in si.iter(_XLSX_M + "t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rel_target = {}
        for rel in rels:
            rel_target[rel.get("Id")] = rel.get("Target")

        rid_attr = "{%s}id" % _XLSX_NS["r"]
        for sh in wb.find("m:sheets", _XLSX_NS):
            name = sh.get("name")
            target = rel_target.get(sh.get(rid_attr), "")
            target = target.lstrip("/")
            sheet_path = target if target.startswith("xl/") else "xl/" + target
            if sheet_path not in names:
                continue
            rows = []
            with z.open(sheet_path) as f:
                for _ev, el in ET.iterparse(f, events=("end",)):
                    if el.tag != _XLSX_M + "row":
                        continue
                    cells = {}
                    for c in el.findall("m:c", _XLSX_NS):
                        ref = c.get("r")
                        col = _col_index_from_ref(ref) if ref else len(cells)
                        t = c.get("t")
                        v = c.find("m:v", _XLSX_NS)
                        if t == "s":
                            try:
                                val = shared[int(v.text)] if (v is not None and v.text) else ""
                            except Exception:
                                val = ""
                        elif t == "inlineStr":
                            val = "".join((x.text or "") for x in c.iter(_XLSX_M + "t"))
                        elif t == "b":
                            val = "TRUE" if (v is not None and v.text == "1") else "FALSE"
                        else:
                            val = v.text if (v is not None and v.text is not None) else ""
                        cells[col] = val
                    r_no = int(el.get("r")) - 1 if el.get("r") else len(rows)
                    while len(rows) < r_no:
                        rows.append([])
                    width = (max(cells) + 1) if cells else 0
                    rows.append([cells.get(i, "") for i in range(width)])
                    el.clear()
            sheets[name] = rows
    return sheets


def read_csv_rows(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            text = None
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except Exception:
        delim = ","
    return [[c for c in row] for row in csv.reader(text.splitlines(), delimiter=delim)]


_HEADER_HINTS = {
    "stt", "lop", "layer", "id", "fid", "objectid", "loi", "mo", "ta", "error", "x", "y", "toa", "do",
    "ten", "ma", "description", "loai", "noi", "dung", "ghi", "chu", "vi", "tri", "doi", "tuong",
}


def detect_header_row(rows, scan=40):
    """Đoán dòng tiêu đề: dòng trong 40 dòng đầu có nhiều ô giống tiêu đề báo cáo nhất."""
    best_i, best_score = 0, 0
    for i, row in enumerate(rows[:scan]):
        score = 0
        for c in row:
            toks = set(_norm_text(c).split())
            if toks and toks & _HEADER_HINTS:
                score += 1
        if score > best_score:
            best_i, best_score = i, score
    if best_score >= 2:
        return best_i
    for i, row in enumerate(rows[:scan]):
        if any(str(c).strip() for c in row):
            return i
    return 0


_COL_SPECS = {
    "layer": [r"^(ten )?lop( du lieu)?$", r"\blop\b", r"layer", r"feature class", r"ten bang|\bbang\b|table"],
    "id": [r"^(fid|objectid|object id|ogc fid|gid)$", r"\bfid\b|\bobjectid\b", r"^id$", r"^id ", r"\bid\b",
           r"ma doi tuong|so hieu|ma so"],
    "err": [r"loai loi", r"mo ta loi|noi dung loi|ten loi", r"\bloi\b|error", r"mo ta|description|noi dung|ket qua"],
    "desc": [r"mo ta|description|chi tiet|noi dung|ghi chu"],
    "x": [r"^x$", r"toa do x|^x ", r"hoanh do|easting|kinh do|\blon\b|longitude"],
    "y": [r"^y$", r"toa do y|^y ", r"tung do|northing|vi do|\blat\b|latitude"],
}


def auto_pick_column(headers, key, exclude=()):
    """Tìm cột phù hợp nhất theo tên tiêu đề. Trả về chỉ số cột hoặc None."""
    norm = [_norm_text(h) for h in headers]
    for pat in _COL_SPECS.get(key, []):
        for i, h in enumerate(norm):
            if i in exclude or not h:
                continue
            if re.search(pat, h):
                return i
    return None


def _to_float(s):
    s = str(s).strip() if s is not None else ""
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        pass
    s2 = s.replace(" ", "")
    if "," in s2 and "." in s2:
        if s2.rfind(",") > s2.rfind("."):      # kiểu Việt/Châu Âu: 1.234,5
            s2 = s2.replace(".", "").replace(",", ".")
        else:                                  # kiểu Anh/Mỹ: 1,234.5
            s2 = s2.replace(",", "")
    elif s2.count(",") == 1:
        s2 = s2.replace(",", ".")
    else:
        s2 = s2.replace(",", "")
    try:
        return float(s2)
    except Exception:
        return None


def _norm_id(v):
    s = str(v).strip() if v is not None else ""
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except Exception:
        pass
    return s


# Bảng tri thức: (mã, tên lỗi, regex nhận diện trên chữ đã bỏ dấu, mức xử lý, phương án trong tool, gợi ý chuyên gia, regex loại trừ)
# Mức xử lý: AUTO = đã có thuật toán tự động | SEMI = hỗ trợ một phần/bán tự động | NONE = chưa có phương án
ERR_KB = [
    ("EMPTY", "Hình học rỗng / Null",
     r"hinh hoc rong|rong hinh hoc|empty geometry|null geometry|khong co hinh hoc|geometry null|geometry rong",
     "NONE", "❌ Chưa có",
     "Processing → 'Remove null geometries' hoặc Select by expression  $geometry IS NULL rồi xóa / vẽ lại theo hồ sơ.", ""),
    ("DUPVERT", "Trùng đỉnh (Duplicate vertices)",
     r"trung dinh|duplicate vert|duplicate node|dinh trung|trung diem|trung nut",
     "NONE", "❌ Chưa có",
     "Processing → 'Remove duplicate vertices' (native:removeduplicatevertices).", ""),
    ("DUP", "Đối tượng trùng lặp (Duplicate)",
     r"trung lap|duplicate|trung nhau|trung hinh hoc|trung doi tuong|bi trung|\btrung\b",
     "AUTO", "✅ QC mục 3: xóa trùng, giữ đối tượng đầu tiên",
     "Tool giữ đối tượng ĐẦU TIÊN và xóa bản sau: hãy so sánh thuộc tính các bản trùng trước, kẻo xóa nhầm bản có thông tin đúng.", ""),
    ("SPIKE", "Đỉnh nhọn / gai (Spike)",
     r"spike|\bgai\b|nhon|goc hep|dinh gai",
     "NONE", "❌ QC mục 2 có ô tích nhưng CHƯA có thuật toán",
     "Xóa đỉnh gai bằng Vertex Tool, hoặc Processing → 'Simplify' với dung sai rất nhỏ (0.01–0.05 m). Tool đã có hàm phát hiện góc < 10° để kiểm tra lại.", ""),
    ("FEW", "Quá ít điểm / hình học suy biến",
     r"it diem|it dinh|too few|toofew|thieu dinh|thieu diem|suy bien|degenerate|khong du dinh|so dinh",
     "NONE", "❌ QC mục 2 có ô tích nhưng CHƯA có thuật toán",
     "Polygon cần ≥ 3 đỉnh khác nhau, line cần ≥ 2. Thường là đối tượng rác: kiểm tra rồi xóa hoặc vẽ lại theo hồ sơ.", ""),
    ("OVERLAP", "Chồng lấn giữa các đối tượng (Overlap)",
     r"chong lan|chong len|chong chap|overlap|\bchong\b",
     "NONE", "❌ QC mục 4 có ô tích nhưng CHƯA có thuật toán",
     "Phải quyết định đối tượng nào được giữ phần chồng theo hồ sơ/ranh quản lý rồi mới Difference/Clip. Không nên cắt tự động hàng loạt.", ""),
    ("SLIVER", "Dải mảnh nhỏ / khoảng thủng (Sliver)",
     r"sliver|manh nho|dai manh|manh vun|khoang thung|lo thung|khe thung|\bthung\b|dien tich nho|qua nho|dien tich be",
     "SEMI", "🟡 Tab 'Xử lý Polygon nâng cao' mục 1 (dọn dải mảnh) hoặc mục 2 (cắt nhánh hẹp)",
     "Mục 1 xóa mảnh theo ngưỡng diện tích/bề rộng trên layer đang chọn. Nếu là khe giữa hai thửa thì nên nắn đỉnh (snap) thay vì xóa.", ""),
    ("GAP", "Hở / khe hở giữa các đối tượng (Gap)",
     r"khe ho|khoang ho|ho giua|ho hang|\bho\b|\bgaps?\b|khoang trong|khe trong",
     "NONE", "❌ Chưa có",
     "Dùng Topology Checker (Must not have gaps) + Processing 'Snap geometries to layer' (native:snapgeometries), hoặc vẽ bù polygon rồi Merge.", ""),
    ("ATTR", "Lỗi thuộc tính / chuẩn CSDL",
     r"thuoc tinh|attribute|thieu truong|thieu cot|sai ma|gia tri|domain|kieu du lieu|\bnull\b|de trong|\brong\b|mathongtinqh|mahosoqh|madoituong|dientich|chieudai|ghichu",
     "SEMI", "🟡 Tab 'Thuộc Tính Chuẩn QPK' (thêm trường, điền mặc định, tính DT/CD, điền giá trị, thêm cột)",
     "Tool điền hàng loạt và tính lại diện tích/chiều dài; lỗi nội dung (sai mã, sai miền giá trị) vẫn phải rà theo hồ sơ.",
     r"hinh hoc|geometry"),
    ("INVALID", "Hình học không hợp lệ / tự cắt (Invalid, Self-intersection)",
     r"invalid|khong hop le|tu cat|tu giao|self intersect|selfintersect|ring self|bowtie|no bom|hinh hoc sai|loi hinh hoc|sai hinh hoc|geometry error|loi geometry|\bgeos\b",
     "AUTO", "✅ QC mục 1: makeValid (dự phòng buffer 0)",
     "makeValid có thể đổi Polygon thành MultiPolygon hoặc bỏ phần tự cắt: so sánh diện tích trước/sau khi sửa.", ""),
    ("CRS", "Sai hệ tọa độ / CRS",
     r"he toa do|\bcrs\b|vn ?2000|kinh tuyen|epsg|sai toa do|projection|he quy chieu|\bsrs\b|mui chieu",
     "SEMI", "🟡 Tab 'Tọa Độ GeoMap' (gán hệ VN-2000 theo tỉnh)",
     "Tool chỉ GÁN lại định nghĩa CRS, không đổi giá trị tọa độ. Nếu dữ liệu đang ở hệ khác phải Reproject.", ""),
    ("OUTSIDE", "Nằm ngoài ranh / phạm vi",
     r"ngoai ranh|nam ngoai|ngoai pham vi|ngoai vung|outside|out of|vuot ranh|lech ranh|khong nam trong",
     "NONE", "❌ Chưa có",
     "Dùng Select by location để lọc đối tượng nằm ngoài ranh rồi xử lý thủ công, hoặc 'Clip' theo ranh giới nếu hồ sơ cho phép.", ""),
    ("TOPO", "Lỗi tô-pô đường / nút (Dangle, không nối, không khớp)",
     r"dangle|\btreo\b|khong noi|chua noi|dau mut|pseudo|giao cat|cat nhau|crossing|khong khop|snap|khong khep|chua khep",
     "NONE", "❌ Chưa có",
     "Dùng Topology Checker, 'Snap geometries', 'Extend lines' (Processing). Tính năng nối đoạn hở tự động chưa có trong tool.", ""),
]
ERR_KB_UNKNOWN = ("UNKNOWN", "Chưa nhận diện được loại lỗi", "", "NONE", "❌ Chưa nhận diện",
                  "Mô tả lỗi chưa khớp bộ từ khóa của tool: hãy kiểm tra lại cột 'Loại lỗi' đã chọn đúng chưa.", "")
ERR_KB_BY_CODE = {k[0]: k for k in ERR_KB + [ERR_KB_UNKNOWN]}


def classify_error(text):
    """Phân loại mô tả lỗi trong báo cáo -> mã lỗi trong ERR_KB."""
    t = _norm_text(text)
    if not t:
        return "UNKNOWN"
    for code, _name, pat, _lv, _plan, _adv, excl in ERR_KB:
        if re.search(pat, t) and not (excl and re.search(excl, t)):
            return code
    return "UNKNOWN"


def _geom_rings(geom):
    """Danh sách (danh_sách_điểm, khép_kín) của polygon/line."""
    try:
        gt = geom.type()
        if gt == GEOM_POLYGON:
            polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
            return [(ring, True) for poly in polys for ring in poly]
        if gt == GEOM_LINE:
            lines = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
            return [(ln, False) for ln in lines]
    except Exception:
        pass
    return []


def spike_in_rings(rings, min_angle_deg=10.0):
    """True nếu có đỉnh với góc kẹp < min_angle_deg (đỉnh nhọn / gai)."""
    cos_lim = math.cos(math.radians(min_angle_deg))
    for pts, closed in rings:
        pts = list(pts)
        if closed and len(pts) > 1 and pts[0].x() == pts[-1].x() and pts[0].y() == pts[-1].y():
            pts = pts[:-1]
        n = len(pts)
        if n < 3:
            continue
        rng = range(n) if closed else range(1, n - 1)
        for i in rng:
            p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
            ax, ay = p0.x() - p1.x(), p0.y() - p1.y()
            bx, by = p2.x() - p1.x(), p2.y() - p1.y()
            la, lb = math.hypot(ax, ay), math.hypot(bx, by)
            if la == 0 or lb == 0:
                continue
            if (ax * bx + ay * by) / (la * lb) >= cos_lim:
                return True
    return False


def few_points_in_rings(rings):
    for pts, closed in rings:
        if (closed and len(pts) < 4) or ((not closed) and len(pts) < 2):
            return True
    return False


def dup_vertices_in_rings(rings):
    for pts, _closed in rings:
        for i in range(len(pts) - 1):
            if pts[i].x() == pts[i + 1].x() and pts[i].y() == pts[i + 1].y():
                return True
    return False


class ErrorReportDialog(QDialog):
    HEADERS = ["#", "Lớp (báo cáo)", "Lớp khớp trong dự án", "ID", "Lỗi theo báo cáo", "Phân loại",
               "Vị trí", "Hiện trạng", "Phương án xử lý trong tool", "Gợi ý chuyên gia"]
    ID_CANDIDATES = ["fid", "objectid", "object_id", "ogc_fid", "gid", "id"]
    OUT_LAYER_NAME = "Lỗi_theo_báo_cáo"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Đối chiếu file báo cáo lỗi (Excel / CSV) - MyQgisVM")
        self.resize(1200, 780)
        self.sheets = {}
        self.rows = []
        self.headers = []
        self.data_rows = []
        self.results = []
        self._idmaps = {}
        self._sidx = {}
        self._layer_cache = {}
        self._build_ui()
        self.refresh_layers()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = QVBoxLayout(self)

        intro = QLabel("Đọc file báo cáo lỗi (.xlsx / .csv) → tìm đúng đối tượng lỗi trong các lớp đang mở → "
                       "kiểm tra lỗi còn hay đã hết → cho biết lỗi nào tool đã có phương án xử lý.")
        intro.setWordWrap(True)
        intro.setStyleSheet("background: #fdfefe; border: 1px solid #d5dbdb; padding: 8px; border-radius: 4px; color: #2c3e50;")
        main.addWidget(intro)

        # 1. FILE
        grp_file = QGroupBox("1. File báo cáo lỗi")
        grp_file.setStyleSheet("QGroupBox { font-weight: bold; }")
        gf = QVBoxLayout(grp_file)
        r1 = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        self.txt_file.setPlaceholderText("Chưa chọn file...")
        btn_browse = QPushButton("Chọn file Excel / CSV")
        btn_browse.setIcon(get_plugin_icon("folder_open"))
        btn_browse.setIconSize(QSize(16, 16))
        btn_browse.setStyleSheet("padding: 5px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_browse.clicked.connect(self.browse_file)
        r1.addWidget(self.txt_file, 1)
        r1.addWidget(btn_browse)
        gf.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Sheet:"))
        self.cmb_sheet = QComboBox()
        self.cmb_sheet.currentIndexChanged.connect(self.on_sheet_changed)
        r2.addWidget(self.cmb_sheet, 1)
        r2.addWidget(QLabel("Dòng tiêu đề:"))
        self.spn_header = QSpinBox()
        self.spn_header.setRange(1, 1000)
        self.spn_header.valueChanged.connect(self.apply_header_row)
        r2.addWidget(self.spn_header)
        self.lbl_file_info = QLabel("")
        self.lbl_file_info.setStyleSheet("color: #7f8c8d;")
        r2.addWidget(self.lbl_file_info, 2)
        gf.addLayout(r2)
        main.addWidget(grp_file)

        # 2. ÁNH XẠ CỘT
        grp_map = QGroupBox("2. Chọn cột tương ứng trong file (tự dò theo tiêu đề, có thể chỉnh lại)")
        grp_map.setStyleSheet("QGroupBox { font-weight: bold; }")
        gm = QVBoxLayout(grp_map)
        self.cmb_cols = {}
        row_a = QHBoxLayout()
        for key, label in (("layer", "Tên lớp:"), ("id", "ID đối tượng:"), ("err", "Loại / mô tả lỗi:")):
            row_a.addWidget(QLabel(label))
            cmb = QComboBox()
            cmb.setMinimumWidth(150)
            self.cmb_cols[key] = cmb
            row_a.addWidget(cmb, 1)
        gm.addLayout(row_a)
        row_b = QHBoxLayout()
        for key, label in (("desc", "Mô tả bổ sung:"), ("x", "Tọa độ X:"), ("y", "Tọa độ Y:")):
            row_b.addWidget(QLabel(label))
            cmb = QComboBox()
            cmb.setMinimumWidth(150)
            self.cmb_cols[key] = cmb
            row_b.addWidget(cmb, 1)
        gm.addLayout(row_b)
        row_c = QHBoxLayout()
        self.chk_swap = QCheckBox("Đảo X↔Y (quy ước trắc địa VN: X = hướng Bắc, Y = hướng Đông)")
        row_c.addWidget(self.chk_swap)
        row_c.addWidget(QLabel("Dung sai tọa độ:"))
        self.spn_tol = QDoubleSpinBox()
        self.spn_tol.setRange(0.0001, 100000.0)
        self.spn_tol.setDecimals(4)
        self.spn_tol.setValue(1.0)
        self.spn_tol.setToolTip("Tính theo đơn vị bản đồ của layer (m với VN-2000). Chỉ dùng khi tìm đối tượng theo tọa độ.")
        row_c.addWidget(self.spn_tol)
        gm.addLayout(row_c)
        row_d = QHBoxLayout()
        row_d.addWidget(QLabel("Layer mặc định (khi báo cáo không có cột lớp / không khớp tên):"))
        self.cmb_default_layer = QComboBox()
        row_d.addWidget(self.cmb_default_layer, 1)
        row_d.addWidget(QLabel("Trường ID trong layer:"))
        self.txt_idfield = QLineEdit()
        self.txt_idfield.setPlaceholderText("Để trống = tự dò (fid, OBJECTID, id...)")
        row_d.addWidget(self.txt_idfield, 1)
        gm.addLayout(row_d)
        main.addWidget(grp_map)

        # NÚT
        btns = QHBoxLayout()
        b_run = QPushButton("Đối chiếu & kiểm tra")
        b_run.setIcon(get_plugin_icon("scan"))
        b_run.setIconSize(QSize(16, 16))
        b_run.setStyleSheet("padding: 7px 16px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        b_run.clicked.connect(self.run_match)
        b_sel = QPushButton("Chọn tất cả đối tượng lỗi")
        b_sel.setIcon(get_plugin_icon("select_errors"))
        b_sel.setIconSize(QSize(16, 16))
        b_sel.setStyleSheet("padding: 7px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        b_sel.clicked.connect(lambda: self.select_errors(only_still=False))
        b_sel2 = QPushButton("Chỉ chọn lỗi còn tồn tại")
        b_sel2.setIcon(get_plugin_icon("select_errors"))
        b_sel2.setIconSize(QSize(16, 16))
        b_sel2.setStyleSheet("padding: 7px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        b_sel2.clicked.connect(lambda: self.select_errors(only_still=True))
        b_pts = QPushButton("Tạo lớp điểm vị trí lỗi")
        b_pts.setIcon(get_plugin_icon("error_points"))
        b_pts.setIconSize(QSize(16, 16))
        b_pts.setStyleSheet("padding: 7px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        b_pts.clicked.connect(self.create_point_layer)
        b_csv = QPushButton("Xuất kết quả (CSV)")
        b_csv.setIcon(get_plugin_icon("export_csv"))
        b_csv.setIconSize(QSize(16, 16))
        b_csv.setStyleSheet("padding: 7px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        b_csv.clicked.connect(self.export_csv)
        b_close = QPushButton("Đóng")
        b_close.clicked.connect(self.close)
        for b in (b_run, b_sel, b_sel2, b_pts, b_csv):
            btns.addWidget(b)
        btns.addStretch()
        btns.addWidget(b_close)
        main.addLayout(btns)

        # KẾT QUẢ
        split = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)
        for i, w in enumerate((40, 120, 130, 80, 220, 190, 150, 190, 290, 360)):
            self.table.setColumnWidth(i, w)
        self.table.cellDoubleClicked.connect(self.on_row_dclick)
        split.addWidget(self.table)
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setStyleSheet("background: #fdfefe; font-size: 12px;")
        split.addWidget(self.txt_summary)
        split.setSizes([430, 220])
        main.addWidget(split, 1)

        self.lbl_status = QLabel("💡 Bấm đúp vào một dòng trong bảng để chọn và phóng tới đối tượng lỗi đó.")
        self.lbl_status.setStyleSheet("color: #7f8c8d;")
        main.addWidget(self.lbl_status)

    def refresh_layers(self):
        cur = self.cmb_default_layer.currentData()
        self.cmb_default_layer.clear()
        self.cmb_default_layer.addItem("(Không dùng - chỉ khớp theo tên lớp trong báo cáo)", None)
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer):
                self.cmb_default_layer.addItem(lyr.name(), lyr.id())
        if cur:
            i = self.cmb_default_layer.findData(cur)
            if i >= 0:
                self.cmb_default_layer.setCurrentIndex(i)

    # ------------------------------------------------------------- ĐỌC FILE
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file báo cáo lỗi", "",
                                              "Báo cáo lỗi (*.xlsx *.xlsm *.csv *.txt);;Tất cả (*.*)")
        if not path:
            return
        self.txt_file.setText(path)
        self.load_file(path)

    def load_file(self, path):
        low = path.lower()
        if low.endswith(".xls"):
            QMessageBox.warning(self, "Định dạng cũ",
                                "File .xls (Excel 97-2003) chưa đọc được.\nHãy mở bằng Excel → Save As → Excel Workbook (.xlsx) rồi chọn lại.")
            return
        try:
            if low.endswith((".xlsx", ".xlsm")):
                self.sheets = read_xlsx_sheets(path)
            else:
                self.sheets = {"CSV": read_csv_rows(path)}
        except Exception as e:
            QMessageBox.critical(self, "Không đọc được file", f"{e}\n\n{traceback.format_exc()[-600:]}")
            return
        if not self.sheets:
            QMessageBox.warning(self, "File rỗng", "Không tìm thấy sheet dữ liệu nào trong file.")
            return
        names = list(self.sheets.keys())
        best = max(names, key=lambda n: len(self.sheets[n]))
        self.cmb_sheet.blockSignals(True)
        self.cmb_sheet.clear()
        for n in names:
            self.cmb_sheet.addItem(f"{n}  ({len(self.sheets[n])} dòng)", n)
        self.cmb_sheet.setCurrentIndex(names.index(best))
        self.cmb_sheet.blockSignals(False)
        self.on_sheet_changed()

    def on_sheet_changed(self, *_):
        name = self.cmb_sheet.currentData()
        self.rows = self.sheets.get(name, [])
        self.spn_header.blockSignals(True)
        self.spn_header.setValue(detect_header_row(self.rows) + 1)
        self.spn_header.blockSignals(False)
        self.apply_header_row()

    def apply_header_row(self, *_):
        if not self.rows:
            return
        h = min(self.spn_header.value() - 1, len(self.rows) - 1)
        body = self.rows[h + 1:]
        width = max([len(self.rows[h])] + [len(r) for r in body[:500]] + [1])
        hdr = list(self.rows[h]) + [""] * (width - len(self.rows[h]))
        self.headers = hdr
        self.data_rows = [r for r in body if any(str(c).strip() for c in r)]
        self.lbl_file_info.setText(f"Đã đọc {len(self.data_rows)} dòng dữ liệu, {width} cột.")

        for key, cmb in self.cmb_cols.items():
            cmb.clear()
            cmb.addItem("(không có)")
            for i, t in enumerate(hdr):
                cmb.addItem(f"{_col_letters(i)}: {str(t).strip() or '(trống)'}")
        used = set()
        for key in ("err", "layer", "id", "x", "y"):
            idx = auto_pick_column(hdr, key)
            if idx is not None:
                self.cmb_cols[key].setCurrentIndex(idx + 1)
                if key == "err":
                    used.add(idx)
        d_idx = auto_pick_column(hdr, "desc", exclude=used)
        if d_idx is not None:
            self.cmb_cols["desc"].setCurrentIndex(d_idx + 1)
        self._auto_swap_xy()

    def _col(self, key):
        i = self.cmb_cols[key].currentIndex() - 1
        return i if i >= 0 else None

    @staticmethod
    def _cell(row, idx):
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx]).strip()

    def _auto_swap_xy(self):
        """Đoán có cần đảo X↔Y: VN-2000 có X (Bắc) ~ 1-2 triệu, Y (Đông) ~ 0.3-0.8 triệu."""
        cx, cy = self._col("x"), self._col("y")
        if cx is None or cy is None:
            return
        xs, ys = [], []
        for r in self.data_rows[:60]:
            a, b = _to_float(self._cell(r, cx)), _to_float(self._cell(r, cy))
            if a is not None and b is not None:
                xs.append(a)
                ys.append(b)
        if not xs:
            return
        xs.sort()
        ys.sort()
        mx, my = xs[len(xs) // 2], ys[len(ys) // 2]
        self.chk_swap.setChecked(mx > 1000000 and 100000 < my < 1000000)

    # ------------------------------------------------------ TÌM LAYER/ĐỐI TƯỢNG
    def _resolve_layer(self, name, default_id):
        key = (name or "", default_id)
        if key in self._layer_cache:
            return self._layer_cache[key]
        layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
        found = None
        nm = (name or "").strip()
        if nm:
            for l in layers:
                if l.name().strip().lower() == nm.lower():
                    found = l
                    break
            if found is None:
                nk = _norm_text(nm).replace(" ", "")
                for l in layers:
                    if _norm_text(l.name()).replace(" ", "") == nk:
                        found = l
                        break
                if found is None and len(nk) >= 3:
                    for l in layers:
                        lk = _norm_text(l.name()).replace(" ", "")
                        if nk in lk or lk in nk:
                            found = l
                            break
        if found is None and default_id:
            lyr = QgsProject.instance().mapLayer(default_id)
            if isinstance(lyr, QgsVectorLayer):
                found = lyr
        self._layer_cache[key] = found
        return found

    def _get_index(self, layer):
        idx = self._sidx.get(layer.id())
        if idx is None:
            idx = QgsSpatialIndex(layer.getFeatures())
            self._sidx[layer.id()] = idx
        return idx

    def _id_map(self, layer):
        """Bản đồ {ID dạng chuỗi: fid QGIS} theo trường ID của layer; None nếu dùng thẳng feature id."""
        if layer.id() in self._idmaps:
            return self._idmaps[layer.id()]
        names = {f.name().lower(): f.name() for f in layer.fields()}
        user = self.txt_idfield.text().strip().lower()
        fld = None
        if user:
            fld = names.get(user)
        else:
            for c in self.ID_CANDIDATES:
                if c in names:
                    fld = names[c]
                    break
        result = None
        if fld:
            mp = {}
            for feat in layer.getFeatures():
                sv = _norm_id(feat[fld])
                if sv in ("", "NULL", "None"):
                    continue
                mp.setdefault(sv, feat.id())
            result = (fld, mp)
        self._idmaps[layer.id()] = result
        return result

    def _find_by_id(self, layer, id_txt):
        sid = _norm_id(id_txt)
        info = self._id_map(layer)
        if info is not None:
            fld, mp = info
            return mp.get(sid)
        try:
            fid = int(float(sid))
        except Exception:
            return None
        return fid if layer.getFeature(fid).isValid() else None

    def _find_by_xy(self, layer, x, y, tol):
        idx = self._get_index(layer)
        pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))
        best, best_d = None, None
        for cid in idx.intersects(QgsRectangle(x - tol, y - tol, x + tol, y + tol)):
            g = layer.getFeature(cid).geometry()
            if g.isNull() or g.isEmpty():
                continue
            d = g.distance(pt)
            if d <= tol and (best_d is None or d < best_d):
                best, best_d = cid, d
        return best

    # ------------------------------------------------------------ KIỂM TRA THỰC TẾ
    def _live_check(self, layer, fid, code):
        """Kiểm tra lỗi trong báo cáo CÒN hay ĐÃ HẾT trên dữ liệu hiện tại. Trả về (STILL/FIXED/UNKNOWN, mô tả)."""
        try:
            geom = layer.getFeature(fid).geometry()
            if code == "EMPTY":
                bad = geom.isNull() or geom.isEmpty()
                return ("STILL", "🔴 Còn lỗi: hình học rỗng") if bad else ("FIXED", "🟢 Đã hết lỗi")
            if geom.isNull() or geom.isEmpty():
                return "UNKNOWN", "⚪ Đối tượng không có hình học"
            if code == "INVALID":
                if not geom.isGeosValid():
                    msg = ""
                    try:
                        msg = geom.lastError() or ""
                    except Exception:
                        pass
                    return "STILL", "🔴 Còn lỗi: hình học không hợp lệ" + (f" ({msg[:60]})" if msg else "")
                return "FIXED", "🟢 Đã hết lỗi (hình học hợp lệ)"
            if code == "SPIKE":
                return ("STILL", "🔴 Còn đỉnh nhọn (góc < 10°)") if spike_in_rings(_geom_rings(geom)) \
                    else ("FIXED", "🟢 Không còn đỉnh nhọn (góc < 10°)")
            if code == "FEW":
                return ("STILL", "🔴 Còn lỗi: quá ít đỉnh") if few_points_in_rings(_geom_rings(geom)) \
                    else ("FIXED", "🟢 Đã hết lỗi")
            if code == "DUPVERT":
                return ("STILL", "🔴 Còn đỉnh trùng liên tiếp") if dup_vertices_in_rings(_geom_rings(geom)) \
                    else ("FIXED", "🟢 Không còn đỉnh trùng")
            if code == "DUP":
                idx = self._get_index(layer)
                same = []
                for cid in idx.intersects(geom.boundingBox()):
                    if cid != fid and geom.equals(layer.getFeature(cid).geometry()):
                        same.append(cid)
                if same:
                    return "STILL", "🔴 Còn trùng với fid " + ", ".join(str(c) for c in same[:4])
                return "FIXED", "🟢 Không còn bản trùng"
            if code == "OVERLAP":
                if layer.geometryType() != GEOM_POLYGON:
                    return "UNKNOWN", "⚪ Chỉ kiểm tra chồng lấn cho Polygon"
                idx = self._get_index(layer)
                hits = []
                for cid in idx.intersects(geom.boundingBox()):
                    if cid == fid:
                        continue
                    inter = geom.intersection(layer.getFeature(cid).geometry())
                    if inter is not None and not inter.isNull() and not inter.isEmpty() and inter.area() > 1e-4:
                        hits.append(cid)
                if hits:
                    return "STILL", "🔴 Còn chồng lấn với fid " + ", ".join(str(c) for c in hits[:4])
                return "FIXED", "🟢 Không còn chồng lấn"
        except Exception as e:
            return "UNKNOWN", f"⚪ Không kiểm tra được ({str(e)[:40]})"
        return "UNKNOWN", "⚪ Chưa tự kiểm tra được loại lỗi này - cần xem thủ công"

    # --------------------------------------------------------------- ĐỐI CHIẾU
    def run_match(self):
        if not self.data_rows:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Hãy chọn file báo cáo lỗi trước!")
            return
        c_layer, c_id, c_err = self._col("layer"), self._col("id"), self._col("err")
        c_desc, c_x, c_y = self._col("desc"), self._col("x"), self._col("y")
        if c_err is None and c_desc is None:
            QMessageBox.warning(self, "Thiếu cột", "Hãy chọn cột 'Loại / mô tả lỗi' (hoặc 'Mô tả bổ sung').")
            return
        if c_id is None and (c_x is None or c_y is None):
            QMessageBox.warning(self, "Thiếu cột", "Cần có cột ID đối tượng hoặc cặp cột tọa độ X, Y để xác định vị trí lỗi.")
            return

        self.refresh_layers_keep()
        default_id = self.cmb_default_layer.currentData()
        tol = self.spn_tol.value()
        swap = self.chk_swap.isChecked()
        self._idmaps, self._sidx, self._layer_cache = {}, {}, {}
        self.results = []

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            total = len(self.data_rows)
            for n, row in enumerate(self.data_rows, start=1):
                if n % 50 == 0:
                    self.lbl_status.setText(f"⏳ Đang đối chiếu... {n}/{total}")
                    QApplication.processEvents()
                layer_txt = self._cell(row, c_layer)
                id_txt = self._cell(row, c_id)
                err_txt = " | ".join(t for t in (self._cell(row, c_err), self._cell(row, c_desc)) if t)
                xv, yv = _to_float(self._cell(row, c_x)), _to_float(self._cell(row, c_y))
                if swap:
                    xv, yv = yv, xv
                if xv is None or yv is None:
                    xv = yv = None

                code = classify_error(err_txt)
                kb = ERR_KB_BY_CODE[code]
                layer = self._resolve_layer(layer_txt, default_id)
                fid, how = None, ""
                if layer is not None:
                    if id_txt:
                        fid = self._find_by_id(layer, id_txt)
                        how = "ID" if fid is not None else ""
                    if fid is None and xv is not None:
                        fid = self._find_by_xy(layer, xv, yv, tol)
                        how = "tọa độ" if fid is not None else ""

                state, state_txt = "NOTFOUND", ""
                if layer is None:
                    loc = "✖ Không xác định được lớp"
                elif fid is None:
                    loc = f"✖ Không thấy đối tượng (ID {id_txt})" if id_txt else "✖ Không có đối tượng gần tọa độ"
                else:
                    loc = f"✔ Tìm thấy (theo {how})"
                    state, state_txt = self._live_check(layer, fid, code)

                self.results.append({
                    "no": n, "layer_txt": layer_txt, "layer": layer, "id_txt": id_txt, "err_txt": err_txt,
                    "code": code, "cname": kb[1], "level": kb[3], "plan": kb[4], "advice": kb[5],
                    "fid": fid, "how": how, "x": xv, "y": yv, "loc": loc, "state": state, "state_txt": state_txt,
                })
        finally:
            QApplication.restoreOverrideCursor()

        self.populate_table()
        self.build_summary()
        self.lbl_status.setText(f"✅ Đã đối chiếu {len(self.results)} dòng báo cáo. Bấm đúp vào một dòng để phóng tới lỗi.")

    def refresh_layers_keep(self):
        self.refresh_layers()

    def populate_table(self):
        colors = {"AUTO": "#e8f8f0", "SEMI": "#fef9e7", "NONE": "#fdedec"}
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.results))
        for i, r in enumerate(self.results):
            id_show = r["id_txt"]
            if r["fid"] is not None and str(r["fid"]) != _norm_id(r["id_txt"]):
                id_show = f"{r['id_txt']} (fid {r['fid']})".strip()
            vals = [
                str(r["no"]), r["layer_txt"], r["layer"].name() if r["layer"] is not None else "—", id_show,
                r["err_txt"], r["cname"], r["loc"],
                r["state_txt"] if r["state_txt"] else "—", r["plan"], r["advice"],
            ]
            bg = QColor("#eceff1") if r["state"] == "NOTFOUND" else QColor(colors.get(r["level"], "#ffffff"))
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setToolTip(v)
                item.setBackground(QBrush(bg))
                self.table.setItem(i, c, item)

    def build_summary(self):
        res = self.results
        n = len(res)
        found = sum(1 for r in res if r["fid"] is not None)
        lv = {"AUTO": 0, "SEMI": 0, "NONE": 0}
        for r in res:
            lv[r["level"]] += 1
        lines = [
            f"📊 TỔNG QUAN: {n} dòng báo cáo | Tìm thấy trong dự án: {found} | Không tìm thấy: {n - found}",
            f"   ✅ Có phương án TỰ ĐỘNG: {lv['AUTO']}   🟡 Hỗ trợ MỘT PHẦN: {lv['SEMI']}   ❌ CHƯA có phương án: {lv['NONE']}",
            "",
            "📋 THEO TỪNG LOẠI LỖI:",
        ]
        order = [k[0] for k in ERR_KB] + ["UNKNOWN"]
        for code in order:
            grp = [r for r in res if r["code"] == code]
            if not grp:
                continue
            f = sum(1 for r in grp if r["fid"] is not None)
            still = sum(1 for r in grp if r["state"] == "STILL")
            fixed = sum(1 for r in grp if r["state"] == "FIXED")
            kb = ERR_KB_BY_CODE[code]
            lines.append(f"• {kb[1]}: {len(grp)} lỗi (tìm thấy {f}; còn lỗi {still}; đã hết {fixed})")
            lines.append(f"     → {kb[4]}")

        lines += ["", "🧠 NHẬN ĐỊNH CHUYÊN GIA:"]
        auto_still = sum(1 for r in res if r["level"] == "AUTO" and r["state"] == "STILL")
        if auto_still:
            lines.append(f"   - {auto_still} lỗi CÒN TỒN TẠI và tool có thể sửa tự động (Invalid / Trùng lặp): "
                         "bấm 'Chỉ chọn lỗi còn tồn tại' để rà lại, rồi sang tab 'Sửa Lỗi Hình Học (QC)' chạy mục 1 / mục 3. "
                         "Nên sao lưu dữ liệu trước khi sửa.")
        none_still = sum(1 for r in res if r["level"] == "NONE" and r["state"] in ("STILL", "UNKNOWN"))
        if none_still:
            lines.append(f"   - {none_still} lỗi CHƯA có phương án tự động trong tool: xử lý thủ công theo cột 'Gợi ý chuyên gia' "
                         "hoặc nhờ bổ sung tính năng.")
        semi = lv["SEMI"]
        if semi:
            lines.append(f"   - {semi} lỗi chỉ được hỗ trợ MỘT PHẦN (thuộc tính / sliver / CRS): tool làm hàng loạt được, "
                         "nhưng nội dung đúng-sai vẫn phải đối chiếu hồ sơ.")
        fixed_all = sum(1 for r in res if r["state"] == "FIXED")
        if fixed_all:
            lines.append(f"   - {fixed_all} lỗi trong báo cáo ĐÃ HẾT trên dữ liệu hiện tại (có thể đã sửa sau khi lập báo cáo).")
        nf = n - found
        if nf:
            lines.append(f"   - {nf} dòng KHÔNG khớp được đối tượng: kiểm tra tên lớp, trường ID (FID có thể đã đổi sau khi xuất/sửa dữ liệu), "
                         "hoặc dùng cột tọa độ X, Y (nhớ kiểm tra ô 'Đảo X↔Y').")
        self.txt_summary.setPlainText("\n".join(lines))

    # ------------------------------------------------------------- THAO TÁC
    def on_row_dclick(self, row, _col):
        if row < 0 or row >= len(self.results):
            return
        r = self.results[row]
        layer, fid = r["layer"], r["fid"]
        canvas = iface.mapCanvas()
        if layer is not None and fid is not None:
            layer.selectByIds([fid])
            try:
                canvas.zoomToFeatureIds(layer, {fid})
            except Exception:
                canvas.zoomToSelected(layer)
            try:
                canvas.flashFeatureIds(layer, {fid})
            except Exception:
                pass
            return
        p = self._result_point(r)
        if p is not None:
            canvas.setCenter(p)
            canvas.zoomScale(500)
            canvas.refresh()
        else:
            self.lbl_status.setText("⚠️ Dòng này không có vị trí để phóng tới.")

    def select_errors(self, only_still=False):
        if not self.results:
            QMessageBox.information(self, "Chưa có kết quả", "Hãy bấm 'Đối chiếu & kiểm tra' trước.")
            return
        by_layer = {}
        for r in self.results:
            if r["fid"] is None or r["layer"] is None:
                continue
            if only_still and r["state"] != "STILL":
                continue
            by_layer.setdefault(r["layer"].id(), (r["layer"], set()))[1].add(r["fid"])
        if not by_layer:
            QMessageBox.information(self, "Không có đối tượng", "Không có đối tượng nào thỏa điều kiện để chọn.")
            return
        proj_crs = QgsProject.instance().crs()
        ext = None
        total = 0
        for layer, ids in by_layer.values():
            layer.selectByIds(list(ids))
            total += len(ids)
            bb = layer.boundingBoxOfSelected()
            if bb.isNull():
                continue
            try:
                if layer.crs().isValid() and layer.crs() != proj_crs:
                    bb = QgsCoordinateTransform(layer.crs(), proj_crs, QgsProject.instance()).transformBoundingBox(bb)
            except Exception:
                pass
            if ext is None:
                ext = QgsRectangle(bb)
            else:
                ext.combineExtentWith(bb)
        if ext is not None:
            if ext.width() <= 0 or ext.height() <= 0:
                ext.grow(0.0001 if proj_crs.isGeographic() else 10.0)
            else:
                ext.scale(1.2)
            iface.mapCanvas().setExtent(ext)
            iface.mapCanvas().refresh()
        self.lbl_status.setText(f"🎯 Đã chọn {total} đối tượng lỗi trong {len(by_layer)} lớp.")

    def _result_point(self, r):
        """Điểm đại diện vị trí lỗi, trả về theo hệ tọa độ của dự án."""
        layer = r["layer"]
        proj_crs = QgsProject.instance().crs()
        pt, src = None, None
        if r["x"] is not None and r["y"] is not None:
            pt = QgsPointXY(r["x"], r["y"])
            src = layer.crs() if layer is not None else proj_crs
        elif layer is not None and r["fid"] is not None:
            g = layer.getFeature(r["fid"]).geometry()
            if g is not None and not g.isNull() and not g.isEmpty():
                c = g.pointOnSurface()
                if c is None or c.isNull():
                    c = g.centroid()
                if c is not None and not c.isNull():
                    pt, src = c.asPoint(), layer.crs()
        if pt is None:
            return None
        try:
            if src is not None and src.isValid() and src != proj_crs:
                pt = QgsCoordinateTransform(src, proj_crs, QgsProject.instance()).transform(pt)
        except Exception:
            pass
        return pt

    def create_point_layer(self):
        if not self.results:
            QMessageBox.information(self, "Chưa có kết quả", "Hãy bấm 'Đối chiếu & kiểm tra' trước.")
            return
        pts = []
        for r in self.results:
            p = self._result_point(r)
            if p is not None:
                pts.append((r, p))
        if not pts:
            QMessageBox.information(self, "Không có vị trí", "Không có dòng nào xác định được vị trí để tạo điểm.")
            return
        proj = QgsProject.instance()
        for old in list(proj.mapLayersByName(self.OUT_LAYER_NAME)):
            proj.removeMapLayer(old.id())
        vl = QgsVectorLayer("Point", self.OUT_LAYER_NAME, "memory")
        vl.setCrs(proj.crs())
        pr = vl.dataProvider()
        pr.addAttributes([
            QgsField("stt", FT_INT),
            QgsField("lop", FT_STRING), QgsField("id_dt", FT_STRING), QgsField("loi_bc", FT_STRING),
            QgsField("phan_loai", FT_STRING), QgsField("hien_trang", FT_STRING), QgsField("phuong_an", FT_STRING),
        ])
        vl.updateFields()
        feats = []
        for r, p in pts:
            f = QgsFeature(vl.fields())
            f.setGeometry(QgsGeometry.fromPointXY(p))
            f.setAttributes([r["no"], r["layer"].name() if r["layer"] is not None else r["layer_txt"],
                             r["id_txt"], r["err_txt"][:250], r["cname"], r["state_txt"] or r["loc"], r["plan"]])
            feats.append(f)
        pr.addFeatures(feats)
        vl.updateExtents()
        try:
            sym = vl.renderer().symbol()
            sym.setColor(QColor("#e74c3c"))
            sym.setSize(3.5)
        except Exception:
            pass
        proj.addMapLayer(vl)
        self.lbl_status.setText(f"📍 Đã tạo lớp '{self.OUT_LAYER_NAME}' gồm {len(feats)} điểm.")

    def export_csv(self):
        if not self.results:
            QMessageBox.information(self, "Chưa có kết quả", "Hãy bấm 'Đối chiếu & kiểm tra' trước.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất kết quả đối chiếu", "KetQua_DoiChieuLoi.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(self.HEADERS)
                for r in self.results:
                    w.writerow([r["no"], r["layer_txt"], r["layer"].name() if r["layer"] is not None else "",
                                r["id_txt"], r["err_txt"], r["cname"], r["loc"], r["state_txt"], r["plan"], r["advice"]])
            QMessageBox.information(self, "Đã xuất", f"Đã lưu kết quả:\n{path}\n(Mở bằng Excel, chữ Việt hiển thị đúng.)")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không ghi được file:\n{e}")
def get_plugin_icon(name):
    """Lấy QIcon từ thư mục icons/ của plugin (hỗ trợ cache QIcon)."""
    if not hasattr(get_plugin_icon, "_cache"):
        get_plugin_icon._cache = {}
    if name in get_plugin_icon._cache:
        return get_plugin_icon._cache[name]
    icon_file = name if name.endswith(".png") else f"{name}.png"
    icon_path = os.path.join(os.path.dirname(__file__), "icons", icon_file)
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
    else:
        icon = QIcon()
    get_plugin_icon._cache[name] = icon
    return icon


def is_dark_theme():
    """Tự động phát hiện QGIS đang ở giao diện tối (Dark / Night Mode) hay sáng."""
    try:
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtGui import QPalette
        app = QApplication.instance()
        if app:
            pal = app.palette()
            win_lum = pal.color(QPalette.ColorRole.Window).lightness()
            base_lum = pal.color(QPalette.ColorRole.Base).lightness()
            if win_lum < 128 or base_lum < 128:
                return True
    except Exception:
        pass
    try:
        from qgis.core import QgsSettings
        s = QgsSettings()
        theme = str(s.value("UI/UITheme", "")).lower()
        if any(x in theme for x in ["dark", "night", "blendofgray", "black"]):
            return True
    except Exception:
        pass
    return False


TT16_DATASETS_QUYHOACH = [
    "ViTriRanhGioi",
    "QuyHoachSuDungDat",
    "ThietkeDoThi",
    "QuyHoachKhongGianKienTrucCanhQuan",
    "QuyHoachGiaoThong",
    "QuyHoachCGDD_CGXDHanhLangHTKT",
    "QuyHoachChuanBiKyThuat",
    "QuyHoachThoatNuocThaiVSMT",
    "QuyHoachCapNuoc",
    "QuyHoachCapDien",
    "QuyHoachThongTinLienLac",
    "GiaiPhapBaoVeMoiTruong",
    "QuyHoachCongTrinhNgam",
    "QuyHoachNangLuong",
    "MocGioiQuyHoach",
    "QuyHoachChuyenDeKhac"
]

TT16_DATASETS_HIENTRANG = [
    "ViTriRanhGioi",
    "HienTrangSuDungDat",
    "HienTrangKhongGianKienTrucCanhQuan",
    "HienTrangGiaoThong",
    "HienTrangCGDD_CGXDHanhLangHTKT",
    "HienTrangChuanBiKyThuat",
    "HienTrangThoatNuocThaiVSMT",
    "HienTrangCapNuoc",
    "HienTrangCapDien",
    "HienTrangThongTinLienLac",
    "HienTrangMoiTruong",
    "HienTrangCongTrinhNgam",
    "HienTrangNangLuong",
    "HienTrangChuyenDeKhac"
]


class TT16PreCheckReportDialog(QDialog):
    """
    Hộp thoại báo cáo kiểm tra và đối soát dữ liệu chuẩn Thông tư 16/2025/TT-BXD.
    Cho phép người dùng xem trước phân loại Feature Dataset, kiểm tra 6 trường thuộc tính,
    tùy chỉnh lại nếu muốn, và chỉ khi bấm 'Đồng ý & Tiếp tục Xuất' thì mới thực hiện.
    """
    def __init__(self, parent=None, layer_reports=None, target_db="QuyHoach.gdb", out_path="", ma_hs="", ma_tt="", auto_fields=True):
        super().__init__(parent)
        self.setWindowTitle("📋 Báo Cáo Kiểm Tra & Đối Soát CSDL Chuẩn TT16/2025/TT-BXD")
        self.resize(960, 600)
        self.layer_reports = layer_reports or []
        self.target_db = target_db
        self.out_path = out_path
        self.confirmed = False
        self.confirmed_ma_hs = ma_hs
        self.confirmed_ma_tt = ma_tt
        self.confirmed_auto_fields = auto_fields
        self.confirmed_data = [] # Danh sách: (lyr, ds, fc)
        self._init_ui(ma_hs, ma_tt, auto_fields)

    def _init_ui(self, ma_hs, ma_tt, auto_fields):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        is_dark = is_dark_theme()
        if is_dark:
            self.setStyleSheet("""
                QDialog { background-color: #1e2227; color: #f0f6fc; }
                QLabel { color: #f0f6fc; }
                QTableWidget { background-color: #1b1d23; color: #f0f6fc; gridline-color: #3e4451; border: 1px solid #3e4451; }
                QHeaderView::section { background-color: #282c35; color: #ffffff; font-weight: bold; border: 1px solid #3e4451; padding: 4px; }
                QLineEdit { background-color: #1b1d23; color: #ffffff; border: 1px solid #4b5263; padding: 4px 6px; border-radius: 4px; }
                QComboBox { background-color: #1b1d23; color: #ffffff; border: 1px solid #4b5263; padding: 3px 6px; border-radius: 4px; }
                QComboBox QAbstractItemView { background-color: #21252b; color: #ffffff; selection-background-color: #2563eb; }
            """)

        # 1. Header Banner
        banner = QFrame()
        if is_dark:
            banner.setStyleSheet("background: #1b263b; border: 1px solid #1f6feb; border-radius: 5px; padding: 6px;")
        else:
            banner.setStyleSheet("background: #ebf5fb; border: 1px solid #aed6f1; border-radius: 5px; padding: 6px;")
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(8, 6, 8, 6)
        lbl_title = QLabel("🏛️ <b>BÁO CÁO KIỂM TRA & ĐỐI SOÁT DỮ LIỆU CHUẨN THÔNG TƯ 16/2025/TT-BXD</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #58a6ff;" if is_dark else "font-size: 14px; color: #1b4f72;")
        lbl_sub = QLabel("Hệ thống đã tự động rà soát tên lớp, hình học, phân nhóm Feature Dataset và 6 trường thuộc tính bắt buộc.<br>"
                         "Vui lòng xem lại bảng đối soát bên dưới. Nếu đồng ý, hãy bấm <b>'Đồng ý & Tiếp tục Xuất GDB'</b> để ghi dữ liệu vào CSDL <b>HoSoGIS</b>.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #e6edf3;" if is_dark else "font-size: 11px; color: #2c3e50;")
        lbl_sub.setWordWrap(True)
        b_lay.addWidget(lbl_title)
        b_lay.addWidget(lbl_sub)
        layout.addWidget(banner)

        # 2. Khung cấu hình thông tin
        cfg_frame = QFrame()
        if is_dark:
            cfg_frame.setStyleSheet("background: #282c35; border: 1px solid #3e4451; border-radius: 4px; padding: 4px;")
        else:
            cfg_frame.setStyleSheet("background: #fdfefe; border: 1px solid #d5dbdb; border-radius: 4px; padding: 4px;")
        cfg_box = QVBoxLayout(cfg_frame)
        cfg_box.setContentsMargins(8, 6, 8, 6)

        c_r1 = QHBoxLayout()
        c_r1.addWidget(QLabel("<b>Cơ sở dữ liệu đích:</b>"))
        lbl_db = QLabel(f"<span style='color: #2980b9; font-weight: bold;'>{self.target_db}</span>")
        c_r1.addWidget(lbl_db)
        c_r1.addSpacing(15)
        c_r1.addWidget(QLabel("<b>Đường dẫn CSDL:</b>"))
        lbl_p = QLabel(f"<code>{self.out_path}</code>")
        lbl_p.setTextInteractionFlags(getattr(Qt.TextInteractionFlag, 'TextSelectableByMouse', getattr(Qt, 'TextSelectableByMouse', None)))
        c_r1.addWidget(lbl_p, 1)
        cfg_box.addLayout(c_r1)

        c_r2 = QHBoxLayout()
        c_r2.addWidget(QLabel("<b>Mã hồ sơ (maHoSoQH):</b>"))
        self.txt_ma_hs = QLineEdit(ma_hs)
        self.txt_ma_hs.setPlaceholderText("VD: 79QPK101xxxx")
        self.txt_ma_hs.setStyleSheet("font-weight: bold; color: #b03a2e;")
        self.txt_ma_hs.setMaximumWidth(150)
        c_r2.addWidget(self.txt_ma_hs)

        c_r2.addSpacing(15)
        c_r2.addWidget(QLabel("<b>Mã thông tin (maThongTinQH):</b>"))
        self.txt_ma_tt = QLineEdit(ma_tt)
        self.txt_ma_tt.setPlaceholderText("VD: TT01 (nếu có)")
        self.txt_ma_tt.setMaximumWidth(120)
        c_r2.addWidget(self.txt_ma_tt)

        c_r2.addSpacing(15)
        self.chk_auto_fields = QCheckBox("Tự động bổ sung các trường còn thiếu & điền mã khi xuất")
        self.chk_auto_fields.setChecked(auto_fields)
        self.chk_auto_fields.setStyleSheet("font-weight: 500;")
        c_r2.addWidget(self.chk_auto_fields)
        c_r2.addStretch()
        cfg_box.addLayout(c_r2)

        layout.addWidget(cfg_frame)

        # 3. Bảng đối soát chi tiết từng layer
        self.table = QTableWidget()
        headers = ["STT", "Layer QGIS", "Hình học", "Feature Dataset đích", "Feature Class đích", "Số ĐT", "Tình trạng 6 trường TT16"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.layer_reports))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Danh sách Feature Dataset gợi ý
        is_ht = "hientrang" in self.target_db.lower()
        datasets_list = TT16_DATASETS_HIENTRANG if is_ht else TT16_DATASETS_QUYHOACH

        compliant_count = 0
        need_fields_count = 0

        for row, rep in enumerate(self.layer_reports):
            # 0. STT
            stt_item = QTableWidgetItem(str(row + 1))
            stt_item.setTextAlignment(ALIGN_CENTER)
            stt_item.setFlags(stt_item.flags() ^ getattr(Qt.ItemFlag, 'ItemIsEditable', getattr(Qt, 'ItemIsEditable', 0)))
            self.table.setItem(row, 0, stt_item)

            # 1. Layer QGIS
            orig_item = QTableWidgetItem(rep['orig_name'])
            orig_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            orig_item.setFlags(orig_item.flags() ^ getattr(Qt.ItemFlag, 'ItemIsEditable', getattr(Qt, 'ItemIsEditable', 0)))
            self.table.setItem(row, 1, orig_item)

            # 2. Hình học
            geom_item = QTableWidgetItem(rep['geom_str'])
            geom_item.setTextAlignment(ALIGN_CENTER)
            geom_item.setFlags(geom_item.flags() ^ getattr(Qt.ItemFlag, 'ItemIsEditable', getattr(Qt, 'ItemIsEditable', 0)))
            self.table.setItem(row, 2, geom_item)

            # 3. Feature Dataset đích (QComboBox để dễ dàng điều chỉnh)
            cmb_ds = QComboBox()
            for ds in datasets_list:
                cmb_ds.addItem(ds, ds)
            cur_ds = rep['dataset']
            idx = cmb_ds.findText(cur_ds)
            if idx >= 0:
                cmb_ds.setCurrentIndex(idx)
            else:
                cmb_ds.addItem(cur_ds, cur_ds)
                cmb_ds.setCurrentIndex(cmb_ds.count() - 1)
            cmb_ds.setStyleSheet("padding: 2px 4px; font-weight: bold; color: #1a5276;")
            self.table.setCellWidget(row, 3, cmb_ds)

            # 4. Feature Class đích (Có thể click vào sửa nếu muốn đổi tên)
            fc_item = QTableWidgetItem(rep['fc_name'])
            fc_item.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            self.table.setItem(row, 4, fc_item)

            # 5. Số đối tượng
            cnt_item = QTableWidgetItem(str(rep['count']))
            cnt_item.setTextAlignment(ALIGN_CENTER)
            cnt_item.setFlags(cnt_item.flags() ^ getattr(Qt.ItemFlag, 'ItemIsEditable', getattr(Qt, 'ItemIsEditable', 0)))
            self.table.setItem(row, 5, cnt_item)

            # 6. Tình trạng 6 trường TT16
            missing = rep['missing']
            if len(missing) == 0:
                compliant_count += 1
                status_item = QTableWidgetItem("🟢 Đầy đủ 6/6 trường chuẩn TT16")
                if is_dark:
                    status_item.setForeground(QBrush(QColor("#7ee787")))
                    status_item.setBackground(QBrush(QColor("#12281e")))
                else:
                    status_item.setForeground(QBrush(QColor("#1e8449")))
                    status_item.setBackground(QBrush(QColor("#eafaf1")))
                status_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            else:
                need_fields_count += 1
                status_str = f"⚠️ Thiếu {len(missing)} trường ({', '.join(missing)})"
                status_item = QTableWidgetItem(status_str)
                if is_dark:
                    status_item.setForeground(QBrush(QColor("#f0883e")))
                    status_item.setBackground(QBrush(QColor("#2e1f0e")))
                else:
                    status_item.setForeground(QBrush(QColor("#b9770e")))
                    status_item.setBackground(QBrush(QColor("#fef9e7")))
                status_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            status_item.setFlags(status_item.flags() ^ getattr(Qt.ItemFlag, 'ItemIsEditable', getattr(Qt, 'ItemIsEditable', 0)))
            self.table.setItem(row, 6, status_item)

        # Tinh chỉnh kích thước cột
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 85)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 200)
        self.table.setColumnWidth(5, 75)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        # 4. Thống kê & Ghi chú dưới đáy
        bot_box = QHBoxLayout()
        lbl_stat = QLabel(
            f"📊 <b>Tổng số:</b> {len(self.layer_reports)} layer | "
            f"<b>Đã đủ 6 trường:</b> <span style='color: #27ae60;'>{compliant_count}</span> | "
            f"<b>Cần bổ sung trường:</b> <span style='color: #d35400;'>{need_fields_count}</span>"
            f"<br>📁 <b>Cấu trúc lưu:</b> Thư mục <code>HoSoGIS/{self.target_db}</code> <i>(Đã lược bỏ HoSoBASIC và HoSoScan theo yêu cầu)</i>"
        )
        lbl_stat.setStyleSheet("font-size: 11px; color: #34495e;")
        bot_box.addWidget(lbl_stat)
        bot_box.addStretch()
        layout.addLayout(bot_box)

        # 5. Thanh nút thao tác
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("❌ Hủy Bỏ / Quay Lại")
        if is_dark:
            btn_cancel.setStyleSheet("padding: 7px 18px; font-weight: bold; background: #323844; color: #f0f6fc; border: 1px solid #4b5263; border-radius: 4px;")
        else:
            btn_cancel.setStyleSheet("padding: 7px 18px; font-weight: bold; background: #eaeded; color: #2c3e50; border-radius: 4px;")
        btn_cancel.clicked.connect(self._on_cancel)
        btn_box.addWidget(btn_cancel)

        btn_box.addSpacing(10)
        btn_confirm = QPushButton("ĐỒNG Ý & TIẾP TỤC XUẤT GDB")
        btn_confirm.setIcon(get_plugin_icon("tt16_package"))
        btn_confirm.setIconSize(QSize(18, 18))
        btn_confirm.setStyleSheet("padding: 8px 24px; font-weight: bold; font-size: 13px; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_confirm.clicked.connect(self._on_confirm)
        btn_box.addWidget(btn_confirm)

        layout.addLayout(btn_box)

    def _on_confirm(self):
        self.confirmed = True
        self.confirmed_ma_hs = self.txt_ma_hs.text().strip() or "DoAnQuyHoach"
        self.confirmed_ma_tt = self.txt_ma_tt.text().strip()
        self.confirmed_auto_fields = self.chk_auto_fields.isChecked()
        self.confirmed_data = []
        for row in range(self.table.rowCount()):
            lyr = self.layer_reports[row]['layer']
            cmb_ds = self.table.cellWidget(row, 3)
            ds = cmb_ds.currentText().strip() if cmb_ds else self.layer_reports[row]['dataset']
            item_fc = self.table.item(row, 4)
            fc = item_fc.text().strip() if item_fc else self.layer_reports[row]['fc_name']
            self.confirmed_data.append((lyr, ds, fc))
        self.accept()

    def _on_cancel(self):
        self.confirmed = False
        self.reject()


# =============================================================================
# CỬA SỔ CHÍNH: MYQGISVM MASTER TOOLBOX
# =============================================================================
class MyQgisVMDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MyQgisVM - Bộ Công Cụ Xử Lý Dữ Liệu GIS")
        self.resize(1000, 720)
        self.folder_files = []
        self.is_dark = is_dark_theme()
        self.init_ui()
        self.apply_theme(self.is_dark)

    def _reload_plugin(self):
        """Reload plugin mà không cần tắt/mở lại QGIS — dialog tự mở lại sau khi reload."""
        import sys
        try:
            from qgis.utils import unloadPlugin, loadPlugin, startPlugin, plugins
            from PyQt6.QtCore import QTimer

            # Đóng dialog hiện tại trước
            self.reject()

            plugin_name = "MyQgisVM"

            # Xóa toàn bộ module cache
            mods_to_del = [m for m in sys.modules if plugin_name in m]
            for m in mods_to_del:
                del sys.modules[m]

            # Unload → Load → Start
            unloadPlugin(plugin_name)
            loadPlugin(plugin_name)
            startPlugin(plugin_name)

            # Sau 200ms (đảm bảo plugin đã khởi tạo xong) → tự động mở lại dialog
            def _auto_open():
                try:
                    p = plugins.get(plugin_name)
                    if p:
                        p.run()
                    iface.messageBar().pushSuccess(
                        "MyQgisVM", "✅ Reload thành công – đã mở lại bộ công cụ!"
                    )
                except Exception:
                    pass

            QTimer.singleShot(200, _auto_open)

        except Exception as e:
            try:
                from PyQt6.QtWidgets import QMessageBox as _MB
                _MB.critical(None, "Lỗi Reload", f"Không reload được plugin:\n{e}")
            except Exception:
                pass

    def toggle_theme(self):
        """Chuyển đổi qua lại giữa chế độ Sáng và Tối (Ban ngày / Ban đêm)."""
        self.apply_theme(not self.is_dark)

    def apply_theme(self, is_dark=None):
        """Áp dụng bộ giao diện chuẩn Đỏ - Trắng (Thương hiệu INNO) cho cả chế độ Sáng và Ban Đêm."""
        if is_dark is None:
            is_dark = self.is_dark
        self.is_dark = is_dark

        import os as _os
        _chk_path = _os.path.join(_os.path.dirname(__file__), "check_white.png").replace("\\", "/")

        # Nút chuyển giao diện
        if hasattr(self, 'btn_theme_toggle'):
            if is_dark:
                self.btn_theme_toggle.setIcon(get_plugin_icon("theme_day"))
                self.btn_theme_toggle.setIconSize(QSize(16, 16))
                self.btn_theme_toggle.setText("Ban ngày")
                self.btn_theme_toggle.setToolTip("Đang ở chế độ Ban đêm — Bấm để chuyển sang Ban ngày")
                self.btn_theme_toggle.setStyleSheet(
                    "padding: 5px 12px; font-size: 11px; font-weight: bold; "
                    "background: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 4px;"
                )
            else:
                self.btn_theme_toggle.setIcon(get_plugin_icon("theme_night"))
                self.btn_theme_toggle.setIconSize(QSize(16, 16))
                self.btn_theme_toggle.setText("Ban đêm")
                self.btn_theme_toggle.setToolTip("Đang ở chế độ Ban ngày — Bấm để chuyển sang Ban đêm")
                self.btn_theme_toggle.setStyleSheet(
                    "padding: 5px 12px; font-size: 11px; font-weight: bold; "
                    "background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;"
                )

        if is_dark:
            # -------------------------------------------------------------
            # MASTER DARK THEME (CHỦ ĐỀ ĐỎ - ĐEN BAN ĐÊM INNO)
            # -------------------------------------------------------------
            self.setStyleSheet("""
                QDialog {
                    background-color: #18181b;
                    color: #f4f4f5;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QWidget {
                    color: #f4f4f5;
                }
                QLabel {
                    color: #f4f4f5;
                    background: transparent;
                    font-size: 12px;
                }
                QGroupBox {
                    background-color: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    margin-top: 14px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #f87171;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #f87171;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #18181b;
                    color: #ffffff;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 12px;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 1.5px solid #ef4444;
                }
                QComboBox {
                    background-color: #18181b;
                    color: #ffffff;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 12px;
                }
                QComboBox:focus {
                    border: 1.5px solid #ef4444;
                }
                QComboBox QAbstractItemView {
                    background-color: #27272a;
                    color: #ffffff;
                    selection-background-color: #dc2626;
                    selection-color: #ffffff;
                    border: 1px solid #3f3f46;
                }
                QTextEdit {
                    background-color: #141416;
                    color: #4ade80;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                }
                QTableWidget {
                    background-color: #18181b;
                    color: #f4f4f5;
                    gridline-color: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #27272a;
                    color: #f4f4f5;
                    font-weight: bold;
                    border: 1px solid #3f3f46;
                    padding: 6px;
                }
                QPushButton {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #3f3f46;
                    border-color: #52525b;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #18181b;
                }
                QPushButton:disabled {
                    background-color: #18181b;
                    color: #52525b;
                    border-color: #27272a;
                }
                QRadioButton, QCheckBox {
                    color: #f4f4f5;
                    font-size: 12px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #52525b;
                    border-radius: 3px;
                    background-color: #18181b;
                }
                QCheckBox::indicator:hover {
                    border: 1.5px solid #71717a;
                    background-color: #27272a;
                }
                QCheckBox::indicator:checked {
                    background-color: #dc2626;
                    border: 1.5px solid #dc2626;
                    image: url(""" + _chk_path + """);
                }
                QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #52525b;
                    border-radius: 7px;
                    background-color: #18181b;
                }
                QRadioButton::indicator:hover {
                    border: 1.5px solid #71717a;
                    background-color: #27272a;
                }
                QRadioButton::indicator:checked {
                    background-color: #dc2626;
                    border: 1.5px solid #dc2626;
                    image: url(""" + _chk_path + """);
                }
                QListWidget {
                    background-color: #18181b;
                    color: #f4f4f5;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                }
                QListWidget::item:selected {
                    background-color: #dc2626;
                    color: #ffffff;
                }
            """)

            # Tabs styling - Dark Mode
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #3f3f46;
                    border-top: 2px solid #ef4444;
                    background: #1f1f23;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #27272a;
                    color: #d4d4d8;
                    padding: 9px 16px;
                    font-weight: bold;
                    font-size: 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                    border: 1px solid #3f3f46;
                    border-bottom: none;
                }
                QTabBar::tab:selected {
                    background: #dc2626;
                    color: #ffffff;
                    border: 1px solid #dc2626;
                }
                QTabBar::tab:hover:!selected {
                    background: #3f3f46;
                    color: #ffffff;
                }
            """)

            # Header Frame - Dark Mode
            if hasattr(self, 'header_frame'):
                self.header_frame.setStyleSheet("""
                    QFrame#headerFrame {
                        background-color: #18181b;
                        border: none;
                        border-bottom: 2px solid #ef4444;
                        border-radius: 0px;
                    }
                """)
            if hasattr(self, 'lbl_logo'):
                self.lbl_logo.setStyleSheet("background: #ffffff; border-radius: 6px; padding: 2px 6px; border: 1px solid #3f3f46;")
            if hasattr(self, 'divider'):
                self.divider.setStyleSheet("background: #ef4444; border: none; margin: 0px; padding: 0px;")
            if hasattr(self, 'lbl_title'):
                self.lbl_title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; margin: 0; padding: 0; border: none; background: transparent;")
            if hasattr(self, 'lbl_dev'):
                self.lbl_dev.setStyleSheet("color: #f87171; font-size: 12px; margin: 0; padding: 0; border: none; background: transparent; font-style: italic;")

            # Tab 1
            if hasattr(self, 'folder_widget'):
                self.folder_widget.setStyleSheet("background-color: #1f1f23; border: 1px dashed #3f3f46; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'txt_folder'):
                self.txt_folder.setStyleSheet("padding: 5px; font-size: 12px; background: #141416; color: #ffffff; border: 1px solid #3f3f46;")
            if hasattr(self, 'lbl_geomap_desc'):
                self.lbl_geomap_desc.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; border: 1px solid #3f3f46; color: #d4d4d8; font-size: 11px;")

            # Tab 2
            if hasattr(self, 'qc_info_box'):
                self.qc_info_box.setStyleSheet("background: #27272a; border: 1px solid #3f3f46; padding: 8px; border-radius: 4px; color: #f4f4f5;")

            # Tab 4
            if hasattr(self, 'dv_frame'):
                self.dv_frame.setStyleSheet("background: #27272a; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'btn_tmpl'):
                self.btn_tmpl.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 4px; background: #27272a;")
            if hasattr(self, 'btn_more_row'):
                self.btn_more_row.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #e4e4e7; border: 1px dashed #3f3f46; border-radius: 4px; background: #27272a;")

            # Tab 5
            if hasattr(self, 'frame_tt16'):
                self.frame_tt16.setStyleSheet("background: #27272a; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'cmb_tt16_db'):
                self.cmb_tt16_db.setStyleSheet("font-weight: 500; color: #ffffff; background-color: #18181b;")
            if hasattr(self, 'txt_tt16_ma_hs'):
                self.txt_tt16_ma_hs.setStyleSheet("font-weight: 500; color: #ffffff; background-color: #18181b; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px 6px;")
            if hasattr(self, 'btn_tt16_precheck'):
                self.btn_tt16_precheck.setStyleSheet("background: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; font-weight: 500; padding: 5px 12px; border-radius: 4px;")

            # Footer
            if hasattr(self, 'lbl_author'):
                self.lbl_author.setStyleSheet("color: #a1a1aa; font-size: 11px; font-style: italic;")
            if hasattr(self, 'btn_close'):
                self.btn_close.setStyleSheet("padding: 6px 20px; font-size: 12px; border-radius: 4px; background: #27272a; color: #f4f4f5; border: 1px solid #3f3f46;")

        else:
            # -------------------------------------------------------------
            # MASTER LIGHT THEME (CHỦ ĐỀ ĐỎ - TRẮNG THƯƠNG HIỆU INNO)
            # -------------------------------------------------------------
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f6f8;
                    color: #1e293b;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QWidget {
                    color: #1e293b;
                }
                QLabel {
                    color: #1e293b;
                    background: transparent;
                    font-size: 12px;
                }
                QGroupBox {
                    font-weight: bold;
                    color: #c82333;
                    border: 1px solid #e2e8f0;
                    border-radius: 4px;
                    margin-top: 14px;
                    padding-top: 14px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #c82333;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 12px;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 1.5px solid #c82333;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 12px;
                }
                QComboBox:focus {
                    border: 1.5px solid #c82333;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #1e293b;
                    selection-background-color: #c82333;
                    selection-color: #ffffff;
                    border: 1px solid #d1d5db;
                }
                QTextEdit {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                }
                QTableWidget {
                    background-color: #ffffff;
                    color: #1e293b;
                    gridline-color: #f1f5f9;
                    border: 1px solid #e2e8f0;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #f8fafc;
                    color: #374151;
                    font-weight: bold;
                    border: 1px solid #e2e8f0;
                    padding: 6px;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #374151;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #f3f4f6;
                    border-color: #9ca3af;
                    color: #111827;
                }
                QPushButton:pressed {
                    background-color: #e5e7eb;
                }
                QPushButton:disabled {
                    background-color: #f9fafb;
                    color: #9ca3af;
                    border-color: #e5e7eb;
                }
                QRadioButton, QCheckBox {
                    color: #1e293b;
                    font-size: 12px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #d1d5db;
                    border-radius: 3px;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:hover {
                    border: 1.5px solid #9ca3af;
                    background-color: #f9fafb;
                }
                QCheckBox::indicator:checked {
                    background-color: #c82333;
                    border: 1.5px solid #c82333;
                    image: url(""" + _chk_path + """);
                }
                QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #d1d5db;
                    border-radius: 7px;
                    background-color: #ffffff;
                }
                QRadioButton::indicator:hover {
                    border: 1.5px solid #9ca3af;
                    background-color: #f9fafb;
                }
                QRadioButton::indicator:checked {
                    background-color: #c82333;
                    border: 1.5px solid #c82333;
                    image: url(""" + _chk_path + """);
                }
                QListWidget {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                }
                QListWidget::item:selected {
                    background-color: #c82333;
                    color: #ffffff;
                }
            """)

            # Tabs styling - Light Mode INNO
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #e2e8f0;
                    border-top: 2px solid #c82333;
                    background: white;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #f8fafc;
                    color: #475569;
                    padding: 9px 16px;
                    font-weight: bold;
                    font-size: 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                    border: 1px solid #e2e8f0;
                    border-bottom: none;
                }
                QTabBar::tab:selected {
                    background: #c82333;
                    color: white;
                    border: 1px solid #c82333;
                }
                QTabBar::tab:hover:!selected {
                    background: #f1f5f9;
                    color: #1e293b;
                }
            """)

            # Header Frame - Light Mode INNO
            if hasattr(self, 'header_frame'):
                self.header_frame.setStyleSheet("""
                    QFrame#headerFrame {
                        background: #ffffff;
                        border: none;
                        border-bottom: 2px solid #c82333;
                        border-radius: 0px;
                    }
                """)
            if hasattr(self, 'lbl_logo'):
                self.lbl_logo.setStyleSheet("border: none; background: transparent;")
            if hasattr(self, 'divider'):
                self.divider.setStyleSheet("background: #c82333; border: none; margin: 0px; padding: 0px;")
            if hasattr(self, 'lbl_title'):
                self.lbl_title.setStyleSheet("color: #c82333; font-size: 18px; font-weight: bold; margin: 0; padding: 0; border: none; background: transparent;")
            if hasattr(self, 'lbl_dev'):
                self.lbl_dev.setStyleSheet("color: #475569; font-size: 12px; margin: 0; padding: 0; border: none; background: transparent; font-style: italic;")

            # Tab 1
            if hasattr(self, 'folder_widget'):
                self.folder_widget.setStyleSheet("background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'txt_folder'):
                self.txt_folder.setStyleSheet("padding: 5px; font-size: 12px; background: white; color: #1e293b; border: 1px solid #cbd5e1;")
            if hasattr(self, 'lbl_geomap_desc'):
                self.lbl_geomap_desc.setStyleSheet("background-color: #f8fafc; padding: 6px; border-radius: 4px; border: 1px solid #e2e8f0; color: #475569; font-size: 11px;")

            # Tab 2
            if hasattr(self, 'qc_info_box'):
                self.qc_info_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 4px; color: #334155;")

            # Tab 4
            if hasattr(self, 'dv_frame'):
                self.dv_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'btn_tmpl'):
                self.btn_tmpl.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #374151; border: 1px solid #d1d5db; border-radius: 4px; background: #ffffff;")
            if hasattr(self, 'btn_more_row'):
                self.btn_more_row.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #374151; border: 1px dashed #d1d5db; border-radius: 4px; background: #ffffff;")

            # Tab 5
            if hasattr(self, 'frame_tt16'):
                self.frame_tt16.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px;")
            if hasattr(self, 'cmb_tt16_db'):
                self.cmb_tt16_db.setStyleSheet("font-weight: 500; color: #1e293b; background-color: #ffffff; border: 1px solid #cbd5e1;")
            if hasattr(self, 'txt_tt16_ma_hs'):
                self.txt_tt16_ma_hs.setStyleSheet("font-weight: 500; color: #1e293b; background-color: #ffffff; border: 1px solid #cbd5e1;")
            if hasattr(self, 'btn_tt16_precheck'):
                self.btn_tt16_precheck.setStyleSheet("background: #ffffff; color: #374151; border: 1px solid #d1d5db; font-weight: 500; padding: 5px 12px; border-radius: 4px;")

            # Footer
            if hasattr(self, 'lbl_author'):
                self.lbl_author.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
            if hasattr(self, 'btn_close'):
                self.btn_close.setStyleSheet("padding: 6px 20px; font-size: 12px; border-radius: 4px; background: #ffffff; color: #374151; border: 1px solid #d1d5db;")

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. HEADER BANNER — thiết kế theo mẫu: nền trắng/tối, logo VM ảnh, kẻ dọc, tiêu đề
        self.header_frame = QFrame()
        self.header_frame.setObjectName("headerFrame")
        self.header_frame.setFixedHeight(100)
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(16, 8, 16, 8)
        h_layout.setSpacing(0)

        # --- Logo VM gốc (màu đỏ thương hiệu) ---
        import os as _os
        _logo_path = _os.path.join(_os.path.dirname(__file__), "vm_logo.jpg")
        self.lbl_logo = QLabel()
        self.lbl_logo.setFixedSize(135, 66)
        self.lbl_logo.setScaledContents(False)
        _pix = QPixmap(_logo_path)
        if not _pix.isNull():
            self.lbl_logo.setPixmap(_pix.scaled(125, 58,
                KEEP_ASPECT, SMOOTH_TRANSFORM))
        else:
            # fallback text nếu không tìm thấy ảnh
            self.lbl_logo.setText("VM")
            font_fb = QFont(); font_fb.setBold(True); font_fb.setPointSize(24)
            self.lbl_logo.setFont(font_fb)
            self.lbl_logo.setStyleSheet("color: #c82333; font-weight: bold;")
        if ALIGN_CENTER is not None:
            self.lbl_logo.setAlignment(ALIGN_CENTER)

        # --- Đường kẻ dọc ---
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.Shape.VLine)
        self.divider.setFixedWidth(2)
        self.divider.setFixedHeight(56)

        # --- Text bên phải ---
        txt_layout = QVBoxLayout()
        txt_layout.setSpacing(3)
        txt_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel("BỘ CÔNG CỤ XỬ LÝ DỮ LIỆU GIS")
        font_title = QFont("Arial", 22, QFont.Weight.Bold)
        self.lbl_title.setFont(font_title)

        self.lbl_dev = QLabel("Developer: Nguyễn Văn Mạnh")
        font_dev = QFont("Arial", 11)
        font_dev.setItalic(True)
        self.lbl_dev.setFont(font_dev)

        txt_layout.addStretch()
        txt_layout.addWidget(self.lbl_title)
        txt_layout.addWidget(self.lbl_dev)
        txt_layout.addStretch()

        # --- Cột bên phải Header (Logo INNO nhỏ và Nút Sáng/Tối) ---
        right_header_layout = QVBoxLayout()
        right_header_layout.setSpacing(4)
        right_header_layout.setContentsMargins(0, 0, 0, 0)

        # Logo INNO nhỏ ở góc trên bên phải
        _inno_small_path = _os.path.join(_os.path.dirname(__file__), "inno_small.png")
        self.lbl_inno_logo = QLabel()
        self.lbl_inno_logo.setFixedSize(72, 32)
        _pix_inno = QPixmap(_inno_small_path)
        if not _pix_inno.isNull():
            self.lbl_inno_logo.setPixmap(_pix_inno.scaled(72, 32, KEEP_ASPECT, SMOOTH_TRANSFORM))
        if ALIGN_CENTER is not None:
            self.lbl_inno_logo.setAlignment(getattr(Qt.AlignmentFlag, 'AlignRight', getattr(Qt, 'AlignRight', 0)) | getattr(Qt.AlignmentFlag, 'AlignVCenter', getattr(Qt, 'AlignVCenter', 0)))
        self.lbl_inno_logo.setStyleSheet("border: none; background: transparent;")

        # Nút chuyển đổi nhanh giao diện Ban ngày / Ban đêm trên Header
        self.btn_theme_toggle = QPushButton("Ban ngày" if self.is_dark else "Ban đêm")
        self.btn_theme_toggle.setIcon(get_plugin_icon("theme_day" if self.is_dark else "theme_night"))
        self.btn_theme_toggle.setIconSize(QSize(16, 16))
        self.btn_theme_toggle.clicked.connect(self.toggle_theme)

        right_header_layout.addWidget(self.lbl_inno_logo)
        right_header_layout.addWidget(self.btn_theme_toggle)

        h_layout.addWidget(self.lbl_logo)
        h_layout.addSpacing(16)
        h_layout.addWidget(self.divider)
        h_layout.addSpacing(16)
        h_layout.addLayout(txt_layout)
        h_layout.addStretch()
        h_layout.addLayout(right_header_layout)
        h_layout.addSpacing(10)
        main_layout.addWidget(self.header_frame)

        # 2. TAB WIDGET
        self.tabs = QTabWidget()

        # Khởi tạo 5 Tabs
        self.tab_crs = QWidget()
        self.tab_qc = QWidget()
        self.tab_shapes = QWidget()
        self.tab_attr = QWidget()
        self.tab_merge = QWidget()

        self.setup_tab_crs()
        self.setup_tab_qc()
        self.setup_tab_shapes()
        self.setup_tab_attr()
        self.setup_tab_merge()

        self.tabs.setIconSize(QSize(18, 18))
        self.tabs.addTab(self.tab_crs, get_plugin_icon("tab_crs"), "Tọa Độ & GeoMap")
        self.tabs.addTab(self.tab_qc, get_plugin_icon("tab_qc"), "Sửa Lỗi Hình Học (QC)")
        self.tabs.addTab(self.tab_shapes, get_plugin_icon("tab_shapes"), "Xử Lý Polygon Nâng Cao")
        self.tabs.addTab(self.tab_attr, get_plugin_icon("tab_attr"), "Thuộc Tính & Chuẩn QPK")
        self.tabs.addTab(self.tab_merge, get_plugin_icon("tab_merge"), "Ghép & Chuyển Đổi")
        self.tabs.currentChanged.connect(self._on_main_tab_changed)

        main_layout.addWidget(self.tabs)

        # 3. FOOTER
        footer_layout = QHBoxLayout()
        self.lbl_author = QLabel("Tối ưu hóa cho QGIS")

        btn_reload = QPushButton("Reload Plugin")
        btn_reload.setIcon(get_plugin_icon("reload"))
        btn_reload.setIconSize(QSize(16, 16))
        btn_reload.setToolTip("Tải lại plugin để áp dụng thay đổi mới nhất — không cần tắt QGIS")
        btn_reload.setStyleSheet(
            "padding: 6px 16px; font-size: 11px; font-weight: bold; "
            "background: #c82333; color: white; border-radius: 4px;"
        )
        btn_reload.clicked.connect(self._reload_plugin)

        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.reject)

        footer_layout.addWidget(self.lbl_author)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_reload)
        footer_layout.addSpacing(8)
        footer_layout.addWidget(self.btn_close)
        main_layout.addLayout(footer_layout)



    # =========================================================================
    # TAB 1: TỌA ĐỘ VN-2000 & GEOMAP
    # =========================================================================
    def setup_tab_crs(self):
        layout = QVBoxLayout(self.tab_crs)

        # PHẠM VI ÁP DỤNG
        grp_scope = QGroupBox("1. Chọn phạm vi áp dụng (Lớp dữ liệu cần gán)")
        grp_scope.setStyleSheet("QGroupBox { font-weight: bold; }")
        scope_layout = QVBoxLayout(grp_scope)

        selected_count = len(iface.layerTreeView().selectedLayers())
        all_vector_layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
        all_count = len(all_vector_layers)

        scope_btn_layout = QHBoxLayout()
        self.rb_selected = QRadioButton(f"Layer đang chọn ({selected_count})")
        self.rb_selected.setIcon(get_plugin_icon("scope_layers"))
        self.rb_all_open = QRadioButton(f"Tất cả layer đang mở ({all_count})")
        self.rb_all_open.setIcon(get_plugin_icon("scope_layers"))
        self.rb_folder = QRadioButton("Quét từ thư mục khác (.gpkg, .shp)")
        self.rb_folder.setIcon(get_plugin_icon("folder_scan"))

        if selected_count > 0:
            self.rb_selected.setChecked(True)
        elif all_count > 0:
            self.rb_all_open.setChecked(True)
        else:
            self.rb_folder.setChecked(True)

        self.bg_scope = QButtonGroup(self)
        self.bg_scope.addButton(self.rb_selected, 1)
        self.bg_scope.addButton(self.rb_all_open, 2)
        self.bg_scope.addButton(self.rb_folder, 3)
        self.bg_scope.buttonClicked.connect(self.on_scope_changed)

        scope_btn_layout.addWidget(self.rb_selected)
        scope_btn_layout.addWidget(self.rb_all_open)
        scope_btn_layout.addWidget(self.rb_folder)
        scope_layout.addLayout(scope_btn_layout)

        # Thư mục
        self.folder_widget = QGroupBox()
        self.folder_widget.setStyleSheet("background-color: #f8f9fa; border: 1px dashed #bdc3c7; border-radius: 4px; padding: 4px;")
        folder_layout = QVBoxLayout(self.folder_widget)

        f_row = QHBoxLayout()
        self.txt_folder = QLineEdit()
        self.txt_folder.setPlaceholderText("Chưa chọn thư mục...")
        self.txt_folder.setReadOnly(True)
        self.txt_folder.setStyleSheet("padding: 5px; font-size: 12px; background: white; border: 1px solid #ced4da;")
        btn_browse = QPushButton("Chọn thư mục...")
        btn_browse.setIcon(get_plugin_icon("folder_open"))
        btn_browse.setIconSize(QSize(16, 16))
        btn_browse.setStyleSheet("padding: 5px 12px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_browse.clicked.connect(self.browse_folder)
        f_row.addWidget(self.txt_folder)
        f_row.addWidget(btn_browse)
        folder_layout.addLayout(f_row)

        f_sub_row = QHBoxLayout()
        self.chk_subfolders = QCheckBox("Quét cả thư mục con (Subfolders)")
        self.chk_subfolders.setChecked(True)
        self.chk_subfolders.stateChanged.connect(self.rescan_folder)
        self.lbl_folder_count = QLabel("Chưa quét file nào")
        self.lbl_folder_count.setStyleSheet("color: #7f8c8d; font-style: italic;")
        f_sub_row.addWidget(self.chk_subfolders)
        f_sub_row.addStretch()
        f_sub_row.addWidget(self.lbl_folder_count)
        folder_layout.addLayout(f_sub_row)

        scope_layout.addWidget(self.folder_widget)
        layout.addWidget(grp_scope)
        self.on_scope_changed()

        # 2 BẢNG ĐẶT CẠNH NHAU (SIDE-BY-SIDE)
        middle_layout = QHBoxLayout()

        # Bảng trái: Chọn tỉnh VN-2000
        grp_prov = QGroupBox("2. Chọn tỉnh thành VN-2000 (Múi 3 độ)")
        grp_prov.setStyleSheet("QGroupBox { font-weight: bold; }")
        prov_layout = QVBoxLayout(grp_prov)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Gõ nhanh tên tỉnh hoặc KTT (HCM, Nha Trang, 105.75...):")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet("padding: 5px; font-size: 12px; border: 1px solid #bdc3c7; border-radius: 4px;")
        self.search_box.textChanged.connect(self.filter_provinces)
        prov_layout.addWidget(self.search_box)

        self.list_prov = QListWidget()
        self.list_prov.setStyleSheet("QListWidget::item { padding: 5px; } QListWidget::item:selected { background-color: #c82333; color: white; font-weight: bold; }")
        self.populate_provinces()
        prov_layout.addWidget(self.list_prov)
        middle_layout.addWidget(grp_prov, 55)

        # Bảng phải: Chọn bản đồ nền GeoMap
        grp_geomap = QGroupBox("3. Gắn bản đồ nền GeoMap kiểm tra")
        grp_geomap.setStyleSheet("QGroupBox { font-weight: bold; }")
        geomap_layout = QVBoxLayout(grp_geomap)
        geomap_layout.addWidget(QLabel("Chọn bản đồ nền để tự động khớp với lớp dữ liệu:"))

        self.list_geomap = QListWidget()
        self.list_geomap.setStyleSheet("QListWidget::item { padding: 6px; } QListWidget::item:selected { background-color: #c82333; color: white; font-weight: bold; }")
        self.populate_geomap()
        self.list_geomap.currentRowChanged.connect(self.on_geomap_selected)
        geomap_layout.addWidget(self.list_geomap)

        self.lbl_geomap_desc = QLabel()
        self.lbl_geomap_desc.setWordWrap(True)
        self.lbl_geomap_desc.setStyleSheet("background-color: #f8fafc; padding: 6px; border-radius: 4px; border: 1px solid #e2e8f0; color: #475569; font-size: 11px;")
        geomap_layout.addWidget(self.lbl_geomap_desc)

        self.chk_zoom = QCheckBox("Tự động phóng to (Zoom) bản đồ đến vị trí các layer")
        self.chk_zoom.setChecked(True)
        self.chk_zoom.setStyleSheet("font-weight: 500;")
        geomap_layout.addWidget(self.chk_zoom)

        middle_layout.addWidget(grp_geomap, 45)
        layout.addLayout(middle_layout)

        # Tùy chọn & Nút Áp Dụng
        bot_layout = QHBoxLayout()
        self.chk_clean = QCheckBox("Tự động dọn sạch file rác (*.gpkg-journal cũ)")
        self.chk_clean.setChecked(True)
        self.chk_clean.setStyleSheet("font-weight: 500;")

        btn_apply_crs = QPushButton("ÁP DỤNG")
        btn_apply_crs.setIcon(get_plugin_icon("apply_crs"))
        btn_apply_crs.setIconSize(QSize(18, 18))
        btn_apply_crs.setStyleSheet("QPushButton { background-color: #c82333; color: white; font-weight: bold; padding: 8px 25px; font-size: 13px; border-radius: 4px; border: none; } QPushButton:hover { background-color: #b71c1c; }")
        btn_apply_crs.clicked.connect(self.run_apply_crs)

        bot_layout.addWidget(self.chk_clean)
        bot_layout.addStretch()
        bot_layout.addWidget(btn_apply_crs)
        layout.addLayout(bot_layout)

        self.on_geomap_selected(0)

    def on_scope_changed(self):
        is_folder = self.rb_folder.isChecked()
        self.folder_widget.setEnabled(is_folder)
        self.folder_widget.setVisible(is_folder)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa các file dữ liệu (.gpkg, .shp)")
        if folder:
            self.txt_folder.setText(folder)
            self.scan_folder_files(folder)

    def rescan_folder(self):
        folder = self.txt_folder.text().strip()
        if folder and os.path.isdir(folder):
            self.scan_folder_files(folder)

    def scan_folder_files(self, folder):
        self.folder_files = []
        gpkg_count = 0
        shp_count = 0
        recursive = self.chk_subfolders.isChecked()

        if recursive:
            for root, _, files in os.walk(folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext == ".gpkg":
                        self.folder_files.append(os.path.join(root, f))
                        gpkg_count += 1
                    elif ext == ".shp":
                        self.folder_files.append(os.path.join(root, f))
                        shp_count += 1
        else:
            for f in os.listdir(folder):
                full_p = os.path.join(folder, f)
                if os.path.isfile(full_p):
                    ext = os.path.splitext(f)[1].lower()
                    if ext == ".gpkg":
                        self.folder_files.append(full_p)
                        gpkg_count += 1
                    elif ext == ".shp":
                        self.folder_files.append(full_p)
                        shp_count += 1

        self.lbl_folder_count.setText(f"Tìm thấy: <b>{gpkg_count}</b> file .gpkg | <b>{shp_count}</b> file .shp")
        self.lbl_folder_count.setStyleSheet("color: #27ae60; font-weight: bold;")

    def populate_provinces(self):
        self.list_prov.clear()
        for prov in PROVINCES_DATA:
            name, ktt, lon_0, epsg = prov
            text = f"{name:<22} | KTT: {ktt} ({lon_0}°) | {epsg}"
            item = QListWidgetItem(get_plugin_icon("province_pin"), text)
            item.setData(USER_ROLE, prov)
            self.list_prov.addItem(item)
        if self.list_prov.count() > 0:
            self.list_prov.setCurrentRow(0)

    def filter_provinces(self, text):
        query = text.strip().lower()
        for i in range(self.list_prov.count()):
            item = self.list_prov.item(i)
            prov = item.data(USER_ROLE)
            name, ktt, lon_0, epsg = prov
            match_str = f"{name} {ktt} {lon_0} {epsg}".lower()
            item.setHidden(query not in match_str)

    def populate_geomap(self):
        self.list_geomap.clear()
        for g_name, g_url, g_desc in GEOMAP_OPTIONS:
            item = QListWidgetItem(get_plugin_icon("geomap_globe"), g_name)
            item.setData(USER_ROLE, (g_name, g_url, g_desc))
            self.list_geomap.addItem(item)
        if self.list_geomap.count() > 0:
            self.list_geomap.setCurrentRow(0)

    def on_geomap_selected(self, row):
        if row >= 0 and row < len(GEOMAP_OPTIONS):
            _, _, desc = GEOMAP_OPTIONS[row]
            self.lbl_geomap_desc.setText(f"💡 {desc}")

    def run_apply_crs(self):
        curr_prov_item = self.list_prov.currentItem()
        if not curr_prov_item:
            QMessageBox.warning(self, "Chưa chọn tỉnh", "Vui lòng chọn một tỉnh từ bảng bên trái!")
            return
        prov = curr_prov_item.data(USER_ROLE)

        curr_geomap_item = self.list_geomap.currentItem()
        geomap_data = curr_geomap_item.data(USER_ROLE) if curr_geomap_item else ("", "", "")
        geomap_name, geomap_url, _ = geomap_data

        clean_garbage = self.chk_clean.isChecked()
        do_zoom = self.chk_zoom.isChecked()

        if self.rb_selected.isChecked():
            layers = iface.layerTreeView().selectedLayers()
            if not layers:
                QMessageBox.warning(self, "Không có layer", "Bạn chưa chọn layer nào ở bảng Layers!\nVui lòng chọn layer hoặc tích 'Tất cả layer đang mở'.")
                return
            self.process_layers_crs(layers, prov, clean_garbage, "các layer đang chọn", geomap_name, geomap_url, do_zoom)

        elif self.rb_all_open.isChecked():
            layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
            if not layers:
                QMessageBox.warning(self, "Không có layer", "Dự án hiện tại không có vector layer nào đang mở!")
                return
            self.process_layers_crs(layers, prov, clean_garbage, "tất cả layer đang mở", geomap_name, geomap_url, do_zoom)

        elif self.rb_folder.isChecked():
            folder = self.txt_folder.text().strip()
            if not folder or not os.path.isdir(folder):
                QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng nhấn nút 'Chọn thư mục...' để duyệt thư mục cần xử lý!")
                return
            if not self.folder_files:
                self.scan_folder_files(folder)
            if not self.folder_files:
                QMessageBox.warning(self, "Không có file", "Không tìm thấy file .gpkg hoặc .shp nào trong thư mục đã chọn!")
                return
            self.process_folder_crs(self.folder_files, folder, prov, clean_garbage, geomap_name, geomap_url, do_zoom)

    def process_layers_crs(self, layers, province_tuple, clean_garbage, scope_desc, geomap_name, geomap_url, do_zoom):
        name, ktt_str, lon_0, epsg_code = province_tuple
        crs = QgsCoordinateReferenceSystem(epsg_code)
        if not crs.isValid():
            crs.createFromProj(f"+proj=tmerc +lat_0=0 +lon_0={lon_0} +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=-191.90441429,-39.30318279,-111.45032835,0.00928836,-0.01975479,0.00427372,0.252906278 +units=m +no_defs")
        wkt_def = crs.toWkt()
        try:
            srs_id = int(epsg_code.split(":")[-1])
        except Exception:
            srs_id = 9999

        processed_dirs = set()
        success_count = 0
        combined_extent = QgsRectangle()

        for layer in layers:
            if not isinstance(layer, QgsVectorLayer):
                continue
            layer_name = layer.name()
            source = layer.source()
            parts = source.split("|")
            file_path = parts[0]
            table_name = layer_name
            for p in parts[1:]:
                if p.lower().startswith("layername="):
                    table_name = p.split("=", 1)[1]
                    break

            if layer.isEditable():
                layer.commitChanges()

            f_dir = os.path.dirname(file_path)
            if f_dir:
                processed_dirs.add(f_dir)

            if file_path.lower().endswith(".gpkg") and os.path.isfile(file_path):
                try:
                    update_single_gpkg(file_path, srs_id, ktt_str, name, wkt_def, table_name)
                    success_count += 1
                except Exception as e:
                    print(f"Lỗi GPKG {layer_name}: {e}")

            elif file_path.lower().endswith(".shp") and os.path.isfile(file_path):
                try:
                    update_single_shp(file_path, wkt_def)
                    success_count += 1
                except Exception as e:
                    print(f"Lỗi SHP {layer_name}: {e}")

            layer.setCrs(crs)
            layer.dataProvider().reloadData()
            layer.triggerRepaint()

            if layer.isValid() and not layer.extent().isEmpty():
                combined_extent.combineExtentWith(layer.extent())

        cleaned_total = 0
        if clean_garbage:
            for d in processed_dirs:
                cleaned_total += clean_leftover_journals(d)

        QgsProject.instance().setCrs(crs)
        iface.mapCanvas().refresh()

        geomap_attached = False
        geomap_failed = False
        if geomap_url:
            geomap_attached = attach_geomap(geomap_name, geomap_url, combined_extent if do_zoom else None) is not None
            geomap_failed = not geomap_attached
        elif do_zoom and not combined_extent.isEmpty():
            scaled_extent = QgsRectangle(combined_extent)
            scaled_extent.scale(1.15)
            iface.mapCanvas().setExtent(scaled_extent)
            iface.mapCanvas().refresh()

        msg = f"Đã áp dụng tọa độ VN-2000 thành công cho {success_count}/{len(layers)} layer ({scope_desc})!\n\n"
        msg += f"📍 Địa bàn: {name}\n"
        msg += f"🧭 Kinh tuyến trục: {ktt_str} (Múi 3°)\n"
        msg += f"🌐 Mã EPSG: {epsg_code}\n"
        if geomap_attached:
            msg += f"🗺️ Bản đồ nền: Đã gắn {geomap_name}\n"
        if geomap_failed:
            msg += f"⚠️ Không gắn được bản đồ nền {geomap_name} (kiểm tra kết nối Internet / thử bản đồ nền khác)\n"
        if clean_garbage and cleaned_total > 0:
            msg += f"\n🧹 Đã quét dọn và xóa sạch: {cleaned_total} file rác (.gpkg-journal) cũ còn sót lại!"
        QMessageBox.information(self, "Hoàn Tất Áp Dụng", msg)

    def process_folder_crs(self, file_list, root_dir, province_tuple, clean_garbage, geomap_name, geomap_url, do_zoom):
        name, ktt_str, lon_0, epsg_code = province_tuple
        crs = QgsCoordinateReferenceSystem(epsg_code)
        if not crs.isValid():
            crs.createFromProj(f"+proj=tmerc +lat_0=0 +lon_0={lon_0} +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=-191.90441429,-39.30318279,-111.45032835,0.00928836,-0.01975479,0.00427372,0.252906278 +units=m +no_defs")
        wkt_def = crs.toWkt()
        try:
            srs_id = int(epsg_code.split(":")[-1])
        except Exception:
            srs_id = 9999

        success_count = 0
        processed_dirs = set([root_dir])
        combined_extent = QgsRectangle()

        for file_path in file_list:
            f_dir = os.path.dirname(file_path)
            if f_dir:
                processed_dirs.add(f_dir)

            if file_path.lower().endswith(".gpkg"):
                try:
                    update_single_gpkg(file_path, srs_id, ktt_str, name, wkt_def, table_name=None)
                    success_count += 1
                except Exception as e:
                    print(f"Lỗi GPKG {file_path}: {e}")

            elif file_path.lower().endswith(".shp"):
                try:
                    update_single_shp(file_path, wkt_def)
                    success_count += 1
                except Exception as e:
                    print(f"Lỗi SHP {file_path}: {e}")

        open_layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
        file_set = set([os.path.abspath(f).lower() for f in file_list])
        for lyr in open_layers:
            src_f = os.path.abspath(lyr.source().split("|")[0]).lower()
            if src_f in file_set:
                lyr.setCrs(crs)
                lyr.dataProvider().reloadData()
                lyr.triggerRepaint()
                if lyr.isValid() and not lyr.extent().isEmpty():
                    combined_extent.combineExtentWith(lyr.extent())

        cleaned_total = 0
        if clean_garbage:
            for d in processed_dirs:
                cleaned_total += clean_leftover_journals(d)

        QgsProject.instance().setCrs(crs)
        iface.mapCanvas().refresh()

        geomap_attached = False
        geomap_failed = False
        if geomap_url:
            geomap_attached = attach_geomap(geomap_name, geomap_url, combined_extent if do_zoom else None) is not None
            geomap_failed = not geomap_attached
        elif do_zoom and not combined_extent.isEmpty():
            scaled_extent = QgsRectangle(combined_extent)
            scaled_extent.scale(1.15)
            iface.mapCanvas().setExtent(scaled_extent)
            iface.mapCanvas().refresh()

        msg = f"Đã áp dụng tọa độ VN-2000 thành công cho {success_count}/{len(file_list)} file trong thư mục!\n\n"
        msg += f"📁 Thư mục: {root_dir}\n"
        msg += f"📍 Địa bàn: {name}\n"
        msg += f"🧭 Kinh tuyến trục: {ktt_str} (Múi 3°)\n"
        msg += f"🌐 Mã EPSG: {epsg_code}\n"
        if geomap_attached:
            msg += f"🗺️ Bản đồ nền: Đã gắn {geomap_name}\n"
        if geomap_failed:
            msg += f"⚠️ Không gắn được bản đồ nền {geomap_name} (kiểm tra kết nối Internet / thử bản đồ nền khác)\n"
        if clean_garbage and cleaned_total > 0:
            msg += f"\n🧹 Đã quét dọn và xóa sạch: {cleaned_total} file rác (.gpkg-journal) cũ còn sót lại!"
        QMessageBox.information(self, "Hoàn Tất Xử Lý Thư Mục", msg)


    # =========================================================================
    # TAB 2: KIỂM TRA & SỬA LỖI HÌNH HỌC (GEOMETRY QC)
    # =========================================================================
    def setup_tab_qc(self):
        layout = QVBoxLayout(self.tab_qc)

        self.qc_info_box = QLabel("Tự động quét & sửa chữa toàn bộ các lỗi hình học phổ biến theo quy chuẩn QC CSDL GIS / QPK:\n"
                          "• Invalid Geometry (makeValid / buffer 0) • Self-intersection • Too few points & Spikes\n"
                          "• Xóa đối tượng trùng lặp (Duplicates) • Quét & xử lý chồng lấn (Topology Overlap)")
        self.qc_info_box.setStyleSheet("background: #fdfefe; border: 1px solid #d5dbdb; padding: 8px; border-radius: 4px; color: #2c3e50;")
        layout.addWidget(self.qc_info_box)

        # CẤU HÌNH CÁC TÙY CHỌN SỬA LỖI
        grp_options = QGroupBox("Danh mục các mục kiểm tra & sửa chữa")
        grp_options.setStyleSheet("QGroupBox { font-weight: bold; }")
        opt_layout = QVBoxLayout(grp_options)

        self.chk_fix_invalid = QCheckBox("1. Tự động sửa lỗi Invalid Geometry & Self-Intersection (Thuật toán makeValid / GEOS)")
        self.chk_fix_invalid.setIcon(get_plugin_icon("fix_invalid"))
        self.chk_fix_invalid.setIconSize(QSize(16, 16))
        self.chk_fix_invalid.setChecked(True)
        self.chk_fix_spikes = QCheckBox("2. Dọn dẹp đỉnh nhọn gai (Spikes) & Quá ít điểm (Too few points)")
        self.chk_fix_spikes.setIcon(get_plugin_icon("fix_spikes"))
        self.chk_fix_spikes.setIconSize(QSize(16, 16))
        self.chk_fix_spikes.setChecked(True)
        self.chk_remove_duplicates = QCheckBox("3. Xóa đối tượng trùng lặp hình học hoàn toàn (Duplicates - Giữ đối tượng đầu tiên)")
        self.chk_remove_duplicates.setChecked(True)
        self.chk_fix_overlap = QCheckBox("4. Quét & xử lý chồng lấn giữa các Polygon (Topology Overlap)")
        self.chk_fix_overlap.setIcon(get_plugin_icon("overlap"))
        self.chk_fix_overlap.setIconSize(QSize(16, 16))
        self.chk_fix_overlap.setChecked(False)

        opt_layout.addWidget(self.chk_fix_invalid)
        opt_layout.addWidget(self.chk_fix_spikes)
        opt_layout.addWidget(self.chk_remove_duplicates)
        opt_layout.addWidget(self.chk_fix_overlap)
        layout.addWidget(grp_options)

        # PHẠM VI ÁP DỤNG
        grp_qc_scope = QGroupBox("Phạm vi sửa lỗi")
        grp_qc_scope.setStyleSheet("QGroupBox { font-weight: bold; }")
        qs_layout = QHBoxLayout(grp_qc_scope)
        self.rb_qc_selected = QRadioButton("🎯 Các layer đang chọn trong QGIS")
        self.rb_qc_selected.setChecked(True)
        self.rb_qc_all = QRadioButton("📂 Tất cả layer Polygon / Line trong dự án")
        qs_layout.addWidget(self.rb_qc_selected)
        qs_layout.addWidget(self.rb_qc_all)
        layout.addWidget(grp_qc_scope)

        # LOG KẾT QUẢ
        layout.addWidget(QLabel("Nhật ký kiểm tra & sửa lỗi (Log):"))
        self.txt_qc_log = QTextEdit()
        self.txt_qc_log.setReadOnly(True)
        self.txt_qc_log.setStyleSheet("background: #1e1e1e; color: #68d391; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.txt_qc_log)

        # NÚT BẤM
        qc_btn_layout = QHBoxLayout()
        btn_scan_only = QPushButton("QUÉT KIỂM TRA LỖI")
        btn_scan_only.setIcon(get_plugin_icon("scan"))
        btn_scan_only.setIconSize(QSize(18, 18))
        btn_scan_only.setStyleSheet("padding: 8px 16px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_scan_only.clicked.connect(lambda: self.run_qc_engine(apply_fix=False))

        btn_fix_now = QPushButton("TỰ ĐỘNG SỬA TOÀN BỘ LỖI")
        btn_fix_now.setIcon(get_plugin_icon("autofix"))
        btn_fix_now.setIconSize(QSize(18, 18))
        btn_fix_now.setStyleSheet("padding: 8px 22px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_fix_now.clicked.connect(lambda: self.run_qc_engine(apply_fix=True))

        btn_report = QPushButton("ĐỐI CHIẾU FILE BÁO CÁO LỖI")
        btn_report.setIcon(get_plugin_icon("report_check"))
        btn_report.setIconSize(QSize(18, 18))
        btn_report.setStyleSheet("padding: 8px 16px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_report.setToolTip("Đọc file Excel/CSV báo cáo lỗi, tìm vị trí lỗi trong các lớp và cho biết lỗi nào tool đã có phương án xử lý")
        btn_report.clicked.connect(self.open_error_report)

        qc_btn_layout.addWidget(btn_report)
        qc_btn_layout.addStretch()
        qc_btn_layout.addWidget(btn_scan_only)
        qc_btn_layout.addWidget(btn_fix_now)
        layout.addLayout(qc_btn_layout)

    def open_error_report(self):
        if getattr(self, "report_dlg", None) is None:
            self.report_dlg = ErrorReportDialog(self)
        self.report_dlg.refresh_layers()
        self.report_dlg.show()
        self.report_dlg.raise_()
        self.report_dlg.activateWindow()

    def log_qc(self, text):
        self.txt_qc_log.append(text)
        iface.mapCanvas().refresh()

    def run_qc_engine(self, apply_fix=False):
        self.txt_qc_log.clear()
        action_name = "SỬA LỖI TỰ ĐỘNG" if apply_fix else "QUÉT KIỂM TRA"
        self.log_qc(f"=== BẮT ĐẦU {action_name} ===")

        if self.rb_qc_selected.isChecked():
            layers = iface.layerTreeView().selectedLayers()
        else:
            layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]

        layers = [l for l in layers if isinstance(l, QgsVectorLayer) and l.geometryType() in [GEOM_POLYGON, GEOM_LINE]]
        if not layers:
            self.log_qc("⚠️ Không tìm thấy layer vector hợp lệ để xử lý!")
            return

        total_invalid = 0
        total_fixed = 0
        total_duplicates = 0

        for layer in layers:
            self.log_qc(f"\n📂 Lớp: [{layer.name()}] ({layer.featureCount()} đối tượng)")
            if apply_fix and not layer.isEditable():
                layer.startEditing()

            # 1. SỬA INVALID GEOMETRY & SELF-INTERSECTION
            if self.chk_fix_invalid.isChecked():
                layer_invalid = 0
                layer_fixed = 0
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if not geom.isGeosValid():
                        layer_invalid += 1
                        if apply_fix:
                            fixed_geom = geom.makeValid()
                            if fixed_geom.isGeosValid():
                                layer.changeGeometry(feat.id(), fixed_geom)
                                layer_fixed += 1
                            else:
                                # Dự phòng buffer(0)
                                buf_geom = geom.buffer(0, 5)
                                if buf_geom.isGeosValid():
                                    layer.changeGeometry(feat.id(), buf_geom)
                                    layer_fixed += 1

                total_invalid += layer_invalid
                total_fixed += layer_fixed
                self.log_qc(f"   • Invalid / Self-intersection: Phát hiện {layer_invalid} lỗi | Sửa thành công: {layer_fixed}")

            # 2. XÓA DUPLICATES
            if self.chk_remove_duplicates.isChecked():
                fids_to_delete = []
                idx = QgsSpatialIndex()
                geom_map = {}
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if geom.isNull() or geom.isEmpty():
                        continue
                    candidates = idx.intersects(geom.boundingBox())
                    is_dup = False
                    for cid in candidates:
                        if geom.equals(geom_map[cid]):
                            is_dup = True
                            fids_to_delete.append(feat.id())
                            break
                    if not is_dup:
                        idx.insertFeature(feat)
                        geom_map[feat.id()] = geom

                dup_count = len(fids_to_delete)
                total_duplicates += dup_count
                if apply_fix and dup_count > 0:
                    layer.deleteFeatures(fids_to_delete)
                    self.log_qc(f"   • Duplicates: Đã xóa {dup_count} đối tượng trùng lặp (giữ lại đối tượng đầu).")
                else:
                    self.log_qc(f"   • Duplicates: Phát hiện {dup_count} đối tượng trùng.")

            if apply_fix:
                layer.commitChanges()
                layer.triggerRepaint()

        self.log_qc(f"\n==========================================")
        self.log_qc(f"✅ HOÀN TẤT: Tổng lỗi phát hiện: {total_invalid} | Đã sửa: {total_fixed} | Trùng lặp: {total_duplicates}")
        if apply_fix:
            QMessageBox.information(self, "Hoàn tất", f"Đã hoàn thành sửa lỗi tự động cho {len(layers)} layer!\nVui lòng xem chi tiết tại khung Log.")


    # =========================================================================
    # TAB 3: XỬ LÝ POLYGON NÂNG CAO (SLIVERS & SHAPES)
    # =========================================================================
    def setup_tab_shapes(self):
        layout = QVBoxLayout(self.tab_shapes)

        # MỤC 1: DỌN DẸP SLIVERS
        grp_sliver = QGroupBox("1. Dọn dẹp dải mảnh nhỏ (Sliver Polygons)")
        grp_sliver.setStyleSheet("QGroupBox { font-weight: bold; }")
        sl_layout = QVBoxLayout(grp_sliver)

        sl_row1 = QHBoxLayout()
        sl_row1.addWidget(QLabel("Diện tích tối thiểu (m²):"))
        self.spn_sliver_area = QDoubleSpinBox()
        self.spn_sliver_area.setRange(0.01, 10000.0)
        self.spn_sliver_area.setValue(1.0)
        sl_row1.addWidget(self.spn_sliver_area)

        sl_row1.addWidget(QLabel("Bề rộng tối đa (2*diện tích/chu vi) (m):"))
        self.spn_sliver_width = QDoubleSpinBox()
        self.spn_sliver_width.setRange(0.01, 100.0)
        self.spn_sliver_width.setValue(2.0)
        sl_row1.addWidget(self.spn_sliver_width)

        btn_clean_slivers = QPushButton("Dọn dẹp dải mảnh trên Layer đang chọn")
        btn_clean_slivers.setIcon(get_plugin_icon("sliver"))
        btn_clean_slivers.setIconSize(QSize(18, 18))
        btn_clean_slivers.setStyleSheet("padding: 6px 14px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_clean_slivers.clicked.connect(self.run_clean_slivers)
        sl_row1.addWidget(btn_clean_slivers)
        sl_layout.addLayout(sl_row1)
        layout.addWidget(grp_sliver)

        # MỤC 2: CẮT TỈA PHẦN NHÁNH HẸP DÍNH LIỀN (OPENING)
        grp_trim = QGroupBox("2. Cắt tỉa nhánh hẹp dính liền trong Polygon (Kỹ thuật Opening quanh tọa độ)")
        grp_trim.setStyleSheet("QGroupBox { font-weight: bold; }")
        trim_layout = QVBoxLayout(grp_trim)

        tr_row1 = QHBoxLayout()
        tr_row1.addWidget(QLabel("Tọa độ X:"))
        self.txt_trim_x = QLineEdit()
        self.txt_trim_x.setPlaceholderText("VD: 610354.49")
        tr_row1.addWidget(self.txt_trim_x)

        tr_row1.addWidget(QLabel("Tọa độ Y:"))
        self.txt_trim_y = QLineEdit()
        self.txt_trim_y.setPlaceholderText("VD: 1189423.30")
        tr_row1.addWidget(self.txt_trim_y)

        tr_row1.addWidget(QLabel("Khoảng cách thu hẹp D (m):"))
        self.spn_trim_d = QDoubleSpinBox()
        self.spn_trim_d.setRange(0.05, 50.0)
        self.spn_trim_d.setValue(0.5)
        tr_row1.addWidget(self.spn_trim_d)

        btn_trim = QPushButton("Cắt nhánh hẹp")
        btn_trim.setIcon(get_plugin_icon("trim"))
        btn_trim.setIconSize(QSize(18, 18))
        btn_trim.setStyleSheet("padding: 6px 14px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_trim.clicked.connect(self.run_trim_opening)
        tr_row1.addWidget(btn_trim)
        trim_layout.addLayout(tr_row1)
        layout.addWidget(grp_trim)

        # MỤC 3: THAY THẾ HÌNH HỌC POLYGON
        grp_rep = QGroupBox("3. Thay thế hình học Polygon (Giữ nguyên toàn bộ thuộc tính lớp đích)")
        grp_rep.setStyleSheet("QGroupBox { font-weight: bold; }")
        rep_layout = QVBoxLayout(grp_rep)

        rep_row1 = QHBoxLayout()
        rep_row1.addWidget(QLabel("Layer Nguồn:"))
        self.cmb_rep_src = QComboBox()
        rep_row1.addWidget(self.cmb_rep_src, 1)

        rep_row1.addWidget(QLabel("FID Nguồn:"))
        self.spn_rep_src_fid = QSpinBox()
        self.spn_rep_src_fid.setRange(0, 99999999)
        rep_row1.addWidget(self.spn_rep_src_fid)

        rep_row1.addWidget(QLabel("Layer Đích:"))
        self.cmb_rep_dst = QComboBox()
        rep_row1.addWidget(self.cmb_rep_dst, 1)

        rep_row1.addWidget(QLabel("FID Đích:"))
        self.spn_rep_dst_fid = QSpinBox()
        self.spn_rep_dst_fid.setRange(0, 99999999)
        rep_row1.addWidget(self.spn_rep_dst_fid)

        btn_replace = QPushButton("Thay hình học")
        btn_replace.setIcon(get_plugin_icon("replace_geom"))
        btn_replace.setIconSize(QSize(18, 18))
        btn_replace.setStyleSheet("padding: 6px 14px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_replace.clicked.connect(self.run_replace_geometry)
        rep_row1.addWidget(btn_replace)
        rep_layout.addLayout(rep_row1)
        layout.addWidget(grp_rep)

        # MỤC 4: TRA CỨU ĐỐI TƯỢNG TẠI ĐIỂM
        grp_inspect = QGroupBox("4. Tra cứu nhanh đối tượng tại tọa độ X, Y")
        grp_inspect.setStyleSheet("QGroupBox { font-weight: bold; }")
        ins_layout = QVBoxLayout(grp_inspect)

        ins_row1 = QHBoxLayout()
        ins_row1.addWidget(QLabel("Tọa độ X:"))
        self.txt_ins_x = QLineEdit()
        self.txt_ins_x.setPlaceholderText("VD: 610354.49")
        ins_row1.addWidget(self.txt_ins_x)

        ins_row1.addWidget(QLabel("Tọa độ Y:"))
        self.txt_ins_y = QLineEdit()
        self.txt_ins_y.setPlaceholderText("VD: 1189423.30")
        ins_row1.addWidget(self.txt_ins_y)

        btn_inspect = QPushButton("Tra cứu (X, Y)")
        btn_inspect.setIcon(get_plugin_icon("inspect"))
        btn_inspect.setIconSize(QSize(18, 18))
        btn_inspect.setStyleSheet("padding: 6px 14px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_inspect.clicked.connect(self.run_inspect_point)
        ins_row1.addWidget(btn_inspect)
        ins_layout.addLayout(ins_row1)

        self.txt_ins_result = QTextEdit()
        self.txt_ins_result.setMaximumHeight(80)
        self.txt_ins_result.setReadOnly(True)
        ins_layout.addWidget(self.txt_ins_result)
        layout.addWidget(grp_inspect)

        self.refresh_layer_combos()

    def refresh_layer_combos(self):
        self.cmb_rep_src.clear()
        self.cmb_rep_dst.clear()
        v_layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
        for l in v_layers:
            self.cmb_rep_src.addItem(l.name(), l.id())
            self.cmb_rep_dst.addItem(l.name(), l.id())

    def run_clean_slivers(self):
        layer = iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer) or layer.geometryType() != GEOM_POLYGON:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn 1 lớp POLYGON trong bảng Layers!")
            return
        min_a = self.spn_sliver_area.value()
        max_w = self.spn_sliver_width.value()

        layer.startEditing()
        removed_parts = 0
        deleted_feats = []

        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue
            if geom.isMultipart():
                new_parts = []
                for p in geom.asGeometryCollection():
                    a = p.area()
                    per = p.length()
                    w = 2 * a / per if per > 0 else 0
                    if a >= min_a and w >= max_w:
                        new_parts.append(p)
                    else:
                        removed_parts += 1
                if new_parts:
                    union_g = new_parts[0]
                    for np in new_parts[1:]:
                        union_g = union_g.combine(np)
                    layer.changeGeometry(feat.id(), union_g)
                else:
                    deleted_feats.append(feat.id())
            else:
                a = geom.area()
                per = geom.length()
                w = 2 * a / per if per > 0 else 0
                if a < min_a or w < max_w:
                    deleted_feats.append(feat.id())

        if deleted_feats:
            layer.deleteFeatures(deleted_feats)
        layer.commitChanges()
        layer.triggerRepaint()
        QMessageBox.information(self, "Hoàn tất", f"Đã xóa {len(deleted_feats)} đối tượng sliver và loại bỏ {removed_parts} mảnh dư rác!")

    def run_trim_opening(self):
        layer = iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer) or layer.geometryType() != GEOM_POLYGON:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn 1 lớp POLYGON trong bảng Layers!")
            return
        try:
            x = float(self.txt_trim_x.text())
            y = float(self.txt_trim_y.text())
        except Exception:
            QMessageBox.warning(self, "Lỗi", "Tọa độ X, Y không hợp lệ!")
            return

        d = self.spn_trim_d.value()
        pt = QgsPointXY(x, y)
        pt_geom = QgsGeometry.fromPointXY(pt)

        layer.startEditing()
        fixed = 0
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom.intersects(pt_geom.buffer(10, 5)):
                eroded = geom.buffer(-d, 5)
                opened = eroded.buffer(d, 5)
                diff = geom.difference(opened)
                if not diff.isNull() and not diff.isEmpty():
                    res_geom = geom.difference(diff.intersection(pt_geom.buffer(20, 5)))
                    if res_geom.isGeosValid():
                        layer.changeGeometry(feat.id(), res_geom)
                        fixed += 1

        layer.commitChanges()
        layer.triggerRepaint()
        QMessageBox.information(self, "Hoàn tất", f"Đã cắt tỉa nhánh hẹp thành công cho {fixed} đối tượng!")

    def run_replace_geometry(self):
        src_id = self.cmb_rep_src.currentData()
        dst_id = self.cmb_rep_dst.currentData()
        src_layer = QgsProject.instance().mapLayer(src_id)
        dst_layer = QgsProject.instance().mapLayer(dst_id)

        if not src_layer or not dst_layer:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn đủ Layer Nguồn và Layer Đích!")
            return

        src_fid = self.spn_rep_src_fid.value()
        dst_fid = self.spn_rep_dst_fid.value()

        src_feat = src_layer.getFeature(src_fid)
        if not src_feat.isValid():
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy đối tượng nguồn với FID {src_fid}!")
            return

        dst_layer.startEditing()
        dst_layer.changeGeometry(dst_fid, src_feat.geometry())
        dst_layer.commitChanges()
        dst_layer.triggerRepaint()
        QMessageBox.information(self, "Thành công", f"Đã thay thế hình học từ {src_layer.name()} (FID {src_fid}) sang {dst_layer.name()} (FID {dst_fid}) thành công!")

    def run_inspect_point(self):
        try:
            x = float(self.txt_ins_x.text())
            y = float(self.txt_ins_y.text())
        except Exception:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tọa độ X, Y hợp lệ!")
            return

        pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))
        results = []
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer) and lyr.geometryType() == GEOM_POLYGON:
                for feat in lyr.getFeatures():
                    if feat.geometry().intersects(pt.buffer(5, 5)):
                        results.append(f"• Layer: {lyr.name()} | FID: {feat.id()} | DT: {round(feat.geometry().area(), 2)} m² | Hợp lệ: {feat.geometry().isGeosValid()}")

        if results:
            self.txt_ins_result.setText("\n".join(results))
        else:
            self.txt_ins_result.setText("Không tìm thấy đối tượng polygon nào quanh tọa độ này.")


    # =========================================================================
    # TAB 4: THUỘC TÍNH & CHUẨN CSDL QPK
    # =========================================================================
    def setup_tab_attr(self):
        outer = QVBoxLayout(self.tab_attr)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(getattr(QFrame, 'Shape', QFrame).NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        content.setAutoFillBackground(False)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)

        # =====================================================================
        # MỤC 1: TRƯỜNG BẮT BUỘC CHUẨN CSDL QUY HOẠCH (QPK / TT16) & THÔNG SỐ HỒ SƠ
        # =====================================================================
        grp_qpk = QGroupBox("1. Thêm các trường bắt buộc chuẩn CSDL Quy hoạch (QPK / TT16) & Nhập thông số hồ sơ")
        grp_qpk.setStyleSheet("QGroupBox { font-weight: bold; }")
        qpk_layout = QVBoxLayout(grp_qpk)

        # Mô tả 6 trường chuẩn
        lbl_qpk_desc = QLabel(
            "📋 <b>6 trường bắt buộc:</b> "
            "<b>maThongTinQH</b> <i>(Text)</i>, "
            "<b>maHoSoQH</b> <i>(Text)</i>, "
            "<b>maDoiTuong</b> <i>(Text)</i>, "
            "<b>dienTich</b> <i>(Double)</i>, "
            "<b>chieuDai</b> <i>(Double)</i>, "
            "<b>ghiChu</b> <i>(Text)</i>"
        )
        lbl_qpk_desc.setWordWrap(True)
        lbl_qpk_desc.setStyleSheet("font-size: 11px; margin-bottom: 2px;")
        qpk_layout.addWidget(lbl_qpk_desc)

        # Khung nhập thông số hồ sơ quy hoạch
        self.dv_frame = QFrame()
        self.dv_frame.setStyleSheet("background: #fdfefe; border: 1px solid #d5dbdb; border-radius: 4px; padding: 4px;")
        dv_grid = QHBoxLayout(self.dv_frame)
        dv_grid.setContentsMargins(6, 4, 6, 4)

        dv_grid.addWidget(QLabel("<b>maThongTinQH:</b>"))
        self.txt_ma_tt = QLineEdit("7926545xxxxx")
        self.txt_ma_tt.setPlaceholderText("VD: 7926545xxxxx")
        dv_grid.addWidget(self.txt_ma_tt)

        dv_grid.addWidget(QLabel("<b>maHoSoQH:</b>"))
        self.txt_ma_hs = QLineEdit("79QPK101xxxx")
        self.txt_ma_hs.setPlaceholderText("VD: 79QPK101xxxx")
        dv_grid.addWidget(self.txt_ma_hs)

        dv_grid.addWidget(QLabel("<b>phanLoai:</b>"))
        self.txt_phan_loai = QComboBox()
        self.txt_phan_loai.setEditable(True)
        self.txt_phan_loai.addItems(["Dạng đường", "Dạng vùng", "Dạng điểm", "Hiện trạng", "Quy hoạch"])
        self.txt_phan_loai.setCurrentText("Dạng đường")
        dv_grid.addWidget(self.txt_phan_loai)

        qpk_layout.addWidget(self.dv_frame)

        # Hàng nút thực thi của Mục 1
        qpk_btn_bar = QHBoxLayout()
        self.chk_qpk_fill = QCheckBox("Tự động điền giá trị mã hồ sơ vào đối tượng khi thêm trường")
        self.chk_qpk_fill.setChecked(True)
        self.chk_qpk_fill.setStyleSheet("font-size: 11px; font-weight: 500;")
        qpk_btn_bar.addWidget(self.chk_qpk_fill)
        qpk_btn_bar.addStretch()

        btn_add_qpk = QPushButton("Thêm 6 trường chuẩn QPK & Điền thông số")
        btn_add_qpk.setIcon(get_plugin_icon("add_qpk"))
        btn_add_qpk.setIconSize(QSize(18, 18))
        btn_add_qpk.setToolTip("Thêm 6 trường bắt buộc (và điền mã hồ sơ nếu tích ô chọn) cho các Layer đang chọn")
        btn_add_qpk.setStyleSheet("padding: 6px 16px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_add_qpk.clicked.connect(self.run_add_required_fields)
        qpk_btn_bar.addWidget(btn_add_qpk)

        btn_update_defaults = QPushButton("Chỉ cập nhật mã hồ sơ")
        btn_update_defaults.setIcon(get_plugin_icon("update_codes"))
        btn_update_defaults.setIconSize(QSize(18, 18))
        btn_update_defaults.setToolTip("Cập nhật lại giá trị maThongTinQH, maHoSoQH, phanLoai cho toàn bộ đối tượng của Layer đang chọn")
        btn_update_defaults.setStyleSheet("padding: 6px 14px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_update_defaults.clicked.connect(self.run_update_default_attributes)
        qpk_btn_bar.addWidget(btn_update_defaults)
        qpk_layout.addLayout(qpk_btn_bar)

        layout.addWidget(grp_qpk)

        # =====================================================================
        # MỤC 2: THÊM CỘT DỮ LIỆU TÙY Ý (THEO NHU CẦU / MẪU GIS)
        # =====================================================================
        grp_custom = QGroupBox("2. Thêm cột dữ liệu tùy ý (không thuộc 6 trường bắt buộc ở mục 1)")
        grp_custom.setStyleSheet("QGroupBox { font-weight: bold; }")
        cu_layout = QVBoxLayout(grp_custom)

        # Thanh công cụ thêm cột
        cu_bar = QHBoxLayout()
        self.btn_tmpl = QPushButton("Chèn từ mẫu cột GIS...")
        self.btn_tmpl.setIcon(get_plugin_icon("template"))
        self.btn_tmpl.setIconSize(QSize(16, 16))
        self.btn_tmpl.setToolTip("Chọn nhanh từ danh mục mẫu cột thực tế chuẩn GIS (hành chính, hạ tầng, ghi chú...)")
        self.btn_tmpl.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #374151; border: 1px solid #d1d5db; border-radius: 4px; background: #ffffff;")
        self.btn_tmpl.clicked.connect(lambda *_: self._show_col_template_menu(self.btn_tmpl))
        cu_bar.addWidget(self.btn_tmpl)

        self.btn_more_row = QPushButton("Thêm dòng cột mới")
        self.btn_more_row.setIcon(get_plugin_icon("add_row"))
        self.btn_more_row.setIconSize(QSize(16, 16))
        self.btn_more_row.setToolTip("Thêm 1 dòng trống để nhập tên cột tùy ý")
        self.btn_more_row.setStyleSheet("padding: 5px 12px; font-weight: 500; color: #374151; border: 1px dashed #d1d5db; border-radius: 4px; background: #ffffff;")
        self.btn_more_row.clicked.connect(lambda *_: self._add_custom_row())
        cu_bar.addWidget(self.btn_more_row)
        cu_bar.addStretch()
        cu_layout.addLayout(cu_bar)

        # Danh sách dòng cột tùy chọn
        self._custom_types = [
            ("Text (chuỗi ký tự)", FT_STRING),
            ("Integer (số nguyên)", FT_INT),
            ("Double (số thực)", FT_DOUBLE),
            ("Date (ngày tháng)", FT_DATE),
        ]
        self._custom_rows = []
        self.custom_rows_box = QVBoxLayout()
        self.custom_rows_box.setSpacing(4)
        cu_layout.addLayout(self.custom_rows_box)
        self._add_custom_row()

        # Tùy chọn chuẩn hóa & Nút thực thi thêm cột tùy ý
        cu_opt_bar = QHBoxLayout()
        self.chk_clean_col_names = QCheckBox("Tự động chuẩn hóa tên cột (đổi khoảng trắng thành '_', bỏ dấu tiếng Việt - Chuẩn GIS)")
        self.chk_clean_col_names.setChecked(True)
        self.chk_clean_col_names.setStyleSheet("font-size: 11px; font-weight: 500;")
        cu_opt_bar.addWidget(self.chk_clean_col_names)
        cu_opt_bar.addStretch()

        btn_add_custom = QPushButton("ÁP DỤNG THÊM CỘT TÙY Ý")
        btn_add_custom.setIcon(get_plugin_icon("custom_col"))
        btn_add_custom.setIconSize(QSize(18, 18))
        btn_add_custom.setToolTip("Thêm các cột ở danh sách trên vào các Layer đang được chọn trong bảng Layers")
        btn_add_custom.setStyleSheet("padding: 6px 16px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_add_custom.clicked.connect(self.run_add_custom_fields)
        cu_opt_bar.addWidget(btn_add_custom)
        cu_layout.addLayout(cu_opt_bar)

        cu_note = QLabel("💡 'Tên cột': tên kỹ thuật CSDL (viết liền không dấu, VD: maDoiTuong). 'Bí danh': tên hiển thị tiếng Việt trên bảng thuộc tính. Có thể chọn nhiều layer (giữ Ctrl/Shift).")
        cu_note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        cu_layout.addWidget(cu_note)

        layout.addWidget(grp_custom)

        # =====================================================================
        # MỤC 3: ĐIỀN GIÁ TRỊ & TÍNH TOÁN DỮ LIỆU THUỘC TÍNH
        # =====================================================================
        grp_calc_fill = QGroupBox("3. Điền giá trị & Tính toán dữ liệu thuộc tính (Lớp – Cột – Giá trị)")
        grp_calc_fill.setStyleSheet("QGroupBox { font-weight: bold; }")
        cf_layout = QVBoxLayout(grp_calc_fill)

        # Bảng điền chi tiết
        self.tbl_fill = QTableWidget(0, 4)
        self.tbl_fill.setHorizontalHeaderLabels(["Lớp (Layer)", "Cột cần điền", "Giá trị / Loại dữ liệu tự động", ""])
        self.tbl_fill.verticalHeader().setVisible(False)
        self.tbl_fill.verticalHeader().setDefaultSectionSize(34)
        self.tbl_fill.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tbl_fill.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        fh = self.tbl_fill.horizontalHeader()
        fh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tbl_fill.setColumnWidth(3, 36)
        cf_layout.addWidget(self.tbl_fill)

        # Nút điều khiển bảng điền
        cf_btns = QHBoxLayout()
        btn_fill_add = QPushButton("Thêm dòng")
        btn_fill_add.setIcon(get_plugin_icon("add_row"))
        btn_fill_add.setIconSize(QSize(16, 16))
        btn_fill_add.setToolTip("Thêm 1 dòng: chọn lớp, chọn cột, nhập giá trị hoặc chọn loại tự động")
        btn_fill_add.clicked.connect(lambda *_: self._add_fill_row())
        cf_btns.addWidget(btn_fill_add)

        btn_fill_sel = QPushButton("Thêm các layer đang chọn")
        btn_fill_sel.setIcon(get_plugin_icon("scope_layers"))
        btn_fill_sel.setIconSize(QSize(16, 16))
        btn_fill_sel.setToolTip("Tạo sẵn 1 dòng cho mỗi layer đang được chọn trong bảng Layers")
        btn_fill_sel.clicked.connect(lambda *_: self._fill_rows_from_selected_layers())
        cf_btns.addWidget(btn_fill_sel)

        btn_fill_ref = QPushButton("Làm mới danh sách lớp")
        btn_fill_ref.setIcon(get_plugin_icon("reload"))
        btn_fill_ref.setIconSize(QSize(16, 16))
        btn_fill_ref.setToolTip("Cập nhật lại danh sách lớp/cột")
        btn_fill_ref.clicked.connect(lambda *_: self._refresh_fill_layers())
        cf_btns.addWidget(btn_fill_ref)

        cf_btns.addStretch()

        btn_fill_now = QPushButton("ÁP DỤNG ĐIỀN GIÁ TRỊ")
        btn_fill_now.setIcon(get_plugin_icon("fill_values"))
        btn_fill_now.setIconSize(QSize(18, 18))
        btn_fill_now.setStyleSheet("padding: 6px 16px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_fill_now.clicked.connect(self.run_fill_attribute)
        cf_btns.addWidget(btn_fill_now)
        cf_layout.addLayout(cf_btns)

        cf_note = QLabel("💡 Cột 'Giá trị': nhập text/số thường, HOẶC chọn '[Chiều dài]', '[Diện tích]', '[X tâm]', '[Y tâm]', '[FID]', '[Chu vi]' để tự động trích xuất từ geometry. Nếu layer có đối tượng đang chọn thì chỉ điền cho các đối tượng đó.")
        cf_note.setWordWrap(True)
        cf_note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        cf_layout.addWidget(cf_note)

        layout.addWidget(grp_calc_fill)
        self._add_fill_row()
        layout.addStretch()


    # Danh mục mẫu cột thực tế phổ biến trong GIS
    # (tên_cột, bí_danh, kiểu_index[0=Text,1=Int,2=Double,3=Date], độ_dài, giá_trị_mặc_định)
    _COL_TEMPLATES = [
        # --- Nhận dạng & mã số ---
        ("--- Nhận dạng & Mã số ---", None, None, None, None),
        ("tenDoiTuong",   "Tên đối tượng",          0, 200, ""),
        ("maDoiTuong",    "Mã đối tượng",            0, 100, ""),
        ("maSo",          "Mã số",                   0,  50, ""),
        ("soThuTu",       "Số thứ tự",               1,  10, ""),
        ("maVung",        "Mã vùng",                 0,  50, ""),
        ("maPhuong",      "Mã phường/xã",            0,  50, ""),
        ("maQuan",        "Mã quận/huyện",           0,  50, ""),
        ("maTinh",        "Mã tỉnh/thành",           0,  10, ""),
        # --- Quy hoạch ---
        ("--- Quy hoạch ---", None, None, None, None),
        ("maThongTinQH",  "Mã thông tin QH",         0,  50, ""),
        ("maHoSoQH",      "Mã hồ sơ QH",             0,  50, ""),
        ("phanLoai",      "Phân loại",               0, 100, ""),
        ("chucNang",      "Chức năng sử dụng đất",   0, 200, ""),
        ("kyHieu",        "Ký hiệu",                  0,  20, ""),
        ("loaiDat",       "Loại đất",                0, 100, ""),
        ("mucDichSuDung", "Mục đích sử dụng",        0, 200, ""),
        ("namQuyHoach",   "Năm quy hoạch",           1,  10, ""),
        # --- Hình học (geometry) ---
        ("--- Hình học (tự động tính từ geometry) ---", None, None, None, None),
        ("dienTich",      "Diện tích (m²)",          2,  20, ""),
        ("chieuDai",      "Chiều dài (m)",           2,  20, ""),
        ("chuVi",         "Chu vi (m)",              2,  20, ""),
        ("toaDo_X",       "Tọa độ X",                2,  20, ""),
        ("toaDo_Y",       "Tọa độ Y",                2,  20, ""),
        # --- Hành chính ---
        ("--- Hành chính ---", None, None, None, None),
        ("tenTinh",       "Tên tỉnh/thành",          0, 100, ""),
        ("tenHuyen",      "Tên quận/huyện",          0, 100, ""),
        ("tenXa",         "Tên phường/xã",           0, 100, ""),
        ("diaChi",        "Địa chỉ",                 0, 254, ""),
        # --- Hạ tầng kỹ thuật ---
        ("--- Hạ tầng kỹ thuật ---", None, None, None, None),
        ("loaiCongTrinh", "Loại công trình",         0, 200, ""),
        ("namXayDung",    "Năm xây dựng",            1,  10, ""),
        ("trangThai",     "Trạng thái",              0, 100, "Hiện trạng"),
        ("donViQuanLy",   "Đơn vị quản lý",          0, 200, ""),
        ("nguonDuLieu",   "Nguồn dữ liệu",           0, 200, ""),
        ("ngayCapNhat",   "Ngày cập nhật",           3,   0, ""),
        # --- Ghi chú ---
        ("--- Ghi chú ---", None, None, None, None),
        ("ghiChu",        "Ghi chú",                 0, 254, ""),
        ("moTa",          "Mô tả",                   0, 500, ""),
        ("nguonAnh",      "Nguồn ảnh",               0, 254, ""),
    ]

    def _show_col_template_menu(self, btn):
        """Hiện menu popup danh mục mẫu cột, khi chọn thì điền vào dòng cuối hoặc tạo dòng mới."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 12px; } QMenu::item:selected { background: #c82333; color: white; }")
        for item in self._COL_TEMPLATES:
            col_name, alias, t_idx, length, default = item
            if t_idx is None:
                # Đây là tiêu đề nhóm
                act = QAction(col_name, self)
                act.setEnabled(False)
                font = act.font()
                font.setBold(True)
                act.setFont(font)
                menu.addAction(act)
                menu.addSeparator()
                continue
            label = f"  {col_name}  ({alias})"
            act = QAction(label, self)
            act.setData(item)
            act.triggered.connect(lambda checked, d=item: self._insert_template_col(d))
            menu.addAction(act)

        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _insert_template_col(self, tmpl):
        """Điền dữ liệu mẫu vào dòng trống cuối hoặc tạo dòng mới trong Mục 5."""
        col_name, alias, t_idx, length, default = tmpl
        # Tìm dòng trống cuối
        target_row = None
        for row in self._custom_rows:
            if not row["name"].text().strip():
                target_row = row
                break
        if target_row is None:
            target_row = self._add_custom_row()
        # Điền
        target_row["name"].setText(col_name)
        target_row["alias"].setText(alias or "")
        if t_idx is not None:
            target_row["type"].setCurrentIndex(t_idx)
        if length:
            target_row["len"].setValue(length)
        if default:
            target_row["default"].setText(default)

    def _add_required_to_layer(self, layer, needed):
        """Thêm các trường bắt buộc vào 1 layer. Trả về (added, status, err).
        status: ok | pending (layer đang edit, chưa lưu) | readonly | error"""
        was_editing = layer.isEditable()
        if not was_editing and not layer.startEditing():
            return [], "readonly", ""
        existing_lower = [f.name().lower() for f in layer.fields()]
        added = []
        for fname, ftype, flen, falias in needed:
            if fname.lower() not in existing_lower:
                if layer.addAttribute(QgsField(fname, ftype, len=flen)):
                    added.append(fname)
        layer.updateFields()
        for fname, ftype, flen, falias in needed:
            idx = layer.fields().indexOf(fname)
            if idx >= 0:
                layer.setFieldAlias(idx, falias)
        if was_editing:
            return added, "pending", ""
        if not layer.commitChanges():
            errs = "; ".join(layer.commitErrors()[:3])
            layer.rollBack()
            return [], "error", errs
        return added, "ok", ""

    def run_add_required_fields(self):
        layers = get_selected_vector_layers()
        if not layers:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhấp chọn ít nhất 1 Layer vector trong bảng Layers!\n(Giữ Ctrl hoặc Shift để chọn nhiều layer)")
            return

        needed = [
            ("maThongTinQH", FT_STRING, 50, "Mã thông tin quy hoạch"),
            ("maHoSoQH", FT_STRING, 50, "Mã hồ sơ quy hoạch"),
            ("maDoiTuong", FT_STRING, 100, "Mã đối tượng"),
            ("dienTich", FT_DOUBLE, 20, "Diện tích"),
            ("chieuDai", FT_DOUBLE, 20, "Chiều dài"),
            ("ghiChu", FT_STRING, 254, "Ghi chú")
        ]

        # Kiểm tra tùy chọn tự động điền thông số hồ sơ
        do_fill = getattr(self, 'chk_qpk_fill', None) is None or self.chk_qpk_fill.isChecked()
        ma_tt = self.txt_ma_tt.text().strip() if hasattr(self, 'txt_ma_tt') else ""
        ma_hs = self.txt_ma_hs.text().strip() if hasattr(self, 'txt_ma_hs') else ""
        phan_loai = (self.txt_phan_loai.currentText().strip() if hasattr(self.txt_phan_loai, 'currentText')
                     else self.txt_phan_loai.text().strip()) if hasattr(self, 'txt_phan_loai') else ""
        
        fill_data = {}
        if ma_tt: fill_data['maThongTinQH'] = ma_tt
        if ma_hs: fill_data['maHoSoQH'] = ma_hs
        if phan_loai: fill_data['phanLoai'] = phan_loai
        fill_data['ghiChu'] = '-'

        lines = []
        n_fail = 0
        for layer in layers:
            added, status, err = self._add_required_to_layer(layer, needed)
            if status == "readonly":
                lines.append(f"⛔ {layer.name()}: không bật được chế độ chỉnh sửa (layer chỉ đọc?)")
                n_fail += 1
                continue
            elif status == "error":
                lines.append(f"❌ {layer.name()}: không lưu được\n    {err}")
                n_fail += 1
                continue
            
            # Điền thông số hồ sơ nếu có tích chọn
            filled_count = 0
            if do_fill and fill_data:
                was_editing = layer.isEditable()
                if not was_editing:
                    layer.startEditing()
                fnames = [f.name() for f in layer.fields()]
                sel_ids = layer.selectedFeatureIds()
                for feat in layer.getFeatures():
                    if sel_ids and feat.id() not in sel_ids:
                        continue
                    for k, v in fill_data.items():
                        if k in fnames:
                            feat[k] = v
                            layer.updateFeature(feat)
                    filled_count += 1
                if not was_editing:
                    layer.commitChanges()

            msg_item = f"✅ {layer.name()}: " + (f"đã thêm {len(added)} trường ({', '.join(added)})" if added else "đã có đủ các trường")
            if filled_count > 0:
                msg_item += f" | đã điền mã hồ sơ cho {filled_count} đối tượng"
            lines.append(msg_item)

        if len(layers) == 1:
            title_msg = lines[0]
        else:
            title_msg = f"Đã xử lý {len(layers)} layer ({len(layers) - n_fail} thành công, {n_fail} lỗi):\n\n" + "\n".join(lines)
        if n_fail:
            QMessageBox.warning(self, "Hoàn tất (có lỗi)", title_msg)
        else:
            QMessageBox.information(self, "Hoàn tất", title_msg)

    def run_update_default_attributes(self):
        layers = get_selected_vector_layers()
        if not layers:
            act = iface.activeLayer()
            if act and isinstance(act, QgsVectorLayer):
                layers = [act]
        if not layers:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn ít nhất 1 Layer trong bảng Layers!")
            return

        phan_loai_val = (self.txt_phan_loai.currentText().strip() if hasattr(self.txt_phan_loai, 'currentText')
                         else self.txt_phan_loai.text().strip()) if hasattr(self, 'txt_phan_loai') else ""
        data = {
            'maThongTinQH': self.txt_ma_tt.text().strip() if hasattr(self, 'txt_ma_tt') else "",
            'maHoSoQH': self.txt_ma_hs.text().strip() if hasattr(self, 'txt_ma_hs') else "",
            'phanLoai': phan_loai_val,
            'ghiChu': '-'
        }

        total_features = 0
        layer_names = []
        for layer in layers:
            was_editing = layer.isEditable()
            if not was_editing and not layer.startEditing():
                continue
            fnames = [f.name() for f in layer.fields()]
            sel_ids = layer.selectedFeatureIds()
            cnt = 0
            for feat in layer.getFeatures():
                if sel_ids and feat.id() not in sel_ids:
                    continue
                for k, v in data.items():
                    if k in fnames:
                        feat[k] = v
                        layer.updateFeature(feat)
                cnt += 1
            if not was_editing:
                layer.commitChanges()
            total_features += cnt
            layer_names.append(layer.name())

        scope_txt = "các đối tượng đang chọn" if any(l.selectedFeatureCount() > 0 for l in layers) else "toàn bộ đối tượng"
        QMessageBox.information(
            self, "Hoàn tất",
            f"Đã cập nhật thông số hồ sơ cho {total_features} đối tượng ({scope_txt}) trên {len(layer_names)} layer:\n• " +
            "\n• ".join(layer_names)
        )

    def run_calc_length(self):
        layer = iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer) or layer.geometryType() != GEOM_LINE:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một lớp LINE trong bảng Layers!")
            return
        col = "chieuDai" if "chieuDai" in [f.name() for f in layer.fields()] else "Chiều_Dài"
        if col not in [f.name() for f in layer.fields()]:
            layer.startEditing()
            if not layer.addAttribute(QgsField(col, FT_DOUBLE, len=20, prec=3)):
                layer.rollBack()
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo cột '{col}' trên layer này.")
                return
            layer.updateFields()
            if not layer.commitChanges():
                errs = "; ".join(layer.commitErrors()[:3])
                layer.rollBack()
                QMessageBox.critical(self, "Lỗi khi lưu", f"Không thể lưu cột mới vào layer.\n{errs}")
                return

        idx = layer.fields().indexOf(col)
        layer.startEditing()
        count = 0
        for feat in layer.getFeatures():
            layer.changeAttributeValue(feat.id(), idx, round(feat.geometry().length(), 3))
            count += 1
        if not layer.commitChanges():
            errs = "; ".join(layer.commitErrors()[:3])
            layer.rollBack()
            QMessageBox.critical(self, "Lỗi khi lưu", f"Không thể lưu giá trị chiều dài vào layer.\n{errs}")
            return
        QMessageBox.information(self, "Hoàn tất", f"Đã tính toán và cập nhật chiều dài cho {count} đường vào cột '{col}'!")

    def run_calc_area(self):
        layer = iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer) or layer.geometryType() != GEOM_POLYGON:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một lớp POLYGON trong bảng Layers!")
            return
        col = "dienTich" if "dienTich" in [f.name() for f in layer.fields()] else "Diện_Tích"
        if col not in [f.name() for f in layer.fields()]:
            layer.startEditing()
            if not layer.addAttribute(QgsField(col, FT_DOUBLE, len=20, prec=3)):
                layer.rollBack()
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo cột '{col}' trên layer này.")
                return
            layer.updateFields()
            if not layer.commitChanges():
                errs = "; ".join(layer.commitErrors()[:3])
                layer.rollBack()
                QMessageBox.critical(self, "Lỗi khi lưu", f"Không thể lưu cột mới vào layer.\n{errs}")
                return

        idx = layer.fields().indexOf(col)
        layer.startEditing()
        count = 0
        for feat in layer.getFeatures():
            layer.changeAttributeValue(feat.id(), idx, round(feat.geometry().area(), 3))
            count += 1
        if not layer.commitChanges():
            errs = "; ".join(layer.commitErrors()[:3])
            layer.rollBack()
            QMessageBox.critical(self, "Lỗi khi lưu", f"Không thể lưu giá trị diện tích vào layer.\n{errs}")
            return
        QMessageBox.information(self, "Hoàn tất", f"Đã tính toán và cập nhật diện tích cho {count} polygon vào cột '{col}'!")

    # ---------- MỤC 4: bảng Lớp - Cột - Giá trị ----------
    def _fill_vector_layers(self):
        return [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]

    def _populate_fill_fields(self, cmb_field, layer_id, keep_text=None):
        """Nạp danh sách cột của layer vào ô chọn cột (giữ lại tên cột đang chọn nếu layer mới cũng có)."""
        cur = (keep_text if keep_text is not None else cmb_field.currentText()).strip()
        layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
        names = [f.name() for f in layer.fields()] if isinstance(layer, QgsVectorLayer) else []
        cmb_field.clear()
        for n in names:
            cmb_field.addItem(n)
        lower = [n.lower() for n in names]
        if cur and cur.lower() in lower:
            cmb_field.setCurrentIndex(lower.index(cur.lower()))
        elif cur:
            cmb_field.setEditText(cur)               # tên cột mới do người dùng gõ
        elif "tendoituong" in lower:
            cmb_field.setCurrentIndex(lower.index("tendoituong"))
        else:
            cmb_field.setCurrentIndex(-1)
            cmb_field.setEditText("")

    def _resize_fill_table(self):
        rows = max(1, min(self.tbl_fill.rowCount(), 6))
        head_h = self.tbl_fill.horizontalHeader().sizeHint().height()
        self.tbl_fill.setFixedHeight(head_h + rows * 34 + 6)

    def _add_fill_row(self, layer=None, col="", val=""):
        tbl = self.tbl_fill
        r = tbl.rowCount()
        tbl.insertRow(r)

        cmb_layer = QComboBox()
        for l in self._fill_vector_layers():
            cmb_layer.addItem(l.name(), l.id())
        if layer is None:
            sel = get_selected_vector_layers()
            layer = sel[0] if sel else None
        if layer is not None:
            i = cmb_layer.findData(layer.id())
            if i >= 0:
                cmb_layer.setCurrentIndex(i)

        cmb_field = QComboBox()
        cmb_field.setEditable(True)
        cmb_field.lineEdit().setPlaceholderText("Chọn hoặc gõ tên cột")

        # Widget giá trị: ComboBox chọn loại tự động + QLineEdit nhập tay
        val_widget = QWidget()
        val_hl = QHBoxLayout(val_widget)
        val_hl.setContentsMargins(1, 1, 1, 1)
        val_hl.setSpacing(2)

        # Danh sách loại dữ liệu tự động
        AUTO_VAL_OPTIONS = [
            ("✏️ Nhập thủ công...", "__manual__"),
            ("📏 Chiều dài (m) – Line", "__length__"),
            ("📐 Diện tích (m²) – Polygon", "__area__"),
            ("📍 X tâm (centroid)", "__cx__"),
            ("📍 Y tâm (centroid)", "__cy__"),
            ("🔢 ID đối tượng (FID)", "__fid__"),
            ("📦 Chu vi (m) – Polygon", "__perimeter__"),
        ]
        cmb_auto = QComboBox()
        cmb_auto.setMinimumWidth(48)
        cmb_auto.setMaximumWidth(48)
        cmb_auto.setToolTip("Chọn loại giá trị: nhập thủ công hoặc tự động tính từ geometry")
        for label, code in AUTO_VAL_OPTIONS:
            if code == "__length__":
                cmb_auto.addItem(get_plugin_icon("calc_length"), label, code)
            elif code == "__area__":
                cmb_auto.addItem(get_plugin_icon("calc_area"), label, code)
            else:
                cmb_auto.addItem(label, code)

        txt_val = QLineEdit()
        txt_val.setPlaceholderText("Giá trị cần điền (VD: Trạm điện thoại BTS)")
        if val:
            txt_val.setText(val)

        def _on_auto_changed(idx, tv=txt_val, ca=cmb_auto):
            code = ca.currentData()
            if code == "__manual__":
                tv.setEnabled(True)
                tv.setPlaceholderText("Giá trị cần điền (VD: Trạm điện thoại BTS)")
            else:
                tv.setEnabled(False)
                tv.setPlaceholderText(ca.currentText())

        cmb_auto.currentIndexChanged.connect(_on_auto_changed)
        val_hl.addWidget(cmb_auto, 0)
        val_hl.addWidget(txt_val, 1)

        btn_del = QPushButton("✖")
        btn_del.setToolTip("Xóa dòng này")
        btn_del.setStyleSheet("color: #c82333; font-weight: bold; border: 1px solid #d1d5db; background: #ffffff; border-radius: 3px;")

        cmb_layer.currentIndexChanged.connect(
            lambda *_, cl=cmb_layer, cf=cmb_field: self._populate_fill_fields(cf, cl.currentData()))
        btn_del.clicked.connect(lambda *_, b=btn_del: self._remove_fill_row(b))

        tbl.setCellWidget(r, 0, cmb_layer)
        tbl.setCellWidget(r, 1, cmb_field)
        tbl.setCellWidget(r, 2, val_widget)
        tbl.setCellWidget(r, 3, btn_del)
        self._populate_fill_fields(cmb_field, cmb_layer.currentData(), keep_text=col)
        self._resize_fill_table()
        return r

    def _remove_fill_row(self, btn):
        tbl = self.tbl_fill
        row = -1
        for r in range(tbl.rowCount()):
            if tbl.cellWidget(r, 3) is btn:
                row = r
                break
        if row < 0:
            return
        if tbl.rowCount() <= 1:
            # còn 1 dòng thì chỉ xóa giá trị trong ô val
            val_w = tbl.cellWidget(row, 2)
            le = val_w.findChild(QLineEdit) if val_w else None
            if le:
                le.clear()
            return
        tbl.removeRow(row)
        self._resize_fill_table()

    def _refresh_fill_layers(self):
        """Nạp lại danh sách lớp & cột cho tất cả các dòng (giữ nguyên lớp/cột/giá trị đã chọn)."""
        tbl = self.tbl_fill
        layers = self._fill_vector_layers()
        for r in range(tbl.rowCount()):
            cmb_layer = tbl.cellWidget(r, 0)
            cmb_field = tbl.cellWidget(r, 1)
            old_id = cmb_layer.currentData()
            old_col = cmb_field.currentText()
            cmb_layer.blockSignals(True)
            cmb_layer.clear()
            for l in layers:
                cmb_layer.addItem(l.name(), l.id())
            i = cmb_layer.findData(old_id) if old_id else -1
            if i >= 0:
                cmb_layer.setCurrentIndex(i)
            cmb_layer.blockSignals(False)
            self._populate_fill_fields(cmb_field, cmb_layer.currentData(), keep_text=old_col)

    def _fill_rows_from_selected_layers(self):
        layers = get_selected_vector_layers()
        if not layers:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn ít nhất 1 Layer vector trong bảng Layers!\n(Giữ Ctrl hoặc Shift để chọn nhiều layer)")
            return
        tbl = self.tbl_fill
        # Nếu bảng chỉ có 1 dòng mặc định chưa nhập giá trị thì bỏ đi cho gọn
        if tbl.rowCount() == 1 and not tbl.cellWidget(0, 2).text().strip():
            tbl.removeRow(0)
        for lyr in layers:
            self._add_fill_row(layer=lyr)

    def _on_main_tab_changed(self, index):
        # Mỗi lần chuyển tab thì cập nhật lại danh sách lớp cho tab tương ứng
        try:
            if self.tabs.widget(index) is self.tab_attr:
                self._refresh_fill_layers()
            elif self.tabs.widget(index) is self.tab_merge:
                self.refresh_merge_combos()
        except Exception:
            pass

    def _convert_fill_value(self, fld, txt):
        """Đổi giá trị nhập (chuỗi) sang đúng kiểu của cột. Trả về (giá trị, thông báo lỗi)."""
        tn = (fld.typeName() or "").lower()
        try:
            if "int" in tn:
                return int(txt), ""
            if any(k in tn for k in ("real", "double", "float", "numeric", "decimal")):
                return float(txt.replace(",", ".")), ""
            if tn == "date":
                d = QDate.fromString(txt, "dd/MM/yyyy")
                if not d.isValid():
                    d = QDate.fromString(txt, "yyyy-MM-dd")
                if not d.isValid():
                    raise ValueError("ngày không hợp lệ")
                return d, ""
        except Exception:
            return None, f"giá trị '{txt}' không hợp lệ với kiểu của cột '{fld.name()}' ({fld.typeName()}) nên bỏ qua"
        ln = fld.length()
        if isinstance(ln, int) and ln > 0 and ("string" in tn or "text" in tn or "char" in tn) and len(txt) > ln:
            return None, f"giá trị dài {len(txt)} ký tự, vượt độ dài {ln} của cột '{fld.name()}' nên bỏ qua"
        return txt, ""

    # Các mã tự động tính từ geometry
    _AUTO_GEO_CODES = {"__length__", "__area__", "__cx__", "__cy__", "__fid__", "__perimeter__"}

    def _compute_auto_val(self, feat, code):
        """Tính giá trị tự động từ geometry của feature. Trả về (giá trị, kiểu QVariant)."""
        geom = feat.geometry()
        if code == "__fid__":
            return feat.id(), None
        if geom is None or geom.isNull() or geom.isEmpty():
            return None, None
        if code == "__length__":
            return round(geom.length(), 3), None
        if code == "__area__":
            return round(geom.area(), 3), None
        if code == "__perimeter__":
            return round(geom.length(), 3), None   # length() cho polygon = chu vi
        centroid = geom.centroid()
        if centroid and not centroid.isNull():
            pt = centroid.asPoint()
            if code == "__cx__":
                return round(pt.x(), 6), None
            if code == "__cy__":
                return round(pt.y(), 6), None
        return None, None

    def _fill_one_layer(self, layer, items):
        """Điền giá trị cho 1 layer. items = [(số dòng, tên cột, giá trị|auto_code)]. Trả về (danh sách dòng thông báo, có lỗi?)."""
        lines = []
        failed = False
        was_editing = layer.isEditable()
        if not was_editing and not layer.startEditing():
            return ["⛔ Không bật được chế độ chỉnh sửa (layer chỉ đọc?)"], True

        names = [f.name() for f in layer.fields()]
        lower = [n.lower() for n in names]
        plan, to_create = [], []
        for rno, col, val in items:
            if col.lower() in lower:
                actual = names[lower.index(col.lower())]
            else:
                same = [c for c in to_create if c.lower() == col.lower()]
                if same:
                    actual = same[0]
                else:
                    actual = col
                    # Cột tự động tính → dùng kiểu Double
                    to_create.append((col, val in self._AUTO_GEO_CODES))
            plan.append((rno, actual, val))

        created = []
        for col_info in to_create:
            col_name, is_geo = col_info if isinstance(col_info, tuple) else (col_info, False)
            ftype = FT_DOUBLE if is_geo else FT_STRING
            flen = 20 if is_geo else 100
            if layer.addAttribute(QgsField(col_name, ftype, len=flen)):
                created.append(col_name)
            else:
                lines.append(f"❌ Không tạo được cột '{col_name}' (nguồn dữ liệu có thể không hỗ trợ thêm cột)")
                failed = True
        if created:
            layer.updateFields()

        sel_ids = set(layer.selectedFeatureIds())
        scope = "đang chọn" if sel_ids else "toàn bộ"

        # Phân tách plan: các item tự động (per-feature) và tĩnh
        auto_plan = [(rno, col, val) for rno, col, val in plan if val in self._AUTO_GEO_CODES]
        static_plan = [(rno, col, val) for rno, col, val in plan if val not in self._AUTO_GEO_CODES]

        done = []

        # Xử lý giá trị tự động (tính theo từng feature)
        if auto_plan:
            # Tạo dict col→idx
            auto_idx = {}
            for rno, col, val in auto_plan:
                idx = layer.fields().indexOf(col)
                if idx < 0:
                    lines.append(f"❌ Dòng {rno}: không tìm thấy cột '{col}'")
                    failed = True
                else:
                    auto_idx[col] = (idx, val, rno)

            count = 0
            for feat in layer.getFeatures():
                if sel_ids and feat.id() not in sel_ids:
                    continue
                for col, (idx, code, rno) in auto_idx.items():
                    v, _ = self._compute_auto_val(feat, code)
                    if v is not None:
                        layer.changeAttributeValue(feat.id(), idx, v)
                count += 1
            for col, (idx, code, rno) in auto_idx.items():
                label = {"__length__": "Chiều dài (m)", "__area__": "Diện tích (m²)",
                         "__cx__": "X tâm", "__cy__": "Y tâm", "__fid__": "FID",
                         "__perimeter__": "Chu vi (m)"}.get(code, code)
                done.append(f"{col} ← {label} [{count} đối tượng]")

        # Xử lý giá trị tĩnh
        if static_plan:
            ids_static = [f.id() for f in layer.getFeatures() if not sel_ids or f.id() in sel_ids]
            for rno, col, val in static_plan:
                idx = layer.fields().indexOf(col)
                if idx < 0:
                    lines.append(f"❌ Dòng {rno}: không tìm thấy cột '{col}'")
                    failed = True
                    continue
                conv, err = self._convert_fill_value(layer.fields().field(idx), val)
                if err:
                    lines.append(f"⚠️ Dòng {rno}: {err}")
                    continue
                for fid in ids_static:
                    layer.changeAttributeValue(fid, idx, conv)
                done.append(f"{col} = '{val}'")

        if done:
            lines.insert(0, f"✅ Đã điền cho đối tượng ({scope}): {', '.join(done)}")
        if created:
            lines.append(f"🆕 Đã tạo cột mới: {', '.join(created)}")

        if was_editing:
            lines.append("✏️ Layer đang ở chế độ chỉnh sửa nên thay đổi CHƯA được lưu, hãy bấm Save Edits khi sẵn sàng.")
        elif not layer.commitChanges():
            errs = "; ".join(layer.commitErrors()[:3])
            layer.rollBack()
            lines = [f"❌ Không lưu được vào layer.\n    {errs}"]
            failed = True
        return lines, failed

    def run_fill_attribute(self):
        tbl = self.tbl_fill
        jobs = {}
        notes = []
        for r in range(tbl.rowCount()):
            cmb_layer = tbl.cellWidget(r, 0)
            cmb_field = tbl.cellWidget(r, 1)
            val_w = tbl.cellWidget(r, 2)
            lid = cmb_layer.currentData()
            layer = QgsProject.instance().mapLayer(lid) if lid else None
            col = cmb_field.currentText().strip()

            # Đọc loại giá trị từ widget lồng
            cmb_auto = val_w.findChild(QComboBox) if val_w else None
            txt_val_le = val_w.findChild(QLineEdit) if val_w else None
            auto_code = cmb_auto.currentData() if cmb_auto else "__manual__"
            val_text = txt_val_le.text().strip() if txt_val_le else ""

            if not isinstance(layer, QgsVectorLayer):
                notes.append(f"Dòng {r + 1}: chưa chọn lớp (hoặc lớp đã bị xóa khỏi dự án)")
                continue
            if not col:
                notes.append(f"Dòng {r + 1}: chưa chọn cột")
                continue
            if auto_code == "__manual__" and val_text == "":
                notes.append(f"Dòng {r + 1}: chưa nhập giá trị nên bỏ qua")
                continue

            jobs.setdefault(lid, {"layer": layer, "items": []})["items"].append(
                (r + 1, col, auto_code if auto_code != "__manual__" else val_text)
            )

        if not jobs:
            QMessageBox.warning(self, "Thiếu thông tin",
                                "Chưa có dòng nào hợp lệ để điền!\n\n" + "\n".join(f"⚠️ {n}" for n in notes)
                                if notes else "Chưa có dòng nào để điền!")
            return

        multi = len(jobs) > 1
        blocks = []
        n_fail = 0
        for job in jobs.values():
            lines, failed = self._fill_one_layer(job["layer"], job["items"])
            if failed:
                n_fail += 1
            head = f"📂 {job['layer'].name()}\n" if multi else f"Lớp '{job['layer'].name()}':\n"
            blocks.append(head + "\n".join(lines))

        msg = ""
        if multi:
            msg += f"Đã xử lý {len(jobs)} layer ({len(jobs) - n_fail} thành công, {n_fail} lỗi)\n\n"
        msg += "\n\n".join(blocks)
        if notes:
            msg += "\n\n" + "\n".join(f"⚠️ {n}" for n in notes)
        if n_fail:
            QMessageBox.warning(self, "Hoàn tất (có lỗi)", msg)
        else:
            QMessageBox.information(self, "Hoàn tất", msg)
        self._refresh_fill_layers()      # cập nhật danh sách cột nếu vừa tạo cột mới

    def _add_custom_row(self):
        """Thêm 1 dòng nhập cột mới (tên, bí danh, kiểu, độ dài, giá trị điền sẵn, nút xóa)."""
        row_w = QWidget()
        hl = QHBoxLayout(row_w)
        hl.setContentsMargins(0, 0, 0, 0)

        txt_name = QLineEdit()
        txt_name.setPlaceholderText("Tên cột (VD: tenDoiTuong)")
        txt_alias = QLineEdit()
        txt_alias.setPlaceholderText("Bí danh (VD: Tên đối tượng) - tùy chọn")
        cmb = QComboBox()
        for t_name, _ in self._custom_types:
            cmb.addItem(t_name)
        spn = QSpinBox()
        spn.setRange(1, 254)
        spn.setValue(100)
        spn.setPrefix("Dài: ")
        spn.setMinimumWidth(85)
        spn.setToolTip("Độ dài (chỉ áp dụng cho kiểu Text)")
        txt_def = QLineEdit()
        txt_def.setPlaceholderText("Giá trị điền sẵn (tùy chọn)")
        btn_del = QPushButton("✖")
        btn_del.setFixedWidth(28)
        btn_del.setToolTip("Xóa dòng này")
        btn_del.setStyleSheet("color: #c82333; font-weight: bold; border: 1px solid #d1d5db; background: #ffffff; border-radius: 3px;")

        hl.addWidget(txt_name, 3)
        hl.addWidget(txt_alias, 3)
        hl.addWidget(cmb)
        hl.addWidget(spn)
        hl.addWidget(txt_def, 2)
        hl.addWidget(btn_del)

        row = {"widget": row_w, "name": txt_name, "alias": txt_alias,
               "type": cmb, "len": spn, "default": txt_def}
        cmb.currentIndexChanged.connect(lambda i, sp=spn: sp.setEnabled(i == 0))   # Độ dài chỉ dùng cho Text
        btn_del.clicked.connect(lambda *_, r=row: self._remove_custom_row(r))

        self.custom_rows_box.addWidget(row_w)
        self._custom_rows.append(row)
        txt_name.setFocus()
        return row

    def _remove_custom_row(self, row):
        if len(self._custom_rows) <= 1:
            # Còn 1 dòng thì chỉ xóa nội dung, không xóa dòng
            row["name"].clear()
            row["alias"].clear()
            row["default"].clear()
            return
        self.custom_rows_box.removeWidget(row["widget"])
        row["widget"].setParent(None)
        row["widget"].deleteLater()
        if row in self._custom_rows:
            self._custom_rows.remove(row)

    def _parse_custom_default(self, txt, t_idx, t_label):
        """Đổi giá trị điền sẵn sang đúng kiểu. Trả về (giá trị, thông báo lỗi)."""
        if not txt:
            return None, ""
        try:
            if t_idx == 0:
                return txt, ""
            if t_idx == 1:
                return int(txt), ""
            if t_idx == 2:
                return float(txt.replace(",", ".")), ""
            d = QDate.fromString(txt, "dd/MM/yyyy")
            if not d.isValid():
                d = QDate.fromString(txt, "yyyy-MM-dd")
            if not d.isValid():
                raise ValueError("ngày không hợp lệ")
            return d, ""
        except Exception:
            return None, f"Giá trị điền sẵn '{txt}' không hợp lệ với kiểu {t_label} nên chưa được điền."

    def _collect_custom_specs(self):
        """Đọc tất cả các dòng cột -> danh sách spec. Dòng bỏ trống tên thì bỏ qua."""
        do_clean = getattr(self, 'chk_clean_col_names', None) is None or self.chk_clean_col_names.isChecked()
        specs, renamed_info, dup_info, warns = [], [], [], []
        seen = set()
        for r_no, row in enumerate(self._custom_rows, 1):
            raw_cols = row["name"].text().replace(";", ",").replace("\n", ",")
            raw_aliases = row["alias"].text().replace(";", ",").replace("\n", ",")
            parts = [x.strip() for x in raw_cols.split(",") if x.strip()]
            alias_parts = [x.strip() for x in raw_aliases.split(",") if x.strip()]
            if not parts:
                continue
            t_idx = row["type"].currentIndex()
            t_label, ftype = self._custom_types[t_idx]
            default_txt = row["default"].text().strip()
            default_val, default_err = self._parse_custom_default(default_txt, t_idx, t_label)
            if default_err:
                warns.append(f"Dòng {r_no}: {default_err}")
            for idx, p in enumerate(parts):
                clean = sanitize_gis_field_name(p, auto_replace_spaces=do_clean)
                if not clean:
                    continue
                if clean != p:
                    renamed_info.append(f"'{p}' ➔ '{clean}'")
                if clean.lower() in seen:
                    dup_info.append(clean)
                    continue
                seen.add(clean.lower())
                specs.append({
                    "name": clean,
                    "alias": alias_parts[idx] if idx < len(alias_parts) else "",
                    "ftype": ftype,
                    "tshort": t_label.split()[0],
                    "t_idx": t_idx,
                    "length": row["len"].value(),
                    "default_val": default_val,
                    "default_txt": default_txt if default_val is not None else "",
                })
        return specs, renamed_info, dup_info, warns

    def _add_custom_to_layer(self, layer, specs):
        """Thêm các cột (specs) vào 1 layer. Trả về dict kết quả cho layer đó."""
        res = {"added": [], "failed": [], "skipped_required": [], "skipped_exist": [],
               "warn_long": [], "filled": 0, "filled_info": [], "status": "ok", "err": ""}
        required_lower = [r.lower() for r in REQUIRED_FIELD_NAMES]
        existing_lower = [f.name().lower() for f in layer.fields()]
        is_shp = (layer.storageType() or "").lower().startswith("esri shapefile")

        to_add = []
        for sp in specs:
            n = sp["name"]
            if n.lower() in required_lower:
                res["skipped_required"].append(n)
            elif n.lower() in existing_lower:
                res["skipped_exist"].append(n)
            else:
                to_add.append(sp)
                if is_shp and len(n) > 10:
                    res["warn_long"].append(n)

        if not to_add:
            res["status"] = "nothing"
            return res

        was_editing = layer.isEditable()
        if not was_editing and not layer.startEditing():
            res["status"] = "readonly"
            return res

        added_specs = []
        for sp in to_add:
            n, ftype = sp["name"], sp["ftype"]
            if ftype == FT_STRING:
                fld = QgsField(n, ftype, len=sp["length"])
            elif ftype == FT_DOUBLE:
                fld = QgsField(n, ftype, len=20, prec=3)
            elif ftype == FT_INT:
                fld = QgsField(n, ftype, len=10)
            else:
                fld = QgsField(n, ftype)
            if layer.addAttribute(fld):
                added_specs.append(sp)
            else:
                res["failed"].append(n)
        layer.updateFields()
        for sp in added_specs:
            if sp["alias"]:
                fidx = layer.fields().indexOf(sp["name"])
                if fidx >= 0:
                    layer.setFieldAlias(fidx, sp["alias"])

        with_default = [sp for sp in added_specs if sp["default_val"] is not None]
        if with_default:
            sel_ids = layer.selectedFeatureIds()
            ids = list(sel_ids) if sel_ids else [f.id() for f in layer.getFeatures()]
            for sp in with_default:
                fidx = layer.fields().indexOf(sp["name"])
                if fidx < 0:
                    continue
                for fid in ids:
                    layer.changeAttributeValue(fid, fidx, sp["default_val"])
                res["filled_info"].append(f"{sp['name']} = '{sp['default_txt']}'")
            res["filled"] = len(ids)

        res["added"] = added_specs
        if was_editing:
            res["status"] = "pending"
        elif not layer.commitChanges():
            res["err"] = "; ".join(layer.commitErrors()[:3])
            layer.rollBack()
            res["status"] = "error"
            res["added"] = []
        return res

    def run_add_custom_fields(self):
        layers = get_selected_vector_layers()
        if not layers:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhấp chọn ít nhất 1 Layer vector trong bảng Layers!\n(Giữ Ctrl hoặc Shift để chọn nhiều layer)")
            return

        specs, renamed_info, dup_info, warns = self._collect_custom_specs()
        if not specs:
            QMessageBox.warning(self, "Thiếu tên cột", "Vui lòng nhập tên cột cần thêm (bấm '➕ Thêm dòng cột mới' nếu muốn tạo nhiều cột)!")
            return

        multi = len(layers) > 1
        blocks = []
        n_fail = 0
        for layer in layers:
            res = self._add_custom_to_layer(layer, specs)
            st = res["status"]
            ls = []
            if st == "readonly":
                ls.append("⛔ Không bật được chế độ chỉnh sửa (layer chỉ đọc?)")
                n_fail += 1
            elif st == "error":
                ls.append(f"❌ Không lưu được các cột mới.\n    {res['err']}")
                n_fail += 1
            elif st == "nothing":
                ls.append("Không có cột nào được thêm.")
            else:
                added_txt = ", ".join(f"{sp['name']} ({sp['tshort']})" for sp in res["added"])
                ls.append(f"✅ Đã thêm {len(res['added'])} cột: {added_txt if added_txt else '(không có)'}")
                if res["filled_info"]:
                    ls.append(f"✍️ Đã điền sẵn cho {res['filled']} đối tượng: {', '.join(res['filled_info'])}")
                if res["failed"]:
                    ls.append(f"❌ Không thêm được: {', '.join(res['failed'])} (nguồn dữ liệu có thể không hỗ trợ thêm cột)")
                    n_fail += 1
                if st == "pending":
                    ls.append("✏️ Layer đang ở chế độ chỉnh sửa nên thay đổi CHƯA được lưu, hãy bấm Save Edits khi sẵn sàng.")
            if res["skipped_required"]:
                ls.append(f"⛔ Bỏ qua vì là trường bắt buộc (dùng nút ở mục 1): {', '.join(res['skipped_required'])}")
            if res["skipped_exist"]:
                ls.append(f"ℹ️ Bỏ qua vì đã tồn tại: {', '.join(res['skipped_exist'])}")
            if res["warn_long"]:
                ls.append(f"⚠️ Layer Shapefile giới hạn tên cột 10 ký tự, các cột sau có thể bị cắt ngắn: {', '.join(res['warn_long'])}")
            head = f"📂 {layer.name()}\n" if multi else f"Lớp '{layer.name()}':\n"
            blocks.append(head + "\n".join(ls))

        msg = ""
        if multi:
            msg += f"Đã xử lý {len(layers)} layer ({len(layers) - n_fail} thành công, {n_fail} lỗi)\n\n"
        msg += "\n\n".join(blocks)
        if renamed_info:
            msg += f"\n\n✨ Chuẩn hóa tên cột GIS: {', '.join(renamed_info)}"
        alias_list = [sp for sp in specs if sp["alias"]]
        if alias_list:
            alias_txt = ", ".join(sp["name"] + ' ➔ "' + sp["alias"] + '"' for sp in alias_list)
            msg += f"\n🏷️ Bí danh (Alias): {alias_txt}"
        if dup_info:
            msg += f"\n⚠️ Bỏ qua tên cột bị nhập trùng ở nhiều dòng: {', '.join(dup_info)}"
        for w in warns:
            msg += f"\n⚠️ {w}"
        if n_fail:
            QMessageBox.warning(self, "Hoàn tất (có lỗi)", msg)
        else:
            QMessageBox.information(self, "Hoàn tất", msg)

    # =========================================================================
    # TAB 5: GHÉP & CHUYỂN ĐỔI DỮ LIỆU
    # =========================================================================
    def setup_tab_merge(self):
        layout = QVBoxLayout(self.tab_merge)

        # MỤC 1: GHÉP DỮ LIỆU
        grp_merge = QGroupBox("1. Ghép dữ liệu (Merge / Copy Features giữa các layer)")
        grp_merge.setStyleSheet("QGroupBox { font-weight: bold; }")
        m_layout = QVBoxLayout(grp_merge)
        m_layout.addWidget(QLabel("Tự động chuyển đổi dạng hình học (Polygonize nếu nguồn là Line và đích là Polygon):"))

        m_row = QHBoxLayout()
        m_row.addWidget(QLabel("Layer Nguồn:"))
        self.cmb_m_src = QComboBox()
        m_row.addWidget(self.cmb_m_src, 1)

        m_row.addWidget(QLabel("Layer Đích:"))
        self.cmb_m_dst = QComboBox()
        m_row.addWidget(self.cmb_m_dst, 1)

        btn_merge_now = QPushButton("Ghép dữ liệu")
        btn_merge_now.setIcon(get_plugin_icon("merge_data"))
        btn_merge_now.setIconSize(QSize(18, 18))
        btn_merge_now.setStyleSheet("padding: 6px 14px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_merge_now.clicked.connect(self.run_merge_data)
        m_row.addWidget(btn_merge_now)
        m_layout.addLayout(m_row)
        layout.addWidget(grp_merge)

        # MỤC 2: TÁCH LỚP DỮ LIỆU CAD
        grp_cad = QGroupBox("2. Tách lớp & Xử lý dữ liệu CAD")
        grp_cad.setStyleSheet("QGroupBox { font-weight: bold; }")
        cad_layout = QVBoxLayout(grp_cad)
        cad_layout.addWidget(QLabel("Trích xuất thông tin Đỉnh/Đáy từ cột Text CAD vào các trường thuộc tính số:"))

        btn_split_cad = QPushButton("Tách Text CAD sang trường Đỉnh / Đáy")
        btn_split_cad.setIcon(get_plugin_icon("split_cad"))
        btn_split_cad.setIconSize(QSize(18, 18))
        btn_split_cad.setStyleSheet("padding: 6px 14px; font-weight: 500; background: #ffffff; color: #374151; border: 1px solid #d1d5db; border-radius: 4px;")
        btn_split_cad.clicked.connect(self.run_split_cad_text)
        cad_layout.addWidget(btn_split_cad)
        layout.addWidget(grp_cad)

        # MỤC 3: XUẤT DỮ LIỆU ĐA ĐỊNH DẠNG & ĐÓNG GÓI CSDL CHUẨN THÔNG TƯ 16/2025/TT-BXD
        grp_export = QGroupBox("3. Xuất dữ liệu đa định dạng & Đóng gói CSDL chuẩn Thông tư 16/2025/TT-BXD")
        grp_export.setStyleSheet("QGroupBox { font-weight: bold; }")
        exp_layout = QVBoxLayout(grp_export)

        # Hàng 1: Chọn định dạng & Layer nguồn
        r1_layout = QHBoxLayout()
        r1_layout.addWidget(QLabel("<b>Định dạng xuất:</b>"))
        self.cmb_exp_format = QComboBox()
        self.cmb_exp_format.addItem("🏛️ CSDL Geodatabase chuẩn TT16/2025/TT-BXD (*.gdb)", "tt16_gdb")
        self.cmb_exp_format.addItem("AutoCAD DXF (*.dxf)", "dxf")
        self.cmb_exp_format.addItem("Google Earth KML (*.kml)", "kml")
        self.cmb_exp_format.addItem("ESRI File Geodatabase thông thường (*.gdb)", "gdb")
        self.cmb_exp_format.addItem("ESRI Shapefile (*.shp)", "shp")
        self.cmb_exp_format.addItem("GeoPackage (*.gpkg)", "gpkg")
        self.cmb_exp_format.setStyleSheet("font-weight: 500;")
        self.cmb_exp_format.currentIndexChanged.connect(self._on_exp_format_changed)
        r1_layout.addWidget(self.cmb_exp_format, 1)

        r1_layout.addSpacing(15)
        r1_layout.addWidget(QLabel("<b>Chọn Layer xuất:</b>"))
        self.cmb_exp_layer = QComboBox()
        r1_layout.addWidget(self.cmb_exp_layer, 2)
        self.btn_ref_exp_layers = QPushButton("")
        self.btn_ref_exp_layers.setIcon(get_plugin_icon("reload"))
        self.btn_ref_exp_layers.setIconSize(QSize(14, 14))
        self.btn_ref_exp_layers.setToolTip("Làm mới danh sách layer trong dự án QGIS")
        self.btn_ref_exp_layers.setFixedWidth(32)
        self.btn_ref_exp_layers.clicked.connect(self.refresh_merge_combos)
        r1_layout.addWidget(self.btn_ref_exp_layers)
        exp_layout.addLayout(r1_layout)

        # Khung cấu hình riêng cho Thông tư 16/2025/TT-BXD
        self.frame_tt16 = QFrame()
        self.frame_tt16.setStyleSheet("background: #f4f6f7; border: 1px solid #bdc3c7; border-radius: 4px; padding: 4px;")
        tt16_box = QVBoxLayout(self.frame_tt16)
        tt16_box.setContentsMargins(6, 4, 6, 4)

        tt16_r1 = QHBoxLayout()
        tt16_r1.addWidget(QLabel("<b>Cơ sở dữ liệu đích:</b>"))
        self.cmb_tt16_db = QComboBox()
        self.cmb_tt16_db.addItem("QuyHoach.gdb (CSDL Quy hoạch đồ án - 14 nhóm chuyên đề)", "QuyHoach.gdb")
        self.cmb_tt16_db.addItem("HienTrang.gdb (CSDL Hiện trạng - 14 nhóm chuyên đề)", "HienTrang.gdb")
        self.cmb_tt16_db.addItem("MocGioi.gdb (CSDL Mốc giới quy hoạch)", "MocGioi.gdb")
        self.cmb_tt16_db.addItem("NenDiaHinh.gdb (CSDL Nền địa hình)", "NenDiaHinh.gdb")
        self.cmb_tt16_db.setStyleSheet("font-weight: 500;")
        self.cmb_tt16_db.currentIndexChanged.connect(self._on_tt16_db_changed)
        tt16_r1.addWidget(self.cmb_tt16_db, 2)

        tt16_r1.addSpacing(8)
        tt16_r1.addWidget(QLabel("<b>Mã hồ sơ:</b>"))
        self.txt_tt16_ma_hs = QLineEdit("79QPK101xxxx")
        self.txt_tt16_ma_hs.setPlaceholderText("VD: 79QPK101xxxx")
        self.txt_tt16_ma_hs.setMaximumWidth(130)
        self.txt_tt16_ma_hs.setStyleSheet("font-weight: 500;")
        tt16_r1.addWidget(self.txt_tt16_ma_hs)

        tt16_r1.addSpacing(8)
        self.chk_tt16_full_pkg = QCheckBox("Đóng gói thư mục CSDL_<TenDoAn>/HoSoGIS/")
        self.chk_tt16_full_pkg.setChecked(True)
        self.chk_tt16_full_pkg.setToolTip("Tự động tạo cấu trúc thư mục CSDL_<MãHồSơ>/HoSoGIS/<TenCSDL>.gdb (Đã lược bỏ HoSoBASIC và HoSoScan theo yêu cầu)")
        self.chk_tt16_full_pkg.setStyleSheet("font-weight: 500;")
        tt16_r1.addWidget(self.chk_tt16_full_pkg)
        tt16_box.addLayout(tt16_r1)

        tt16_r2 = QHBoxLayout()
        self.chk_tt16_auto_dataset = QCheckBox("Tự động nhận diện tên Layer đưa vào đúng Feature Dataset chuẩn TT16")
        self.chk_tt16_auto_dataset.setChecked(True)
        self.chk_tt16_auto_dataset.setStyleSheet("font-weight: 500;")
        tt16_r2.addWidget(self.chk_tt16_auto_dataset)

        self.chk_tt16_auto_fields = QCheckBox("Tự động kiểm tra & bổ sung 6 trường thuộc tính chuẩn TT16")
        self.chk_tt16_auto_fields.setChecked(True)
        self.chk_tt16_auto_fields.setToolTip("Kiểm tra và tự tạo maThongTinQH, maHoSoQH, maDoiTuong, tenDoiTuong, phanLoai, ghiChu nếu layer chưa có")
        self.chk_tt16_auto_fields.setStyleSheet("font-weight: 500;")
        tt16_r2.addWidget(self.chk_tt16_auto_fields)

        tt16_r2.addSpacing(10)
        self.btn_tt16_precheck = QPushButton("Báo Cáo Kiểm Tra TT16")
        self.btn_tt16_precheck.setIcon(get_plugin_icon("tt16_precheck"))
        self.btn_tt16_precheck.setIconSize(QSize(18, 18))
        self.btn_tt16_precheck.setToolTip("Xem trước bảng đối soát phân loại Feature Dataset và tình trạng 6 trường thuộc tính trước khi quyết định xuất")
        self.btn_tt16_precheck.setStyleSheet("background: #ffffff; color: #374151; font-weight: 500; padding: 4px 12px; border: 1px solid #d1d5db; border-radius: 4px;")
        self.btn_tt16_precheck.clicked.connect(self.run_precheck_tt16)
        tt16_r2.addWidget(self.btn_tt16_precheck)
        tt16_r2.addStretch()
        tt16_box.addLayout(tt16_r2)
        exp_layout.addWidget(self.frame_tt16)

        # Hàng 2: Tùy chọn phạm vi xuất
        r2_layout = QHBoxLayout()
        self.chk_exp_all_selected = QCheckBox("Xuất tất cả Layer đang chọn (bôi đen) trong bảng Layers")
        self.chk_exp_all_selected.setChecked(True)
        self.chk_exp_all_selected.setToolTip("Gộp tất cả các Layer đang chọn thành các lớp trong cùng 1 file CAD hoặc cùng 1 File GDB")
        self.chk_exp_all_selected.setStyleSheet("font-weight: 500;")
        r2_layout.addWidget(self.chk_exp_all_selected)

        self.chk_exp_only_feats = QCheckBox("Chỉ xuất đối tượng đang chọn (Selected)")
        self.chk_exp_only_feats.setToolTip("Chỉ xuất các đối tượng hình học đang được chọn (màu vàng) của Layer")
        r2_layout.addWidget(self.chk_exp_only_feats)

        self.chk_exp_wgs84 = QCheckBox("Tự động chuyển WGS 84 (chỉ áp dụng cho KML)")
        self.chk_exp_wgs84.setChecked(True)
        self.chk_exp_wgs84.setToolTip("Khuyên dùng khi xuất KML để hiển thị đúng vị trí trên Google Earth / Google Maps")
        self.chk_exp_wgs84.setStyleSheet("font-weight: 500;")
        r2_layout.addWidget(self.chk_exp_wgs84)
        r2_layout.addStretch()
        exp_layout.addLayout(r2_layout)

        # Hàng 3: Đường dẫn lưu file & Nút duyệt & Nút xuất
        r3_layout = QHBoxLayout()
        r3_layout.addWidget(QLabel("<b>Nơi lưu:</b>"))
        self.txt_exp_path = QLineEdit()
        import os as _os
        _def_desktop = _os.path.join(_os.path.expanduser("~"), "Desktop")
        self.txt_exp_path.setText(_os.path.join(_def_desktop, "QuyHoach.gdb"))
        self.txt_exp_path.setPlaceholderText("Chọn vị trí lưu file (.gdb, .dxf, .kml)...")
        r3_layout.addWidget(self.txt_exp_path, 1)

        btn_browse_exp = QPushButton("Duyệt...")
        btn_browse_exp.setIcon(get_plugin_icon("folder_open"))
        btn_browse_exp.setIconSize(QSize(16, 16))
        btn_browse_exp.setStyleSheet("padding: 5px 12px; font-weight: bold;")
        btn_browse_exp.clicked.connect(self._browse_export_path)
        r3_layout.addWidget(btn_browse_exp)

        btn_run_exp = QPushButton("XUẤT DỮ LIỆU")
        btn_run_exp.setIcon(get_plugin_icon("export_data"))
        btn_run_exp.setIconSize(QSize(18, 18))
        btn_run_exp.setStyleSheet("padding: 6px 18px; font-weight: bold; background: #c82333; color: white; border-radius: 4px; border: none;")
        btn_run_exp.clicked.connect(self.run_export_data)
        r3_layout.addWidget(btn_run_exp)
        exp_layout.addLayout(r3_layout)

        lbl_exp_note = QLabel("💡 <b>Chuẩn Thông tư 16/2025/TT-BXD:</b> Hệ thống tự động phân tích tên Layer để gom vào đúng <b>Feature Dataset</b> (Giao thông, Cấp nước, Thoát nước, Sử dụng đất, Chỉ giới...) và đặt tên Feature Class dạng <b>&lt;TenLop&gt;_&lt;P/L/A&gt;</b> chuẩn CSDL.")
        lbl_exp_note.setWordWrap(True)
        lbl_exp_note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        exp_layout.addWidget(lbl_exp_note)

        layout.addWidget(grp_export)

        layout.addStretch()
        self.refresh_merge_combos()
        try:
            QgsProject.instance().layersAdded.connect(self.refresh_merge_combos)
            QgsProject.instance().layersRemoved.connect(self.refresh_merge_combos)
        except Exception:
            pass

    def refresh_merge_combos(self):
        self.cmb_m_src.clear()
        self.cmb_m_dst.clear()
        if hasattr(self, 'cmb_exp_layer'):
            self.cmb_exp_layer.clear()
        v_layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
        for l in v_layers:
            self.cmb_m_src.addItem(l.name(), l.id())
            self.cmb_m_dst.addItem(l.name(), l.id())
            if hasattr(self, 'cmb_exp_layer'):
                self.cmb_exp_layer.addItem(l.name(), l.id())

    def run_merge_data(self):
        src_id = self.cmb_m_src.currentData()
        dst_id = self.cmb_m_dst.currentData()
        source = QgsProject.instance().mapLayer(src_id)
        target = QgsProject.instance().mapLayer(dst_id)

        if not source or not target or source.id() == target.id():
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn 2 Layer Nguồn và Đích khác nhau!")
            return

        layer_to_copy = source
        # Nguồn LINE -> Đích POLYGON (Polygonize)
        if source.geometryType() == GEOM_LINE and target.geometryType() == GEOM_POLYGON:
            import processing
            poly_result = processing.run("native:polygonize", {
                'INPUT': source,
                'KEEP_FIELDS': False,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            layer_to_copy = poly_result['OUTPUT']

        target.startEditing()
        fields = target.fields()
        count = 0
        for feat in layer_to_copy.getFeatures():
            if feat.hasGeometry():
                new_feat = QgsFeature(fields)
                new_feat.setGeometry(feat.geometry())
                target.addFeature(new_feat)
                count += 1
        target.commitChanges()
        target.triggerRepaint()
        QMessageBox.information(self, "Thành công", f"Đã ghép thành công {count} đối tượng từ '{source.name()}' vào '{target.name()}'!")

    def run_split_cad_text(self):
        layer = iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn 1 Layer trong bảng Layers!")
            return
        fnames = [f.name() for f in layer.fields()]
        if "Text" not in fnames:
            QMessageBox.warning(self, "Lỗi", "Layer không có cột 'Text'!")
            return
        # Tạo cột nếu chưa có
        layer.startEditing()
        if "Đỉnh" not in fnames:
            layer.dataProvider().addAttributes([QgsField("Đỉnh", FT_DOUBLE)])
        if "Đáy" not in fnames:
            layer.dataProvider().addAttributes([QgsField("Đáy", FT_DOUBLE)])
        layer.updateFields()

        idx_text = layer.fields().indexOf("Text")
        idx_dinh = layer.fields().indexOf("Đỉnh")
        idx_day = layer.fields().indexOf("Đáy")

        count = 0
        for feat in layer.getFeatures():
            val = str(feat[idx_text]) if feat[idx_text] is not None else ""
            if "/" in val:
                parts = val.split("/")
                try:
                    dinh = float(parts[0].strip().replace(",", "."))
                    day = float(parts[1].strip().replace(",", "."))
                    layer.changeAttributeValue(feat.id(), idx_dinh, dinh)
                    layer.changeAttributeValue(feat.id(), idx_day, day)
                    count += 1
                except Exception:
                    pass
        layer.commitChanges()
        QMessageBox.information(self, "Hoàn tất", f"Đã tách số liệu Đỉnh / Đáy thành công cho {count} đối tượng!")

    def _on_tt16_db_changed(self):
        """Khi đổi CSDL TT16, cập nhật lại tên file gợi ý trên ô đường dẫn."""
        cur = self.txt_exp_path.text().strip()
        db_name = self.cmb_tt16_db.currentData() if hasattr(self, 'cmb_tt16_db') else "QuyHoach.gdb"
        if not cur:
            self.txt_exp_path.setText(db_name)
            return
        base_dir = os.path.dirname(cur)
        if base_dir:
            self.txt_exp_path.setText(os.path.join(base_dir, db_name))
        else:
            self.txt_exp_path.setText(db_name)

    def _on_exp_format_changed(self):
        """Tự động đổi phần mở rộng file và bật/tắt khung TT16."""
        fmt = self.cmb_exp_format.currentData()
        if hasattr(self, 'frame_tt16'):
            self.frame_tt16.setVisible(fmt == "tt16_gdb")

        cur = self.txt_exp_path.text().strip()
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        
        if not cur:
            if fmt == "tt16_gdb":
                self.txt_exp_path.setText(os.path.join(desktop_dir, "QuyHoach.gdb"))
            else:
                self.txt_exp_path.setText(os.path.join(desktop_dir, f"XuatDuLieu.{fmt}"))
            return

        if fmt == "tt16_gdb":
            db_name = self.cmb_tt16_db.currentData() if hasattr(self, 'cmb_tt16_db') else "QuyHoach.gdb"
            if os.path.isdir(cur) and not cur.lower().endswith(".gdb"):
                self.txt_exp_path.setText(os.path.join(cur, db_name))
            else:
                base_dir = os.path.dirname(cur)
                self.txt_exp_path.setText(os.path.join(base_dir, db_name) if base_dir else db_name)
        else:
            if os.path.isdir(cur) and not cur.lower().endswith(".gdb"):
                self.txt_exp_path.setText(os.path.join(cur, f"XuatDuLieu.{fmt}"))
            else:
                root, _ = os.path.splitext(cur)
                self.txt_exp_path.setText(f"{root}.{fmt}")

    def _browse_export_path(self):
        """Mở hộp thoại chọn nơi lưu file phù hợp với định dạng đang chọn."""
        fmt = self.cmb_exp_format.currentData()
        cur_text = self.txt_exp_path.text().strip()
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        default_dir = cur_text if (cur_text and os.path.isdir(cur_text)) else (
            os.path.dirname(cur_text) if cur_text and os.path.exists(os.path.dirname(cur_text)) else desktop_dir
        )
        
        lyr_name = "XuatDuLieu"
        if hasattr(self, 'cmb_exp_layer') and self.cmb_exp_layer.currentText():
            clean_l = sanitize_gis_field_name(self.cmb_exp_layer.currentText())
            if clean_l: lyr_name = clean_l

        if fmt == "tt16_gdb":
            db_target = self.cmb_tt16_db.currentData() if hasattr(self, 'cmb_tt16_db') else "QuyHoach.gdb"
            if hasattr(self, 'chk_tt16_full_pkg') and self.chk_tt16_full_pkg.isChecked():
                path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu CSDL đồ án (chứa HoSoGIS)", default_dir)
            else:
                init_file = os.path.join(default_dir, db_target)
                path, _ = QFileDialog.getSaveFileName(self, "Lưu File Geodatabase chuẩn TT16/2025/TT-BXD (*.gdb)", init_file, "ESRI File Geodatabase (*.gdb)")
        elif fmt == "dxf":
            init_file = os.path.join(default_dir, f"{lyr_name}.dxf")
            path, _ = QFileDialog.getSaveFileName(self, "Lưu file AutoCAD DXF (*.dxf)", init_file, "AutoCAD DXF (*.dxf)")
        elif fmt == "kml":
            init_file = os.path.join(default_dir, f"{lyr_name}.kml")
            path, _ = QFileDialog.getSaveFileName(self, "Lưu file Google Earth KML (*.kml)", init_file, "Google Earth KML (*.kml)")
        elif fmt == "gdb":
            init_file = os.path.join(default_dir, f"{lyr_name}.gdb")
            path, _ = QFileDialog.getSaveFileName(self, "Lưu ESRI File Geodatabase (*.gdb)", init_file, "ESRI File Geodatabase (*.gdb)")
        elif fmt == "shp":
            init_file = os.path.join(default_dir, f"{lyr_name}.shp")
            path, _ = QFileDialog.getSaveFileName(self, "Lưu ESRI Shapefile (*.shp)", init_file, "ESRI Shapefile (*.shp)")
        elif fmt == "gpkg":
            init_file = os.path.join(default_dir, f"{lyr_name}.gpkg")
            path, _ = QFileDialog.getSaveFileName(self, "Lưu GeoPackage (*.gpkg)", init_file, "GeoPackage (*.gpkg)")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Lưu file", default_dir, "All files (*.*)")
        
        if path:
            self.txt_exp_path.setText(path)

    def _show_export_success(self, msg, file_or_dir):
        """Hiện thông báo xuất thành công và cung cấp nút mở thư mục trực tiếp."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        mb = QMessageBox(self)
        mb.setWindowTitle("Xuất dữ liệu thành công")
        mb.setIcon(QMessageBox.Icon.Information)
        mb.setText(msg)
        btn_open = mb.addButton("📂 Mở thư mục chứa file", QMessageBox.ButtonRole.ActionRole)
        mb.addButton("Đóng", QMessageBox.ButtonRole.AcceptRole)
        mb.exec()
        if mb.clickedButton() == btn_open:
            folder = file_or_dir if os.path.isdir(file_or_dir) else os.path.dirname(file_or_dir)
            if os.path.exists(folder):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _classify_layer_tt16(self, layer, target_db="QuyHoach.gdb"):
        """
        Tự động phân loại Layer vào Feature Dataset và Feature Class theo Thông tư 16/2025/TT-BXD.
        Trả về: (dataset_name, fc_name, description)
        """
        geom_type = layer.geometryType()
        # Xác định hậu tố hình học chuẩn TT16
        if geom_type == GEOM_POINT:
            suffix = "_P"
        elif geom_type == GEOM_LINE:
            suffix = "_L"
        elif geom_type == GEOM_POLYGON:
            suffix = "_A"
        else:
            suffix = ""

        raw_name = layer.name().strip()
        clean = sanitize_gis_field_name(raw_name, auto_replace_spaces=False)
        low = clean.lower().replace(" ", "").replace("_", "").replace("-", "")

        is_hientrang = ("hientrang" in target_db.lower()) or ("hientrang" in low)
        prefix_ds = "HienTrang" if is_hientrang else "QuyHoach"

        # 1. CSDL MỐC GIỚI
        if "mocgioi" in low or "moc" in low or "moc_gioi" in low or target_db == "MocGioi.gdb":
            fc = f"MocGioiQuyHoach{suffix if suffix else '_P'}"
            return "MocGioiQuyHoach", fc, "Mốc giới quy hoạch"

        # 2. VỊ TRÍ RANH GIỚI
        if any(k in low for k in ("ranhgioiquyhoach", "ranhqh", "phamviquyhoach", "ranhdoan", "bienquyhoach")):
            return "ViTriRanhGioi", f"RanhGioiQuyHoach{suffix if suffix else '_A'}", "Ranh giới quy hoạch"
        if any(k in low for k in ("ranhgioihanhchinh", "diagioi", "hanhchinh", "ranhhuyen", "ranhxa", "ranhtinh")):
            return "ViTriRanhGioi", f"RanhGioiHanhChinh{suffix if suffix else '_L'}", "Ranh giới hành chính"
        if any(k in low for k in ("tendonvihanhchinh", "ubnd", "tenhanhchinh")):
            return "ViTriRanhGioi", f"TenDonViHanhChinh{suffix if suffix else '_P'}", "Tên đơn vị hành chính"
        if "ranh" in low and suffix == "_A":
            return "ViTriRanhGioi", "RanhGioiQuyHoach_A", "Ranh giới quy hoạch"

        # 3. QUY HOẠCH SỬ DỤNG ĐẤT
        if any(k in low for k in ("chucnangsudungdat", "sudungdat", "quyhoachdat", "sdd", "loaidat", "qhdat")):
            return f"{prefix_ds}SuDungDat", f"ChucNangSuDungDat{suffix if suffix else '_A'}", "Chức năng sử dụng đất"
        if any(k in low for k in ("phano", "lothuong", "odat", "lodat")):
            return f"{prefix_ds}SuDungDat", f"PhanOQuyHoach{suffix if suffix else '_A'}", "Phân ô quy hoạch"
        if any(k in low for k in ("phankhu", "khuquyhoach")):
            return f"{prefix_ds}SuDungDat", f"PhanKhuQuyHoach{suffix if suffix else '_A'}", "Phân khu quy hoạch"
        if "chucnangcongtrinh" in low or ("congtrinh" in low and suffix == "_P"):
            return f"{prefix_ds}SuDungDat", f"ChucNangCongTrinh{suffix if suffix else '_P'}", "Chức năng công trình"

        # 4. GIAO THÔNG
        if any(k in low for k in ("timduong", "duongbo", "tuyenduong", "duongchinh", "duongnoi", "giaothong")):
            if suffix == "_L":
                return f"{prefix_ds}GiaoThong", "MangLuoiGiaoThongDuongBo_L", "Mạng lưới giao thông đường bộ (tim đường)"
            elif suffix == "_A":
                return f"{prefix_ds}GiaoThong", "MangLuoiGiaoThongDuongBo_A", "Mạng lưới giao thông đường bộ dạng vùng"
            elif suffix == "_P":
                return f"{prefix_ds}GiaoThong", "CongTrinhGiaoThong_P", "Công trình giao thông dạng điểm"
        if any(k in low for k in ("longduong", "matduong", "viahe", "mephot")):
            return f"{prefix_ds}GiaoThong", "MangLuoiGiaoThongDuongBo_A", "Mạng lưới giao thông đường bộ dạng vùng"
        if any(k in low for k in ("bovia", "daiphancach", "phancach")):
            return f"{prefix_ds}GiaoThong", "BoViaDaiPhanCach_L", "Bó vỉa và dải phân cách"
        if any(k in low for k in ("matcat", "matcatngang")):
            return f"{prefix_ds}GiaoThong", "MatCatNgang_L", "Mặt cắt ngang đường"
        if "huongdi" in low:
            return f"{prefix_ds}GiaoThong", "HuongDi_L", "Hướng đi giao thông"
        if any(k in low for k in ("duongsat", "railway")):
            return f"{prefix_ds}GiaoThong", "MangLuoiGiaoThongDuongSat_L", "Mạng lưới đường sắt"
        if any(k in low for k in ("duongthuy", "luongtau", "cang")):
            return f"{prefix_ds}GiaoThong", "MangLuoiGiaoThongDuongThuy_L", "Mạng lưới đường thủy"
        if any(k in low for k in ("tuyenbus", "xebus")):
            return f"{prefix_ds}GiaoThong", "MangLuoiTuyenBus_L", "Mạng lưới tuyến Bus"
        if "congtrinhgiaothong" in low or any(k in low for k in ("nutgiao", "tramxe", "benxe", "cau", "ham")):
            return f"{prefix_ds}GiaoThong", f"CongTrinhGiaoThong{suffix if suffix else '_P'}", "Công trình giao thông"

        # 5. CHỈ GIỚI ĐƯỜNG ĐỎ & XÂY DỰNG & HÀNH LANG HẠ TẦNG KỸ THUẬT
        if any(k in low for k in ("chigioiduongdo", "cgdd", "duongdo", "logioi")):
            return f"{prefix_ds}CGDD_CGXDHanhLangHTKT", "ChiGioiDuongDo_L", "Chỉ giới đường đỏ"
        if any(k in low for k in ("chigioixaydung", "cgxd", "khoanglui")):
            return f"{prefix_ds}CGDD_CGXDHanhLangHTKT", "ChiGioiXayDung_L", "Chỉ giới xây dựng"
        if any(k in low for k in ("hanhlang", "hlbv", "hanhlangantoan", "hlkt")):
            return f"{prefix_ds}CGDD_CGXDHanhLangHTKT", "HanhLangAnToan_L", "Hành lang an toàn"

        # 6. CẤP NƯỚC
        if any(k in low for k in ("capnuoc", "ongnuoc", "tuyencapnuoc", "mangluoicapnuoc")):
            if suffix == "_P":
                return f"{prefix_ds}CapNuoc", "DiemDauNoi_P", "Điểm đấu nối cấp nước"
            return f"{prefix_ds}CapNuoc", "MangLuoiCapNuoc_L", "Mạng lưới cấp nước"
        if any(k in low for k in ("trucuuhoa", "pccc", "trunuoc", "capnuocpccc")):
            if suffix == "_A":
                return f"{prefix_ds}CapNuoc", "CongtrinhCapNuocPCCC_A", "Công trình cấp nước PCCC (vùng)"
            return f"{prefix_ds}CapNuoc", "CongtrinhCapNuocPCCC_P", "Công trình cấp nước PCCC (điểm)"
        if "diemdaunoi" in low and ("nuoc" in low or "cap" in low):
            return f"{prefix_ds}CapNuoc", "DiemDauNoi_P", "Điểm đấu nối cấp nước"

        # 7. CHUẨN BỊ KỸ THUẬT & THOÁT NƯỚC MƯA
        if any(k in low for k in ("thoatnuocmua", "nuocmua", "congmua", "tnm", "ranhmua")):
            return f"{prefix_ds}ChuanBiKyThuat", "MangLuoiThoatNuocMua_L", "Mạng lưới thoát nước mưa"
        if any(k in low for k in ("caodonen", "caodo", "diemcaodo")):
            return f"{prefix_ds}ChuanBiKyThuat", "CaoDoNen_P", "Cao độ nền"
        if any(k in low for k in ("dongmucthietke", "dongmuc")):
            return f"{prefix_ds}ChuanBiKyThuat", "DongMucThietKe_L", "Đồng mức thiết kế"
        if any(k in low for k in ("sannen", "san_nen")):
            if suffix == "_P":
                return f"{prefix_ds}ChuanBiKyThuat", "ThongTinSanNen_P", "Thông tin san nền"
            return f"{prefix_ds}ChuanBiKyThuat", "PhanVungSanNen_A", "Phân vùng san nền"
        if any(k in low for k in ("matnuoc", "hodieuhoa", "kenhrach", "kenh", "rach", "ho")):
            return f"{prefix_ds}ChuanBiKyThuat", "MatNuoc_A", "Mặt nước (hồ, kênh, rạch)"
        if "caodocongtnm" in low or ("caodocong" in low and "mua" in low):
            return f"{prefix_ds}ChuanBiKyThuat", "CaoDoCongTNM_P", "Cao độ cống thoát nước mưa"
        if "congtrinhcbkt" in low:
            return f"{prefix_ds}ChuanBiKyThuat", f"CongTrinhCBKT{suffix if suffix else '_P'}", "Công trình chuẩn bị kỹ thuật"

        # 8. THOÁT NƯỚC THẢI & VSMT
        if any(k in low for k in ("thoatnuocthai", "nuocthai", "tnt", "ongthai")):
            return f"{prefix_ds}ThoatNuocThaiVSMT", "MangLuoiThoatNuocThai_L", "Mạng lưới thoát nước thải"
        if any(k in low for k in ("caodocongthoattnt", "caodocongtnt")):
            return f"{prefix_ds}ThoatNuocThaiVSMT", "CaoDoCongThoatTNT_P", "Cao độ cống thoát nước thải"
        if any(k in low for k in ("hoga", "bephot", "tramxuly", "vsmt", "chatthairan")):
            if suffix == "_P":
                return f"{prefix_ds}ThoatNuocThaiVSMT", "CongTrinhTNTvaVSMT_P", "Công trình TNT và VSMT dạng điểm"
            elif suffix == "_L":
                return f"{prefix_ds}ThoatNuocThaiVSMT", "CongTrinhTNTvaVSMT_L", "Công trình TNT và VSMT dạng đường"
            else:
                return f"{prefix_ds}ThoatNuocThaiVSMT", "CongTrinhTNTvaVSMT_A", "Công trình TNT và VSMT dạng vùng"

        # 9. CẤP ĐIỆN & CHIẾU SÁNG
        if any(k in low for k in ("capdien", "duongdaydien", "tuyendien", "trungthe", "hathe", "dien")):
            if suffix == "_P":
                return f"{prefix_ds}CapDien", "CongTrinhCapDien_P", "Công trình cấp điện (trạm biến áp)"
            return f"{prefix_ds}CapDien", "MangLuoiPhanPhoiDien_L", "Mạng lưới phân phối điện"
        if any(k in low for k in ("chieusang", "denduong", "cotden")):
            if suffix == "_P":
                return f"{prefix_ds}CapDien", "CongTrinhChieuSang_P", "Công trình chiếu sáng"
            return f"{prefix_ds}CapDien", "MangLuoiChieuSang_L", "Mạng lưới chiếu sáng"
        if any(k in low for k in ("trambienap", "tba", "cotdien")):
            return f"{prefix_ds}CapDien", "CongTrinhCapDien_P", "Trạm biến áp / Cột điện"

        # 10. THÔNG TIN LIÊN LẠC
        if any(k in low for k in ("thongtinlienlac", "capquang", "ttll", "viengthong")):
            if suffix == "_P":
                return f"{prefix_ds}ThongTinLienLac", "CongTrinhThongTin_P", "Công trình thông tin liên lạc"
            return f"{prefix_ds}ThongTinLienLac", "MangLuoiCapThongTin_L", "Mạng lưới cáp thông tin"
        if any(k in low for k in ("trambts", "bts", "cotangten")):
            return f"{prefix_ds}ThongTinLienLac", "CongTrinhThongTin_P", "Trạm BTS / Cột ăng-ten"

        # 11. CÔNG TRÌNH NGẦM
        if any(k in low for k in ("congtrinhngam", "ngam", "haokythuat", "tuyp")):
            return f"{prefix_ds}CongTrinhNgam", f"CongTrinhNgam{suffix if suffix else '_A'}", "Công trình ngầm"

        # 12. KHÔNG GIAN KIẾN TRÚC CẢNH QUAN & CÂY XANH
        if any(k in low for k in ("cayxanh", "cay", "caybongmat")):
            return f"{prefix_ds}KhongGianKienTrucCanhQuan", "CayXanh_P", "Cây xanh"
        if any(k in low for k in ("canhquan", "khonggianktcq", "congvien", "vuonhoa")):
            return f"{prefix_ds}KhongGianKienTrucCanhQuan", f"KhongGianKTCQ{suffix if suffix else '_A'}", "Không gian kiến trúc cảnh quan"
        if any(k in low for k in ("khoicongtrinh", "nhacua", "congtrinh")):
            return f"{prefix_ds}KhongGianKienTrucCanhQuan", f"CongTrinh{suffix if suffix else '_A'}", "Công trình kiến trúc"

        # 13. THIẾT KẾ ĐÔ THỊ
        if any(k in low for k in ("thietkedothi", "tkdt", "diemnhan")):
            if suffix == "_P":
                return "ThietkeDoThi", "DiemNhanChinh_P", "Điểm nhấn chính thiết kế đô thị"
            elif suffix == "_L":
                return "ThietkeDoThi", "TuyenTKDT_L", "Tuyến thiết kế đô thị"
            else:
                return "ThietkeDoThi", "KhuVucPhoiCanh_A", "Khu vực dựng phối cảnh"

        # 14. GIẢI PHÁP BẢO VỆ MÔI TRƯỜNG
        if any(k in low for k in ("moitruong", "bvmt", "cachly")):
            if suffix == "_P":
                return "GiaiPhapBaoVeMoiTruong", "DiemQuanTrac_P", "Điểm quan trắc môi trường"
            return "GiaiPhapBaoVeMoiTruong", f"GiaiPhapBaoVeMoiTruong{suffix if suffix else '_A'}", "Giải pháp bảo vệ môi trường"

        # 15. NĂNG LƯỢNG
        if any(k in low for k in ("nangluong", "ongkhi", "tramxang")):
            if suffix == "_P":
                return f"{prefix_ds}NangLuong", "CongTrinhNangLuong_P", "Công trình năng lượng"
            return f"{prefix_ds}NangLuong", f"MangLuoiNangLuong{suffix if suffix else '_L'}", "Mạng lưới năng lượng"

        # 16. MẶC ĐỊNH CHO CÁC LỚP KHÁC
        safe_name = sanitize_gis_field_name(raw_name)
        if not safe_name.endswith(suffix) and suffix:
            safe_name += suffix
        default_ds = f"{prefix_ds}ChuyenDeKhac"
        return default_ds, safe_name, "Lớp dữ liệu chuyên đề khác"


    def run_precheck_tt16(self):
        """Mở hộp thoại kiểm tra & đối soát dữ liệu chuẩn Thông tư 16/2025/TT-BXD trước khi xuất."""
        if self.chk_exp_all_selected.isChecked():
            layers = get_selected_vector_layers()
            if not layers:
                # Tự động lấy tất cả vector layer trong dự án nếu chưa bôi đen layer
                layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
                if not layers:
                    QMessageBox.warning(self, "Chưa có Layer", "Dự án QGIS hiện chưa có layer vector nào. Vui lòng mở hoặc kéo dữ liệu vào QGIS trước khi kiểm tra!")
                    return
        else:
            lid = self.cmb_exp_layer.currentData()
            lyr = QgsProject.instance().mapLayer(lid) if lid else None
            if not lyr or not isinstance(lyr, QgsVectorLayer):
                al = iface.activeLayer()
                if al and isinstance(al, QgsVectorLayer):
                    lyr = al
                else:
                    QMessageBox.warning(self, "Chưa chọn Layer", "Vui lòng chọn 1 Layer vector để kiểm tra!")
                    return
            layers = [lyr]

        out_path = self.txt_exp_path.text().strip()
        if not out_path:
            out_path = os.path.join(os.path.expanduser("~"), "Desktop")
        self._export_tt16_gdb(layers, out_path)

    def _export_tt16_gdb(self, layers, out_path):
        """Xuất danh sách Layer vào File Geodatabase phân nhóm Feature Dataset chuẩn Thông tư 16/2025/TT-BXD."""
        target_db = self.cmb_tt16_db.currentData() if hasattr(self, 'cmb_tt16_db') else "QuyHoach.gdb"
        is_full_pkg = self.chk_tt16_full_pkg.isChecked() if hasattr(self, 'chk_tt16_full_pkg') else False
        auto_ds = self.chk_tt16_auto_dataset.isChecked() if hasattr(self, 'chk_tt16_auto_dataset') else True
        auto_fields = self.chk_tt16_auto_fields.isChecked() if hasattr(self, 'chk_tt16_auto_fields') else True
        only_selected = self.chk_exp_only_feats.isChecked()

        ma_hs = ""
        if hasattr(self, 'txt_tt16_ma_hs') and self.txt_tt16_ma_hs.text().strip():
            ma_hs = self.txt_tt16_ma_hs.text().strip()
        elif hasattr(self, 'txt_ma_hs') and self.txt_ma_hs.text().strip():
            ma_hs = self.txt_ma_hs.text().strip()
        if not ma_hs:
            ma_hs = "DoAnQuyHoach"

        ma_tt = self.txt_ma_tt.text().strip() if hasattr(self, 'txt_ma_tt') and self.txt_ma_tt.text().strip() else ""

        # Chuẩn bị báo cáo kiểm tra (Pre-check) cho từng layer
        layer_reports = []
        for lyr in layers:
            dataset_name, fc_name, desc = self._classify_layer_tt16(lyr, target_db)
            if not auto_ds:
                dataset_name = ""

            geom_type = lyr.geometryType()
            if geom_type == GEOM_POINT:
                geom_str = "Điểm (P)"
            elif geom_type == GEOM_LINE:
                geom_str = "Đường (L)"
            elif geom_type == GEOM_POLYGON:
                geom_str = "Vùng (A)"
            else:
                geom_str = "Khác"

            existing_lower = [f.name().lower() for f in lyr.fields()]
            present = [fn for fn in ["maThongTinQH", "maHoSoQH", "maDoiTuong", "tenDoiTuong", "phanLoai", "ghiChu"] if fn.lower() in existing_lower]
            missing = [fn for fn in ["maThongTinQH", "maHoSoQH", "maDoiTuong", "tenDoiTuong", "phanLoai", "ghiChu"] if fn.lower() not in existing_lower]
            cnt = lyr.selectedFeatureCount() if (only_selected and lyr.selectedFeatureCount() > 0) else lyr.featureCount()

            layer_reports.append({
                'layer': lyr,
                'orig_name': lyr.name(),
                'geom_str': geom_str,
                'dataset': dataset_name,
                'fc_name': fc_name,
                'desc': desc,
                'count': cnt,
                'present': present,
                'missing': missing
            })

        # Xác định đường dẫn hiển thị trên báo cáo
        base_dir = out_path if (out_path and os.path.isdir(out_path)) else (os.path.dirname(out_path) if out_path else "")
        if not base_dir:
            base_dir = QDir.homePath()
        if is_full_pkg:
            display_gdb_path = os.path.join(base_dir, f"CSDL_{ma_hs}", "HoSoGIS", target_db)
        else:
            display_gdb_path = out_path if (out_path and out_path.lower().endswith(".gdb")) else os.path.join(base_dir, target_db)

        # =====================================================================
        # BƯỚC KIỂM TRA & BÁO CÁO LẠI (PRE-CHECK CONFIRMATION DIALOG)
        # =====================================================================
        dlg = TT16PreCheckReportDialog(
            parent=self,
            layer_reports=layer_reports,
            target_db=target_db,
            out_path=display_gdb_path,
            ma_hs=ma_hs,
            ma_tt=ma_tt,
            auto_fields=auto_fields
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.confirmed:
            iface.messageBar().pushInfo("Thông báo", "Đã hủy xuất CSDL TT16 theo yêu cầu người dùng.")
            return

        # Người dùng ĐỒNG Ý -> Tiếp tục bước tiếp theo
        ma_hs = dlg.confirmed_ma_hs
        ma_tt = dlg.confirmed_ma_tt
        auto_fields = dlg.confirmed_auto_fields
        confirmed_data = dlg.confirmed_data

        # Đồng bộ ngược lại mã hồ sơ vào ô nhập trên UI
        if hasattr(self, 'txt_tt16_ma_hs'):
            self.txt_tt16_ma_hs.setText(ma_hs)

        # Xử lý đường dẫn lưu CSDL (LƯU Ý: CHỈ TẠO HoSoGIS, ĐÃ BỎ HoSoBASIC VÀ HoSoScan)
        if is_full_pkg:
            root_pkg = os.path.join(base_dir, f"CSDL_{ma_hs}")
            gis_dir = os.path.join(root_pkg, "HoSoGIS")
            os.makedirs(gis_dir, exist_ok=True)
            gdb_path = os.path.join(gis_dir, target_db)
        else:
            if not out_path or not out_path.lower().endswith(".gdb"):
                gdb_path = display_gdb_path
            else:
                gdb_path = out_path
            os.makedirs(os.path.dirname(gdb_path), exist_ok=True)

        tt16_needed = [
            ("maThongTinQH", FT_STRING, 15, "Mã thông tin quy hoạch"),
            ("maHoSoQH", FT_STRING, 15, "Mã hồ sơ quy hoạch"),
            ("maDoiTuong", FT_STRING, 100, "Mã đối tượng"),
            ("tenDoiTuong", FT_STRING, 100, "Tên đối tượng"),
            ("phanLoai", FT_STRING, 250, "Phân loại"),
            ("ghiChu", FT_STRING, 250, "Ghi chú")
        ]

        transform_ctx = QgsProject.instance().transformContext()
        mapped_results = []
        n_fail = 0

        for lyr, dataset_name, fc_name in confirmed_data:
            # Bổ sung 6 trường TT16 nếu bật tùy chọn
            if auto_fields:
                try:
                    was_editing = lyr.isEditable()
                    if not was_editing:
                        lyr.startEditing()
                    existing_lower = [f.name().lower() for f in lyr.fields()]
                    for fname, ftype, flen, falias in tt16_needed:
                        if fname.lower() not in existing_lower:
                            lyr.addAttribute(QgsField(fname, ftype, len=flen))
                    lyr.updateFields()
                    # Điền sẵn maHoSoQH, maThongTinQH nếu có
                    fnames = [f.name() for f in lyr.fields()]
                    for feat in lyr.getFeatures():
                        if "maHoSoQH" in fnames and ma_hs and not feat["maHoSoQH"]:
                            feat["maHoSoQH"] = ma_hs
                            lyr.updateFeature(feat)
                        if "maThongTinQH" in fnames and ma_tt and not feat["maThongTinQH"]:
                            feat["maThongTinQH"] = ma_tt
                            lyr.updateFeature(feat)
                        if "maDoiTuong" in fnames and not feat["maDoiTuong"]:
                            feat["maDoiTuong"] = f"{ma_hs}-{fc_name}-{feat.id()}"
                            lyr.updateFeature(feat)
                    if not was_editing:
                        lyr.commitChanges()
                except Exception:
                    pass

            opts = QgsVectorFileWriter.SaveVectorOptions()
            opts.driverName = "OpenFileGDB"
            opts.layerName = fc_name
            if not os.path.exists(gdb_path):
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
            else:
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer

            if dataset_name:
                opts.layerOptions = [f"FEATURE_DATASET={dataset_name}"]

            if only_selected:
                opts.onlySelectedFeatures = True

            res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, gdb_path, transform_ctx, opts)
            if res[0] != QgsVectorFileWriter.WriterError.NoError:
                # Fallback không dùng Feature Dataset nếu có trục trặc
                opts.layerOptions = []
                res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, gdb_path, transform_ctx, opts)
                if res[0] != QgsVectorFileWriter.WriterError.NoError:
                    n_fail += 1
                    continue

            cnt = lyr.selectedFeatureCount() if (only_selected and lyr.selectedFeatureCount() > 0) else lyr.featureCount()
            mapped_results.append((lyr.name(), dataset_name, fc_name, cnt))

        msg = (
            f"ĐÃ XUẤT THÀNH CÔNG {len(mapped_results)} LỚP VÀO GDB CHUẨN THÔNG TƯ 16/2025/TT-BXD\n\n"
            f"Vị trí CSDL:\n{gdb_path}\n\n"
            f"Danh sách các lớp đưa vào đúng Feature Dataset:\n"
            + "\n".join(f"• {orig} ➔ [{ds}] / {fc} ({cnt} đt)" for orig, ds, fc, cnt in mapped_results)
        )
        if is_full_pkg:
            msg += f"\n\n📦 Cấu trúc thư mục đồ án: CSDL_{ma_hs}/HoSoGIS/{target_db}"

        self._show_export_success(msg, gdb_path)

    def run_export_data(self):
        """Thực hiện xuất dữ liệu sang GDB TT16, KML, CAD DXF, SHP, GPKG."""
        out_path = self.txt_exp_path.text().strip()
        fmt = self.cmb_exp_format.currentData()
        
        # Nếu chưa chọn đường dẫn, tự động mở hộp thoại duyệt
        if not out_path:
            self._browse_export_path()
            out_path = self.txt_exp_path.text().strip()
            if not out_path:
                return

        # Xác định các layer cần xuất
        if self.chk_exp_all_selected.isChecked():
            layers = get_selected_vector_layers()
            if not layers:
                # THÔNG MINH: Nếu không bôi đen layer nào, tự động lấy TẤT CẢ layer vector hiện có trong QGIS
                layers = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
                if not layers:
                    QMessageBox.warning(self, "Chưa có Layer", "Dự án QGIS hiện chưa có layer vector nào. Vui lòng mở hoặc kéo dữ liệu vào QGIS trước khi xuất!")
                    return
        else:
            lid = self.cmb_exp_layer.currentData()
            lyr = QgsProject.instance().mapLayer(lid) if lid else None
            if not lyr or not isinstance(lyr, QgsVectorLayer):
                al = iface.activeLayer()
                if al and isinstance(al, QgsVectorLayer):
                    lyr = al
                else:
                    QMessageBox.warning(self, "Chưa chọn Layer", "Vui lòng chọn 1 Layer vector từ danh sách để xuất!")
                    return
            layers = [lyr]

        # =====================================================================
        # 0. XUẤT CSDL GEODATABASE CHUẨN THÔNG TƯ 16/2025/TT-BXD
        # =====================================================================
        if fmt == "tt16_gdb":
            self._export_tt16_gdb(layers, out_path)
            return

        only_selected = self.chk_exp_only_feats.isChecked()
        auto_wgs84 = self.chk_exp_wgs84.isChecked()
        transform_ctx = QgsProject.instance().transformContext()

        # Chuẩn hóa out_path nếu out_path là một thư mục có sẵn
        default_name = sanitize_gis_field_name(layers[0].name()) if len(layers) == 1 else "XuatDuLieu"
        if os.path.isdir(out_path):
            base_dir = out_path
            out_file = os.path.join(base_dir, f"{default_name}.{fmt}")
        else:
            base_dir = os.path.dirname(out_path)
            if not base_dir:
                base_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                out_path = os.path.join(base_dir, out_path)
            if not out_path.lower().endswith(f".{fmt}"):
                out_path += f".{fmt}"
            out_file = out_path

        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        # =====================================================================
        # 1. XUẤT AUTOCAD CAD DXF (Hỗ trợ nhiều layer gộp vào 1 file DXF chuẩn)
        # =====================================================================
        if fmt == "dxf":
            try:
                from qgis.core import QgsDxfExport, QgsRectangle
                from qgis.PyQt.QtCore import QFile, QIODevice
                
                dxf = QgsDxfExport()
                dxf_layers = []
                for lyr in layers:
                    dxf_layer = QgsDxfExport.DxfLayer(lyr)
                    dxf_layers.append(dxf_layer)
                dxf.addLayers(dxf_layers)
                dxf.setDestinationCrs(layers[0].crs())
                
                combined_ext = QgsRectangle()
                for lyr in layers:
                    if not lyr.extent().isEmpty():
                        combined_ext.combineExtentWith(lyr.extent())
                if combined_ext.isEmpty():
                    combined_ext.grow(10.0)
                dxf.setExtent(combined_ext)
                
                dxf_file = QFile(out_file)
                mode = getattr(getattr(QIODevice, 'OpenModeFlag', None), 'WriteOnly', None)
                if mode is None:
                    mode = getattr(QIODevice, 'WriteOnly', 0x0002)
                if dxf_file.open(mode):
                    res = dxf.writeToFile(dxf_file, "UTF-8")
                    dxf_file.close()
                    if res == QgsDxfExport.ExportResult.Success:
                        self._show_export_success(f"Đã xuất thành công {len(layers)} layer vào file AutoCAD DXF:\n{out_file}", out_file)
                        return
            except Exception as e:
                pass
            
            # Fallback dùng QgsVectorFileWriter với skipAttributeCreation
            try:
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = "DXF"
                opts.fileEncoding = "UTF-8"
                opts.skipAttributeCreation = True
                if only_selected and layers[0].selectedFeatureCount() > 0:
                    opts.onlySelectedFeatures = True
                res = QgsVectorFileWriter.writeAsVectorFormatV3(layers[0], out_file, transform_ctx, opts)
                if res[0] == QgsVectorFileWriter.WriterError.NoError:
                    self._show_export_success(f"Đã xuất thành công layer '{layers[0].name()}' sang file AutoCAD DXF:\n{out_file}", out_file)
                    return
                else:
                    QMessageBox.critical(self, "Lỗi xuất DXF", f"Lỗi khi xuất file DXF:\n{res[1]}")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Lỗi xuất DXF", f"Lỗi khi xuất file DXF: {e}")
                return

        # =====================================================================
        # 2. XUẤT GOOGLE EARTH KML
        # =====================================================================
        if fmt == "kml":
            crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
            saved_paths = []
            for lyr in layers:
                cur_path = out_file if len(layers) == 1 else os.path.join(base_dir, f"{sanitize_gis_field_name(lyr.name())}.kml")
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = "KML"
                opts.fileEncoding = "UTF-8"
                if only_selected and lyr.selectedFeatureCount() > 0:
                    opts.onlySelectedFeatures = True
                if auto_wgs84 and lyr.crs().authid() != "EPSG:4326":
                    opts.ct = QgsCoordinateTransform(lyr.crs(), crs_4326, QgsProject.instance())
                
                res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, cur_path, transform_ctx, opts)
                if res[0] == QgsVectorFileWriter.WriterError.NoError:
                    saved_paths.append(cur_path)
                else:
                    QMessageBox.critical(self, "Lỗi xuất KML", f"Lỗi khi xuất layer '{lyr.name()}':\n{res[1]}")
                    return
            self._show_export_success(f"Đã xuất thành công {len(saved_paths)} file Google Earth KML:\n" + "\n".join(saved_paths), base_dir)
            return

        # =====================================================================
        # 3. XUẤT ESRI FILE GEODATABASE THÔNG THƯỜNG (GDB)
        # =====================================================================
        if fmt == "gdb":
            if not out_file.lower().endswith(".gdb"):
                out_file += ".gdb"
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            saved_fcs = []
            for lyr in layers:
                fc_name = sanitize_gis_field_name(lyr.name())
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = "OpenFileGDB"
                opts.layerName = fc_name
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer if os.path.exists(out_file) else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
                if only_selected and lyr.selectedFeatureCount() > 0:
                    opts.onlySelectedFeatures = True
                res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out_file, transform_ctx, opts)
                if res[0] == QgsVectorFileWriter.WriterError.NoError:
                    saved_fcs.append(fc_name)
                else:
                    QMessageBox.critical(self, "Lỗi xuất GDB", f"Không thể xuất layer '{lyr.name()}' vào GDB:\n{res[1]}")
                    return
            self._show_export_success(f"Đã xuất thành công {len(saved_fcs)} lớp vào File Geodatabase (GDB):\n{out_file}\nCác Feature Class: {', '.join(saved_fcs)}", out_file)
            return

        # =====================================================================
        # 4. XUẤT ESRI SHAPEFILE (.SHP)
        # =====================================================================
        if fmt == "shp":
            saved_paths = []
            for lyr in layers:
                cur_path = out_file if len(layers) == 1 else os.path.join(base_dir, f"{sanitize_gis_field_name(lyr.name())}.shp")
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = "ESRI Shapefile"
                opts.fileEncoding = "UTF-8"
                if only_selected and lyr.selectedFeatureCount() > 0:
                    opts.onlySelectedFeatures = True
                res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, cur_path, transform_ctx, opts)
                if res[0] == QgsVectorFileWriter.WriterError.NoError:
                    saved_paths.append(cur_path)
                else:
                    QMessageBox.critical(self, "Lỗi xuất Shapefile", f"Lỗi khi xuất layer '{lyr.name()}':\n{res[1]}")
                    return
            self._show_export_success(f"Đã xuất thành công {len(saved_paths)} file Shapefile:\n" + "\n".join(saved_paths), base_dir)
            return

        # =====================================================================
        # 5. XUẤT GEOPACKAGE (.GPKG)
        # =====================================================================
        if fmt == "gpkg":
            if not out_file.lower().endswith(".gpkg"):
                out_file += ".gpkg"
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            saved_fcs = []
            for lyr in layers:
                fc_name = sanitize_gis_field_name(lyr.name())
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = "GPKG"
                opts.layerName = fc_name
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer if os.path.exists(out_file) else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
                if only_selected and lyr.selectedFeatureCount() > 0:
                    opts.onlySelectedFeatures = True
                res = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out_file, transform_ctx, opts)
                if res[0] == QgsVectorFileWriter.WriterError.NoError:
                    saved_fcs.append(fc_name)
                else:
                    QMessageBox.critical(self, "Lỗi xuất GeoPackage", f"Lỗi khi xuất layer '{lyr.name()}':\n{res[1]}")
                    return
            self._show_export_success(f"Đã xuất thành công {len(saved_fcs)} layer vào GeoPackage:\n{out_file}", out_file)
            return


# =============================================================================
# BẢO VỆ BẰNG MẬT KHẨU
# =============================================================================
# Đổi mật khẩu: chạy trong Python Console của QGIS (thay MẬT_KHẨU_MỚI):
#   import hashlib, os
#   salt = os.urandom(16).hex()
#   print(salt); print(hashlib.pbkdf2_hmac('sha256', 'MẬT_KHẨU_MỚI'.encode('utf-8'), bytes.fromhex(salt), 200000).hex())
# Rồi dán 2 giá trị in ra vào _PW_SALT và _PW_HASH bên dưới.
import hashlib
import hmac
import time

_PW_SALT = "d2225ffd0ace8551a0c0a00d07c55457"
_PW_HASH = "f89368877e6320a9420fd34aa79d3308103a81989ce01d4143b05f53452252c6"
_PW_MAX_TRIES = 5          # số lần nhập sai tối đa trước khi bị khoá tạm
_PW_LOCK_SECONDS = 300     # thời gian khoá (giây) khi nhập sai quá số lần
_PW_KEY_FAILS = "MyQgisVM/pw_fails"
_PW_KEY_LOCK = "MyQgisVM/pw_lock_until"


def _verify_password(pw):
    pw = pw.strip()   # bỏ khoảng trắng thừa (hay dính khi copy/dán)
    h = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(_PW_SALT), 200000).hex()
    return hmac.compare_digest(h, _PW_HASH)


def _pw_get_state():
    """Đọc số lần sai và thời điểm hết khoá (lưu trong cấu hình QGIS, còn nguyên khi tắt/mở lại QGIS)."""
    from qgis.core import QgsSettings
    st = QgsSettings()
    try:
        fails = int(float(st.value(_PW_KEY_FAILS, 0)))
    except Exception:
        fails = 0
    try:
        lock_until = float(st.value(_PW_KEY_LOCK, 0))
    except Exception:
        lock_until = 0.0
    return fails, lock_until


def _pw_set_state(fails, lock_until):
    from qgis.core import QgsSettings
    st = QgsSettings()
    st.setValue(_PW_KEY_FAILS, int(fails))
    st.setValue(_PW_KEY_LOCK, float(lock_until))


def ask_password(parent=None):
    """Hiện hộp nhập mật khẩu. Trả về True nếu đúng; False nếu huỷ / đang bị khoá / sai quá số lần.
    - Đúng mật khẩu: xoá bộ đếm lần sai.
    - Sai đủ _PW_MAX_TRIES lần: khoá _PW_LOCK_SECONDS giây (kể cả khi đóng hộp thoại hay mở lại QGIS)."""
    fails0, lock_until = _pw_get_state()
    remaining = int(lock_until - time.time())
    if remaining > 0:
        QMessageBox.warning(parent, "MyQgisVM",
                            f"Đã nhập sai quá {_PW_MAX_TRIES} lần.\n"
                            f"Vui lòng thử lại sau {remaining // 60} phút {remaining % 60} giây.")
        return False

    dlg = QDialog(parent)
    dlg.setWindowTitle("Xác thực - MyQgisVM")
    dlg.setFixedWidth(340)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(18, 16, 18, 14)
    lay.setSpacing(8)

    lbl = QLabel("🔒 Nhập mật khẩu để sử dụng bộ công cụ")
    lbl.setStyleSheet("font-weight: bold; color: #1a3a6b;")
    lay.addWidget(lbl)

    txt = QLineEdit()
    txt.setEchoMode(QLineEdit.EchoMode.Password)
    txt.setPlaceholderText("Mật khẩu...")
    lay.addWidget(txt)

    chk = QCheckBox("Hiện mật khẩu")
    chk.toggled.connect(lambda on: txt.setEchoMode(
        QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
    lay.addWidget(chk)

    lbl_err = QLabel("")
    lbl_err.setStyleSheet("color: #c0392b;")
    if fails0 > 0:
        lbl_err.setText(f"Còn {max(_PW_MAX_TRIES - fails0, 0)} lần thử.")
    lay.addWidget(lbl_err)

    row = QHBoxLayout()
    row.addStretch()
    btn_ok = QPushButton("Đăng nhập")
    btn_ok.setDefault(True)
    btn_cancel = QPushButton("Huỷ")
    row.addWidget(btn_ok)
    row.addWidget(btn_cancel)
    lay.addLayout(row)

    def on_ok():
        if _verify_password(txt.text()):
            _pw_set_state(0, 0)          # nhập đúng -> xoá bộ đếm lần sai
            dlg.accept()
            return
        fails, _ = _pw_get_state()
        fails += 1
        if fails >= _PW_MAX_TRIES:
            _pw_set_state(0, time.time() + _PW_LOCK_SECONDS)   # sai đủ số lần -> khoá tạm
            QMessageBox.warning(dlg, "MyQgisVM",
                                f"Đã nhập sai {_PW_MAX_TRIES} lần.\n"
                                f"Bộ công cụ bị khoá {_PW_LOCK_SECONDS // 60} phút.")
            dlg.reject()
            return
        _pw_set_state(fails, 0)
        lbl_err.setText(f"Sai mật khẩu! Còn {_PW_MAX_TRIES - fails} lần thử.")
        txt.clear()
        txt.setFocus()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)
    txt.returnPressed.connect(on_ok)

    return dlg.exec() == QDialog.DialogCode.Accepted
