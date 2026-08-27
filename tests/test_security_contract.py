#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "stack/docker-compose.yml"
ENV = ROOT / "stack/.env.example"
VERSIONS = ROOT / "stack/versions.env"


def env_values(path: Path) -> dict[str, str]:
    return {
        key: value
        for raw in path.read_text().splitlines()
        if raw and not raw.startswith("#") and "=" in raw
        for key, value in [raw.split("=", 1)]
    }


LOCAL_INPUTS = env_values(ENV)
ALLOWED_BINDINGS = {LOCAL_INPUTS["LAN_IP"], LOCAL_INPUTS["TAILSCALE_IP"], "127.0.0.1"}
HEALTHCHECK_REQUIRED = {
    "aperture",
    "autobrr",
    "bazarr",
    "flaresolverr",
    "gateway-lan",
    "gateway-tailscale",
    "homarr",
    "jackett",
    "jellyfin",
    "jellyseerr",
    "profilarr",
    "prowlarr",
    "qbittorrent",
    "radarr",
    "sonarr",
    "torrserver",
    "uptime-kuma",
}


def rendered_compose() -> dict:
    command = [
        "docker",
        "compose",
        "--profile",
        "*",
        "--env-file",
        str(ENV),
        "--env-file",
        str(VERSIONS),
        "-f",
        str(COMPOSE),
        "config",
        "--format",
        "json",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class SecurityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = rendered_compose()
        cls.services = cls.config["services"]

    def test_required_security_services_exist(self) -> None:
        self.assertIn("docker-socket-proxy", self.services)
        self.assertIn("uptime-kuma", self.services)

    def test_only_socket_proxy_mounts_docker_socket(self) -> None:
        offenders: list[str] = []
        for name, service in self.services.items():
            for volume in service.get("volumes", []):
                source = volume.get("source", "") if isinstance(volume, dict) else str(volume)
                if source == "/var/run/docker.sock" and name != "docker-socket-proxy":
                    offenders.append(name)
        self.assertEqual([], offenders)

    def test_no_service_uses_host_network(self) -> None:
        offenders = [
            name
            for name, service in self.services.items()
            if service.get("network_mode") == "host"
        ]
        self.assertEqual([], offenders)

    def test_published_ports_bind_only_to_lan_tailscale_or_loopback(self) -> None:
        offenders: list[str] = []
        for name, service in self.services.items():
            for port in service.get("ports", []):
                host_ip = port.get("host_ip") if isinstance(port, dict) else None
                if host_ip not in ALLOWED_BINDINGS:
                    offenders.append(f"{name}:{host_ip or '*'}")
        self.assertEqual([], offenders)

    def test_only_gateways_and_lan_discovery_publish_ports(self) -> None:
        allowed = {"gateway-lan", "gateway-tailscale", "qbittorrent", "jellyfin", "torrserver"}
        offenders = sorted(
            name
            for name, service in self.services.items()
            if service.get("ports") and name not in allowed
        )
        self.assertEqual([], offenders)

    def test_docker_proxy_disallows_mutation(self) -> None:
        environment = self.services["docker-socket-proxy"].get("environment", {})
        self.assertEqual("0", environment.get("POST"))
        self.assertNotIn("ports", self.services["docker-socket-proxy"])

    def test_torrserver_has_a_direct_lan_port_only(self) -> None:
        ports = self.services["torrserver"].get("ports", [])
        self.assertEqual(1, len(ports))
        self.assertEqual(LOCAL_INPUTS["LAN_IP"], ports[0].get("host_ip"))
        self.assertEqual(18090, int(ports[0].get("published")))
        lan_gateway_ports = {int(port.get("published")) for port in self.services["gateway-lan"].get("ports", [])}
        tailscale_gateway_ports = {int(port.get("published")) for port in self.services["gateway-tailscale"].get("ports", [])}
        self.assertNotIn(18090, lan_gateway_ports)
        self.assertIn(18090, tailscale_gateway_ports)

    def test_prowlarr_waits_for_flaresolverr_on_cold_start(self) -> None:
        dependency = self.services["prowlarr"].get("depends_on", {}).get("flaresolverr", {})
        self.assertEqual("service_healthy", dependency.get("condition"))
        self.assertEqual("2147483648", self.services["flaresolverr"].get("shm_size"))

    def test_long_running_http_services_have_healthchecks(self) -> None:
        missing = sorted(
            name
            for name in HEALTHCHECK_REQUIRED
            if "healthcheck" not in self.services.get(name, {})
        )
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
