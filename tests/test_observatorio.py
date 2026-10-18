"""Pruebas locales sin depender de Renfe ni de conexiones externas."""
import json
import pathlib
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ObservatorioTests(unittest.TestCase):
    def test_python_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ("collector.py", "report.py"):
                py_compile.compile(str(ROOT / path), cfile=str(pathlib.Path(tmp) / (path + ".pyc")), doraise=True)

    def test_report_inferred_calendar_not_presented_as_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = pathlib.Path(tmp)
            shutil.copy(ROOT / "report.py", dest / "report.py")
            data=dest/"data";data.mkdir()
            (data/"observations").mkdir()
            key="20261018|6289D26957C1"
            schedule={key:{"stops":[{"stop":"Reinosa","departure":"14:41:00"},{"stop":"Santander","arrival":"16:27:00"}],"basis":"servicio deducido de trip_id GTFS-RT; calendario no acreditado"}}
            index={"trips":{"6289D26957C1":{"origin":"Reinosa","destination":"Santander","stops":[{"id":"14202","name":"Reinosa"},{"id":"14234","name":"Pujayo"},{"id":"14223","name":"Santander"}]}}}
            (data/"schedule.json").write_text(json.dumps(schedule))
            (data/"c1_index.json").write_text(json.dumps(index))
            (data/"status.json").write_text(json.dumps({"error": None}))
            observation={"key":key,"captured_at":"2026-10-18T15:20:00+02:00","calendar_matched":False,"delays":[{"stop_id":"14234","event":"arrival","delay_seconds":1320}]}
            (data/"observations"/"20261018.jsonl").write_text(json.dumps(observation)+"\n")
            result=subprocess.run([sys.executable,str(dest/"report.py")],cwd=str(dest),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            day=json.loads((data/"dashboard.json").read_text())["days"][0]
            self.assertIsNone(day["coverage_pct"])
            self.assertEqual(day["sample_coverage_pct"],100.0)
            self.assertIn("no es calendario verificado",day["scheduled_basis"])
            self.assertEqual(day["ranking"][0]["train"],"26957")
            self.assertEqual(day["ranking"][0]["max_delay_stop"],"Pujayo")
            self.assertEqual(day["ranking"][0]["theoretical_departure"],"14:41:00")
            self.assertEqual(day["ranking"][0]["theoretical_arrival"],"16:27:00")

    def test_reference_timetable_if_available(self):
        p=ROOT/"data"/"schedule.json"
        if not p.exists():
            self.skipTest("Aún no se ha guardado el horario GTFS")
        schedule=json.loads(p.read_text())
        refs=[("20261018|6289D26908C1","Santander","08:14:00","Reinosa","09:45:00"),
              ("20261018|6289D26957C1","Reinosa","14:41:00","Santander","16:27:00")]
        for key,origin,start,dest,end in refs:
            if key not in schedule:
                self.skipTest("La versión del GTFS aún no contiene los servicios comparados")
            stops=schedule[key]["stops"]
            self.assertEqual((stops[0]["stop"],stops[0]["departure"],stops[-1]["stop"],stops[-1]["arrival"]),(origin,start,dest,end))
if __name__=="__main__":
    unittest.main()
