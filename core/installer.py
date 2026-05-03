"""
Installer module for GTNH Mod Installer
Handles installation and uninstallation of mods, scripts, and configs
"""
import os
import shutil
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from utils.logger import logger
from utils.helpers import load_json, save_json, init_external_content
from core.minecraft import MinecraftPath


class ResourceType(Enum):
    MOD = "mods"
    SCRIPT = "scripts"
    CONFIG = "configs"
    FONT = "fonts"
    RESOURCEPACK = "resourcepacks"
    SHADERPACK = "shaderpacks"
    SERVERUTILITIES = "serverutilities"


@dataclass
class Resource:
    """Represents an installable resource"""
    id: str
    name: str
    filename: str
    source_path: str
    resource_type: ResourceType
    size: int = 0
    version: str = ""
    mc_version: str = ""  # Compatible MC version (e.g., "2.7.0")
    description: str = ""
    server_required: bool = False  # For mods: whether server install is needed
    # Note: Server installation rules:
    # MOD -> depends on server_required field
    # SCRIPT, CONFIG, SERVERUTILITIES -> always install on both client and server
    # FONT, RESOURCEPACK, SHADERPACK -> client only


class Installer:
    """Handles installation and uninstallation of resources"""

    INSTALLED_FILE = "installed.json"
    CONTENT_DIR = "Addcontent"

    def __init__(self, mc_path: MinecraftPath, gtnh_version: str = ""):
        self.mc_path = mc_path
        self.server_mc_path: Optional[MinecraftPath] = None
        self.gtnh_version = gtnh_version
        self.client_installed_path = os.path.join(
            mc_path.mc_path,
            "gtnh_installer_data",
            self.INSTALLED_FILE
        )
        self.server_installed_path: Optional[str] = None
        self._client_installed: Optional[Dict] = None
        self._server_installed: Optional[Dict] = None
        self._content_base: Optional[str] = None

    def set_gtnh_version(self, version: str):
        """Set GTNH version and update content path"""
        self.gtnh_version = version
        self._content_base = None

    def set_server_path(self, server_path: str):
        """Set server .minecraft path"""
        if server_path and os.path.exists(server_path):
            self.server_mc_path = MinecraftPath(server_path)
            self.server_installed_path = os.path.join(
                server_path,
                "gtnh_installer_data",
                self.INSTALLED_FILE
            )
            logger.info(f"服务端路径已设置: {server_path}")
        else:
            self.server_mc_path = None
            self.server_installed_path = None

    def get_content_base(self) -> str:
        """Get the base path for content based on GTNH version"""
        if self._content_base is None:
            # Initialize external content folder if needed
            content_dir = init_external_content()
            self._content_base = os.path.join(content_dir, self.gtnh_version)
        return self._content_base

    @staticmethod
    def _empty_installed() -> Dict:
        """Return empty installed structure"""
        return {
            "mods": [],
            "scripts": [],
            "configs": [],
            "fonts": [],
            "resourcepacks": [],
            "shaderpacks": [],
            "serverutilities": []
        }

    @staticmethod
    def _entry_id(entry) -> str:
        """Extract resource id from legacy string or structured entry."""
        if isinstance(entry, dict):
            return entry.get("id", "")
        return entry

    @staticmethod
    def _entry_filename(entry) -> str:
        """Extract tracked filename from legacy string or structured entry."""
        if isinstance(entry, dict):
            return entry.get("filename", "") or entry.get("id", "")
        return entry

    @staticmethod
    def _entry_name(entry) -> str:
        """Extract tracked display name from legacy string or structured entry."""
        if isinstance(entry, dict):
            return entry.get("name", "") or entry.get("id", "")
        return entry

    def _get_installed_entry(self, installed_data: Dict, type_key: str, resource_id: str):
        """Get raw installed entry by id."""
        for entry in installed_data.get(type_key, []):
            if self._entry_id(entry) == resource_id:
                return entry
        return None

    def _record_installed_resource(self, installed_data: Dict, type_key: str, resource: Resource):
        """Persist structured install metadata while remaining backward compatible."""
        entry = {
            "id": resource.id,
            "name": resource.name,
            "filename": resource.filename
        }
        existing = installed_data.get(type_key, [])
        for idx, current in enumerate(existing):
            if self._entry_id(current) == resource.id:
                existing[idx] = entry
                return
        existing.append(entry)

    def _load_client_installed(self) -> Dict:
        """Load client installed resources"""
        if self._client_installed is not None:
            return self._client_installed
        data = load_json(self.client_installed_path)
        if data:
            self._client_installed = data
        else:
            self._client_installed = self._empty_installed()
        return self._client_installed

    def _load_server_installed(self) -> Dict:
        """Load server installed resources"""
        if self._server_installed is not None:
            return self._server_installed
        if self.server_installed_path:
            data = load_json(self.server_installed_path)
            if data:
                self._server_installed = data
            else:
                self._server_installed = self._empty_installed()
        else:
            self._server_installed = self._empty_installed()
        return self._server_installed

    def _save_client_installed(self):
        """Save client installed resources"""
        os.makedirs(os.path.dirname(self.client_installed_path), exist_ok=True)
        save_json(self.client_installed_path, self._client_installed)

    def _save_server_installed(self):
        """Save server installed resources"""
        if self.server_installed_path and self._server_installed is not None:
            os.makedirs(os.path.dirname(self.server_installed_path), exist_ok=True)
            save_json(self.server_installed_path, self._server_installed)

    def refresh_installed_cache(self):
        """Clear the installed cache to force reload from file"""
        self._client_installed = None
        self._server_installed = None

    def load_resources(self, resource_type: ResourceType) -> List[Resource]:
        """Load available resources from resources.json and directory"""
        content_base = self.get_content_base()
        type_dir = os.path.join(content_base, resource_type.value)
        json_path = os.path.join(content_base, "resources.json")

        # Load resource info from JSON, keyed by filename for lookup
        resource_info: Dict[str, dict] = {}
        if os.path.exists(json_path):
            data = load_json(json_path)
            if data:
                for item in data.get(resource_type.value, []):
                    # Key by filename for directory scanning lookup
                    filename = item.get("filename", "")
                    if filename:
                        resource_info[filename] = item

        if not os.path.exists(type_dir):
            logger.debug(f"目录不存在: {type_dir}")
            return []

        resources = []

        for item in os.listdir(type_dir):
            item_path = os.path.join(type_dir, item)

            # Get info from JSON by filename
            info = resource_info.get(item, {})

            if resource_type == ResourceType.SERVERUTILITIES and not os.path.isdir(item_path):
                continue

            if os.path.isfile(item_path):
                resource = Resource(
                    id=info.get("id", item),
                    name=info.get("name", item),
                    filename=item,
                    source_path=item_path,
                    resource_type=resource_type,
                    size=os.path.getsize(item_path),
                    version=info.get("version", ""),
                    mc_version=info.get("mc_version", ""),
                    description=info.get("description", ""),
                    server_required=info.get("server_required", False)
                )
                resources.append(resource)

            elif os.path.isdir(item_path):
                resource = Resource(
                    id=info.get("id", item),
                    name=info.get("name", item),
                    filename=item,
                    source_path=item_path,
                    resource_type=resource_type,
                    size=self._get_dir_size(item_path),
                    version=info.get("version", ""),
                    mc_version=info.get("mc_version", ""),
                    description=info.get("description", ""),
                    server_required=info.get("server_required", False)
                )
                resources.append(resource)

        return resources

    def _get_dir_size(self, path: str) -> int:
        """Get total size of a directory"""
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def get_resource_by_id(self, resource_id: str, resource_type: ResourceType) -> Optional[Resource]:
        """Get a specific resource by ID"""
        resources = self.load_resources(resource_type)
        for res in resources:
            if res.id == resource_id:
                return res
        return None

    def _get_dest_dir(self, resource_type: ResourceType, mc_path: MinecraftPath = None) -> Optional[str]:
        """Get destination directory for a resource type"""
        target = mc_path or self.mc_path
        if resource_type == ResourceType.MOD:
            return target.get_mods_path()
        elif resource_type == ResourceType.SCRIPT:
            return target.get_scripts_path()
        elif resource_type == ResourceType.CONFIG:
            return target.get_config_path()
        elif resource_type == ResourceType.FONT:
            return target.get_fonts_path()
        elif resource_type == ResourceType.RESOURCEPACK:
            return target.get_resourcepacks_path()
        elif resource_type == ResourceType.SHADERPACK:
            return target.get_shaderpacks_path()
        elif resource_type == ResourceType.SERVERUTILITIES:
            return target.get_serverutilities_path()
        return None

    def _copy_resource(self, source_path: str, dest_dir: str, filename: str) -> Tuple[bool, str]:
        """Copy a resource file or directory to destination"""
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)

        try:
            if os.path.isfile(source_path):
                if os.path.exists(dest_path):
                    logger.warning(f"文件已存在，将覆盖: {filename}")
                shutil.copy2(source_path, dest_path)
                logger.info(f"已复制: {filename}")
                return True, f"已复制: {filename}"

            elif os.path.isdir(source_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
                logger.info(f"已复制目录: {filename}")
                return True, f"已复制目录: {filename}"

            else:
                return False, f"源文件不存在: {source_path}"

        except Exception as e:
            return False, f"复制失败: {str(e)}"

    def _copy_directory_merge(self, source_path: str, dest_dir: str, dirname: str) -> Tuple[bool, str]:
        """Copy a directory resource and overwrite same-name files."""
        if not os.path.isdir(source_path):
            return False, f"源文件夹不存在: {source_path}"

        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, dirname)

        try:
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            logger.info(f"已复制目录: {dirname}")
            return True, f"已复制目录: {dirname}"
        except Exception as e:
            return False, f"复制目录失败: {str(e)}"

    def _copy_config_recursive(self, source_path: str, dest_dir: str) -> Tuple[bool, str, List[str]]:
        """Copy config directory contents recursively, merging with existing files.

        Returns:
            (success, message, list of copied relative paths)
        """
        copied_files = []
        try:
            os.makedirs(dest_dir, exist_ok=True)

            if os.path.isfile(source_path):
                # Single config file
                filename = os.path.basename(source_path)
                dest_path = os.path.join(dest_dir, filename)
                if os.path.exists(dest_path):
                    logger.warning(f"配置文件已存在，将覆盖: {filename}")
                shutil.copy2(source_path, dest_path)
                logger.info(f"已复制配置: {filename}")
                copied_files.append(filename)
                return True, f"已复制配置: {filename}", copied_files

            elif os.path.isdir(source_path):
                # Copy all contents recursively
                for root, dirs, files in os.walk(source_path):
                    rel_dir = os.path.relpath(root, source_path)
                    for f in files:
                        src_file = os.path.join(root, f)
                        if rel_dir == '.':
                            dst_file = os.path.join(dest_dir, f)
                            rel_path = f
                        else:
                            dst_file = os.path.join(dest_dir, rel_dir, f)
                            rel_path = os.path.join(rel_dir, f).replace('\\', '/')

                        if os.path.exists(dst_file):
                            logger.warning(f"配置文件已存在，将覆盖: {rel_path}")
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        logger.info(f"已复制配置: {rel_path}")
                        copied_files.append(rel_path)

                return True, f"已复制 {len(copied_files)} 个配置文件", copied_files

            else:
                return False, f"源路径不存在: {source_path}", []

        except Exception as e:
            return False, f"复制配置失败: {str(e)}", []

    def install_resource(
        self,
        resource: Resource,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        install_side: str = "both"
    ) -> Tuple[bool, str]:
        """
        Install a resource to client and/or server

        Args:
            resource: Resource to install
            progress_callback: Optional progress callback
            install_side: "both", "client", or "server"
        """
        type_key = resource.resource_type.value
        installed_anywhere = False

        # Copy to client
        if install_side in ("both", "client"):
            dest_dir = self._get_dest_dir(resource.resource_type)
            if not dest_dir:
                return False, "未知的资源类型"

            client_copied_files = []
            if resource.resource_type == ResourceType.CONFIG:
                success, message, client_copied_files = self._copy_config_recursive(resource.source_path, dest_dir)
            elif resource.resource_type == ResourceType.FONT:
                fonts_dir = dest_dir
                fontfiles_dir = self.mc_path.get_fontfiles_path()
                os.makedirs(fontfiles_dir, exist_ok=True)
                success, message = self._copy_resource(resource.source_path, fonts_dir, resource.filename)
                if success:
                    success2, message2 = self._copy_resource(resource.source_path, fontfiles_dir, resource.filename)
                    if not success2:
                        logger.warning(f"复制到 fontfiles 失败: {message2}")
            elif resource.resource_type == ResourceType.SERVERUTILITIES:
                success, message = self._copy_directory_merge(resource.source_path, dest_dir, resource.filename)
            else:
                success, message = self._copy_resource(resource.source_path, dest_dir, resource.filename)
            if not success:
                return False, message

            # Record client installation
            client_installed = self._load_client_installed()
            self._record_installed_resource(client_installed, type_key, resource)
            if resource.resource_type == ResourceType.CONFIG and client_copied_files:
                if "config_files" not in client_installed:
                    client_installed["config_files"] = {}
                client_installed["config_files"][resource.id] = client_copied_files
            self._save_client_installed()
            installed_anywhere = True

        # Determine if should install on server
        should_install_server = False
        if install_side in ("both", "server") and self.server_mc_path:
            if resource.resource_type == ResourceType.MOD:
                should_install_server = resource.server_required
            elif resource.resource_type in [ResourceType.SCRIPT, ResourceType.CONFIG, ResourceType.SERVERUTILITIES]:
                should_install_server = True

        if should_install_server:
            server_dest_dir = self._get_dest_dir(resource.resource_type, self.server_mc_path)
            if server_dest_dir:
                if resource.resource_type == ResourceType.CONFIG:
                    server_success, server_message, server_copied_files = self._copy_config_recursive(
                        resource.source_path, server_dest_dir
                    )
                else:
                    if resource.resource_type == ResourceType.SERVERUTILITIES:
                        server_success, server_message = self._copy_directory_merge(
                            resource.source_path, server_dest_dir, resource.filename
                        )
                    else:
                        server_success, server_message = self._copy_resource(
                            resource.source_path, server_dest_dir, resource.filename
                        )
                if server_success:
                    logger.info(f"已同步到服务端: {resource.filename}")
                    server_installed = self._load_server_installed()
                    self._record_installed_resource(server_installed, type_key, resource)
                    if resource.resource_type == ResourceType.CONFIG and server_copied_files:
                        if "config_files" not in server_installed:
                            server_installed["config_files"] = {}
                        server_installed["config_files"][resource.id] = server_copied_files
                    self._save_server_installed()
                    installed_anywhere = True
                else:
                    logger.warning(f"服务端安装失败: {server_message}")

        if not installed_anywhere:
            return False, f"资源无法安装到所选位置: {resource.name}"

        logger.success(f"安装成功: {resource.name}")
        return True, f"成功安装: {resource.name}"

    def uninstall_resource(self, resource_id: str, resource_type: ResourceType, uninstall_server: bool = True) -> Tuple[bool, str]:
        """Uninstall a resource from client and optionally from server"""
        resource = self.get_resource_by_id(resource_id, resource_type)
        type_key = resource_type.value
        removed_from = []
        client_installed = self._load_client_installed()
        server_installed = self._load_server_installed()
        client_entry = self._get_installed_entry(client_installed, type_key, resource_id)
        server_entry = self._get_installed_entry(server_installed, type_key, resource_id)

        if not resource:
            tracked_entry = client_entry or server_entry
            if not tracked_entry:
                return False, f"未找到资源: {resource_id}"
            resource = Resource(
                id=resource_id,
                name=self._entry_name(tracked_entry) or resource_id,
                filename=self._entry_filename(tracked_entry) or resource_id,
                source_path="",
                resource_type=resource_type
            )

        # Uninstall from client
        dest_dir = self._get_dest_dir(resource_type)
        if dest_dir:
            # For configs, delete tracked files
            if resource_type == ResourceType.CONFIG:
                config_files = client_installed.get("config_files", {}).get(resource_id, [])
                if config_files:
                    for rel_path in config_files:
                        file_path = os.path.join(dest_dir, rel_path)
                        try:
                            if os.path.exists(file_path):
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                    logger.info(f"已删除配置文件: {rel_path}")
                                elif os.path.isdir(file_path):
                                    shutil.rmtree(file_path)
                                    logger.info(f"已删除配置目录: {rel_path}")
                        except Exception as e:
                            logger.error(f"删除配置失败 {rel_path}: {str(e)}")
                    # Clean up empty parent directories
                    for rel_path in config_files:
                        parent = os.path.dirname(os.path.join(dest_dir, rel_path))
                        while parent != dest_dir:
                            if os.path.isdir(parent) and not os.listdir(parent):
                                try:
                                    os.rmdir(parent)
                                    logger.info(f"已删除空目录: {os.path.relpath(parent, dest_dir)}")
                                except:
                                    pass
                            parent = os.path.dirname(parent)
                    removed_from.append("客户端")
                    if resource_id in client_installed.get("config_files", {}):
                        del client_installed["config_files"][resource_id]
                else:
                    file_path = os.path.join(dest_dir, resource.filename)
                    try:
                        if os.path.exists(file_path):
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                            logger.info(f"已从客户端删除: {resource.filename}")
                            removed_from.append("客户端")
                    except Exception as e:
                        logger.error(f"客户端删除失败: {str(e)}")
            else:
                file_path = os.path.join(dest_dir, resource.filename)
                try:
                    if os.path.exists(file_path):
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                        logger.info(f"已从客户端删除: {resource.filename}")
                        removed_from.append("客户端")
                except Exception as e:
                    logger.error(f"客户端删除失败: {str(e)}")

                if resource_type == ResourceType.FONT:
                    fontfiles_dir = self.mc_path.get_fontfiles_path()
                    fontfiles_path = os.path.join(fontfiles_dir, resource.filename)
                    try:
                        if os.path.exists(fontfiles_path):
                            if os.path.isfile(fontfiles_path):
                                os.remove(fontfiles_path)
                            elif os.path.isdir(fontfiles_path):
                                shutil.rmtree(fontfiles_path)
                            logger.info(f"已从 fontfiles 删除: {resource.filename}")
                    except Exception as e:
                        logger.error(f"fontfiles 删除失败: {str(e)}")

            if client_entry in client_installed[type_key]:
                client_installed[type_key].remove(client_entry)
            self._save_client_installed()

        # Uninstall from server if requested
        if uninstall_server and self.server_mc_path:
            server_dest_dir = self._get_dest_dir(resource_type, self.server_mc_path)
            if server_dest_dir:
                if resource_type == ResourceType.CONFIG:
                    server_config_files = server_installed.get("config_files", {}).get(resource_id, [])
                    if server_config_files:
                        for rel_path in server_config_files:
                            file_path = os.path.join(server_dest_dir, rel_path)
                            try:
                                if os.path.exists(file_path):
                                    if os.path.isfile(file_path):
                                        os.remove(file_path)
                                        logger.info(f"已从服务端删除配置: {rel_path}")
                                    elif os.path.isdir(file_path):
                                        shutil.rmtree(file_path)
                                        logger.info(f"已从服务端删除配置目录: {rel_path}")
                            except Exception as e:
                                logger.error(f"服务端删除配置失败 {rel_path}: {str(e)}")
                        removed_from.append("服务端")
                        if resource_id in server_installed.get("config_files", {}):
                            del server_installed["config_files"][resource_id]
                    else:
                        server_file_path = os.path.join(server_dest_dir, resource.filename)
                        try:
                            if os.path.exists(server_file_path):
                                if os.path.isfile(server_file_path):
                                    os.remove(server_file_path)
                                elif os.path.isdir(server_file_path):
                                    shutil.rmtree(server_file_path)
                                logger.info(f"已从服务端删除: {resource.filename}")
                                removed_from.append("服务端")
                        except Exception as e:
                            logger.error(f"服务端删除失败: {str(e)}")
                else:
                    server_file_path = os.path.join(server_dest_dir, resource.filename)
                    try:
                        if os.path.exists(server_file_path):
                            if os.path.isfile(server_file_path):
                                os.remove(server_file_path)
                            elif os.path.isdir(server_file_path):
                                shutil.rmtree(server_file_path)
                            logger.info(f"已从服务端删除: {resource.filename}")
                            removed_from.append("服务端")
                    except Exception as e:
                        logger.error(f"服务端删除失败: {str(e)}")

                if server_entry in server_installed[type_key]:
                    server_installed[type_key].remove(server_entry)
                self._save_server_installed()

        if removed_from:
            logger.success(f"卸载成功: {resource.name} (从{'/'.join(removed_from)}卸载)")
            return True, f"成功卸载: {resource.name} (从{'/'.join(removed_from)}卸载)"
        else:
            return True, f"资源未安装: {resource.name}"

    def get_installed_resources(self, resource_type: ResourceType, location: str = "client") -> List[str]:
        """Get list of installed resource IDs for a type"""
        type_key = resource_type.value
        if location == "client":
            return [self._entry_id(entry) for entry in self._load_client_installed().get(type_key, [])]
        elif location == "server":
            return [self._entry_id(entry) for entry in self._load_server_installed().get(type_key, [])]
        else:
            client_set = set(self.get_installed_resources(resource_type, "client"))
            server_set = set(self.get_installed_resources(resource_type, "server"))
            return list(client_set | server_set)

    def is_installed(self, resource_id: str, resource_type: ResourceType, location: str = "client") -> bool:
        """Check if a resource is installed"""
        return resource_id in self.get_installed_resources(resource_type, location)

    def get_install_status(self, resource_id: str, resource_type: ResourceType) -> Dict[str, bool]:
        """Get installation status for client and server"""
        return {
            "client": resource_id in self.get_installed_resources(resource_type, "client"),
            "server": resource_id in self.get_installed_resources(resource_type, "server")
        }

    def get_all_installed_resources(self) -> List[Dict]:
        """Return all tracked installed resources, including entries missing from current content."""
        installed_items = []
        client_installed = self._load_client_installed()
        server_installed = self._load_server_installed()

        for res_type in ResourceType:
            type_key = res_type.value
            seen_ids = set()
            for installed_data, location in (
                (client_installed, "client"),
                (server_installed, "server"),
            ):
                for entry in installed_data.get(type_key, []):
                    res_id = self._entry_id(entry)
                    if not res_id or res_id in seen_ids:
                        continue
                    seen_ids.add(res_id)

                    resource = self.get_resource_by_id(res_id, res_type)
                    client_status = res_id in self.get_installed_resources(res_type, "client")
                    server_status = res_id in self.get_installed_resources(res_type, "server")

                    installed_items.append({
                        "id": res_id,
                        "name": resource.name if resource else self._entry_name(entry) or res_id,
                        "filename": resource.filename if resource else self._entry_filename(entry) or res_id,
                        "resource_type": res_type,
                        "resource": resource,
                        "missing": resource is None,
                        "client_installed": client_status,
                        "server_installed": server_status,
                    })

        return installed_items

    def install_multiple(
        self,
        resources: List[Tuple[str, ResourceType]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        install_side: str = "both"
    ) -> Tuple[int, List[str]]:
        """Install multiple resources"""
        total = len(resources)
        success_count = 0
        errors = []

        for i, (res_id, res_type) in enumerate(resources):
            resource = self.get_resource_by_id(res_id, res_type)
            if not resource:
                errors.append(f"未找到资源: {res_id}")
                continue

            if progress_callback:
                progress_callback(i + 1, total, resource.name)

            success, message = self.install_resource(resource, install_side=install_side)
            if success:
                success_count += 1
            else:
                errors.append(message)

        return success_count, errors
