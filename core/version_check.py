"""
Version compatibility checking for GTNH Mod Installer
"""
import re
from typing import List, Optional, Tuple

from utils.logger import logger
from core.minecraft import MinecraftPath
from core.installer import Resource, ResourceType


class VersionChecker:
    """Handles GTNH version compatibility checking"""

    def __init__(self, mc_path: MinecraftPath):
        self.mc_path = mc_path
        self._gtnh_version: Optional[str] = None
        self._parsed_version: Optional[Tuple[int, ...]] = None

    def set_version(self, version: str):
        """Manually set the GTNH version"""
        self._gtnh_version = version
        self._parsed_version = self._parse_version(version)
        logger.info(f"GTNH 版本已设置: {version}")

    def get_gtnh_version(self) -> Optional[str]:
        """Get current GTNH version"""
        return self._gtnh_version

    def _parse_version(self, version_str: str) -> Optional[Tuple[int, ...]]:
        """Parse version string to tuple of integers"""
        # Remove any non-numeric prefixes/suffixes
        clean = re.sub(r'[^\d.]', '', version_str)
        parts = clean.split('.')

        try:
            # Convert to integers, pad with zeros if needed
            int_parts = []
            for p in parts[:3]:  # Only take first 3 parts (major.minor.patch)
                int_parts.append(int(p) if p else 0)

            # Ensure we have 3 parts
            while len(int_parts) < 3:
                int_parts.append(0)

            return tuple(int_parts)
        except ValueError:
            return None

    def _version_matches(self, required: str, actual: Tuple[int, ...]) -> bool:
        """
        Check if actual version matches required version spec

        Supports formats:
        - "2.5.0" - exact match
        - "2.5.0+" - 2.5.0 or higher
        - "2.5.0-2.6.0" - between 2.5.0 and 2.6.0 inclusive
        - "<2.6.0" - less than 2.6.0
        - ">2.4.0" - greater than 2.4.0
        """
        required = required.strip()

        # Handle range (e.g., "2.5.0-2.6.0")
        if '-' in required and not required.startswith('<') and not required.startswith('>'):
            parts = required.split('-')
            if len(parts) == 2:
                min_ver = self._parse_version(parts[0])
                max_ver = self._parse_version(parts[1])
                if min_ver and max_ver:
                    return min_ver <= actual <= max_ver

        # Handle "or higher" (e.g., "2.5.0+")
        if required.endswith('+'):
            base = self._parse_version(required[:-1])
            if base:
                return actual >= base

        # Handle less than
        if required.startswith('<'):
            ver = self._parse_version(required[1:])
            if ver:
                return actual < ver

        # Handle greater than
        if required.startswith('>'):
            ver = self._parse_version(required[1:])
            if ver:
                return actual > ver

        # Handle exact match
        ver = self._parse_version(required)
        if ver:
            return actual == ver

        # If we can't parse, assume compatible
        return True

    def check_compatibility(self, resource: Resource) -> Tuple[bool, str]:
        """
        Check if a resource is compatible with the current GTNH version

        Returns:
            (is_compatible, message)
        """
        if not self._gtnh_version:
            return True, "未设置GTNH版本，假设兼容"

        if not resource.gtnh_versions:
            return True, "未指定版本要求，假设兼容"

        parsed_actual = self._parsed_version
        if not parsed_actual:
            return True, "无法解析GTNH版本，假设兼容"

        # Check against all specified compatible versions
        for required in resource.gtnh_versions:
            if self._version_matches(required, parsed_actual):
                return True, f"兼容 (GTNH {self._gtnh_version})"

        # Not compatible
        required_str = ", ".join(resource.gtnh_versions)
        return False, f"不兼容 (需要: {required_str})"

    def filter_compatible(self, resources: List[Resource]) -> Tuple[List[Resource], List[Tuple[Resource, str]]]:
        """
        Filter resources into compatible and incompatible lists

        Returns:
            (compatible_resources, [(incompatible_resource, reason), ...])
        """
        compatible = []
        incompatible = []

        for resource in resources:
            is_compatible, message = self.check_compatibility(resource)
            if is_compatible:
                compatible.append(resource)
            else:
                incompatible.append((resource, message))

        return compatible, incompatible

    def get_compatibility_status(self, resource: Resource) -> dict:
        """Get detailed compatibility status for a resource"""
        is_compatible, message = self.check_compatibility(resource)
        gtnh_version = self.get_gtnh_version()

        return {
            "compatible": is_compatible,
            "message": message,
            "gtnh_version": gtnh_version,
            "required_versions": resource.gtnh_versions
        }
