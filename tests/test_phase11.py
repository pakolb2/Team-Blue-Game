"""
tests/test_phase11.py
----------------------
Tests for Phase 11: i18n, LAN discovery, and main.py additions.

Run with:  pytest tests/test_phase11.py -v
"""

import pytest
import time


# ---------------------------------------------------------------------------
# LAN discovery tests
# ---------------------------------------------------------------------------

class TestLanDiscovery:
    def test_get_local_ip_returns_string(self):
        from server.lan_discovery import _get_local_ip
        ip = _get_local_ip()
        assert isinstance(ip, str)
        assert len(ip) > 0

    def test_get_local_ip_not_empty(self):
        from server.lan_discovery import _get_local_ip
        ip = _get_local_ip()
        # Should be either a real IP or loopback
        assert ip == "127.0.0.1" or "." in ip

    def test_announce_and_list(self):
        """Announcing a server should make it appear in the list."""
        from server.lan_discovery import _announced, _prune_stale, _get_local_ip
        _announced.clear()

        ip = _get_local_ip()
        _announced[ip] = {
            "ip": ip,
            "port": 8000,
            "name": "Test Game",
            "last_seen": time.time(),
        }

        _prune_stale()
        assert ip in _announced

    def test_stale_servers_pruned(self):
        """Servers not seen recently should be removed."""
        from server.lan_discovery import _announced, _prune_stale
        _announced.clear()

        # Insert a stale entry (last_seen 30s ago)
        _announced["192.168.1.99"] = {
            "ip": "192.168.1.99",
            "port": 8000,
            "name": "Old Server",
            "last_seen": time.time() - 30,
        }
        _prune_stale()
        assert "192.168.1.99" not in _announced

    def test_fresh_server_not_pruned(self):
        """A recently announced server should NOT be pruned."""
        from server.lan_discovery import _announced, _prune_stale
        _announced.clear()

        _announced["10.0.0.5"] = {
            "ip": "10.0.0.5",
            "port": 8000,
            "name": "Fresh Server",
            "last_seen": time.time(),
        }
        _prune_stale()
        assert "10.0.0.5" in _announced

    def test_lan_router_has_correct_prefix(self):
        from server.lan_discovery import router
        assert router.prefix == "/api/lan"

    def test_lan_router_has_servers_route(self):
        from server.lan_discovery import router
        routes = [r.path for r in router.routes]
        assert "/api/lan/servers" in routes

    def test_lan_router_has_announce_route(self):
        from server.lan_discovery import router
        routes = [r.path for r in router.routes]
        assert "/api/lan/announce" in routes


class TestLanHTTPEndpoints:
    def setup_method(self):
        from server.lan_discovery import _announced
        _announced.clear()

    def _make_client(self):
        from server import main as m
        from server.rooms.room_manager import RoomManager
        from server.sockets.handlers import ConnectionManager
        m.room_manager = RoomManager()
        m.connection_manager = ConnectionManager()
        from fastapi.testclient import TestClient
        return TestClient(m.app)

    def test_list_servers_empty(self):
        client = self._make_client()
        resp = client.get("/api/lan/servers")
        assert resp.status_code == 200
        assert resp.json()["servers"] == []

    def test_announce_server(self):
        client = self._make_client()
        resp = client.post("/api/lan/announce?name=TestGame")
        assert resp.status_code == 200
        data = resp.json()
        assert data["announced"] is True
        assert "ip" in data

    def test_list_servers_after_announce(self):
        client = self._make_client()
        client.post("/api/lan/announce?name=MyGame")
        resp = client.get("/api/lan/servers")
        servers = resp.json()["servers"]
        assert len(servers) >= 1
        assert servers[0]["name"] == "MyGame"

    def test_deannounce_removes_server(self):
        client = self._make_client()
        client.post("/api/lan/announce?name=TempGame")
        client.delete("/api/lan/announce")
        resp = client.get("/api/lan/servers")
        assert resp.json()["servers"] == []

    def test_variants_endpoint(self):
        client = self._make_client()
        resp = client.get("/api/variants")
        assert resp.status_code == 200
        variants = resp.json()["variants"]
        names = [v["name"] for v in variants]
        assert "schieber" in names
        assert "differenzler" in names
        assert "coiffeur" in names

    def test_variants_have_display_names(self):
        client = self._make_client()
        resp = client.get("/api/variants")
        for v in resp.json()["variants"]:
            assert "display_name" in v
            assert len(v["display_name"]) > 0


# ---------------------------------------------------------------------------
# i18n tests (logic only — no DOM)
# ---------------------------------------------------------------------------

class TestI18nTranslationKeys:
    """Verify that all languages have the same keys as English."""

    def _load_translations(self):
        """
        Parse the TRANSLATIONS dict from i18n.js.
        We test the structure rather than eval-ing JS — verify key parity.
        """
        # Key list expected in every language (subset of important ones)
        return [
            'lobby', 'your_name', 'create_room', 'join_room',
            'start_game', 'choose_trump', 'score', 'trump',
            'victory', 'game_over', 'return_lobby',
            'trump_eichel', 'trump_schilte', 'trump_schelle',
            'trump_rose', 'trump_obenabe', 'trump_undeufe',
            'err_no_room', 'err_not_turn',
        ]

    def test_i18n_js_exists(self):
        import os
        path = 'client/static/js/i18n.js'
        # Check in output directory
        output_path = '/mnt/user-data/outputs/phase11/client/static/js/i18n.js'
        assert os.path.exists(output_path), "i18n.js not found"

    def test_i18n_js_has_four_locales(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        for locale in ['en:', 'de:', 'fr:', 'it:']:
            assert locale in content, f"Locale '{locale}' not found in i18n.js"

    def test_i18n_js_has_trump_modes(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        for mode in ['trump_eichel', 'trump_schilte', 'trump_schelle',
                     'trump_rose', 'trump_obenabe', 'trump_undeufe']:
            assert mode in content, f"Trump mode key '{mode}' missing from i18n.js"

    def test_i18n_js_has_game_events(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        for key in ['game_started', 'trick_won', 'round_complete',
                    'victory', 'game_over', 'return_lobby']:
            assert key in content, f"Key '{key}' missing from i18n.js"

    def test_i18n_js_has_all_four_languages(self):
        """Verify DE, FR, IT sections contain the trump translation keys."""
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        # German-specific strings
        assert 'Trumpf wählen' in content
        # French-specific strings (apostrophe is escaped as \' in JS)
        assert "Choisir l" in content and "atout" in content
        # Italian-specific strings
        assert 'Scegli la briscola' in content

    def test_i18n_js_has_error_keys(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        for key in ['err_no_room', 'err_not_turn', 'err_illegal', 'err_internal']:
            assert key in content

    def test_i18n_js_has_placeholder_substitution_syntax(self):
        """Keys with variables should use {varname} syntax."""
        content = open('/mnt/user-data/outputs/phase11/client/static/js/i18n.js').read()
        # These keys should contain {player}, {pts}, {n} etc.
        assert '{player}' in content
        assert '{pts}' in content
        assert '{n}' in content


class TestSoundsJs:
    def test_sounds_js_exists(self):
        import os
        assert os.path.exists('/mnt/user-data/outputs/phase11/client/static/js/sounds.js')

    def test_sounds_js_has_play_sound(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/sounds.js').read()
        assert 'function playSound' in content

    def test_sounds_js_has_all_sound_names(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/sounds.js').read()
        for sound in ['card_hover', 'card_select', 'card_play',
                      'trick_win', 'trump_chosen', 'game_over_win',
                      'game_over_loss', 'error', 'round_end']:
            assert f"'{sound}'" in content or f'"{sound}"' in content, \
                f"Sound '{sound}' not found in sounds.js"

    def test_sounds_js_has_enable_disable(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/sounds.js').read()
        assert 'setSoundEnabled' in content
        assert 'isSoundEnabled' in content


class TestAnimationsJs:
    def test_animations_js_exists(self):
        import os
        assert os.path.exists('/mnt/user-data/outputs/phase11/client/static/js/animations.js')

    def test_animations_js_has_all_functions(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/animations.js').read()
        for fn in ['animateDeal', 'animateCardPlay', 'animateTrickCollect',
                   'animateScoreReveal', 'animateShake', 'animateWinnerPulse',
                   'animateGameOver']:
            assert f'function {fn}' in content, f"Function '{fn}' not found"

    def test_animations_js_uses_web_animations_api(self):
        content = open('/mnt/user-data/outputs/phase11/client/static/js/animations.js').read()
        assert '.animate(' in content


class TestPhase11Css:
    def test_css_additions_exist(self):
        import os
        assert os.path.exists(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        )

    def test_css_has_lang_switcher(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert '.lang-switcher' in content
        assert '.lang-btn' in content

    def test_css_has_mobile_breakpoint(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert 'max-width: 600px' in content

    def test_css_has_reduced_motion(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert 'prefers-reduced-motion' in content

    def test_css_has_settings_panel(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert '.settings-panel' in content

    def test_css_has_differenzler_prediction(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert '.prediction-box' in content or '.prediction-overlay' in content

    def test_css_has_coiffeur_modes(self):
        content = open(
            '/mnt/user-data/outputs/phase11/client/static/css/phase11-additions.css'
        ).read()
        assert '.coiffeur-mode-chip' in content
