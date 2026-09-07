# 验证分配偏好模式的公共行为。
from __future__ import annotations

import unittest

from src.features.allocation.preference_modes import role_preference_mode_error


class AllocationPreferenceModeTests(unittest.TestCase):
    def test_role_priority_accepts_empty_optional_preferences(self):
        self.assertIsNone(role_preference_mode_error("role_priority", {}, {}, {}))
