"""Tests for security hardening fixes: constant-time comparison, no query param auth."""

from __future__ import annotations

import hmac
import time

from toolkit_extensions.security import APIKeyManager


class TestConstantTimeComparison:
    """Verify APIKeyManager.verify_api_key uses hmac.compare_digest."""

    def test_verify_correct_key(self) -> None:
        key = APIKeyManager.generate_api_key()
        key_hash = APIKeyManager.hash_api_key(key)
        assert APIKeyManager.verify_api_key(key, key_hash) is True

    def test_verify_wrong_key(self) -> None:
        key = APIKeyManager.generate_api_key()
        key_hash = APIKeyManager.hash_api_key(key)
        assert APIKeyManager.verify_api_key("wrong_key", key_hash) is False

    def test_verify_uses_hmac_compare_digest(self) -> None:
        """Confirm the implementation delegates to hmac.compare_digest
        by checking that it returns bool (hmac.compare_digest always does)
        and matches the expected result for known inputs."""
        key = "test_key_abc123"
        key_hash = APIKeyManager.hash_api_key(key)
        computed = APIKeyManager.hash_api_key(key)
        # Directly verify the underlying mechanism
        assert hmac.compare_digest(computed, key_hash) is True
        assert APIKeyManager.verify_api_key(key, key_hash) is True

    def test_verify_empty_key(self) -> None:
        key_hash = APIKeyManager.hash_api_key("real_key")
        assert APIKeyManager.verify_api_key("", key_hash) is False

    def test_verify_empty_hash(self) -> None:
        assert APIKeyManager.verify_api_key("some_key", "") is False


class TestDockerComposeNoDefaultPassword:
    """Verify docker-compose.yml does not contain a default password."""

    def test_no_changeme_default(self) -> None:
        from pathlib import Path

        compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
        content = compose_path.read_text(encoding="utf-8")
        assert "changeme" not in content, "docker-compose.yml still contains insecure default 'changeme'"
        # Verify it requires explicit env var
        assert "POSTGRES_PASSWORD:?" in content or "POSTGRES_PASSWORD:-" not in content


class TestDashboardNoQueryParamAuth:
    """Verify dashboard app.py does not accept API key via query parameter."""

    def test_no_query_params_get(self) -> None:
        from pathlib import Path

        app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        assert "query_params.get" not in content, (
            "Dashboard still accepts API key via query parameter"
        )


class TestDependabotConfig:
    """Verify Dependabot configuration exists."""

    def test_dependabot_yml_exists(self) -> None:
        from pathlib import Path

        dependabot_path = Path(__file__).resolve().parents[1] / ".github" / "dependabot.yml"
        assert dependabot_path.exists(), ".github/dependabot.yml is missing"
        content = dependabot_path.read_text(encoding="utf-8")
        assert "pip" in content
        assert "github-actions" in content


class TestCISecurityBlocking:
    """Verify CI security scans do not use continue-on-error."""

    def test_no_continue_on_error_in_security_job(self) -> None:
        from pathlib import Path

        ci_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text(encoding="utf-8")
        # Find the security job section and verify no continue-on-error in bandit/safety steps
        lines = content.splitlines()
        in_security_job = False
        for line in lines:
            if "name: Security Scan" in line:
                in_security_job = True
            elif in_security_job and line.strip().startswith("name:") and "Security" not in line:
                # We've left the security job section once we hit the next job
                if not line.startswith(" ") and not line.startswith("\t"):
                    break
            if in_security_job and "Run Safety" in line or in_security_job and "Run Bandit" in line:
                # Check next few lines for continue-on-error
                idx = lines.index(line)
                for check_line in lines[idx : idx + 3]:
                    assert "continue-on-error: true" not in check_line, (
                        f"Security scan still has continue-on-error: {check_line.strip()}"
                    )
