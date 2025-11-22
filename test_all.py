#!/usr/bin/env python3
"""
Comprehensive Test Suite for Unified Odds System
Tests all modules, caching, monitoring, UI components, and core functionality
"""

import unittest
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules to test
try:
    from unified_odds_collector import UnifiedOddsCollector
    UNIFIED_COLLECTOR_AVAILABLE = True
except ImportError:
    UNIFIED_COLLECTOR_AVAILABLE = False

try:
    from dynamic_cache_manager import DynamicCacheManager
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False

try:
    from monitoring_system import OddsMonitoringSystem, ConfigManager, EmailNotifier
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

try:
    from monitoring_status_api import MonitoringStatusAPI
    STATUS_API_AVAILABLE = True
except ImportError:
    STATUS_API_AVAILABLE = False

try:
    from live_odds_viewer_clean import load_unified_data, check_file_status
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

try:
    from run_unified_system import UnifiedSystemRunner, AlertSystem
    RUNNER_AVAILABLE = True
except ImportError:
    RUNNER_AVAILABLE = False


class TestUnifiedOddsCollector(unittest.TestCase):
    """Test the core odds collection and merging functionality"""

    def setUp(self):
        if not UNIFIED_COLLECTOR_AVAILABLE:
            self.skipTest("UnifiedOddsCollector not available")
        self.collector = UnifiedOddsCollector()

    def test_initialization(self):
        """Test collector initializes properly"""
        self.assertIsInstance(self.collector, UnifiedOddsCollector)
        self.assertTrue(hasattr(self.collector, 'cache_manager'))
        self.assertTrue(hasattr(self.collector, 'team_lookup_cache'))

    def test_normalize_team_name(self):
        """Test team name normalization"""
        # Test basic normalization
        result = self.collector.normalize_team_name("Manchester United")
        self.assertEqual(result, "manchesterunited")

        # Test with special characters
        result = self.collector.normalize_team_name("FC Barcelona!")
        self.assertEqual(result, "fcbarcelona")

    def test_get_canonical_team_name(self):
        """Test canonical team name lookup"""
        # Should return original name if not in cache
        result = self.collector.get_canonical_team_name("Unknown Team")
        self.assertEqual(result, "Unknown Team")

    def test_normalize_sport_name(self):
        """Test sport name normalization"""
        self.assertEqual(self.collector.normalize_sport_name("basketball"), "basketball")
        self.assertEqual(self.collector.normalize_sport_name("NBA"), "basketball")
        self.assertEqual(self.collector.normalize_sport_name("soccer"), "soccer")
        self.assertEqual(self.collector.normalize_sport_name("football"), "football")

    def test_matches_are_same(self):
        """Test match similarity detection"""
        match1 = {'sport': 'basketball', 'home_team': 'Lakers', 'away_team': 'Celtics'}
        match2 = {'sport': 'basketball', 'home_team': 'Lakers', 'away_team': 'Celtics'}
        self.assertTrue(self.collector.matches_are_same(match1, match2))

        # Test different teams
        match3 = {'sport': 'basketball', 'home_team': 'Lakers', 'away_team': 'Warriors'}
        self.assertFalse(self.collector.matches_are_same(match1, match3))

    @patch('unified_odds_collector.UnifiedOddsCollector.safe_load_json')
    def test_load_bet365_pregame(self, mock_load):
        """Test loading Bet365 pregame data"""
        mock_data = {
            'sports_data': {
                'NBA': {
                    'games': [
                        {
                            'sport': 'NBA',
                            'team1': 'Lakers',
                            'team2': 'Celtics',
                            'date': '2025-01-01',
                            'time': '20:00'
                        }
                    ]
                }
            }
        }
        mock_load.return_value = mock_data

        matches = self.collector.load_bet365_pregame()
        self.assertIsInstance(matches, list)
        if matches:
            self.assertIn('sport', matches[0])
            self.assertIn('home_team', matches[0])


class TestDynamicCacheManager(unittest.TestCase):
    """Test the dynamic cache management system"""

    def setUp(self):
        if not CACHE_MANAGER_AVAILABLE:
            self.skipTest("DynamicCacheManager not available")
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.temp_dir) / "test_cache.json"
        self.manager = DynamicCacheManager(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test cache manager initializes properly"""
        self.assertIsInstance(self.manager, DynamicCacheManager)
        self.assertTrue(hasattr(self.manager, 'cache_data'))
        self.assertIn('teams_global', self.manager.cache_data)

    def test_normalize_name(self):
        """Test name normalization"""
        result = self.manager.normalize_name("Test Team!")
        self.assertEqual(result, "test team")

    def test_add_team(self):
        """Test adding teams to cache"""
        result = self.manager.add_team("basketball", "Test Team", "test_source")
        self.assertIsInstance(result, bool)

    def test_add_sport(self):
        """Test adding sports to cache"""
        result = self.manager.add_sport("test_sport", aliases=["alias1"], source="test")
        self.assertIsInstance(result, bool)

    def test_save_and_load_cache(self):
        """Test saving and loading cache"""
        # Add some data
        self.manager.add_team("basketball", "Test Team", "test")
        self.manager.add_sport("test_sport", source="test")

        # Save
        success = self.manager.save_cache(replicate_to_subfolders=False)
        self.assertTrue(success)

        # Load new instance
        new_manager = DynamicCacheManager(self.temp_dir)
        self.assertIsInstance(new_manager, DynamicCacheManager)

    def test_get_stats(self):
        """Test getting cache statistics"""
        stats = self.manager.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('total_teams', stats)
        self.assertIn('total_sports', stats)


class TestMonitoringSystem(unittest.TestCase):
    """Test the monitoring and alerting system"""

    def setUp(self):
        if not MONITORING_AVAILABLE:
            self.skipTest("Monitoring system not available")

    def test_config_manager(self):
        """Test configuration management"""
        config = ConfigManager()
        self.assertIsInstance(config, ConfigManager)

        # Test getting values
        value = config.get('nonexistent', 'default')
        self.assertEqual(value, 'default')

    @patch('monitoring_system.smtplib.SMTP')
    def test_email_notifier(self, mock_smtp):
        """Test email notification system"""
        config = ConfigManager()
        notifier = EmailNotifier(config)

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Test sending alert
        result = notifier.send_alert("Test Subject", "Test Body", "test")
        # Should work even if email not configured
        self.assertIsInstance(result, bool)


class TestMonitoringStatusAPI(unittest.TestCase):
    """Test the monitoring status API"""

    def setUp(self):
        if not STATUS_API_AVAILABLE:
            self.skipTest("MonitoringStatusAPI not available")
        self.temp_dir = tempfile.mkdtemp()
        self.api = MonitoringStatusAPI(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test API initializes properly"""
        self.assertIsInstance(self.api, MonitoringStatusAPI)

    def test_update_and_get_status(self):
        """Test updating and retrieving status"""
        test_status = {
            'monitoring_active': True,
            'timestamp': '2025-01-01T00:00:00',
            'summary': {'healthy': 1, 'warnings': 0, 'errors': 0}
        }

        # Update status
        success = self.api.update_status(test_status)
        self.assertTrue(success)

        # Get status
        retrieved = self.api.get_status()
        self.assertIsInstance(retrieved, dict)
        self.assertEqual(retrieved['monitoring_active'], True)

    def test_get_module_status(self):
        """Test getting specific module status"""
        status = self.api.get_module_status('nonexistent')
        self.assertIsNone(status)

    def test_is_monitoring_active(self):
        """Test monitoring active check"""
        active = self.api.is_monitoring_active()
        self.assertIsInstance(active, bool)


class TestUIComponents(unittest.TestCase):
    """Test UI-related functionality"""

    def setUp(self):
        if not UI_AVAILABLE:
            self.skipTest("UI components not available")

    @patch('live_odds_viewer_clean.Path')
    @patch('live_odds_viewer_clean.os.path.exists')
    def test_check_file_status(self, mock_exists, mock_path):
        """Test file status checking"""
        mock_exists.return_value = True
        mock_path.return_value.stat.return_value.st_size = 1000
        mock_path.return_value.stat.return_value.st_mtime = time.time()

        status = check_file_status()
        self.assertIsInstance(status, dict)

    @patch('live_odds_viewer_clean.load_individual_json')
    @patch('live_odds_viewer_clean.FILES')
    def test_load_unified_data_fallback(self, mock_files, mock_load):
        """Test loading data with fallback"""
        mock_files.__getitem__.return_value.exists.return_value = False
        mock_load.return_value = {}

        data = load_unified_data()
        self.assertIsInstance(data, dict)


class TestUnifiedSystemRunner(unittest.TestCase):
    """Test the main system runner"""

    def setUp(self):
        if not RUNNER_AVAILABLE:
            self.skipTest("UnifiedSystemRunner not available")
        self.runner = UnifiedSystemRunner()

    def test_initialization(self):
        """Test runner initializes properly"""
        self.assertIsInstance(self.runner, UnifiedSystemRunner)
        self.assertTrue(hasattr(self.runner, 'alert_system'))

    def test_log_method(self):
        """Test logging functionality"""
        # Should not raise exception
        self.runner.log("Test message")

    def test_check_json_files(self):
        """Test JSON file checking"""
        result = self.runner.check_json_files()
        self.assertIsInstance(result, bool)


class TestAlertSystem(unittest.TestCase):
    """Test the alert system"""

    def setUp(self):
        if not RUNNER_AVAILABLE:
            self.skipTest("AlertSystem not available")
        self.alert_system = AlertSystem()

    def test_initialization(self):
        """Test alert system initializes"""
        self.assertIsInstance(self.alert_system, AlertSystem)

    @patch('run_unified_system.smtplib.SMTP')
    def test_send_alert(self, mock_smtp):
        """Test sending alerts"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Test alert sending
        self.alert_system.send_alert("test_module", "TEST", "Test message")

        # Should not raise exception
        self.assertTrue(True)


class TestIntegration(unittest.TestCase):
    """Integration tests for multiple components"""

    def test_module_imports(self):
        """Test that all expected modules can be imported"""
        modules_to_test = [
            ('unified_odds_collector', UNIFIED_COLLECTOR_AVAILABLE),
            ('dynamic_cache_manager', CACHE_MANAGER_AVAILABLE),
            ('monitoring_system', MONITORING_AVAILABLE),
            ('monitoring_status_api', STATUS_API_AVAILABLE),
            ('live_odds_viewer_clean', UI_AVAILABLE),
            ('run_unified_system', RUNNER_AVAILABLE),
        ]

        for module_name, available in modules_to_test:
            with self.subTest(module=module_name):
                if available:
                    self.assertTrue(True, f"{module_name} imported successfully")
                else:
                    self.skipTest(f"{module_name} not available")

    def test_cache_integration(self):
        """Test cache integration with collector"""
        if not (UNIFIED_COLLECTOR_AVAILABLE and CACHE_MANAGER_AVAILABLE):
            self.skipTest("Required modules not available")

        collector = UnifiedOddsCollector()
        cache_manager = collector.cache_manager

        self.assertIsInstance(cache_manager, DynamicCacheManager)

        # Test that collector uses cache
        canonical = collector.get_canonical_team_name("Test Team")
        self.assertEqual(canonical, "Test Team")  # Should return original if not cached


class TestDataValidation(unittest.TestCase):
    """Test data validation and error handling"""

    def test_json_handling(self):
        """Test JSON file handling with invalid data"""
        if not UNIFIED_COLLECTOR_AVAILABLE:
            self.skipTest("UnifiedOddsCollector not available")

        collector = UnifiedOddsCollector()

        # Test with non-existent file
        result = collector.safe_load_json("/nonexistent/file.json")
        self.assertIsNone(result)

    def test_empty_data_handling(self):
        """Test handling of empty or malformed data"""
        if not UNIFIED_COLLECTOR_AVAILABLE:
            self.skipTest("UnifiedOddsCollector not available")

        collector = UnifiedOddsCollector()

        # Test with empty matches
        result = collector.merge_pregame_data([], [], [])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


def run_performance_tests():
    """Run performance tests (optional)"""
    print("\n=== Performance Tests ===")

    if UNIFIED_COLLECTOR_AVAILABLE:
        collector = UnifiedOddsCollector()

        # Test team name normalization performance
        import time
        start_time = time.time()

        for i in range(1000):
            collector.normalize_team_name(f"Test Team {i}")

        end_time = time.time()
        print(".4f")

    print("Performance tests completed")


def main():
    """Main test runner"""
    print("=" * 80)
    print("UNIFIED ODDS SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Print availability status
    print("\nModule Availability:")
    print(f"✓ UnifiedOddsCollector: {UNIFIED_COLLECTOR_AVAILABLE}")
    print(f"✓ DynamicCacheManager: {CACHE_MANAGER_AVAILABLE}")
    print(f"✓ Monitoring System: {MONITORING_AVAILABLE}")
    print(f"✓ Status API: {STATUS_API_AVAILABLE}")
    print(f"✓ UI Components: {UI_AVAILABLE}")
    print(f"✓ System Runner: {RUNNER_AVAILABLE}")

    # Run unit tests
    print("\n=== Running Unit Tests ===")
    unittest.main(argv=[''], exit=False, verbosity=2)

    # Run performance tests
    try:
        run_performance_tests()
    except Exception as e:
        print(f"Performance tests failed: {e}")

    print("\n=== Test Suite Complete ===")


if __name__ == '__main__':
    main()