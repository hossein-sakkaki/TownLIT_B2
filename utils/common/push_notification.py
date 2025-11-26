# utils/common/push_notification.py
"""
Deprecated shim for backwards compatibility.
Prefer using utils.firebase.push_engine.push_engine directly.
"""

from utils.firebase.push_engine import push_engine 

__all__ = ["push_engine"]
