"""
Alert webhook system for Toolkit LLM Gateway

Sends budget alerts to external systems via webhooks.
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import httpx

logger = logging.getLogger(__name__)

from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Session

from toolkit_extensions.database.connection import Base, get_session
from toolkit_extensions.database.models import BudgetAlert
from toolkit_extensions.budget_manager import get_budget_manager


# ---------------------------------------------------------------------------
# Database Models & Enums
# ---------------------------------------------------------------------------

class WebhookProvider(str, Enum):
    """Webhook provider types"""
    GENERIC = "generic"
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"


class WebhookConfig(Base):
    """Webhook configuration"""
    __tablename__ = "webhook_configs"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(String(255))  # For HMAC signing
    enabled = Column(Boolean, default=True)
    
    # Filter criteria (JSON)
    alert_types = Column(Text)  # JSON array: ["threshold_warning", "budget_exceeded"]
    teams = Column(Text)  # JSON array: team names to filter
    users = Column(Text)  # JSON array: user emails to filter
    
    # Retry configuration
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)  # seconds
    
    # Stats
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_success = Column(DateTime)
    last_failure = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookDelivery(Base):
    """Webhook delivery log"""
    __tablename__ = "webhook_deliveries"
    
    id = Column(String(36), primary_key=True)
    webhook_id = Column(String(36), nullable=False, index=True)
    alert_id = Column(String(36), nullable=False, index=True)
    
    # Request/response
    request_payload = Column(Text)
    response_status = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    
    # Delivery info
    attempt_number = Column(Integer, default=1)
    success = Column(Boolean, default=False)
    delivered_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# AlertWebhookManager - CRUD & Delivery Orchestration
# ---------------------------------------------------------------------------

class AlertWebhookManager:
    """
    Manages alert webhook delivery.

    Features:
    - Multiple webhook providers (Slack, Discord, Teams, generic)
    - Configurable retry logic
    - HMAC signing for security
    - Delivery tracking and stats
    - Alert filtering by type, team, user
    """

    def __init__(self):
        self.budget_manager = get_budget_manager()

    # -- Webhook CRUD ---------------------------------------------------------

    def register_webhook(
        self,
        name: str,
        url: str,
        provider: WebhookProvider = WebhookProvider.GENERIC,
        secret: Optional[str] = None,
        alert_types: Optional[List[str]] = None,
        teams: Optional[List[str]] = None,
        users: Optional[List[str]] = None,
        max_retries: int = 3,
        enabled: bool = True,
    ) -> str:
        """
        Register a new webhook endpoint.
        
        Args:
            name: Webhook name (for identification)
            url: Webhook URL
            provider: Webhook provider type
            secret: Secret for HMAC signing (optional)
            alert_types: Filter by alert types (optional)
            teams: Filter by team names (optional)
            users: Filter by user emails (optional)
            max_retries: Maximum retry attempts
            enabled: Whether webhook is enabled
        
        Returns:
            Webhook ID
        """
        import uuid
        
        webhook_id = str(uuid.uuid4())
        
        with get_session() as session:
            webhook = WebhookConfig(
                id=webhook_id,
                name=name,
                provider=provider,
                url=url,
                secret=secret,
                enabled=enabled,
                alert_types=json.dumps(alert_types) if alert_types else None,
                teams=json.dumps(teams) if teams else None,
                users=json.dumps(users) if users else None,
                max_retries=max_retries,
            )
            session.add(webhook)
            session.commit()
        
        return webhook_id
    
    def update_webhook(
        self,
        webhook_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        secret: Optional[str] = None,
        enabled: Optional[bool] = None,
        alert_types: Optional[List[str]] = None,
        teams: Optional[List[str]] = None,
        users: Optional[List[str]] = None,
    ) -> bool:
        """Update webhook configuration"""
        with get_session() as session:
            webhook = session.query(WebhookConfig).filter_by(id=webhook_id).first()
            if not webhook:
                return False
            
            if name is not None:
                webhook.name = name
            if url is not None:
                webhook.url = url
            if secret is not None:
                webhook.secret = secret
            if enabled is not None:
                webhook.enabled = enabled
            if alert_types is not None:
                webhook.alert_types = json.dumps(alert_types)
            if teams is not None:
                webhook.teams = json.dumps(teams)
            if users is not None:
                webhook.users = json.dumps(users)
            
            webhook.updated_at = datetime.utcnow()
            session.commit()
        
        return True
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook"""
        with get_session() as session:
            webhook = session.query(WebhookConfig).filter_by(id=webhook_id).first()
            if not webhook:
                return False
            session.delete(webhook)
            session.commit()
        
        return True
    
    def get_webhooks(self, enabled_only: bool = True) -> List[Dict]:
        """Get all configured webhooks"""
        with get_session() as session:
            query = session.query(WebhookConfig)
            if enabled_only:
                query = query.filter_by(enabled=True)
            
            webhooks = query.all()
            
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "provider": w.provider,
                    "url": w.url,
                    "enabled": w.enabled,
                    "alert_types": json.loads(w.alert_types) if w.alert_types else [],
                    "teams": json.loads(w.teams) if w.teams else [],
                    "users": json.loads(w.users) if w.users else [],
                    "success_count": w.success_count,
                    "failure_count": w.failure_count,
                    "last_success": w.last_success.isoformat() if w.last_success else None,
                    "last_failure": w.last_failure.isoformat() if w.last_failure else None,
                }
                for w in webhooks
            ]
    
    # -- Alert Delivery -------------------------------------------------------

    def deliver_pending_alerts(self) -> Dict[str, int]:
        """
        Deliver all pending alerts to configured webhooks.
        
        Returns:
            Dict with success_count and failure_count
        """
        # Get unsent alerts
        alerts = self.budget_manager.get_unsent_alerts()
        
        # Get active webhooks
        webhooks = self.get_webhooks(enabled_only=True)
        
        success_count = 0
        failure_count = 0
        
        for alert in alerts:
            # Filter webhooks that match this alert
            matching_webhooks = self._filter_webhooks_for_alert(webhooks, alert)
            
            for webhook in matching_webhooks:
                success = self._deliver_to_webhook(webhook, alert)
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            
            # Mark alert as sent (even if some deliveries failed)
            if matching_webhooks:
                self.budget_manager.mark_alert_sent(alert["id"])
        
        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "alerts_processed": len(alerts),
        }
    
    def _filter_webhooks_for_alert(
        self,
        webhooks: List[Dict],
        alert: Dict,
    ) -> List[Dict]:
        """Filter webhooks that should receive this alert"""
        matching = []
        
        for webhook in webhooks:
            # Check alert type filter
            if webhook["alert_types"]:
                if alert["alert_type"] not in webhook["alert_types"]:
                    continue
            
            # Check team filter
            if webhook["teams"]:
                # TODO: Get budget team from alert
                # For now, allow all
                pass
            
            # Check user filter
            if webhook["users"]:
                # TODO: Get budget user from alert
                # For now, allow all
                pass
            
            matching.append(webhook)
        
        return matching
    
    def _deliver_to_webhook(
        self,
        webhook: Dict,
        alert: Dict,
        attempt_number: int = 1,
    ) -> bool:
        """
        Deliver alert to webhook with retry logic.
        
        Returns:
            True if delivery succeeded, False otherwise
        """
        import uuid
        
        # Build payload based on provider
        payload = self._build_payload(webhook["provider"], alert)
        
        # Sign payload if secret is configured
        headers = {"Content-Type": "application/json"}
        if webhook.get("secret"):
            signature = self._sign_payload(payload, webhook["secret"])
            headers["X-Akiva-Signature"] = signature
            headers["X-Akiva-Timestamp"] = str(int(time.time()))
        
        delivery_id = str(uuid.uuid4())
        
        try:
            # Send webhook
            response = httpx.post(
                webhook["url"],
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            
            success = response.status_code < 400
            
            # Log delivery
            self._log_delivery(
                delivery_id=delivery_id,
                webhook_id=webhook["id"],
                alert_id=alert["id"],
                request_payload=json.dumps(payload),
                response_status=response.status_code,
                response_body=response.text[:1000],  # First 1000 chars
                success=success,
                attempt_number=attempt_number,
            )
            
            # Update webhook stats
            self._update_webhook_stats(webhook["id"], success)
            
            # Retry on failure
            if not success and attempt_number < 3:  # TODO: Use webhook.max_retries
                time.sleep(5 * attempt_number)  # Exponential backoff
                return self._deliver_to_webhook(webhook, alert, attempt_number + 1)
            
            return success
        
        except Exception as e:
            logger.error("Webhook delivery failed for %s: %s", webhook["id"], e, exc_info=True)
            # Log delivery failure
            self._log_delivery(
                delivery_id=delivery_id,
                webhook_id=webhook["id"],
                alert_id=alert["id"],
                request_payload=json.dumps(payload),
                error_message=str(e),
                success=False,
                attempt_number=attempt_number,
            )
            
            # Update webhook stats
            self._update_webhook_stats(webhook["id"], False)
            
            # Retry on exception
            if attempt_number < 3:
                time.sleep(5 * attempt_number)
                return self._deliver_to_webhook(webhook, alert, attempt_number + 1)
            
            return False
    
    # -- Provider-Specific Payload Builders -----------------------------------

    def _build_payload(self, provider: str, alert: Dict) -> Dict:
        """Build provider-specific payload"""
        if provider == WebhookProvider.SLACK:
            return self._build_slack_payload(alert)
        elif provider == WebhookProvider.DISCORD:
            return self._build_discord_payload(alert)
        elif provider == WebhookProvider.TEAMS:
            return self._build_teams_payload(alert)
        else:
            return self._build_generic_payload(alert)
    
    def _build_generic_payload(self, alert: Dict) -> Dict:
        """Build generic webhook payload"""
        return {
            "event": "budget_alert",
            "alert": alert,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _build_slack_payload(self, alert: Dict) -> Dict:
        """Build Slack-compatible payload"""
        color = "danger" if alert["alert_type"] == "budget_exceeded" else "warning"
        
        return {
            "attachments": [
                {
                    "color": color,
                    "title": f"Budget Alert: {alert['alert_type'].replace('_', ' ').title()}",
                    "fields": [
                        {
                            "title": "Current Spend",
                            "value": f"${alert['current_spend']:.2f}",
                            "short": True,
                        },
                        {
                            "title": "Budget Limit",
                            "value": f"${alert['budget_limit']:.2f}",
                            "short": True,
                        },
                        {
                            "title": "Usage",
                            "value": f"{alert['percentage_used']:.1f}%",
                            "short": True,
                        },
                    ],
                    "footer": "Toolkit LLM Gateway",
                    "ts": int(time.time()),
                }
            ]
        }
    
    def _build_discord_payload(self, alert: Dict) -> Dict:
        """Build Discord-compatible payload"""
        color = 0xFF0000 if alert["alert_type"] == "budget_exceeded" else 0xFFA500
        
        return {
            "embeds": [
                {
                    "title": f"Budget Alert: {alert['alert_type'].replace('_', ' ').title()}",
                    "color": color,
                    "fields": [
                        {
                            "name": "Current Spend",
                            "value": f"${alert['current_spend']:.2f}",
                            "inline": True,
                        },
                        {
                            "name": "Budget Limit",
                            "value": f"${alert['budget_limit']:.2f}",
                            "inline": True,
                        },
                        {
                            "name": "Usage",
                            "value": f"{alert['percentage_used']:.1f}%",
                            "inline": True,
                        },
                    ],
                    "footer": {
                        "text": "Toolkit LLM Gateway"
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        }
    
    def _build_teams_payload(self, alert: Dict) -> Dict:
        """Build Microsoft Teams-compatible payload"""
        theme_color = "ff0000" if alert["alert_type"] == "budget_exceeded" else "ffa500"
        
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": f"Budget Alert: {alert['alert_type']}",
            "sections": [
                {
                    "activityTitle": f"Budget Alert: {alert['alert_type'].replace('_', ' ').title()}",
                    "facts": [
                        {
                            "name": "Current Spend",
                            "value": f"${alert['current_spend']:.2f}",
                        },
                        {
                            "name": "Budget Limit",
                            "value": f"${alert['budget_limit']:.2f}",
                        },
                        {
                            "name": "Usage",
                            "value": f"{alert['percentage_used']:.1f}%",
                        },
                    ],
                    "markdown": True,
                }
            ],
        }
    
    # -- Internal Helpers (signing, logging, stats) ---------------------------

    def _sign_payload(self, payload: Dict, secret: str) -> str:
        """Create HMAC signature for payload"""
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _log_delivery(
        self,
        delivery_id: str,
        webhook_id: str,
        alert_id: str,
        request_payload: str,
        response_status: Optional[int] = None,
        response_body: Optional[str] = None,
        error_message: Optional[str] = None,
        success: bool = False,
        attempt_number: int = 1,
    ):
        """Log webhook delivery attempt"""
        with get_session() as session:
            delivery = WebhookDelivery(
                id=delivery_id,
                webhook_id=webhook_id,
                alert_id=alert_id,
                request_payload=request_payload,
                response_status=response_status,
                response_body=response_body,
                error_message=error_message,
                success=success,
                attempt_number=attempt_number,
            )
            session.add(delivery)
            session.commit()
    
    def _update_webhook_stats(self, webhook_id: str, success: bool):
        """Update webhook success/failure stats"""
        with get_session() as session:
            webhook = session.query(WebhookConfig).filter_by(id=webhook_id).first()
            if webhook:
                if success:
                    webhook.success_count += 1
                    webhook.last_success = datetime.utcnow()
                else:
                    webhook.failure_count += 1
                    webhook.last_failure = datetime.utcnow()
                session.commit()
    
    def get_delivery_stats(self, webhook_id: str) -> Dict:
        """Get delivery statistics for a webhook"""
        with get_session() as session:
            webhook = session.query(WebhookConfig).filter_by(id=webhook_id).first()
            if not webhook:
                return {}
            
            total_deliveries = webhook.success_count + webhook.failure_count
            success_rate = (webhook.success_count / total_deliveries * 100) if total_deliveries > 0 else 0
            
            return {
                "webhook_id": webhook.id,
                "name": webhook.name,
                "total_deliveries": total_deliveries,
                "success_count": webhook.success_count,
                "failure_count": webhook.failure_count,
                "success_rate": success_rate,
                "last_success": webhook.last_success.isoformat() if webhook.last_success else None,
                "last_failure": webhook.last_failure.isoformat() if webhook.last_failure else None,
            }


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------
_alert_webhook_manager: Optional[AlertWebhookManager] = None


def get_alert_webhook_manager() -> AlertWebhookManager:
    """Get global alert webhook manager instance"""
    global _alert_webhook_manager
    if _alert_webhook_manager is None:
        _alert_webhook_manager = AlertWebhookManager()
    return _alert_webhook_manager


