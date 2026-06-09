"""Politiques de conformité — RGPD, SOC2, ISO27001, Data Residency."""

from typing import Any, Dict, List

COMPLIANCE_FRAMEWORKS = {
    "RGPD": {
        "description": "Règlement Général sur la Protection des Données",
        "requirements": ["data_minimization", "right_to_erasure", "consent_tracking", "eu_residency"],
    },
    "SOC2": {
        "description": "Service Organization Control 2",
        "requirements": ["access_control", "audit_trail", "encryption_at_rest", "incident_response"],
    },
    "ISO27001": {
        "description": "Système de management de la sécurité de l'information",
        "requirements": ["risk_assessment", "access_control", "cryptography", "logging"],
    },
}

DATA_RESIDENCY = {
    "EU": {"regions": ["eu-west-1", "eu-central-1"], "providers": ["openai-eu", "mistral"]},
    "US": {"regions": ["us-east-1", "us-west-2"], "providers": ["openai", "anthropic"]},
    "PRIVATE_CLOUD": {"regions": ["on-prem"], "providers": ["vllm", "tgi"]},
}


class ComplianceManager:
    """Valide la conformité des configurations tenant."""

    def list_frameworks(self) -> Dict[str, Dict]:
        return COMPLIANCE_FRAMEWORKS

    def check_compliance(self, tenant_config: Dict) -> Dict[str, Any]:
        tags = tenant_config.get("compliance_tags", [])
        residency = tenant_config.get("data_residency", "EU")
        results = []
        for tag in tags:
            fw = COMPLIANCE_FRAMEWORKS.get(tag.upper())
            if not fw:
                continue
            passed = []
            failed = []
            for req in fw["requirements"]:
                if tenant_config.get(req, False):
                    passed.append(req)
                else:
                    failed.append(req)
            results.append({
                "framework": tag, "passed": passed, "failed": failed,
                "compliant": len(failed) == 0,
            })
        residency_info = DATA_RESIDENCY.get(residency, DATA_RESIDENCY["EU"])
        return {
            "frameworks": results,
            "data_residency": residency,
            "allowed_regions": residency_info["regions"],
            "allowed_providers": residency_info["providers"],
            "overall_compliant": all(r["compliant"] for r in results) if results else True,
        }

    def get_residency_options(self) -> Dict[str, Dict]:
        return DATA_RESIDENCY
