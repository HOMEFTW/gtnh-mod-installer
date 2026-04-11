"""
Backup and restore functionality for GTNH Mod Installer
"""
import os
import shutil
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple


from utils.logger import logger
from utils.helpers import save_json, load_json


class BackupManager:
    """Manages backups of Minecraft directory (supports client and server separately)"""

    BACKUP_DIR_NAME = "gtnh_installer_backups"
    BACKUP_META_FILE = "backup_meta.json"

    def __init__(self, client_path: str, server_path: str = None):
        self.client_path = client_path
        self.server_path = server_path
        self.backup_base = os.path.join(client_path, self.BACKUP_DIR_NAME)
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Ensure backup directory exists"""
        os.makedirs(self.backup_base, exist_ok=True)

    def _get_backup_meta_path(self) -> str:
        """Get path to backup metadata file"""
        return os.path.join(self.backup_base, self.BACKUP_META_FILE)

    def _load_backup_meta(self) -> Dict:
        """Load backup metadata"""
        meta = load_json(self._get_backup_meta_path())
        return meta if meta else {"backups": []}

    def _save_backup_meta(self, meta: Dict):
        """Save backup metadata"""
        save_json(self._get_backup_meta_path(), meta)

    def set_server_path(self, server_path: str):
        """Set server path for backup"""
        self.server_path = server_path

    def create_backup(self, name: Optional[str] = None, backup_type: str = "all") -> Tuple[bool, str]:
        """
        Create a backup of mods, config, and scripts directories

        Args:
            name: Optional name for the backup
            backup_type: "client", "server", or "all"

        Returns:
            (success, message_or_backup_id)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = name if name else f"backup_{timestamp}"
        backup_path = os.path.join(self.backup_base, backup_id)

        # Check if backup with this name already exists
        if os.path.exists(backup_path):
            return False, f"备份 '{backup_id}' 已存在"

        try:
            os.makedirs(backup_path)
            backed_up = {"client": [], "server": []}

            dirs_to_backup = ['mods', 'config', 'scripts']
            installer_data_dir = 'gtnh_installer_data'  # Installation records

            # Backup client
            if backup_type in ("client", "all"):
                client_backup_path = os.path.join(backup_path, "client")
                os.makedirs(client_backup_path)
                for dir_name in dirs_to_backup:
                    src_path = os.path.join(self.client_path, dir_name)
                    if os.path.exists(src_path):
                        dst_path = os.path.join(client_backup_path, dir_name)
                        shutil.copytree(src_path, dst_path)
                        backed_up["client"].append(dir_name)
                        logger.info(f"已备份客户端: {dir_name}")

                # Backup installer data
                installer_data_path = os.path.join(self.client_path, installer_data_dir)
                if os.path.exists(installer_data_path):
                    dst_path = os.path.join(client_backup_path, installer_data_dir)
                    shutil.copytree(installer_data_path, dst_path)
                    backed_up["client"].append(installer_data_dir)
                    logger.info(f"已备份客户端: {installer_data_dir}")

            # Backup server
            if backup_type in ("server", "all") and self.server_path:
                server_backup_path = os.path.join(backup_path, "server")
                os.makedirs(server_backup_path)
                for dir_name in dirs_to_backup:
                    src_path = os.path.join(self.server_path, dir_name)
                    if os.path.exists(src_path):
                        dst_path = os.path.join(server_backup_path, dir_name)
                        shutil.copytree(src_path, dst_path)
                        backed_up["server"].append(dir_name)
                        logger.info(f"已备份服务端: {dir_name}")

                # Backup installer data for server
                installer_data_path = os.path.join(self.server_path, installer_data_dir)
                if os.path.exists(installer_data_path):
                    dst_path = os.path.join(server_backup_path, installer_data_dir)
                    shutil.copytree(installer_data_path, dst_path)
                    backed_up["server"].append(installer_data_dir)
                    logger.info(f"已备份服务端: {installer_data_dir}")

            if not backed_up["client"] and not backed_up["server"]:
                os.rmdir(backup_path)
                return False, "没有可备份的内容"

            # Save backup metadata
            meta = self._load_backup_meta()
            backup_info = {
                "id": backup_id,
                "created": datetime.now().isoformat(),
                "directories": backed_up,
                "auto": name is None,
                "type": backup_type
            }
            meta["backups"].append(backup_info)
            self._save_backup_meta(meta)

            logger.success(f"备份创建成功: {backup_id}")
            return True, backup_id

        except Exception as e:
            logger.error(f"创建备份失败: {str(e)}")
            # Cleanup partial backup
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path, ignore_errors=True)
            return False, f"创建备份失败: {str(e)}"

    def restore_backup(self, backup_id: str, restore_type: str = "all") -> Tuple[bool, str]:
        """
        Restore from a backup

        Args:
            backup_id: ID of the backup to restore
            restore_type: "client", "server", or "all"

        Returns:
            (success, message)
        """
        backup_path = os.path.join(self.backup_base, backup_id)

        if not os.path.exists(backup_path):
            return False, f"备份 '{backup_id}' 不存在"

        try:
            dirs_to_restore = ['mods', 'config', 'scripts', 'gtnh_installer_data']
            restored = []

            # Restore client
            if restore_type in ("client", "all"):
                client_backup_path = os.path.join(backup_path, "client")
                if os.path.exists(client_backup_path):
                    for dir_name in dirs_to_restore:
                        src_path = os.path.join(client_backup_path, dir_name)
                        dst_path = os.path.join(self.client_path, dir_name)

                        if os.path.exists(src_path):
                            # Restore from backup
                            if os.path.exists(dst_path):
                                shutil.rmtree(dst_path)
                            shutil.copytree(src_path, dst_path)
                            # Ensure empty directories from backup are restored
                            self._restore_empty_dirs(src_path, dst_path)
                            logger.info(f"已还原客户端: {dir_name}")
                        elif dir_name == 'gtnh_installer_data' and os.path.exists(dst_path):
                            # If backup doesn't have installer data but current does, delete it
                            shutil.rmtree(dst_path)
                            logger.info(f"已删除客户端: {dir_name} (备份中不存在)")

                    restored.append("客户端")

            # Restore server
            if restore_type in ("server", "all") and self.server_path:
                server_backup_path = os.path.join(backup_path, "server")
                if os.path.exists(server_backup_path):
                    for dir_name in dirs_to_restore:
                        src_path = os.path.join(server_backup_path, dir_name)
                        dst_path = os.path.join(self.server_path, dir_name)

                        if os.path.exists(src_path):
                            # Restore from backup
                            if os.path.exists(dst_path):
                                shutil.rmtree(dst_path)
                            shutil.copytree(src_path, dst_path)
                            # Ensure empty directories from backup are restored
                            self._restore_empty_dirs(src_path, dst_path)
                            logger.info(f"已还原服务端: {dir_name}")
                        elif dir_name == 'gtnh_installer_data' and os.path.exists(dst_path):
                            # If backup doesn't have installer data but current does, delete it
                            shutil.rmtree(dst_path)
                            logger.info(f"已删除服务端: {dir_name} (备份中不存在)")

                    restored.append("服务端")

            if not restored:
                return False, "备份中没有可还原的内容"

            logger.success(f"备份还原成功: {backup_id}")
            return True, f"成功还原备份: {backup_id} ({', '.join(restored)})"

        except Exception as e:
            logger.error(f"还原备份失败: {str(e)}")
            return False, f"还原备份失败: {str(e)}"

    def list_backups(self) -> List[Dict]:
        """
        List all available backups

        Returns:
            List of backup info dictionaries
        """
        meta = self._load_backup_meta()
        backups = []

        for backup_info in meta.get("backups", []):
            backup_path = os.path.join(self.backup_base, backup_info["id"])
            # Verify backup still exists
            if os.path.exists(backup_path):
                # Calculate size
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(backup_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size += os.path.getsize(fp)
                backup_info["size"] = total_size
                backup_info["size_str"] = self._format_size(total_size)

                # Check what's in the backup
                has_client = os.path.exists(os.path.join(backup_path, "client"))
                has_server = os.path.exists(os.path.join(backup_path, "server"))
                backup_info["has_client"] = has_client
                backup_info["has_server"] = has_server

                backups.append(backup_info)

        # Sort by creation date, newest first
        backups.sort(key=lambda x: x.get("created", ""), reverse=True)
        return backups

    def delete_backup(self, backup_id: str) -> Tuple[bool, str]:
        """
        Delete a backup

        Args:
            backup_id: ID of the backup to delete

        Returns:
            (success, message)
        """
        backup_path = os.path.join(self.backup_base, backup_id)

        if not os.path.exists(backup_path):
            return False, f"备份 '{backup_id}' 不存在"

        try:
            shutil.rmtree(backup_path)

            # Update metadata
            meta = self._load_backup_meta()
            meta["backups"] = [b for b in meta["backups"] if b["id"] != backup_id]
            self._save_backup_meta(meta)

            logger.info(f"已删除备份: {backup_id}")
            return True, f"已删除备份: {backup_id}"

        except Exception as e:
            logger.error(f"删除备份失败: {str(e)}")
            return False, f"删除备份失败: {str(e)}"

    def _restore_empty_dirs(self, src_path: str, dst_path: str):
        """Ensure empty directories from backup source are restored to destination"""
        for dirpath, dirnames, filenames in os.walk(src_path):
            rel_dir = os.path.relpath(dirpath, src_path)
            target_dir = os.path.join(dst_path, rel_dir) if rel_dir != '.' else dst_path
            if os.path.isdir(dirpath) and not os.listdir(dirpath):
                os.makedirs(target_dir, exist_ok=True)
                logger.debug(f"已恢复空目录: {rel_dir}")

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

