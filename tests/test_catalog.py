import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("catalog", Path(__file__).parents[1] / "tools/sync_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class ExchangeFormats(unittest.TestCase):
    def egg(self):
        return {"meta":{"version":"PLCN_v3"}, "name":"Example", "docker_images":{"Java":"ghcr.io/example/java:21"},
                "startup_commands":{"Default":"java -jar app.jar","Worker":"java -jar worker.jar"},
                "config":{"files":"{}","startup":"{\"done\":[\"ready\",\"running\"]}"},
                "variables":[{"env_variable":"PORT","default_value":25565,"rules":["required","integer","between:1,65535"]}]}

    def test_pelican_commands_are_preserved_as_variants(self):
        raw = self.egg()
        original = copy.deepcopy(raw)
        variants = catalog.normalize(raw)
        self.assertEqual(raw, original)
        self.assertEqual([egg["startup"] for egg in variants], ["java -jar app.jar", "java -jar worker.jar"])
        self.assertEqual(variants[0]["meta"]["version"], "PTDL_v2")
        self.assertEqual(variants[0]["variables"][0]["rules"], "required|integer|between:1,65535")
        self.assertEqual(variants[0]["variables"][0]["default_value"], "25565")

    def test_invalid_exports_are_not_silently_imported(self):
        raw = self.egg()
        raw["docker_images"] = {}
        with self.assertRaises(ValueError):
            catalog.normalize(raw)

    def test_complete_feed_is_consistent(self):
        catalog.validate()
