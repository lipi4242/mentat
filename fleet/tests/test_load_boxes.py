import json
import tempfile
import unittest
from pathlib import Path

from fleet import registry as reg


class LoadBoxesTest(unittest.TestCase):
    def _w(self, data):
        p = Path(tempfile.mkdtemp()) / "boxes.json"
        p.write_text(json.dumps(data))
        return p

    def test_ket_alak(self):
        b = [{"key": "partfal-box", "hostname": "partfal"}]
        self.assertEqual(reg.load_boxes(self._w({"boxes": b})), b)
        self.assertEqual(reg.load_boxes(self._w(b)), b)

    def test_hibas_alak_ures(self):
        self.assertEqual(reg.load_boxes(self._w("x")), [])
        self.assertEqual(reg.load_boxes(self._w({"boxes": "x"})), [])
        self.assertEqual(reg.load_boxes(self._w([1, {"key": "a"}])), [{"key": "a"}])

    def test_local_host_csupasz_listaval(self):
        p = self._w([{"key": "k1", "hostname": "nincs-ilyen-gep"}])
        self.assertIsNone(reg.local_host(reg.load_boxes(p)))


if __name__ == "__main__":
    unittest.main()
