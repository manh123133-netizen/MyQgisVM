# -*- coding: utf-8 -*-
import os
import sys

# Cho phép nạp thư mục runtime (pyarmor_runtime_*) nằm trong thư mục plugin (bản đã khoá mã)
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)


def classFactory(iface):
    from .plugin import MyQgisVMPlugin
    return MyQgisVMPlugin(iface)
