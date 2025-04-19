# common/config.py
# Управление конфигурацией приложения: загрузка, горячая перезагрузка, версии и feature flags

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

__version__ = "1.0.0"


class VersionInfo(BaseModel):
    version: str
    build_date: Optional[str] = None


class BotConfig(BaseModel):
    id: str
    name: Optional[str]
    webhook_url: Optional[str]


class ChannelConfig(BaseModel):
    id: str
    name: Optional[str]
    account_id: str


class AppConfig(BaseModel):
    bots: List[BotConfig] = Field(default_factory=list)
    channels: List[ChannelConfig] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    version_info: VersionInfo = Field(default_factory=lambda: VersionInfo(version=__version__))


class FeatureFlag:
    """
    Утилита для проверки состояния feature flags из глобальной конфигурации.
    """

    @staticmethod
    def is_enabled(flag_name: str) -> bool:
        manager = ConfigManager.instance()
        return manager.get_feature_flag(flag_name)


class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any):
        raise RuntimeError("Use ConfigManager.instance() to get the singleton instance")

    def __init__(self, config_path: str):  # pragma: no cover
        # Should never be called directly
        pass

    @classmethod
    def instance(cls, config_path: Optional[str] = None) -> "ConfigManager":
        """
        Возвращает единственный экземпляр ConfigManager.
        При первом вызове необходимо передать путь к JSON-файлу конфигурации.
        """
        with cls._lock:
            if cls._instance is None:
                if not config_path:
                    raise ValueError("Config path must be provided on first instantiation")
                cls._instance = super().__new__(cls)
                cls._instance._init(config_path)
            return cls._instance

    def _init(self, config_path: str) -> None:
        self._config_path = Path(config_path)
        self._config_lock = threading.RLock()
        self._load_config()

    def _load_config(self) -> None:
        """
        Загружает и валидирует конфигурацию из JSON-файла.
        """
        raw = self._config_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        try:
            config = AppConfig(**data)
        except ValidationError as e:
            raise RuntimeError(f"Invalid configuration: {e}")
        with self._config_lock:
            self._config = config

    def reload(self) -> None:
        """
        Перезагружает конфигурацию из файла на лету.
        """
        self._load_config()

    # Доступ к элементам конфигурации
    def get_bots(self) -> List[BotConfig]:
        with self._config_lock:
            return list(self._config.bots)

    def get_channels(self) -> List[ChannelConfig]:
        with self._config_lock:
            return list(self._config.channels)

    def get_classes(self) -> List[str]:
        with self._config_lock:
            return list(self._config.classes)

    def get_feature_flag(self, name: str) -> bool:
        with self._config_lock:
            return self._config.feature_flags.get(name, False)

    def get_version_info(self) -> VersionInfo:
        with self._config_lock:
            return self._config.version_info

    def update_config(self, data: Dict[str, Any]) -> None:
        """
        Обновление конфигурации из переданного словаря и сохранение в файл.
        """
        with self._config_lock:
            # Сохраняем текущие version_info, если не передано
            if "version_info" not in data:
                data["version_info"] = self._config.version_info.dict()

            new_config = AppConfig(**data)
            # Записать новый JSON
            self._config_path.write_text(new_config.json(indent=2, ensure_ascii=False), encoding="utf-8")
            self._config = new_config

# Пример использования:
# manager = ConfigManager.instance("/path/to/config.json")
# bots = manager.get_bots()
# FeatureFlag.is_enabled("use_redis_queue")
