"""
Minecraft directory operations for GTNH Mod Installer
"""
import os
from typing import Optional, Tuple, List


class MinecraftPath:
    """Handles Minecraft directory path validation and operations"""

    def __init__(self, mc_path: str):
        self.mc_path = mc_path
        self._is_valid: Optional[bool] = None

    def validate(self) -> Tuple[bool, str]:
        """
        Validate if path is a valid .minecraft directory
        Returns: (is_valid, message)
        """
        if not os.path.exists(self.mc_path):
            return False, "路径不存在"

        if not os.path.isdir(self.mc_path):
            return False, "不是有效的文件夹"

        # Auto-create mods and scripts directories if they don't exist
        self.ensure_directories()

        self._is_valid = True
        return True, "有效的 .minecraft 目录"

    def is_valid(self) -> bool:
        """Check if path is valid"""
        if self._is_valid is None:
            valid, _ = self.validate()
        return self._is_valid

    def get_mods_path(self) -> str:
        """Get mods directory path"""
        return os.path.join(self.mc_path, 'mods')

    def get_config_path(self) -> str:
        """Get config directory path"""
        return os.path.join(self.mc_path, 'config')

    def get_scripts_path(self) -> str:
        """Get scripts directory path (for MineTweaker/CraftTweaker)"""
        return os.path.join(self.mc_path, 'scripts')

    def get_fonts_path(self) -> str:
        """Get fonts directory path"""
        return os.path.join(self.mc_path, 'fonts')

    def get_fontfiles_path(self) -> str:
        """Get fontfiles directory path"""
        return os.path.join(self.mc_path, 'fontfiles')

    def get_resourcepacks_path(self) -> str:
        """Get resourcepacks directory path"""
        return os.path.join(self.mc_path, 'resourcepacks')

    def ensure_directories(self) -> bool:
        """Ensure mods and scripts directories exist, create if missing"""
        dirs = [
            self.get_mods_path(),
            self.get_scripts_path()
        ]
        try:
            for d in dirs:
                os.makedirs(d, exist_ok=True)
            return True
        except OSError:
            return False

    def list_installed_mods(self) -> List[str]:
        """List all installed mod jar files"""
        mods_path = self.get_mods_path()
        if not os.path.exists(mods_path):
            return []
        return [f for f in os.listdir(mods_path) if f.endswith('.jar')]

    def list_installed_configs(self) -> List[str]:
        """List all config files/directories"""
        config_path = self.get_config_path()
        if not os.path.exists(config_path):
            return []
        return os.listdir(config_path)

    def list_installed_scripts(self) -> List[str]:
        """List all script files"""
        scripts_path = self.get_scripts_path()
        if not os.path.exists(scripts_path):
            return []
        return [f for f in os.listdir(scripts_path) if f.endswith(('.zs', '.zsl', '.cfg'))]
