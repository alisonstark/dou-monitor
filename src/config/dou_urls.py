"""
Centralized DOU URL configuration with fallback and health checking.

This module provides resilient URL management for DOU (Diário Oficial da União) access.
If the DOU changes their URL structure, administrators can update the configuration
via the dashboard or CLI without modifying code.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Default path to DOU configuration file
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "dou_config.json"


class DOUUrlConfig:
    """
    Manages DOU URL configuration with health monitoring and fallback support.
    
    Features:
    - Centralized URL management
    - Health monitoring (tracks failures)
    - Admin-configurable URLs (dashboard/CLI)
    - Automatic alerting on consecutive failures
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config: Dict = {}
        self._load_config()
    
    def _load_config(self):
        """Load DOU URL configuration from JSON file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"DOU config not found at {self.config_path}, creating default")
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self._ensure_health_structure()
            
            logger.info(f"DOU config loaded from {self.config_path}")
        
        except Exception as e:
            logger.error(f"Failed to load DOU config: {e}, using hardcoded defaults")
            self._use_fallback_config()
    
    def _create_default_config(self):
        """Create default DOU configuration file"""
        default_config = {
            "_comment": "Configuração de URLs do DOU - Pode ser alterada se o formato mudar",
            "base_url": "https://www.in.gov.br",
            "search_url": "https://www.in.gov.br/consulta/-/buscar/dou",
            "document_url_pattern": "https://www.in.gov.br/web/dou/-/{url_title}",
            "_updated_at": datetime.now().isoformat(),
            "_updated_by": "system",
            "_instructions": {
                "document_url_pattern": "Use {url_title} como placeholder para o título da URL do documento DOU",
                "search_url": "URL base para busca de concursos no DOU",
                "base_url": "Domínio principal do DOU (usado como fallback)"
            },
            "health": {
                "components": {
                    "search": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    },
                    "processing": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    },
                    "pdf_download": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    }
                }
            }
        }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        self.config = default_config
    
    def _use_fallback_config(self):
        """Use hardcoded fallback configuration"""
        self.config = {
            "base_url": "https://www.in.gov.br",
            "search_url": "https://www.in.gov.br/consulta/-/buscar/dou",
            "document_url_pattern": "https://www.in.gov.br/web/dou/-/{url_title}",
            "health": {
                "components": {
                    "search": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    },
                    "processing": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    },
                    "pdf_download": {
                        "last_success": None,
                        "last_failure": None,
                        "consecutive_failures": 0,
                        "alert_threshold": 3
                    }
                }
            }
        }

    def _default_component_health(self) -> Dict:
        return {
            "last_success": None,
            "last_failure": None,
            "consecutive_failures": 0,
            "alert_threshold": 3,
        }

    def _ensure_health_structure(self):
        """Ensure health structure exists and migrate legacy flat format if needed."""
        health = self.config.setdefault("health", {})
        components = health.setdefault("components", {})

        # Migrate legacy flat format into pdf_download component.
        legacy_has_keys = any(
            key in health
            for key in ["last_successful_download", "last_failed_download", "consecutive_failures", "alert_threshold"]
        )
        if legacy_has_keys and "pdf_download" not in components:
            components["pdf_download"] = {
                "last_success": health.get("last_successful_download"),
                "last_failure": health.get("last_failed_download"),
                "consecutive_failures": health.get("consecutive_failures", 0),
                "alert_threshold": health.get("alert_threshold", 3),
            }

        for component in ["search", "processing", "pdf_download"]:
            current = components.get(component, {})
            merged = self._default_component_health()
            merged.update(current if isinstance(current, dict) else {})
            components[component] = merged

    def _record_component_success(self, component: str):
        self._ensure_health_structure()
        comp = self.config["health"]["components"].setdefault(component, self._default_component_health())
        comp["last_success"] = datetime.now().isoformat()
        comp["consecutive_failures"] = 0
        self._save_config()

    def _record_component_failure(self, component: str) -> bool:
        self._ensure_health_structure()
        comp = self.config["health"]["components"].setdefault(component, self._default_component_health())
        comp["last_failure"] = datetime.now().isoformat()
        comp["consecutive_failures"] = comp.get("consecutive_failures", 0) + 1
        threshold = comp.get("alert_threshold", 3)
        alert_needed = comp["consecutive_failures"] >= threshold
        self._save_config()
        if alert_needed:
            logger.critical(
                f"ALERT: {comp['consecutive_failures']} consecutive failures in component '{component}'. "
                "DOU URL pattern/flow may have changed."
            )
        return alert_needed
    
    def get_search_url(self) -> str:
        """Get DOU search URL"""
        return self.config.get("search_url", "https://www.in.gov.br/consulta/-/buscar/dou")
    
    def get_document_url(self, url_title: str) -> str:
        """
        Build document URL from url_title using configured pattern.
        
        Args:
            url_title: The URL title from DOU document
        
        Returns:
            Full document URL
        """
        pattern = self.config.get("document_url_pattern", "https://www.in.gov.br/web/dou/-/{url_title}")
        return pattern.format(url_title=url_title)
    
    def get_base_url(self) -> str:
        """Get DOU base URL"""
        return self.config.get("base_url", "https://www.in.gov.br")
    
    def record_success(self):
        """Backward-compatible wrapper: records success for pdf_download."""
        try:
            self._record_component_success("pdf_download")
        except Exception as e:
            logger.error(f"Failed to record success: {e}")
    
    def record_failure(self) -> bool:
        """Backward-compatible wrapper: records failure for pdf_download."""
        try:
            return self._record_component_failure("pdf_download")
        
        except Exception as e:
            logger.error(f"Failed to record failure: {e}")
            return False

    def record_component_success(self, component: str):
        """Record successful execution for a health component."""
        try:
            self._record_component_success(component)
        except Exception as e:
            logger.error(f"Failed to record success for {component}: {e}")

    def record_component_failure(self, component: str) -> bool:
        """Record failed execution for a health component."""
        try:
            return self._record_component_failure(component)
        except Exception as e:
            logger.error(f"Failed to record failure for {component}: {e}")
            return False
    
    def get_health_status(self) -> Dict:
        """Get current health status"""
        self._ensure_health_structure()
        return self.config.get("health", {})

    def update_alert_thresholds(
        self,
        search_threshold: Optional[int] = None,
        processing_threshold: Optional[int] = None,
        pdf_download_threshold: Optional[int] = None,
        updated_by: str = "admin",
    ) -> Tuple[bool, str]:
        """Update per-component alert thresholds for health monitoring."""
        try:
            self._ensure_health_structure()

            updates = {
                "search": search_threshold,
                "processing": processing_threshold,
                "pdf_download": pdf_download_threshold,
            }

            for component, threshold in updates.items():
                if threshold is None:
                    continue
                if threshold < 1:
                    return False, f"threshold inválido para {component}: use valor >= 1"
                self.config["health"]["components"][component]["alert_threshold"] = int(threshold)

            self.config["_updated_at"] = datetime.now().isoformat()
            self.config["_updated_by"] = updated_by
            self._save_config()

            logger.info(f"DOU alert thresholds updated by {updated_by}")
            return True, "Limiar(es) de alerta atualizados com sucesso"
        except Exception as e:
            logger.error(f"Failed to update alert thresholds: {e}")
            return False, f"Erro ao atualizar limiares: {str(e)}"
    
    def update_urls(self, base_url: Optional[str] = None, 
                   search_url: Optional[str] = None,
                   document_url_pattern: Optional[str] = None,
                   updated_by: str = "admin") -> Tuple[bool, str]:
        """
        Update DOU URLs (admin function).
        
        Args:
            base_url: New base URL (optional)
            search_url: New search URL (optional)
            document_url_pattern: New document URL pattern (optional)
            updated_by: Who updated the config
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if base_url:
                self.config["base_url"] = base_url.rstrip('/')
            
            if search_url:
                self.config["search_url"] = search_url
            
            if document_url_pattern:
                # Validate pattern contains {url_title}
                if "{url_title}" not in document_url_pattern:
                    return False, "document_url_pattern deve conter placeholder {url_title}"
                self.config["document_url_pattern"] = document_url_pattern
            
            self.config["_updated_at"] = datetime.now().isoformat()
            self.config["_updated_by"] = updated_by
            
            # Reset health counters on manual URL update
            self._ensure_health_structure()
            for component in ["search", "processing", "pdf_download"]:
                self.config["health"]["components"][component]["consecutive_failures"] = 0
            
            self._save_config()
            
            logger.info(f"DOU URLs updated by {updated_by}")
            return True, "Configuração de URLs do DOU atualizada com sucesso"
        
        except Exception as e:
            logger.error(f"Failed to update DOU URLs: {e}")
            return False, f"Erro ao atualizar configuração: {str(e)}"
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save DOU config: {e}")


# Global singleton instance
_dou_config_instance: Optional[DOUUrlConfig] = None


def get_dou_config() -> DOUUrlConfig:
    """Get global DOU URL configuration instance (singleton)"""
    global _dou_config_instance
    
    if _dou_config_instance is None:
        _dou_config_instance = DOUUrlConfig()
    
    return _dou_config_instance


def reset_dou_config():
    """Reset global configuration (useful for testing)"""
    global _dou_config_instance
    _dou_config_instance = None
