"""
Download functionality for GTNH Mod Installer
"""
import os
import requests
from typing import Optional, Callable, Tuple
from urllib.parse import urlparse

from utils.logger import logger


class Downloader:
    """Handles file downloads with progress tracking"""

    CHUNK_SIZE = 8192  # 8KB chunks
    TIMEOUT = 30  # seconds

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GTNH-Mod-Installer/1.0'
        })

    def download_file(
        self,
        url: str,
        dest_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, str]:
        """
        Download a file from URL

        Args:
            url: URL to download from
            dest_path: Destination file path
            progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            (success, message)
        """
        try:
            logger.info(f"开始下载: {url}")

            response = self.session.get(
                url,
                stream=True,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()

            # Get file size
            total_size = int(response.headers.get('content-length', 0))

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Download with progress
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)

            logger.success(f"下载完成: {os.path.basename(dest_path)}")
            return True, "下载完成"

        except requests.exceptions.RequestException as e:
            logger.error(f"下载失败: {str(e)}")
            # Cleanup partial file
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False, f"下载失败: {str(e)}"

        except IOError as e:
            logger.error(f"文件写入失败: {str(e)}")
            return False, f"文件写入失败: {str(e)}"

    def download_to_temp(
        self,
        url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Download file to a temporary location

        Returns:
            (success, message, temp_path_or_none)
        """
        import tempfile

        # Get filename from URL
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path) or "download"

        # Create temp file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"gtnh_installer_{filename}")

        success, message = self.download_file(url, temp_path, progress_callback)

        if success:
            return True, message, temp_path
        else:
            return False, message, None

    def get_file_info(self, url: str) -> Tuple[bool, dict]:
        """
        Get file information without downloading

        Returns:
            (success, info_dict)
        """
        try:
            response = self.session.head(url, timeout=self.TIMEOUT, allow_redirects=True)
            response.raise_for_status()

            info = {
                "size": int(response.headers.get('content-length', 0)),
                "content_type": response.headers.get('content-type', ''),
                "filename": os.path.basename(urlparse(response.url).path)
            }
            return True, info

        except requests.exceptions.RequestException:
            return False, {}

    def check_url_accessible(self, url: str) -> Tuple[bool, str]:
        """
        Check if URL is accessible

        Returns:
            (is_accessible, message)
        """
        try:
            response = self.session.head(url, timeout=self.TIMEOUT, allow_redirects=True)
            if response.status_code == 200:
                return True, "URL可访问"
            else:
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.RequestException as e:
            return False, str(e)

    def download_json(self, url: str) -> Tuple[bool, dict]:
        """
        Download and parse JSON file

        Returns:
            (success, data_or_error_dict)
        """
        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return True, data

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}
        except ValueError as e:
            return False, {"error": f"JSON解析失败: {str(e)}"}

    def update_resource_list(self, resource_url: str, dest_path: str) -> Tuple[bool, str]:
        """
        Update resource list from remote URL

        Args:
            resource_url: URL to the JSON resource list
            dest_path: Path to save the updated list

        Returns:
            (success, message)
        """
        success, data = self.download_json(resource_url)

        if not success:
            return False, data.get("error", "下载失败")

        try:
            import json
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.success("资源列表已更新")
            return True, "资源列表已更新"

        except IOError as e:
            return False, f"保存失败: {str(e)}"
